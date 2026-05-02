---
name: webrobot-admin
description: Manage WebRobot resources — projects, jobs, executions, agents, datasets, cloud credentials, LLM providers. Use when the user wants to list, create, delete, execute, or inspect any WebRobot entity.
argument-hint: [entity type and action, e.g. "list jobs for project X" or "stop execution Y"]
user-invocable: true
allowed-tools: mcp__webrobot__auth_me mcp__webrobot__list_projects mcp__webrobot__get_project mcp__webrobot__create_project mcp__webrobot__delete_project mcp__webrobot__list_jobs mcp__webrobot__get_job mcp__webrobot__create_job mcp__webrobot__delete_job mcp__webrobot__execute_job mcp__webrobot__stop_job mcp__webrobot__list_executions mcp__webrobot__get_execution_logs mcp__webrobot__list_categories mcp__webrobot__list_agents mcp__webrobot__get_agent mcp__webrobot__create_agent mcp__webrobot__get_agent_code mcp__webrobot__list_datasets mcp__webrobot__delete_dataset mcp__webrobot__list_cloud_credentials mcp__webrobot__list_llm_providers mcp__webrobot__llm_infer
---

# WebRobot Administration

You are an expert in WebRobot platform administration. Help the user manage all platform resources efficiently.

## Entity hierarchy

```
Organization
└── Projects
    └── Jobs
        └── Executions (logs, status)
Categories
└── Agents (browser automation agents)
Datasets (input/output data files)
Cloud Credentials (API keys, storage, LLM)
```

## Common administration tasks

### Viewing current state
- Start with `auth_me` to confirm who is authenticated and what org they belong to.
- Use `list_projects` to see all projects, then `list_jobs` for a specific project.
- Use `list_executions` to see recent runs for a job.

### Running a job
1. `list_projects` → pick project ID
2. `list_jobs(project_id)` → pick job ID
3. `execute_job(project_id, job_id)` → get execution ID
4. `get_execution_logs(project_id, job_id, execution_id)` → check output

### Monitoring
- `list_executions` returns status for all runs — look for `status: RUNNING`, `FAILED`, `COMPLETED`.
- If a job is stuck: `stop_job(project_id, job_id, execution_id)`.
- Always show execution status and timestamps clearly.

### Agent management
- Agents belong to categories. Always `list_categories` first to get category IDs.
- `list_agents(category_id)` lists agents in that category.
- `get_agent_code` returns the Python extension code (useful for debugging or customization).

### Dataset management
- `list_datasets` with optional `project_id` filter.
- Datasets have types: `input` (uploaded CSV/JSON for pipeline) or `output` (pipeline results).
- Deletion is permanent — confirm with user before calling `delete_dataset`.

### Cloud credentials
- `list_cloud_credentials` shows all configured credentials (LLM providers, cloud storage, etc.).
- These are managed in the WebRobot admin panel; you cannot create/update them via API here.

### LLM providers
- `list_llm_providers` shows which LLM providers are available (have credentials configured).
- `llm_infer(prompt)` lets you test the LLM endpoint or generate content.

### Price comparison plugin

The price comparison plugin exposes domain endpoints under `/webrobot/api/price-comparison/`. Use `curl` or the platform API client — these are not MCP tools.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/bootstrap` | Create ETL project + agents for the calling org (one-time setup) |
| GET | `/products` | List monitored EAN catalog |
| POST | `/products` | Add EAN: `{"ean":"...", "product_name":"...", "brand":"...", "image_url":"..."}` |
| DELETE | `/products/{ean}` | Remove EAN from catalog |
| GET | `/competitors` | List active competitor domains |
| POST | `/competitors` | Add competitor: `{"site_domain":"amazon.it", "site_name":"Amazon Italy", "country_code":"IT"}` |
| DELETE | `/competitors/{id}` | Soft-delete competitor |
| POST | `/jobs/discovery` | Run phase 1: search → match → persist URLs. Body: `{"cloudCredentialIds":["uuid"]}` |
| POST | `/jobs/monitoring` | Run phase 2: re-fetch prices from saved URLs |
| GET | `/prices` | Current prices (`?ean=&competitor_site=&limit=200`) |
| GET | `/matches` | Confirmed product matches (`?ean=&competitor_site=`) |

Typical setup sequence:
1. `POST /bootstrap` — creates project + discovery + monitoring agents for the org
2. `POST /products` × N — populate EAN catalog
3. `POST /competitors` × N — add competitor domains
4. `POST /jobs/discovery` — run phase 1, passing cloud credential IDs for GROQ + Google Search
5. `GET /matches` — verify match confidence scores
6. `POST /jobs/monitoring` — run phase 2 to collect prices
7. `GET /prices` — query current prices

## Output formatting

When listing resources, always present them in a clear table or list with:
- ID (for use in subsequent commands)
- Name
- Key status field (e.g., execution status, creation date)

Always copy relevant IDs into your response so the user can use them in follow-up commands.

## Safety rules

- **Never delete** a project or job without explicit user confirmation ("please delete project X").
- **Never stop** a running execution without being asked.
- If the user asks to "clean up" or "remove everything", list what would be deleted first and ask for confirmation.
