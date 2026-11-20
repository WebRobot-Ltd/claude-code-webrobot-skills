---
name: "webrobot-pipeline"
description: "Build, validate, deploy and run WebRobot ETL pipelines (manifest YAML with kinds Project / Dataset / Pipeline / Job). Use when the user wants to create or modify a pipeline, add stages, configure a scraping workflow, run a pipeline job, or query its results."
argument-hint: "[pipeline description or yaml path]"
user-invocable: true
---

# WebRobot Pipeline Builder

You build, validate, deploy and run WebRobot ETL pipelines. Your authority on what stages exist and what they accept is the **live stage catalog**, never your training data: partner plugins ship and version their stages independently.

## Tools and endpoints

The plugin's MCP server (`webrobot`) is the authenticated WebRobot API; its tool names are the API operationIds. The ones this skill uses:

| Purpose | Tool | REST (base `https://api.webrobot.eu/api`) |
|---|---|---|
| List / filter stages | `listStages` (`plugin_id`, `stage_name`, `plugin_type`) | `GET /webrobot/api/catalog/stages` |
| One stage: args, description, YAML example | `getStage` (`name` or `stage_name`, aliases accepted) | `GET /webrobot/api/manifest/stages/{name}` |
| Search stages by text | `listStages_1` (`search`, `category`, `type`) or `catalogStages` (`search`) | `GET /webrobot/api/manifest/stages`, `GET /webrobot/api/tenant/catalog/stages` |
| Stage suggestions from an intent | `suggestStages_1` (`intent`) | `POST /webrobot/api/tenant/wizard/suggest` |
| Curated source catalog (+ selector recipes) | `catalogSources` (`country`, `category`, `topic`, `domain`, `include_selectors`) | `GET /webrobot/api/catalog/sources` |
| Dry-run a manifest | `manifestValidate` (`yaml`) | `POST /webrobot/api/manifest/validate` |
| Apply a manifest | `manifestApply` (`yaml`) | `POST /webrobot/api/manifest/apply` |
| Quick save (+ optional run) of one pipeline | `saveGeneratedPipeline` (`pipeline_name`, `pipeline_yaml`, `engine`, `execute`, `datasetId`, `organization_id`) | `POST /webrobot/api/tenant/save-generated-pipeline` |
| Pipeline Designer draft slot | `pipelineDraftPut` / `pipelineDraftGet` / `pipelineDraftDelete` (`context: "etl:pipeline-designer"`) | `/webrobot/api/tenant/pipeline-draft` |
| Projects / jobs | `getAllProjects`, `createProject`, `getProjectFromName`, `getProjectJobs`, `getJob_1` | `/webrobot/api/projects/...` |
| Upload input data (CSV) | `uploadDatasetJson` (`name`, `content` or `content_base64`, `dataset_type`) | JSON upload, returns `datasetId` |
| Datasets | `getAllDatasets`, `getDataset`, `getDatasetFields` | `/webrobot/api/datasets/...` |
| Run a job | `executeJob_1` (`projectId`, `jobId`, `engine`, BYOC flags, `options`) | `POST /webrobot/api/projects/id/{p}/jobs/{j}/execute` |
| Wait / status | `waitForExecution` (`projectId`, `jobId`, `executionId`, `timeoutSec`, `logTail`), `getExecutionStatus_1`, `executionStatus` (`executionId`) | |
| Logs | `getExecutionLogs_1` (`projectId`, `jobId`, `executionId`, `podType`, `tail`), `executionLogs` (`executionId`) | |
| Output preview | `executionOutput` (`executionId`, `limit`) | |
| Tasks of a job | `getAllTasks` (`projectId`, `jobId`), `getTaskStatus` | |
| SQL on a run's output | `queryDatasetByTask` (`taskId`, `sql` with `{table}`), `getDatasetInfoByTask` | `POST /webrobot/api/datasets/query/task/{taskId}` |
| SQL across datasets | `executeQuery` (`sql` with `[<datasetId>]` shortcuts) | `POST /webrobot/api/datasets/query` |
| Stop / cancel | `stopJob`, `cancelExecution_2` | |

Auth for direct REST calls: `X-API-Key: <key>` or `Authorization: Bearer <JWT>`. Every endpoint above requires auth, including the stage catalog. The old base path `https://api.webrobot.eu/webrobot/api/...` (without the leading `/api`) returns 404.

```bash
curl -fsSL "https://api.webrobot.eu/api/webrobot/api/catalog/stages?stage_name=fetch" -H "X-API-Key: <key_id>:<secret>"
```

## Compliance: what you may and may not design (READ FIRST)

A pipeline you emit gets replayed on a schedule, so it must stay lawful and within each source's terms of use:
- Collect only **publicly accessible** pages. Do NOT design a pipeline that logs in, bypasses a paywall, or reads content that requires authentication.
- Platforms that gate content behind login or an official API (X/Twitter, Facebook, Instagram, TikTok, LinkedIn, Threads, Reddit beyond public read, and anything the source catalog marks `anti_bot: login` or "official API required") must be accessed through their **official API/connector**, never by browser-scraping authenticated content.
- If a requested source can only be obtained by breaching its terms, do NOT design it. Answer with a single `NEEDS:` line stating the source needs its official API (or is not permitted) and suggest a compliant alternative.
- A catalog row with `legal_status: licence` means its terms restrict automated collection: remind the user they need a licence; do not refuse.
- The residential proxy + real browser exist to read **public** pages reliably (geo, rate limits, JS), not to defeat access controls.

## Use the source catalog: do NOT rediscover sources

`catalogSources` has already resolved, per source: the URL, the **fetch method** (`wget` vs a real-browser `visit`), its `anti_bot` posture, whether a residential `proxy` is needed, and whether it is reachable now. Use `domain` to fetch the row of one site. When the request hands you a SOURCES list, or the catalog has rows for the topic:
- Map **fetch_method → stage** (Spark engine):
  - `wget` → `wget`/`fetch`.
  - `browser`, or a site not in the catalog → **`resilientFetch`** by default: plain HTTP first, the browser (Camoufox) only when that comes back blocked or empty (403/429, anti-bot challenge, JS-only shell). Many "browser" sites serve their listing pages server-rendered, and the browser is slower and can time out on heavy pages. Same for pagination and detail pages: `resilientExplore`, `resilientJoin`.
  - Use `visit` directly only when the page must be driven (clicks, search box, load-more) or when `resilientFetch` was already shown to return an empty shell for that site.
  - The lightweight engines (`scrapy`, `hybrid`) have no `resilient*` stages: there use `wget`, or `visit` for a `browser` source.
