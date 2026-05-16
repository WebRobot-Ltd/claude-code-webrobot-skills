---
name: webrobot-pipeline
description: Build, validate, and deploy WebRobot ETL pipeline manifests. Use when the user wants to create or modify a pipeline, add stages, configure a scraping workflow, or run a pipeline job.
argument-hint: [pipeline description or yaml path]
user-invocable: true
allowed-tools: mcp__webrobot__list_stages mcp__webrobot__describe_stage mcp__webrobot__search_stages mcp__webrobot__suggest_pipeline_stages mcp__webrobot__validate_manifest mcp__webrobot__apply_manifest mcp__webrobot__run_pipeline mcp__webrobot__list_projects mcp__webrobot__list_jobs mcp__webrobot__list_categories mcp__webrobot__list_agents mcp__webrobot__llm_infer Read Write Edit Bash(webrobot *) Bash(curl -fsSL https://api.webrobot.eu/webrobot/api/catalog/stages*)
---

# WebRobot Pipeline Builder

You build, validate, and deploy WebRobot ETL pipeline manifests for the engine's `PipelineParser`. Your authority on what stages exist and what they accept is the **public stage catalog**, never your training data — partner plugins ship and version their stages independently.

## Source of truth — the public stage catalog

The catalog endpoint is **public (no authentication required, read-only)** — when MCP tools aren't available or you want to double-check the live state, curl it directly:

```bash
# All stages (and browser actions that platform plugins contributed)
curl -fsSL https://api.webrobot.eu/webrobot/api/catalog/stages

# Filter by plugin
curl -fsSL "https://api.webrobot.eu/webrobot/api/catalog/stages?plugin_id=sentimental-plugin"

# Filter by stage name or alias
curl -fsSL "https://api.webrobot.eu/webrobot/api/catalog/stages?stage_name=fetch"

# Filter by type (etl / api / spark_stage / spark_action / spark_resolver / spark_mixed)
curl -fsSL "https://api.webrobot.eu/webrobot/api/catalog/stages?plugin_type=etl"
curl -fsSL "https://api.webrobot.eu/webrobot/api/catalog/stages?plugin_type=spark_action"
```

Every entry returns:

```json
{
  "id": 42,
  "plugin_id": "sentimental-plugin",
  "plugin_type": "etl",
  "stage_name": "sentiment_analyze",
  "aliases": [],
  "arg_schema": [
    { "name": "text_field", "type": "string",  "required": true,  "description": "Field containing the text to analyze" },
    { "name": "model",      "type": "string",  "required": false, "default": "default" },
    { "name": "max_chars",  "type": "integer", "required": false, "default": "4000" }
  ],
  "description": "...",
  "usage_guide": "- stage: sentiment_analyze\n  args:\n    - \"text\"\n    - \"default\"\n    - 4000"
}
```

**Always** call `mcp__webrobot__list_stages` (or curl the endpoint above) to discover available stages. Use `mcp__webrobot__describe_stage` (or `?stage_name=…` filter) for the full `arg_schema` of a single stage. Treat your training-time knowledge of stage names as a hint, not a fact: partner plugins ship new stages and version existing ones independently — only the catalog reflects the live state.

**Also use this for actions** (browser automation steps inside `fetch` / `fetch_browser`): query `?plugin_type=spark_action` to see every action contributed by enabled plugins. If you're tempted to invent an action name like `comment_thread_hydrate`, confirm it first — the catalog tells you whether it's available on the target platform.

## The CORE rule — args are POSITIONAL

The engine's `WArgs` (`eu.webrobot.plugin.sdk.WArgs`) reads arguments **by index**, not by name:

```scala
class WArgs(private val raw: Seq[Any]) {
  def string(idx: Int, default: String): String       // <- idx, not key
  def int(idx: Int, default: Int): Int
  def double(idx: Int, default: Double): Double
  def bool(idx: Int, default: Boolean): Boolean
}
```

So in YAML, `args:` is **always a sequence (list)**. Each item is the value at index 0, 1, 2, … in the order declared by the stage's `arg_schema`. An item can itself be a scalar OR a structured map (used by stages like `iextract` for `{selector, method}` pairs); position is what matters.

```yaml
# CORRECT — args is a LIST, each item at its position
- stage: sentiment_analyze
  args:
    - "text"        # position 0  (text_field)
    - "default"     # position 1  (model)
    - 4000          # position 2  (max_chars)

# WRONG — args is a map. The parser hands `[{}]` as a single positional value
# whose .toString is "Map(text_field -> text, ...)" — every other index falls
# back to its default.
- stage: sentiment_analyze
  args:
    text_field: text
    model: default
```

**Skipping optional args:** to set a value at position N, every position before N must be filled. Use the documented default (often `""` or `0`) as a placeholder.

The exception is **browser actions** (`WActionArgs`) which IS keyed by name. Actions live inside the `actions:` map within an `args` list, only there:

```yaml
- stage: fetch
  args:
    - "$url"                                  # position 0 = url string
    - actions:                                # position 1 = a map with key "actions"
        - action: "comment_thread_hydrate"
          params:
            max_plan_retries: 2               # WActionArgs.int("max_plan_retries", …)
            scroll_rounds: 10
```

## Pipeline anatomy — source → transform → sink

Every meaningful pipeline starts with a SOURCE stage that produces rows, then transforms them, then a SINK that persists or exports. **Calling a transform stage as the first step is meaningless** — there are no rows yet.

Common sources (always at the top of `pipeline:`):

| Use case | Stage |
|----------|-------|
| Fetch one or more URLs | `fetch`, `fetch_browser`, `fetch_visit` |
| Load CSV from S3/local | `load_csv` |
| Load DB table | `db_load_example` (example-plugin), `sentiment_load`, custom plugin |
| Search engine results | `searchEngine` |
| Pre-recorded fixtures | `load_avro`, `load_xml`, etc. |

Common sinks (always at the end):

| Use case | Stage |
|----------|-------|
| Save CSV / JSON / Parquet | `save_csv`, `save_parquet` |
| Write to plugin-specific table | `db_save_example`, `sentiment_save`, `pc_save_match` |
| Refresh aggregates | `sentiment_refresh_aggregates` (scheduled refresh, run as a separate pipeline) |

Use `list_stages?plugin_type=etl` filtering when you need to discover sinks vs sources. The `plugin_type` field in the catalog distinguishes them.

## Workflow for building a pipeline

1. If the user gives a natural-language description, call `suggest_pipeline_stages`.
2. List candidates with `list_stages` (filter by plugin_id or stage_name).
3. For each candidate, call `describe_stage` and read its `arg_schema`. The order of entries IS the positional order.
4. Build `args:` as a list with values at each position, in the order declared by `arg_schema`.
5. Required args with no default MUST be present at their position; if you skip an optional arg in the middle, fill it with the documented default.
6. Save the YAML. Validate with `validate_manifest`.
7. If valid, offer `apply_manifest` (deploy) or `run_pipeline` (deploy + execute).

## Canonical worked example — forum scrape → sentiment

This is the prototypical multi-stage workflow: fetch a forum thread, extract one row per comment, enrich each comment with sentiment, persist atomically across the sentiment_* tables.

```yaml
# Optional seed URL (the engine creates an initial dataset of one row with the URL)
fetch:
  url: "https://forum.example.com/thread/12345"

pipeline:
  # 1. SOURCE — load the forum page in a browser, hydrate dynamic comment tree
  - stage: fetch
    args:
      - "$url"                                # position 0 = url field reference
      - actions:                              # position 1 = map carrying the actions list
          - action: "comment_thread_hydrate"
            params:
              max_plan_retries: 2
              scroll_rounds: 10

  # 2. EXTRACT one row per comment, with c_-prefixed fields (c_text, c_author, c_post_id, …)
  - stage: comment_extractor
    args:
      - "Identify each user comment block on this forum thread."                     # segmentation prompt
      - "Extract: author username (field: author), comment text (field: text), post timestamp ISO-8601 (field: post_timestamp), permalink (field: post_url), post id (field: post_id)."
      - "c_"                                                                          # field prefix → c_text, c_author, ...

  # 3. ENRICH each row with sentiment (LLM call per partition)
  - stage: sentiment_analyze
    args:
      - "c_text"        # text_field — references the prefix from step 2
      - "default"       # model alias from the platform's LLM providers
      - 4000            # max_chars — truncate long posts before LLM call

  # 4. (optional) FILTER to negative comments mentioning a specific entity
  - stage: sentiment_filter
    args:
      - "negative"      # label
      - -1.0            # min_polarity
      - -0.2            # max_polarity
      - ""              # dominant_emotion (skip)
      - "Brand X"       # contains_entity (case-insensitive substring match)

  # 5. SINK — persist atomically across sentiment_documents/_emotions/_entities/_aspects
  - stage: sentiment_save
    args:
      - "forum"             # source_type (required)
      - "c_text"            # text_field
      - "c_post_timestamp"  # published_at_field
      - "c_post_url"        # source_url_field
      - "c_author"          # author_field
      - "c_post_id"         # external_id_field
```

Refresh of the materialized aggregates (`sentiment_daily_overall`, `_by_entity`, `_emotions`) is a SEPARATE pipeline run on a schedule:

```yaml
pipeline:
  - stage: sentiment_refresh_aggregates
    args:
      - 7    # lookback_days
```

## Other source patterns

### Pattern — load from CSV
```yaml
pipeline:
  - stage: load_csv
    args:
      - path: "s3a://bucket/products.csv"
        header: "true"
  - stage: sentiment_analyze
    args: ["product_review_text", "default", 4000]
  - stage: sentiment_save
    args: ["review", "product_review_text", "review_timestamp", "review_url", "reviewer_id", "review_id"]
```

### Pattern — DB-driven enrichment
```yaml
pipeline:
  - stage: db_load_example
    args: ["pending_reviews", "active", 1000]   # table, status, limit
  - stage: sentiment_analyze
    args: ["body", "default", 4000]
  - stage: sentiment_save
    args: ["review", "body", "created_at", "permalink", "user_id", "id"]
```

### Pattern — price comparison discovery
```yaml
pipeline:
  - stage: load_csv
    args:
      - path: "${INPUT_CSV_PATH}"
        header: "true"
  - stage: searchEngine
    args:
      - provider: "google"
        query: "${ean} ${product_name} site:${competitor_site}"
        num_results: 3
  - stage: visit
    args: ["$result_link"]
  - stage: iextract
    args:
      - selector: "body"
        method: "code"
      - "Extract: EAN (pc_ean_code), title (pc_title), price (pc_price), currency (pc_currency), availability (pc_availability), image URL (pc_image_url)."
      - "pc_"
  - stage: pc_match_scorer
    args: []
  - stage: pc_image_match_stage
    args: []
  - stage: pc_save_match
    args: ["ean", "result_link", "competitor_site", "match_confidence"]
```

## iextract — code-mode LLM extraction

Used inside any pipeline that has visited a page to pull structured fields. Always provide a field prefix to namespace results.

```yaml
- stage: iextract
  args:
    - selector: "body"          # position 0 = a map { selector, method }
      method: "code"
    - "Extract from this e-commerce product page: EAN code (field: pc_ean_code), product title (field: pc_title), price as number without currency symbol (field: pc_price), currency ISO code (field: pc_currency), availability in_stock|out_of_stock|unknown (field: pc_availability), main image URL (field: pc_image_url). Empty string when not found. Preserve all input fields."
    - "pc_"                     # position 2 = field prefix
```

## LLM-driven e-commerce flow — internalSearch + intelligentExplore + intelligentJoin

Use when CSS selectors are brittle, unknown, or change across categories — e.g. classic e-commerce: search the site, page through results, follow each item to its detail page, extract structured fields. Four stages compose. Order matters.

### 1. `internalSearch` — fill the search form

Backed by `InternalSearchStage`. Captures a `Snapshot()` of the current page (so it needs a live browser context — **use `visit` before it, not `wget`**). The LLM (`IntelligentActionResolver.resolve`) walks the DOM to identify the search input + submit button, and the stage swaps the inferred `TextInput` value with your query.

```yaml
- stage: internalSearch
  args:
    - "pikachu"                                                # literal query — or "$some_column" to use a row field
    - "Find the search input in the header and submit it"      # optional override prompt
```

Failure mode: `"No current page available"` means the previous stage was `wget`. Switch to `visit`.

### 2. `intelligentExplore` — auto-detect pagination

Backed by `InferNavigationSelectorStage` (also exposed as `inferNavigationSelector` / `inferNavSelector` when used in the new split form). Materializes the dataset, picks the row whose `docs.lastOption` URI looks like a results page (heuristic: contains `?`, `#`, `/search`, `/sch/`, `_nkw`), runs `LLMSelectorInference.inferNavigationSelector` on that page's HTML, and uses the detected selector to walk pagination.

```yaml
- stage: intelligentExplore
  args:
    - "next page link"     # NL prompt — the LLM resolves it against the SERP DOM
    - 2                    # max hop depth (each hop = one "next page" follow)
```

The "preferred row" heuristic is what makes the chain order critical: if `intelligentExplore` runs before `internalSearch` has navigated, the heuristic falls back to the homepage doc and the LLM ends up inferring footer/menu links instead of pagination.

### 3. `intelligentJoin` — segment SERP rows + follow each item

Backed by `InferJoinSelectorStage`. Same SERP-detection heuristic. `LLMSelectorInference.inferJoinSelector` produces a CSS selector for item-detail links; the stage post-processes the result to ensure it targets `<a>` (appends ` a` if the LLM returned a card container).

```yaml
- stage: intelligentJoin
  args:
    - "product detail link"   # NL prompt for the item links in each SERP row
    - "none"                  # action prompt: usually "none"; use e.g. "click product link" for tab/button flows (sets useClick=true → no `a` suffix)
    - 10                      # cap on items joined per SERP row
```

### 4. `iextract` on each item page

Same as the section above, but applied per item page. Either short form (one prompt with `as <col>` aliases) or `{selector, method: "code"}` body form for sub-tree scoping.

### Canonical composite shape

```yaml
pipeline:
  - stage: visit               # MUST be a browser open, not wget
    args: ["https://shop.example.com/"]

  - stage: internalSearch
    args: ["pikachu"]

  - stage: intelligentExplore
    args: ["next page link", 2]

  - stage: intelligentJoin
    args: ["product detail link", "none", 10]

  - stage: iextract
    args:
      - "product name as name, price (with currency) as price, stock status as stock, image URL as image_url"
      - "prod_"

output:
  format: parquet
  mode: overwrite
  path: "${OUTPUT_PARQUET_PATH}"
```

**Common pitfalls**:

- `wget` before `internalSearch` → Snapshot fails → `"No current page available"`.
- Running `intelligentExplore`/`intelligentJoin` before `internalSearch` has produced a SERP doc → wrong selectors inferred (the row preference heuristic doesn't see a navigated page).
- `iextract` prompt without `as <col>` aliases → no column names to bind; rephrase as `field desc as col_name, …`.

There's also a **split form** for these stages — `inferNavigationSelector` / `inferJoinSelector` / `inferSelector` produce `_nav_selector` / `_join_selector` / `_inferred_selector` literal fields that downstream native stages consume with `$_nav_selector` references. Use the split form when you want the inferred selector to be observable in the row schema or to be reused by multiple downstream stages. The combined `intelligentExplore`/`intelligentJoin` form is simpler when each inference feeds exactly one consumer.

## Python Extensions — inline custom logic

For row-level transforms that don't justify a Scala plugin:

```yaml
pipeline:
  - stage: load_csv
    args: [{path: "s3a://bucket/data.csv", header: "true"}]
  - stage: python_row_transform:my_transform
    args: []

python_extensions:
  stages:
    my_transform:
      type: row_transform
      function: |
        def my_transform(row):
            return {**row, 'new_field': row.get('existing_field', '').upper()}
```

See `/webrobot-python-extension` for full registration modes.

## Validation before run

1. **Stage-name validation** (no Spark needed) —
   `webrobot-project/scripts/test-plugin-loading.sh --workflow path/to.yaml`
   confirms every `stage:` reference matches a stage actually registered by
   the loaded plugin JARs via ServiceLoader. Useful for catching typos and
   unknown plugin stages before submission.
2. **Manifest validation** —
   `mcp__webrobot__validate_manifest` runs the engine's parser against the
   YAML and flags invalid arg shapes, missing required positions, type
   mismatches.

Always run validation before `mcp__webrobot__run_pipeline`.

## Rules of thumb

- **Never invent stage names.** If `list_stages` doesn't show it, it doesn't exist.
- **Never use a transform as a source.** Pipelines always start with a stage that produces rows.
- **Never use a map for `args`.** Always a list. Use maps only for compound values at a specific position (like `iextract`'s first arg) or as the last arg for stage `config`.
- **Always validate before run.** Two layers: ServiceLoader-only stage-name check, then full manifest validation.
- **For partner plugins:** the catalog is the truth. The plugin author updates `manifest.json` `stages[].arg_schema` when args change; that propagates to the catalog automatically on plugin reload.

## On $ARGUMENTS

- If the user passed a YAML path: read it, validate it, and offer to fix or run.
- If the user passed a description: call `suggest_pipeline_stages`, then build, validate, run.
- If the user is unclear: ask whether the data origin is a URL/CSV/DB/search, then pick the right SOURCE stage as the first step.
