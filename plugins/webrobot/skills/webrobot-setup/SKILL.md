---
name: "webrobot-setup"
description: "Connect Claude Code to WebRobot and find the right tool for a task. Covers the API key (the plugin's \"WebRobot API key\" option), verifying the connection, what each platform area does, and a task-to-tool map (datasets, pipelines, projects and jobs, agents, apps, knowledge, analytics reports, AI Agent Deploy) with exact MCP tool names and REST paths. Use first when the user is getting started, when a WebRobot tool call fails with 401/403/404, or when you don't know which tool covers a task."
argument-hint: "[what to set up or do, e.g. \"connect my account\" or \"which tool runs a job\"]"
user-invocable: true
---

# WebRobot setup and tool map

## 1. Connect

The plugin's MCP server is called `webrobot`:

- URL: `https://mcp-full.webrobot.eu/mcp`
- Auth header: `X-API-Key`, filled from the plugin's **WebRobot API key** option

Claude Code asks for the key when the plugin is installed or enabled and keeps it as a secret. To change it later, open `/plugin`, select `webrobot` and edit its configuration.

The value is the key id and the secret joined by a colon (`key_id:secret`), exactly as the console shows it. The secret alone, or `key_id.secret`, answers 401.

If no key was set, the server connects without one and every call answers 401. Set the key in the plugin's configuration and restart Claude Code; `/mcp` shows whether `webrobot` is connected.

**Getting a key:** in the console go to **Developer → API** and create one. An admin can also create one with the `createApiKey` tool (body `{"label": "...", "owner_role": "developer"}`; `scopes` and `expires_at` are optional; needs the admin role). `listApiKeys` lists them and `deleteApiKey` revokes one.

**Scope:** a key belongs to one organization, and everything it does stays inside that org: it lists, creates and queries only that org's projects, datasets, profiles and apps. The key's role (viewer < developer < admin) decides what it may change.

### Verify

1. `getHealth`: the API is up.
2. `getCurrentUser` (GET `/webrobot/api/auth/me`): who you are, your role and your organization. Always check this first. If the org is wrong, you are using the wrong key.
3. Optional: `balance` (credits), `getEffectiveEntitlements` (what the plan allows).

### Calling the REST API directly

Every tool description says `Executes METHOD /path`. The REST URL is that path with the prefix `https://api.webrobot.eu/api`:

```
tool path:  /webrobot/api/datasets
REST URL:   https://api.webrobot.eu/api/webrobot/api/datasets
```

```bash
export WR=https://api.webrobot.eu/api/webrobot/api
curl -s "$WR/auth/me" -H "X-API-Key: <key_id>:<secret>"
```

You can also log in as a user to get a JWT, then send `Authorization: Bearer <jwt>`:

```bash
curl -s -X POST "$WR/auth/login" -H 'Content-Type: application/json' \
  -d '{"identifier":"me@example.com","password":"..."}'
# -> {"jwt": "..."}  or, with 2FA enabled, {"mfa_token": "..."}; then:
curl -s -X POST "$WR/auth/mfa/challenge" -H 'Content-Type: application/json' \
  -d '{"mfa_token":"<mfa_token>","code":"123456"}'
# -> {"jwt": "..."}
```

## 2. Platform areas

| Area | What it is |
|---|---|
| **Datasets** | CSV/JSON/Parquet files in object storage. You can query them with SQL (Trino). There are *input* datasets (uploaded) and *output* datasets (what job runs write). See the `webrobot-datasets` skill. |
| **Pipelines** | A pipeline is ETL YAML made of stages (fetch, visit, explore, extract, SQL, LLM…). It is stored as an *agent* inside a *category*. See the `webrobot-pipeline` skill. |
| **Projects & jobs** | A project groups jobs. A job is one pipeline plus an optional input dataset. Each execution creates tasks, and each task has an output dataset. |
| **Agents (Agent Studio)** | *Agentic profiles*: LLM agents or teams with tools and MCP servers. You start them as background runs (executions), by schedule or by trigger. |
| **Apps** | Vertical apps built in App Studio from a manifest. They are published at `https://<slug>.webrobot.eu`. |
| **Knowledge** | Indexes that can be searched with RAG over your documents. |
| **Analytics** | Archive of the reports written by the analyst agent (title, question, datasets, markdown report). |
| **AI Agent Deploy** | A persistent chat for a tenant (chat server and Telegram bridge) running a profile on dedicated VMs. |

## 3. Task → tool map