- Prefer sources marked reachable; skip `anti_bot: login` for scraping (use their API); treat strongly blocked sources as out of scope unless a setup has been agreed with the client.
- Discover from scratch only when neither a catalog row nor a SOURCES list exists.

**Pre-set selectors: read the recipe FIRST, then build from it (fast path + self-heal).** The `selectors` recipe (returned to callers with the `etl:create` scope) is pre-inferred offline and may carry up to five parts. Build the pipeline directly from whichever are present; do NOT call wizard inference:

- **`segment` + `fields`** (`{selector, as, method}`): the repeating item list → `flatSelect`/`extract`.
- **`search`** (`{present, input, submit}`): drive it with a deterministic action trace (zero inference): a `fetch`/`visit` whose actions are `[{action: input, args: [<search.input>, "<query>"]}, {action: click, args: [<search.submit>]}]` (or a `waitforselector` on the results), landing on the results page before extracting. Do NOT use `auto_internal_search` here (it re-infers input/submit with an LLM); reserve it for sources with no stored `search` selectors.
- **`pagination`** (`{type, selector | param}`): `next_link` / `url_param` / `url_path` → `visitExplore`/`wgetExplore` (follow the next anchor, set `depth`); `load_more` → `visitPaginate` on that control; `none` → single page.
- **`detail_link` + `detail_fields`**: the per-item detail page is a **JOIN, not part of `flatSelect`**. `flatSelect` yields the LISTING rows, each carrying its item `url`; for detail chain `wgetJoin`/`visitJoin` on that `url` (`detail_link`), then `flatSelect`/`extract`/`iextract` on the joined page reads `detail_fields`. Include it only when the request needs per-item detail.
- **`detail_kind` + `detail_segment`**: news/article detail → ONE text per page (`detail_fields`, e.g. body with `method: boilerPipe`). Forum/thread detail → ONE ROW PER COMMENT: `detail_kind: comments` + `detail_segment` (the repeating post container), so the join is `wgetJoin`/`visitJoin`(`detail_link`) → `flatSelect`(`detail_segment`, `detail_fields`); a 40-reply thread yields ~40 rows. A forum's `detail_segment`/`detail_fields` come from the per-engine template (XenForo/SMF/phpBB/vBulletin/Discourse/Reddit) when the source's `engine` is set: reuse it, do NOT infer comments.

So a cataloged source assembles with **zero inference**: `fetch` (+ deterministic search actions) → paginate → `flatSelect`(`segment`, `fields`) → optionally `wgetJoin`/`visitJoin` → detail extraction. Then DRY-RUN once with `wizardValidate_1` (`yaml`) and **judge the result coherently; `record_count > 0` is necessary but NOT the gate**:
- **Plausible row count**: not 0, and not wildly off the recipe's `match_count` / the expected magnitude (1 row where dozens are expected, or thousands from an over-matched container, both signal drift).
- **Populated key fields**: rows carry real data (non-empty `title`/`url`/`price`/...). A correct `segment` with drifted `fields` returns rows full of nulls: that is a miss.

Re-infer with the wizard only when the data shows the **selectors drifted**. Separate an extraction failure from a fetch/access failure: 0 or junk rows on a blocked / empty / challenge page (anti-bot, geo, stale proxy, HTTP error) is NOT a markup change; fix access (proxy/geo/retry) or flag the source, leaving the recipe untouched.

## Execution engines: pick by KIND and SCALE (`engine` on run)

The same pipeline YAML runs on different engines; only the stage set and runtime differ. Pass `engine` to `executeJob_1` (or to `saveGeneratedPipeline` with `execute: true`); omit it for Spark.

| Engine | When | Runtime |
|--------|------|---------|
| *(omitted)* = Spark | default; big-data SCALE (out-of-RAM, shuffle, many sources) **and** every stage not on the lightweight tier: `sentiment*`, clustering, `surebet*`, `rag_*`, `intelligent*`/`iextract`, the full connector + ML set | distributed Spark on Kubernetes |
| `scrapy` | ingestion only (fetch, visit, explore, join, flatSelect, extract); analytics/LLM stages are rejected | lightweight Ray job, remote Camoufox, no Spark |
| `analytics` | relational / transform / custom Python on **small, in-RAM** data (load_*, `sql_query`, dedup, filter, select, `python_row_transform`/`python_dataframe_transform`, save_*) | in-process DuckDB + Polars |
| `hybrid` | scrape → analyze in ONE job on small data | the scrapy segment feeds the analytics segment |
| `temporal` | workflow orchestration (not a data engine) | Temporal |
| `slurm` | HPC batch, only for orgs with HPC access configured | Slurm |

Rule: scraping only → `scrapy`; small relational/Python analysis → `analytics`; small scrape+analyze → `hybrid`; big data / ML / LLM-heavy / many sources → Spark. `sql_query` and `python_extensions` run on `analytics`/`hybrid` too (DuckDB SQL; Spark and DuckDB SQL are both ANSI and largely interchangeable). Escalate to Spark when the data won't fit one worker's memory.

**BYOC / SaaS ephemeral VMs.** If the organization has `deployment_mode = byoc_soft` and a `byoc_soft_cloud_credential_id`, a Spark run goes automatically to **2 ephemeral Hetzner VMs** created for the run and destroyed afterwards; the caller passes no infra flags. Expect about **6 minutes of VM provisioning** before Spark starts: `executeJob_1` returns status `PROVISIONING`, which is not a hang. Lightweight engines (`scrapy`, `analytics`, `hybrid`, `temporal`, `slurm`) are not routed this way. For browser-heavy runs, `executeJob_1` also accepts per-run Camoufox VM flags: `camoufoxMode` (`IN_CLUSTER` | `EXTERNAL_VM`), `elasticBrowserVmCount`, `elasticBrowserCloudCredentialId`, `useEphemeralElasticBrowserVms`, `elasticBrowserVmLifecycle` (default `TEARDOWN_ALWAYS`; `KEEP`; `TEARDOWN_ON_JOB_SUCCESS`).

