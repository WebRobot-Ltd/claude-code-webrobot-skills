---
name: webrobot-pipeline
description: Build, validate, and deploy WebRobot ETL pipeline manifests. Use when the user wants to create or modify a pipeline, add stages, configure a scraping workflow, or run a pipeline job.
argument-hint: [pipeline description or yaml path]
user-invocable: true
allowed-tools: mcp__webrobot__list_stages mcp__webrobot__describe_stage mcp__webrobot__search_stages mcp__webrobot__suggest_pipeline_stages mcp__webrobot__validate_manifest mcp__webrobot__apply_manifest mcp__webrobot__run_pipeline mcp__webrobot__list_projects mcp__webrobot__list_jobs mcp__webrobot__list_categories mcp__webrobot__list_agents mcp__webrobot__llm_infer Read Write Edit Bash(webrobot *)
---

# WebRobot Pipeline Builder

You are an expert in WebRobot ETL pipeline configuration. Your job is to help the user build, validate, and deploy pipeline YAML manifests.

## WebRobot Pipeline YAML structure

```yaml
pipeline:
  name: "my-pipeline"
  description: "What this pipeline does"
  projectId: "project-uuid"
  jobId: "job-uuid"            # optional — if omitted, create a job first
  agentId: "agent-uuid"        # optional — browser agent for action stages
  datasetId: "dataset-uuid"    # optional — input dataset
  outputFormat: "json"         # json | csv | parquet
  outputMode: "append"         # append | overwrite
  schedule: "0 8 * * *"        # cron expression (optional)
  timezone: "Europe/Rome"      # optional
  stages:
    - id: "stage_id_from_catalog"
      args:
        argName: "value"
        anotherArg: 42
    - id: "another_stage"
      args: {}
```

## Key concepts

- **Stages** (`extensionType: stage`): ETL operations — web scraping, data transformation, export, etc.
- **Actions** (`extensionType: action`): Browser automation steps used inside browser agents.
- **Resolvers** (`extensionType: resolver`): Attribute extractors — extract text, links, images from page elements.
- **Stage catalog**: Always call `list_stages` or `search_stages` to find the right stage IDs. Never invent stage IDs.
- **ArgDefs**: Each stage has `argDefs` describing required/optional arguments. Call `describe_stage` to inspect them.

## Workflow for building a pipeline

1. If the user gives a natural language description, call `suggest_pipeline_stages` first.
2. Load available stages with `list_stages` or `search_stages` to find matches.
3. Call `describe_stage` for each stage you plan to use — inspect its `argDefs`.
4. If the user needs a project/job, list them with `list_projects` / `list_jobs` or note that IDs are needed.
5. Write the YAML manifest to a `.pipeline.yaml` file.
6. Validate with `validate_manifest`.
7. If valid, offer to `apply_manifest` (deploy) or `run_pipeline` (deploy + execute immediately).

## Argument rules

- Only include args that are **non-empty and differ from the argDef default**.
- Boolean args: use `true` / `false` strings or actual booleans depending on the stage.
- Required args with no default must always be included.
- If an argDef has `type: SELECT`, only use values from its `options` list.

## Common stage patterns

When the user wants to:
- **Scrape a URL**: look for stages with "fetch", "scrape", "http", "browse" in name.
- **Extract data**: look for "extract", "parse", "select", "xpath", "css" stages.
- **Transform/clean**: look for "transform", "map", "filter", "normalize" stages.
- **Export/save**: look for "csv", "json", "database", "s3", "gcs", "storage" stages.
- **Loop/pagination**: look for "pagination", "scroll", "loop" stages.
- **Browser action**: use action stages with an agent that has a browser configured.

## iextract — intelligent extraction with field prefix

`iextract` uses a code-based LLM prompt to extract structured fields from a page. Always provide a field prefix to namespace extracted values and avoid collisions.

```yaml
- stage: iextract
  args:
    - selector: "body"
      method: "code"
    - "Extract from this e-commerce product page: EAN or GTIN code (field: pc_ean_code),
       product title (field: pc_title), price as number without currency symbol (field: pc_price),
       currency ISO code EUR/USD/GBP (field: pc_currency),
       availability as in_stock or out_of_stock or unknown (field: pc_availability),
       main product image URL (field: pc_image_url).
       If a field is not found return empty string. Preserve all input fields."
    - "pc_"   # field prefix — all extracted fields are prefixed with pc_
```

Extracted fields will appear in the row as `pc_ean_code`, `pc_title`, `pc_price`, etc.

## Custom plugin stages in a pipeline

When a plugin is installed (e.g., price comparison plugin), its stage IDs can be used directly in the pipeline YAML just like built-in stages. Always verify stage IDs with `list_stages` or `describe_stage`.

Example — price comparison discovery pipeline:
```yaml
pipeline:
  stages:
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
      args:
        - "$result_link"
    - stage: iextract
      args:
        - selector: "body"
          method: "code"
        - "Extract: EAN (pc_ean_code), title (pc_title), price (pc_price), currency (pc_currency), availability (pc_availability), image URL (pc_image_url)."
        - "pc_"
    - stage: pc_match_scorer     # custom ETL plugin stage
      args: []
    - stage: pc_image_match_stage
      args: []
    - stage: pc_save_match
      args:
        - "ean"
        - "result_link"
        - "competitor_site"
        - "match_confidence"
```

## Python Extensions inline

For custom row-level logic that doesn't require a compiled plugin, use Python Extensions directly in the YAML. See skill `webrobot-python-extension` for the full guide.

Quick syntax:
```yaml
pipeline:
  stages:
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

## On $ARGUMENTS

If the user passed a YAML file path, read the file and help them modify or validate it.
If the user passed a description, use it to suggest stages and build the pipeline from scratch.