Tools are named after OpenAPI operationIds. A `_1`/`_2` suffix marks a different endpoint, not a version, so check the path.

### Account
| Task | Tool | HTTP |
|---|---|---|
| Who am I / which org | `getCurrentUser` | GET `/webrobot/api/auth/me` |
| API keys | `listApiKeys`, `createApiKey`, `deleteApiKey` | `/webrobot/api/auth/api-keys` |
| Credits | `balance`, `usage`, `estimate` | `/webrobot/api/credits/*` |
| Cloud/LLM credentials | `getAllCloudCredentials`, `createCloudCredential`, `testCloudCredential` | `/webrobot/api/cloud-credentials` |

### Datasets (details: `webrobot-datasets`)
| Task | Tool | HTTP |
|---|---|---|
| List / get | `getAllDatasets`, `getDataset` | GET `/webrobot/api/datasets[/{id}]` |
| Upload CSV (JSON body, works over MCP) | `uploadDatasetJson` | POST `/webrobot/api/datasets/upload-json` |
| Upload file (multipart, REST only) | `uploadDatasetFile` and then `createDataset_2` | POST `/webrobot/api/datasets/upload`, then POST `/webrobot/api/datasets` |
| Columns | `getDatasetFields` | GET `/webrobot/api/datasets/{id}/fields` |
| SQL on any of your datasets | `executeQuery` | POST `/webrobot/api/datasets/query` |
| SQL on one task's output | `queryDatasetByTask`, `getDatasetInfoByTask` | `/webrobot/api/datasets/query/task/{taskId}` |
| Update / delete | `updateDataset`, `deleteDataset` | PUT/DELETE `/webrobot/api/datasets/{id}` |

### Pipelines (details: `webrobot-pipeline`)
| Task | Tool | HTTP |
|---|---|---|
| Browse the stage catalog | `listStages` | GET `/webrobot/api/catalog/stages` |
| Search stages by category/type/text | `listStages_1` | GET `/webrobot/api/manifest/stages` |
| One stage: args and YAML example | `getStage` (`name`) | GET `/webrobot/api/manifest/stages/{name}` |
| Suggest stages for an intent | `suggestStages_1` (`intent`) | POST `/webrobot/api/tenant/wizard/suggest` |
| Curated sources and how to fetch them | `catalogSources` | GET `/webrobot/api/catalog/sources` |
| Dry-run a manifest | `manifestValidate` (`yaml`) | POST `/webrobot/api/manifest/validate` |
| Create Project/Dataset/Pipeline/Job from a manifest | `manifestApply` (`yaml`) | POST `/webrobot/api/manifest/apply` |
| Save a pipeline by name (and optionally run it) | `saveGeneratedPipeline` (`pipeline_name`, `pipeline_yaml`, `execute`, `engine`, `datasetId`) | POST `/webrobot/api/tenant/save-generated-pipeline` |
| Put YAML in the console's Pipeline Designer draft | `pipelineDraftPut` (`context`, `pipeline_name`, `pipeline_yaml`, `note`); read/clear with `pipelineDraftGet`, `pipelineDraftDelete` | `/webrobot/api/tenant/pipeline-draft` |
| Validate YAML against a live page | `wizardValidate_1` | POST `/webrobot/api/tenant/wizard/validate` |
| Read a stored pipeline | `getResolvedPipelineYaml` (`agentId`) | GET `/webrobot/api/agents/{agentId}/pipeline-yaml` |