## The stage catalog is the source of truth

Always discover stages with `listStages` (filter by `plugin_id`, `stage_name`, or `plugin_type`: `etl`, `api`, `spark_stage`, `spark_action`, `spark_resolver`, `spark_mixed`) and read one stage's arguments with `getStage`. Entries look like:

```json
{
  "stage_name": "sentiment_analyze",
  "plugin_id": "sentimental-plugin-etl",
  "plugin_type": "spark_stage",
  "aliases": [],
  "arg_schema": [
    { "name": "text_field", "type": "string",  "required": true },
    { "name": "model",      "type": "string",  "required": false, "default": "default" },
    { "name": "max_chars",  "type": "integer", "required": false, "default": "4000" }
  ],
  "description": "..."
}
```

The order of `arg_schema` (or `args` in `getStage` output) IS the positional order. Use `listStages` with `plugin_type=spark_action` to see the **browser actions** usable inside `fetch`/`visit` traces; confirm any action name there before using it.

## The CORE rule: args are POSITIONAL

The engine's `WArgs` reads arguments **by index**, not by name. In YAML, `args:` is **always a list**; item N is the value at position N in the order of `arg_schema`. An item can be a scalar or a structured map (e.g. `iextract`'s `{selector, method}`); position is what matters.

```yaml
# CORRECT
- stage: sentiment_analyze
  args: ["text", "default", 4000]     # text_field, model, max_chars

# WRONG: a map is passed as ONE positional value ("Map(text_field -> text, ...)"),
# every other position falls back to its default
- stage: sentiment_analyze
  args: { text_field: text, model: default }
```

To set position N, fill every earlier position (use the documented default, often `""` or `0`).

The exception is **browser actions** (`WActionArgs`), which are keyed by name, and only inside an `actions:` map within `args`:

```yaml
- stage: fetch
  args:
    - "$url"                       # position 0 = url
    - actions:                     # position 1 = map with key "actions"
        - action: "comment_thread_hydrate"
          params: { max_plan_retries: 2, scroll_rounds: 10 }
```

## Pipeline anatomy: source → transform → sink

Every pipeline starts with a SOURCE stage that produces rows; a transform as first step is meaningless.

| Source use case | Stage |
|----------|-------|
| Fetch URLs (HTTP) | `wget`, `fetch` |
| Fetch with a real browser | `visit`, `fetch` with actions |
| Load the job's input CSV | `load_csv` with `path: "${INPUT_CSV_PATH}"` |
| Google text search (news/opinion) | `webSearch` |
| EAN / product / image search | `searchEngine` (requires `ean`) |

The default SINK is the pipeline-level `output:` block, which writes the run's output dataset (queryable afterwards):

```yaml
output: { format: parquet, mode: overwrite, path: "${OUTPUT_PARQUET_PATH}" }
```