A minimal manifest. The Pipeline needs `metadata.category`, given as `ref:<name>` (created if it doesn't exist) or as a numeric category id. A project id does not work there. The Job uses `metadata.project`:

```yaml
apiVersion: webrobot/v1
kind: Project
metadata: { name: demo-project }
---
apiVersion: webrobot/v1
kind: Pipeline
metadata: { name: demo-pipeline, category: ref:demo-pipelines }
spec:
  pipeline:
    - { stage: wget, args: ["https://example.com"] }
  output: { format: parquet, mode: overwrite, path: "${OUTPUT_PARQUET_PATH}" }
---
apiVersion: webrobot/v1
kind: Job
metadata: { name: demo-job, project: ref:demo-project }
spec: { agent: ref:demo-pipeline, enabled: true }
```

`manifestApply` returns `{applied:[{kind,name,id,status}], errors:[]}`. Note the Project and Job ids.

### Projects, jobs, executions
| Task | Tool | HTTP |
|---|---|---|
| List / create project | `getAllProjects`, `createProject` (`name`, `description`) | `/webrobot/api/projects` |
| Find project | `getProject`, `getProjectFromName` | GET `/webrobot/api/projects/id/{id}` / `/{name}` |
| Jobs of a project | `getProjectJobs` | GET `/webrobot/api/projects/id/{projectId}/jobs` |
| Create job (pipeline + input) | `addJobToProject` (`projectId__path`, `name`, `agentId`, `inputDatasetId`) | POST `/webrobot/api/projects/id/{projectId}/jobs` |
| Update / remove job | `updateJob`, `removeJobFromProject` | `/webrobot/api/projects/id/{p}/jobs/{j}` |
| **Run a job** | `executeJob_1` (`projectId`, `jobId`, optional `engine`: `"scrapy"` for ingestion-only) | POST `/webrobot/api/projects/id/{p}/jobs/{j}/execute` → `executionId` |
| Wait for the end | `waitForExecution` (`timeoutSec` max 45, `logTail`). Repeat until `terminal`. At the end it returns `taskId` and `outputDatasetId` (or `logTail` on failure). | GET `.../executions/{executionId}/wait` |
| Status / logs | `getExecutionStatus_1`, `getExecutionLogs_1`, `getJobLogs` | `.../executions/{executionId}/status|logs` |
| Stop | `stopJob`, `cancelExecution_2` | POST `.../stop`, DELETE `.../executions/{executionId}` |
| Tasks (each has `outputDatasetId`) | `getAllTasks` (`projectId`, `jobId`), `list_13` (`jobId`, `status`) | GET `.../jobs/{j}/tasks`, GET `/webrobot/api/tasks` |
| Output rows | `queryDatasetByTask` (`taskId`) | POST `/webrobot/api/datasets/query/task/{taskId}` |
| Schedule a project | `setProjectSchedule` (`cronSchedule`, `enabled`, `timezone`, `jobId`), `getProjectSchedule` | `/webrobot/api/projects/id/{p}/schedule` |
| Metrics | `getJobMetrics`, `getProjectMetrics` | `.../metrics` |

### Agents (Agent Studio)
| Task | Tool | HTTP |
|---|---|---|
| List / get profiles | `listProfiles`, `getProfile`, `getRenderedProfile`, `profileVersions` | `/webrobot/api/agentic/profiles[/{id}]` |
| Create / update / delete | `createProfile` (`name`, `description`, `spec` or `specYaml`, `enabled`), `updateProfile` (`id__path` + fields), `deleteProfile` | same |
| Put a profile in the Agent Studio draft | `agentProfileDraftPut` (`context`, `profileSpec`, `note`) | PUT `/webrobot/api/agentic/profile-draft` |
| **Start a run** | `start` (`profileId` or `profileName`, `inputs`) | POST `/webrobot/api/agentic/start` → `executionId` |
| Run status / logs / cancel | `status` (`eid`), `executionLogs_1` (`eid`, `tail`), `cancel` (`eid`) | `/webrobot/api/agentic/{eid}` |
| Recent runs | `listExecutions` | GET `/webrobot/api/agentic/executions` |
| Schedule a run (cron) | `scheduleAgentic` (`name`, `cronExpr`, `startRequestJson`, `enabled`); remove with `deleteAgenticSchedule` | `/webrobot/api/agentic/schedule` |
| Triggers | `listTriggers`, `createTrigger`, `deleteTrigger` | `/webrobot/api/agentic/triggers` |
| MCP servers available to agents | `listMcpServers`, `createMcpServer`, `updateMcpServer` | `/webrobot/api/agentic/mcp-servers` |
| Marketplace profiles | `list_2`, `detail`, `clone` | `/webrobot/api/agentic/marketplace/listings` |

`scheduleAgentic.startRequestJson` is the `start` body as a JSON string, e.g. `"{\"profileId\":\"42\",\"inputs\":{\"city\":\"Bologna\"}}"`.

### Apps (vertical apps)
The MCP server has **no tool** for apps. Use REST, or build and publish in the console (App Studio):

```bash
curl -s "$WR/vertical-apps" -H "X-API-Key: <key_id>:<secret>"            # {"apps":[{slug,url,previewUrl,...}]}
curl -s "$WR/vertical-apps/<slug>" -H "X-API-Key: <key_id>:<secret>"     # draft + published manifest
curl -s -X PUT "$WR/vertical-apps/<slug>/draft" -H "X-API-Key: <key_id>:<secret>" \
  -H 'Content-Type: application/json' -d '{"manifest":"<manifest JSON as a string>"}'
```

Saving a draft creates the app (slug rule: `^[a-z][a-z0-9-]{1,38}[a-z0-9]$`), and the preview runs at `https://preview-<slug>.webrobot.eu`. Publish from App Studio: it creates the app's agents and pipelines before `POST /vertical-apps/{slug}/publish`.

### Knowledge
| Task | Tool | HTTP |
|---|---|---|
| Ask a question over an index | `ragQuery_1` (`question`, `index_name` or `project_name`, `top_k`, `filters`) | POST `/webrobot/api/tenant/rag/query` |
| Index status | `ragStatus_1` (`index_name`, `project_name`) | GET `/webrobot/api/tenant/rag/status` |
| Create index | `ensureIndex` (`index_name`, `project_name`) | POST `/webrobot/api/rag/index` |

### Analytics reports
| Task | Tool | HTTP |
|---|---|---|
| List / get | `listAnalyticsReports` (`q`, `status`, `savedOnly`, `limit`), `getAnalyticsReport` | `/webrobot/api/analytics/reports` |
| Create / update / delete | `createAnalyticsReport` (`body`: `title`, `question`, `mode` `existing`\|`collect`, `dataset_ids`, `execution_id`, `status`, `report_md`, `saved`), `updateAnalyticsReport`, `deleteAnalyticsReport` | same |

A report row is only the archive. The analysis itself is an agent run (`start`) whose `executionId` you store in the report.

### AI Agent Deploy (tenant chat)
| Task | Tool | HTTP |
|---|---|---|
| List deployments | `list_14` | GET `/webrobot/api/tenant-chat` |
| Deploy a profile as a persistent chat | `create_6` (`tenantId`, `profileId`, `vmCount`, `hetznerToken`, `telegramBotToken`, `claudeToken`) | POST `/webrobot/api/tenant-chat` |
| Status | `get_4` (`tenantId`) | GET `/webrobot/api/tenant-chat/{tenantId}` |
| Swap profile / reload | `reload` (`tenantId`, `profileId`) | POST `.../{tenantId}/reload` |
| Remove (admin) | `delete_4` (`tenantId`, `hetznerToken`) | DELETE `.../{tenantId}` |

## 4. End-to-end: a CSV in, a pipeline run, results out

1. `getCurrentUser` to confirm the org.
2. `uploadDatasetJson` (`name`, `content` = CSV text) → `datasetId`.
3. `getStage` / `suggestStages_1` to choose the stages, then `manifestValidate` and `manifestApply` with Project + Pipeline + Job (`spec.input.dataset: <datasetId>`).
4. `executeJob_1` (`projectId`, `jobId`) → `executionId`.
5. `waitForExecution` (`projectId`, `jobId`, `executionId`). It waits 45 s per call, so repeat until `terminal: true`. It then returns `taskId` and `outputDatasetId`.
6. `queryDatasetByTask` (`taskId`, `sql: "SELECT * FROM {table} LIMIT 50"`).

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| **401** on every call | No key or a bad key. The plugin's **WebRobot API key** option is empty, not in `key_id:secret` form, or the key was revoked. Set it in `/plugin` → `webrobot` and restart Claude Code. |
| **401** on `saveGeneratedPipeline` with a super_admin key | That key has no own org, so pass `organization_id`. |
| **403** | The role is too low (viewer can't create, `indexDataset` and `createApiKey` need admin), or the resource belongs to another org. Check `getCurrentUser`. |
| **404** on something you can see in the console | It belongs to another org (cross-org reads answer 404), or the path is wrong. REST paths need the `/api` prefix: `https://api.webrobot.eu/api/webrobot/api/...`. |
| **402** on `executeJob_1` | Out of credits or plan limit. Check `balance`. |
| **415** / multipart errors over MCP | MCP can't send multipart. Use `uploadDatasetJson` (JSON body) instead of `uploadDatasetFile`, or `curl -F` against the REST endpoint. |
| `manifestValidate`: "Pipeline.metadata.category is required" / "is not a numeric id" | Add `metadata.category: ref:<name>` to the Pipeline doc. In validate, refs to docs in the same manifest show "not found"; they resolve on apply. |
| Tool exists but behaves unexpectedly | Read the tool description: its `Executes METHOD /path` line is the endpoint. The `_1` suffix tools often hit a different service (e.g. `/tenant/...`). |