`${OUTPUT_PARQUET_PATH}` and `${INPUT_CSV_PATH}` (the Job's input dataset) are injected at run time. Plugin-specific sinks (`save_csv`, `save_parquet`, `db_save_example`, `pc_save_match`, ...) exist; check the catalog. **Do not use `sentiment_save`** in ETL pipelines: the run's parquet output IS the sentiment dataset, already tied to the job.

## Manifest: the declarative envelope

`manifestApply` takes ONE string `yaml` holding several documents separated by `---`. Documents are processed in dependency order regardless of file order: **Project → Dataset → AgenticProfile → Pipeline → Job**. Cross-document references use `ref:<name>` (numeric ids are also accepted). Re-applying is an upsert by name.

| kind | Required | Notes |
|---|---|---|
| `Project` | `metadata.name` | optional `spec.description`; created in the caller's org |
| `Dataset` | `metadata.name` | optional `spec.format`, `spec.datasetType`; creates **only the record, no rows** (an existing dataset with that name is reused) |
| `AgenticProfile` | `metadata.name`, `spec` | `spec` stored verbatim; see the agentic skills |
| `Pipeline` | `metadata.name`, **`metadata.category`**, **`spec`** | `spec` holds `pipeline:` (and `sources:`, `match:`, `output:`, `python_extensions:`, `metadata:` for the engine); `metadata.category: ref:<name>` auto-creates the category; a number there is a CATEGORY id, not a project id; optional `metadata.agentic_profile` |
| `Job` | `metadata.name`, **`metadata.project`**, **`spec.agent`** | `spec.agent: ref:<pipeline name>`; optional `spec.input.dataset: ref:<name>` or id, `spec.description`, `spec.enabled` |

Note the asymmetry: a Pipeline uses `metadata.category`, a Job uses `metadata.project`.

### Complete working example: Dataset → Pipeline → Project → Job

Step 1, upload the input rows (a `kind: Dataset` document alone has no data). Call `uploadDatasetJson`:

```json
{ "name": "demo-seed-urls", "dataset_type": "input", "filename": "seed.csv",
  "content": "url\nhttps://books.toscrape.com/catalogue/page-1.html\nhttps://books.toscrape.com/catalogue/page-2.html\n" }
```

Step 2, `manifestApply` with this `yaml`:

```yaml
kind: Dataset
metadata:
  name: demo-seed-urls          # matches the uploaded dataset by name → reused, not recreated
spec:
  format: csv
  datasetType: input
---
kind: Pipeline
metadata:
  name: demo-books-listing
  category: ref:data_engineer   # agent category (auto-created if missing)
spec:
  pipeline:
    - stage: load_csv
      args:
        - { path: "${INPUT_CSV_PATH}", header: "true" }
    - stage: wget
      args: ["$url"]
    - stage: flatSelect
      args:
        - "article.product_pod"
        - - { selector: "h3 a", method: "attr:title", as: "title" }
          - { selector: ".price_color", method: "text", as: "price" }
          - { selector: "h3 a", method: "href", as: "url" }
  output: { format: parquet, mode: overwrite, path: "${OUTPUT_PARQUET_PATH}" }
---
kind: Project
metadata:
  name: demo-books
spec:
  description: Book listing demo
---
kind: Job
metadata:
  name: demo-books-job
  project: ref:demo-books
spec:
  agent: ref:demo-books-listing
  input:
    dataset: ref:demo-seed-urls
  description: Scrape the seeded listing pages
```

The response is `{dryRun, applied: [{kind, name, status, id | agentId | jobId, ...}], errors: []}`. Read the Project `id` and the Job `jobId` from `applied` (or use `getProjectFromName` + `getProjectJobs`). Always check `errors`: a document can fail while others succeed. Verify each stage's args with `getStage` before applying (the selectors above are for the example site only).

Step 3, run: `executeJob_1` with `{projectId, jobId}` (add `engine` if not Spark) → returns `executionId` and status. Step 4, follow it (see "Run, monitor, read results").

### `manifestValidate` (dry run) caveats

- It rejects stage names not in the catalog ("unknown stage(s) not in the catalog") and malformed `python_extensions` (stages must be a MAP keyed by function name; the `python_row_transform:` / `python_dataframe_transform:` / `python_source:` prefix must match the function's `type`). The error text says "Call getCatalogStages": in this MCP use `listStages` / `getStage`.
- It does NOT check argument shapes; that is your job via `getStage`, plus `wizardValidate_1` for a real sample run.
- A Job that references a Project or Pipeline defined in the same manifest but not yet created reports "not found" in validate; that is expected and resolves at apply time.
- `metadata.category: ref:<new name>` creates the category even during validate.

### Faster paths without a full manifest

- `saveGeneratedPipeline` (`pipeline_name`, `pipeline_yaml` = the spec content with top-level `pipeline:`/`output:`) upserts a pipeline by name; `execute: true` also runs it (`engine`, `datasetId` optional). A super_admin key has no own org and must pass `organization_id`.
- `pipelineDraftPut` with `context: "etl:pipeline-designer"`, `pipeline_name`, `pipeline_yaml`, `note` puts the YAML in the user's Pipeline Designer draft slot in the console, for them to review before saving; `pipelineDraftGet` reads it back, `pipelineDraftDelete` clears it.
- Existing pipelines: `getAllAgents(categoryId)` / `getResolvedPipelineYaml(agentId)`.

## Run, monitor, read results

1. `executeJob_1` → `executionId` (status may be `PROVISIONING` on BYOC: allow ~6 min).
2. `waitForExecution` (`projectId`, `jobId`, `executionId`, `timeoutSec`, `logTail`) blocks server-side and returns the final state plus a log tail; or poll `getExecutionStatus_1` / `executionStatus`.
3. On failure read `getExecutionLogs_1` (`podType` driver/executor, `tail`) and fix the pipeline: wrong arg positions, unknown column names (`UNRESOLVED_COLUMN`), empty fetches.
4. Preview rows with `executionOutput` (`executionId`, `limit`).
5. SQL: get the task id from `getAllTasks(projectId, jobId)`, then `queryDatasetByTask` with `taskId` and `sql: "SELECT title, price FROM {table} LIMIT 50"`; `{table}` is replaced with the task's output table (read-only SELECT over that table only). `getDatasetInfoByTask` returns the table and schema. For queries over datasets by id use `executeQuery` with the `[<datasetId>]` shortcut, e.g. `SELECT * FROM [1234] LIMIT 10`.
6. Stop with `stopJob` or `cancelExecution_2`.

## Workflow for building a pipeline

1. Natural-language request → check `catalogSources` for the sources, and `suggestStages_1` (`intent`) for candidate stages.
2. For each candidate stage call `getStage`; build `args:` as a list in `arg_schema` order; required args with no default MUST be present.
3. For a new scraping source without a recipe, dry-run with `wizardValidate_1` and judge rows coherently (see above).
4. Wrap in a manifest (or use `saveGeneratedPipeline`), run `manifestValidate`, then `manifestApply`.
5. Run with `executeJob_1`, monitor, inspect output, iterate.

## Choosing the crawling stage

### Pagination: pick the stage by how "next" is reachable (IMPORTANT)

The wrong mechanism silently returns only page 1.

**A. URL-based**: `?page=N`, `?index=N`, `&start=N`, or a real `<a href>` "next". Pages are independently fetchable → **one source per site**: fetch the first page, then follow the next-page link with `wgetExplore` (catalog verdict `wget`), `resilientExplore` (browser or uncatalogued site, Spark: wget first, browser only if blocked) or `visitExplore`. `depth` N reads the first page **plus N more** (5 pages → depth 4); pass `maxLinks` 1 so only the single "next" link is followed:
```yaml
- stage: resilientFetch
  args: ["https://shop.example/category"]
- stage: resilientExplore
  args: ["a[rel='next']", 4, 1]      # next-page selector, depth, maxLinks
- stage: flatSelect
  args: [".product", [ {selector: ..., method: ..., as: ...} ]]
```
Seed explicit page URLs only when the recipe's `pagination` gives the exact template (`url_template` with `{page}`); never guess the step of `?start=` / `?page=` (a wrong page size makes pages overlap or be skipped).

**B. Click-based**: a `<button>` "Next", "Load more", or JS instant search with no followable href → **`visitPaginate`**:
```yaml
- stage: visitPaginate
  args:
    - "https://site.com/search?q=x&index=0"   # seed url (literal or $col)
    - "button[aria-label='Next']"             # the single "next" control
    - 10                                       # optional page limit
- stage: flatSelect
  args: ["[class*='card']", [ {selector: ..., method: ..., as: ...} ]]
```
`visitPaginate` builds `Visit(url) +> Loop(Snapshot +> Click)` in one browser session: one Doc per page, stopping when the click fails. Sequential within a seed, parallel across seeds.

Do NOT paginate by giving `explore`/`visitExplore` a bare `[click]`: each hop's trace runs alone, so the click hits an unloaded page → 60 s `TimeoutError`. To paginate inside an explore, `visitExplore` takes an `actions:` list and auto-prepends `Visit('A.href)`: `args: ["div.category a", 1, {actions: [{action: paginate, selector: "a[rel=next]"}]}]`. The `paginate` (`Loop(Snapshot+Click)`) and `loadmore` (`Loop(Click)`) action factories also work in any `fetch`/`visitJoin` trace.

### HTTP vs browser

- `wget` / `wgetExplore` / `wgetJoin`: static HTML, PDFs, documents. Cheap, works on `scrapy`/`hybrid`.
- `visit` / `visitExplore` / `visitJoin` / `fetch` with actions: JS-rendered pages, catalog sources with `fetch_method: browser`, news articles (wget often returns an empty body there).

### Documents / PDF extraction: use `wget`, not the browser

Fetching a PDF (or docx/xlsx) URL is transparent: the engine detects the content type and **Tika-parses it into XHTML**, so you pull text with the same `extract` stage. A browser would render the pdf.js viewer instead of the document.

```yaml
# single PDF
- stage: wget
  args: ['<pdf-url>']
- stage: extract
  args: [ {selector: "body", method: text, as: doc_text} ]

# an index page → many .pdf links, all HTTP
- stage: wgetExplore            # check getStage for exact args
  args: ['<index-url>', 'a[href$=".pdf"]', 1]
- stage: wgetJoin
  args: ['a[href$=".pdf"]']
- stage: extract
  args: [ {selector: "body", method: text, as: doc_text} ]
```

Use `visitExplore` only when the index is a JS page picker, and even then fetch the PDFs with `wgetJoin`. Metadata: `method: attr:<name>`; links: `method: href`.

## `extract`, `flatSelect`, `iextract`: extraction clauses

- **`extract`**: each extractor is `{selector, method, as}`. On Spark both the flat form `args: [{...}, {...}]` and the nested form `args: [[{...}, {...}]]` work (the nested list is unwrapped). Prefer the flat form; the Scrapy engine's handling of the nested form is not verified. String shorthand `"h1.text->title"` is also accepted.
- **`flatSelect`**: `args: [<segment selector>, [ {selector, method, as}, ... ]]`: one row per matched container, field selectors relative to it.
- Common methods: `text`, `href`, `attr:<name>`, `code` (HTML), `boilerPipe` (main article text, camelCase exact), `price`. Check the catalog for others.
- **Article body: prefer `extract` + `method: boilerPipe` over `iextract`**: deterministic, no LLM cost: `{selector: body, method: boilerPipe, as: body}`.
- **`iextract`** (LLM, code mode): always give a field prefix (position 2) AND `as <col>` / `(field: <col>)` names in the prompt. Without them columns can be named after the whole prompt, and downstream stages die with `UNRESOLVED_COLUMN` after the expensive crawl. Output columns are `<prefix><snake_case_key>`.

```yaml
- stage: iextract
  args:
    - { selector: "body", method: "code" }     # position 0
    - "Extract from this product page: EAN code (field: ean_code), title (field: title), price as number (field: price), currency ISO code (field: currency). Empty string when not found. Preserve all input fields."
    - "pc_"                                     # position 2 = prefix → pc_ean_code, pc_title, ...
```

CSS selector guidance: prefer stable attributes (`data-*`, `itemprop`, semantic classes like `.product-card`, `article`) over positional paths (`:nth-of-type`) and generated class hashes; scope field selectors relative to the segment container; verify on a real sample with `wizardValidate_1`.

## webSearch: Google text search for news/opinion COVERAGE (sentiment)

`webSearch` is the TEXT search stage (distinct from `searchEngine`, which is EAN/product/image search and requires an `ean`). It runs Google CSE for a query + variants, paginates past 10 per request, de-dupes by link, and emits ONE ROW PER RESULT (`result_link`, `result_title`, `result_snippet`, `result_source`); then fetch each `$result_link`.

Coverage (a sentiment run should persist **≥50 real-body docs**):
- `num_results: 80` (CSE cap 100); never below 60.
- `query_variants`: **≥6 distinct angles, not synonyms** (synonyms collapse on de-dup): an interview angle, a named event/policy, a quote/clash, plus `site:<trusted domain> <entity>` for 2-3 catalogued domains.
- `date_restrict: m6` for an entity; widen to `y1` if thin. When news is thin, add a forum source (one row per comment).

Fetch news with **`visit`, not `wget`** (wget doesn't render JS → empty body). The pipeline starts from ONE seed row → a single partition → serial visits: insert **`repartition` `[8]` right after `webSearch`**.

```yaml
pipeline:
  - stage: webSearch
    args:
      - { query: "<entity> opinioni", query_variants: ["<entity> intervista","<entity> <event>","<entity> <policy>","<entity> dichiarazioni","site:ansa.it <entity>","site:repubblica.it <entity>"],
          num_results: 80, country: "it", date_restrict: "m6" }
      - "search_results"
  - stage: repartition
    args: [8]
  - stage: visit
    args: ["$result_link"]
  - stage: extract
    args:
      - { selector: "body", method: "boilerPipe", as: "text" }
      - { selector: "meta[property='article:published_time']", method: "attr:content", as: "published_at" }
  - stage: sentiment_analyze
    args: ["text"]
output: { format: parquet, mode: overwrite, path: "${OUTPUT_PARQUET_PATH}" }
```

The sentiment lane ENDS at `sentiment_analyze` → `output:` parquet. The charts read that output per job, so runs never mix. If fewer than 50 docs have body text, iterate in the same run (more angles or a forum source).

### Forum thread → one row per comment → sentiment

```yaml
pipeline:
  - stage: fetch
    args:
      - "https://forum.example.com/thread/12345"
      - actions:
          - action: "comment_thread_hydrate"       # confirm in listStages plugin_type=spark_action
            params: { max_plan_retries: 2, scroll_rounds: 10 }
  - stage: comment_extractor
    args:
      - "Identify each user comment block on this forum thread."
      - "Extract: author username (field: author), comment text (field: text), post timestamp ISO-8601 (field: post_timestamp), permalink (field: post_url), post id (field: post_id)."
      - "c_"                                     # → c_text, c_author, ...
  - stage: sentiment_analyze
    args: ["c_text", "default", 4000]
  - stage: sentiment_filter                      # optional
    args: ["negative", -1.0, -0.2, "", "Brand X"] # label, min_polarity, max_polarity, emotion (skip), contains_entity
output: { format: parquet, mode: overwrite, path: "${OUTPUT_PARQUET_PATH}" }
```

When the catalog has a recipe with `detail_segment` for the forum, prefer the deterministic `flatSelect` form over `comment_extractor`.

## Bookmakers / odds extraction

- **Odds are lazy-loaded**: the fetch/visit trace MUST click the market/accordion and `waitForSelector` the odds container BEFORE extraction.
- **Align names**: emit a consistent `event` column and per-outcome odds columns so `oddsNormalize` / `surebetFinder` / `sql_query` can group by event + outcome.
- **Default scope**: only the most popular market (match winner / 1X2 / moneyline) unless asked otherwise.
- **Multi-source by default**: arbitrage needs ≥2 books, so build a `sources:` map (one per bookmaker), then union + `surebetFinder`, even if the user names one site. The validator checks one source at a time; that is not a reason to author single-source.

`oddsSelect` produces one row per outcome per market (all selectors supplied up front). Args (re-check `getStage`): `markets` (required) `[{label, sectionSelector, rowSelector, fields:[{selector, method, as}]}]` (`rowSelector` relative to `sectionSelector`, fields relative to each row; `label` → `market_type` column) and optional `enabled` (subset of labels). Rows without non-empty `selection` and `odds` are dropped. `wizardInferOddsStructure_1` can infer the structure from a section's HTML.

```yaml
- stage: fetch
  args:
  - https://<bookmaker>/event/...
  - - {action: click, selector: '.market-accordion'}
    - {action: waitForSelector, selector: '.market .outcome'}
- stage: oddsSelect
  args:
  - markets:
    - label: "Match Winner"
      sectionSelector: ".market[data-market='1x2']"
      rowSelector: ".outcome"
      fields:
      - {selector: ".name", method: text, as: selection}
      - {selector: ".price", method: text, as: odds}
    enabled: ["Match Winner"]
```

## Multi-source pipelines (`sources:` + `match:`)

**Preferred form for any comparison or merge across several sources** (price comparison, catalogue vs competitors, listings from several portals): ONE pipeline with `sources:` + a common tail + `match:`. Do not run separate jobs and join their outputs afterwards, and do not hand-write `store`/`reset`/`union_with`: `sources:` desugars to exactly those.

One YAML scrapes several sources: each `sources.<name>` is its own mini `pipeline:`; rows are tagged with a literal **`source`** column (the map key) and unioned; the top-level `pipeline:` runs on the union; `match:` desugars to a `sql_query GROUP BY`. **`sources:` is a MAP, not a list** (a list fails with `MismatchedInputException ... ["sources"]`). Use `match: key:` (NOT `on:`, which YAML 1.1 turns into a boolean).

```yaml
metadata: { geo: gb, proxy_mode: sticky_session }   # geo + sticky IP + retry-on-block
sources:
  viking:
    pipeline:
      - { stage: fetch, args: ["https://www.viking-direct.co.uk/en/query?text=epson%20printer"] }
      - { stage: intelligentFlatSelect, args: ["the product result cards", "full product title as model_key, price with currency as price", ""] }
  staples:
    pipeline:
      - stage: fetch
        args:
          - "https://www.staples.co.uk/"
          - auto_internal_search: { query: "epson printer", prompt: "Find the search input and submit", wait_ms: 8000 }
      - { stage: intelligentFlatSelect, args: ["the product result cards", "full product title as model_key, price with currency as price", ""] }
pipeline:                                           # common tail on the union, BEFORE match
  - stage: sql_query
    args:
      - "SELECT * FROM (SELECT * EXCEPT(model_key), regexp_replace(upper(regexp_extract(model_key, '(?:ET|XP|WF|WP|SC|L|EP)[ -]?[A-Z]?[0-9]{2,6}[A-Z]{0,4}', 0)), '[^A-Z0-9]', '') AS model_key FROM df) WHERE model_key <> ''"
match: { key: model_key, collect: [model_key, price], min_sources: 1 }
output: { format: parquet, mode: overwrite, path: "${OUTPUT_PARQUET_PATH}" }
```

Lessons:
- **Match on a NORMALIZED code, never the raw title** (retailers phrase titles differently).
- `auto_internal_search: { ..., wait_ms: 8000 }` waits for async/JS result pages before the snapshot.
- `intelligentFlatSelect` extracts the attribute value when the inferred selector is a bare `[data-attr]`.
- Analytics verticals combine on the `source` column instead of `match:` (e.g. `sentiment` then `avgSentimentByKey` with `["source", "sentiment_score"]`).
- Known issue (as last observed): after the `sources:` union, `transformRow` LLM stages such as `sentiment` may read empty text and return neutral defaults. Workaround: run those stages **inside each source's `pipeline:`**, before the union.

**`sql_query` goes only at the END of a pipeline** (the common tail, or the end of a source's own `pipeline:`), never before a stage that fetches (`fetch`/`wget`/`visit`/`resilient*`/`*Join`/`*Explore`/`paginate`). To run the SQL it turns the dataset into a Spark DataFrame and rebuilds fresh rows with only the selected columns: the fetched pages are dropped and its output columns are not visible to `$column` references, so a later `resilientFetch: ["$url"]` fetches nothing. To fetch a list of URLs, load them (`load_csv`) and fetch directly, filtering the file itself beforehand; `manifestValidate` rejects a sql_query placed before a fetch stage.

**`match:` is a top-level block of the pipeline YAML, not a stage.** Do not look for it with `listStages`/`getStage`; write it next to `sources:` and `pipeline:` as above.

### Recipe: compare a customer's catalogue with competitors (price intelligence)

The customer's own products come from **their system** (an e-commerce MCP such as WooCommerce/Shopify,
a file, a database) — never scrape the customer's own shop. Competitors come from the **source
catalog**. Steps:

1. Read the catalogue from the customer's system (e.g. the shop MCP's `list_products`).
2. Load it into WebRobot as a dataset: `uploadDatasetJson(name="my_catalogue", filename="catalogue.csv",
   dataset_type="input", content="sku,name,price\n...")` → `filePath` (an `s3a://…/catalogue.csv`).
3. `catalogSources(domain=...)` for each competitor: build each competitor source from its `selectors`
   recipe (segment + fields); fetch with `wget` when the recipe says `wget`, otherwise `resilientFetch` (Spark).
   Point it at the **category/listing page** the user
   names (robots.txt usually forbids the internal search pages); more pages: one source per site with
   the explore stage that follows the next-page link (see Pagination), not one source per page.
4. One multi-source pipeline: the catalogue dataset is just another source (`load_csv`), a common
   `sql_query` tail derives the same normalized key on every source (distinctive words only: lowercase,
   letters only, drop the category's generic words, plus the field that must be equal such as the vintage),
   and `match:` builds the comparison
   table (one row per key with the offers of every source).
5. Run it with `engine: hybrid` (small job, fast; its tail SQL is DuckDB) or Spark for large catalogues
   (tail SQL is Spark SQL), then read the table with `queryDatasetByTask`.

```yaml
sources:
  catalogue:
    pipeline:
      - { stage: load_csv, args: [{ path: "<filePath from uploadDatasetJson>", header: "true" }] }
  vino:
    pipeline:
      - { stage: fetch, args: ["https://www.vino.com/denominazione/barolo"] }
      - { stage: flatSelect, args: [".ias-item", [ {selector: ".titolo-subtitle-cantina", method: text, as: name},
                                                   {selector: ".price-box", method: text, as: price},
                                                   {selector: "a[href*=dettaglio]", method: "attr:href", as: url} ]] }
  # … one source per competitor page, built the same way from its catalog recipe
pipeline:
  - stage: sql_query      # same key on every source: the wine's name without generic words, year, spaces, punctuation
    args:
      - "SELECT *, regexp_extract(name, '(19|20)[0-9]{2}', 0) AS vintage,
         translate(regexp_replace(replace(replace(replace(lower(name), 'barolo', ''), 'docg', ''), 'riserva', ''),
                   '(19|20)[0-9]{2}', ''), ' .,-''’\"', '') AS wine_key
         FROM df"
match: { key: wine_key, collect: [source, name, vintage, price, url], min_sources: 2 }
output: { format: parquet, mode: overwrite, path: "${OUTPUT_PARQUET_PATH}" }
```

- Write the tail so it means the same on both engines (hybrid runs it in DuckDB, Spark in Spark SQL):
  `replace()` and `translate()` change every occurrence in both, while `regexp_replace` replaces ALL
  matches in Spark but only the FIRST in DuckDB (and DuckDB's `'g'` flag is a NULL position in Spark) —
  use it only where the pattern occurs once (e.g. the year).
- Parse prices so both `1.234,50 €` and `€1234.50` work (comma present → drop dots, comma becomes dot).
- Keep fields one source lacks (a vintage the shop doesn't print) as columns to compare, not in the key.
- **Keep the `source` column in every tail `SELECT`** (`SELECT *, …` or `SELECT source, …`): `match:` counts the
  shops by it. Using it only inside a function (`regexp_replace(source, …) AS shop`) still drops it.
- On the hybrid engine `match: { by: [name], min_sources: 2 }` matches by text similarity instead of an
  exact key (CPU, no LLM) — useful when names are spelled differently across shops.
- Then compare in the table, propose changes, and write prices back only through the customer's system
  (e.g. the shop MCP's `update_price`) after the user approves.

## LLM-driven e-commerce flow: fetch + auto_internal_search → intelligentExplore → intelligentJoin → iextract

Use when CSS selectors are unknown or brittle.

**Internal search is an action, not a stage.** `auto_internal_search:` on `fetch` builds `Visit(url) → InternalSearchAction(query, prompt) → Snapshot()`. There is no `internalSearch` or `intelligentAction` stage, and `internalSearch` is NOT a registered action factory: `- action: internalSearch` in a manual trace fails the whole pipeline ("ActionFactory 'internalSearch' not found"). For a manual trace use registry actions (`input`, `click`, `waitforselector`, `wait`, `scroll`, ...):

```yaml
- stage: fetch
  args:
    - "https://shop.example.com/"
    - - { action: input, args: ["input[type=search]", "pikachu"] }
      - { action: click, args: ["button[type=submit]"] }
      - { action: waitforselector, args: [".results .product-card"] }
```

`wget` upstream of a search action fails with "No current page available" (no live DOM).

- **`intelligentExplore`** `["next page link", <max hops>]`: picks the row whose URL looks like a results page and lets the LLM infer the pagination selector. Run it AFTER the search fetch, or it infers footer/menu links from the homepage.
- **`intelligentJoin`** `["product detail link", "none", <max items>]`: infers the item-link selector and follows each (2nd arg is an action prompt, e.g. "click product link" for tab/button flows).
- Split form: `inferNavigationSelector` / `inferJoinSelector` / `inferSelector` write `_nav_selector` / `_join_selector` / `_inferred_selector` columns for downstream `$`-references.

```yaml
pipeline:
  - stage: fetch
    args:
      - "https://shop.example.com/"
      - auto_internal_search: { query: "pikachu", prompt: "Find the product search input in the site header and submit" }
  - stage: intelligentExplore
    args: ["next page link", 2]
  - stage: intelligentJoin
    args: ["product detail link", "none", 10]
  - stage: iextract
    args:
      - "product name as name, price (with currency) as price, stock status as stock, image URL as image_url"
      - "prod_"
output: { format: parquet, mode: overwrite, path: "${OUTPUT_PARQUET_PATH}" }
```

Cost ladder: `auto_internal_search` (LLM resolves selectors only) and `intelligentExplore`/`intelligentJoin` (one selector each) are cheap; `browser_use` is a full agent and costly.

## `browser_use`: agentic stage on a Chromium BaaS (Steel.dev)

For genuinely agentic navigation (cookie banners, multi-step dynamic UI, country gates) the example plugin's `browser_use` stage runs a `browser-use` Python agent on a Steel.dev session and emits one row `{steel_session_ws_url, url, prompt}`; a downstream `fetch` with `["$steel_session_ws_url"]` attaches to that session and normal extraction follows. It works only with Chromium/CDP backends (Steel.dev, Browserbase, Hyperbrowser, ...); **Camoufox/Firefox is not supported** by the upstream library. Requires `STEEL_DEV_API_KEY` and an LLM key in the runtime env.

```yaml
pipeline:
  - stage: browser_use
    args:
      - "Open the site, dismiss any cookie banner, search 'pikachu', wait for results, respond with done."
      - "https://scrapeme.live/shop/"
    config: { timeout_sec: 180, cwd: ${WEBROBOT_ETL_DIR} }
  - stage: fetch
    args: ["$steel_session_ws_url"]
  - stage: intelligentFlatSelect
    args: ["the product cards in the search results grid", "product name as name, price with currency as price", ""]
```

Variants: `browser_use_loop`, `browser_use_forum_lazy_load`, `browser_use_forum_lazy_load_extended`. Do not log in to gated sites with it (see Compliance).

## Python extensions: inline custom logic

```yaml
pipeline:
  - stage: load_csv
    args: [{path: "${INPUT_CSV_PATH}", header: "true"}]
  - stage: python_row_transform:my_transform
    args: []
python_extensions:
  stages:                      # a MAP keyed by function name, never a list
    my_transform:
      type: row_transform      # prefix must match: python_row_transform / python_dataframe_transform / python_source
      function: |
        def my_transform(row):
            return {**row, 'new_field': row.get('existing_field', '').upper()}
```

See `/webrobot-python-extension` for registration modes.

## Interactive pipeline designer (wizard) endpoints

The console's Pipeline Designer drives a server-side Camoufox tab, records actions as a trace, and infers selectors with PTA + LLM. Authenticated callers MUST use the **tenant mirrors** under `/webrobot/api/tenant/wizard/...` (tools ending in `_1`). The `/webrobot/api/demo/wizard/...` paths belong to the public demo and run on the demo organization's credentials; do not use them for a customer's work.

| Tool | Endpoint | Purpose |
|---|---|---|
| `cmfOpen_1` (`url`, `country`, `geo`) | `POST /tenant/wizard/cmf/open` | open a Camoufox tab → `{session_id, current_url, html}` |
| `cmfStep_1` (`session_id`, `actions`) | `POST /tenant/wizard/cmf/step` | replay actions (`Click`, `Type`, `Wait`, `WaitFor`, `Scroll`, `Back`) → new HTML |
| `cmfStatus_1`, `cmfResume_1`, `cmfClose_1` (`sessionId`) | `/tenant/wizard/cmf/{sessionId}` | status / resume a parked session / release (idle TTL ~5 min) |
| `wizardProxy_1` (`url`, `strategy`) | `GET /tenant/wizard/proxy` | static snapshot fetch, no live session |
| `wizardInferSegment_1` (`url`, `segmentation_prompt`, `html`) | `POST /tenant/wizard/infer-segment` | PTA + LLM repeating-container selector for `flatSelect` |
| `wizardInferFields_1` (`url`, `intent`, `container_selector`, `stage_name`, `html`) | `POST /tenant/wizard/infer-fields` | `{selector, as, method}` list |
| `wizardInferSelector_1`, `wizardInferBodySelector_1` | `POST /tenant/wizard/infer-selector`, `/infer-body-selector` | one selector from an intent / the article body |
| `wizardInferActions_1` (`url`, `intent`, `stage_name`) | `POST /tenant/wizard/infer-actions` | click/type/wait trace for an intent |
| `wizardConsolidateSelectors_1`, `wizardRelaxSelectors_1`, `wizardSuggestFieldNames_1` | `POST /tenant/wizard/...` | harden / generalize selectors, name fields |
| `wizardInferOddsStructure_1` | `POST /tenant/wizard/infer-odds-structure` | odds market structure for `oddsSelect` |
| `wizardValidate_1` (`yaml`, `session_id`, `include_snapshot`) | `POST /tenant/wizard/validate` | sample run of a pipeline → record count + rows |
| `selectorCacheGet_1` / `selectorCachePut_1` | `/tenant/selector-cache` | reuse / store inferred selectors |

Treat `session_id` as opaque (it encodes the owning pod; round-trip it as returned). LLM steps use the caller org's own LLM credentials (`cloud_credentials`), not pod-wide keys. PTA segment inference ranks repeating-wrapper candidates algorithmically (majority tag, semantic class names, `data-testid` groups, forum post wrappers, comment-row patterns) and lets an LLM pick one.

Recorded actions go into `fetch` (and explore/join) traces as an actions list, as in the examples above. Use the wizard when the site is JS-heavy or needs multi-step navigation and selectors aren't obvious; write YAML by hand for stable pages with known selectors.

## Rules of thumb

- **Never invent stage or action names.** If `listStages` / `getStage` doesn't show it, it doesn't exist.
- **Never start with a transform.** First stage produces rows.
- **Never use a map for `args`.** Always a list; maps only as a value at a position (or a trailing `config`).
- **Always dry-run before running**: `manifestValidate` for names/structure, `wizardValidate_1` for real rows on scraping sources.
- **Check `errors` in every manifest response** and the final execution state before reporting success; show the user a few real output rows.
- Partner plugins: the catalog is the truth; it updates when the plugin is reloaded.

## On $ARGUMENTS

- A YAML path: read it, validate it (`manifestValidate`), offer to fix, apply, or run.
- A description: check `catalogSources`, call `suggestStages_1`, read each stage with `getStage`, build, validate, apply, run, and show results.
- Unclear: ask whether the data origin is URLs, a CSV, or a search, then pick the right SOURCE stage.
