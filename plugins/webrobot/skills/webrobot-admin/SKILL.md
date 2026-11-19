---
name: webrobot-admin
description: Manage WebRobot resources through the authenticated WebRobot MCP — projects, jobs, executions, ETL agents, categories, datasets, cloud credentials, API keys, users/invites/roles, organizations (super admin), billing and credits. Use when the user wants to list, create, update, delete, run, stop or inspect a WebRobot entity.
argument-hint: [entity and action, e.g. "list jobs of project X" or "stop execution Y"]
user-invocable: true
---

# WebRobot Administration

Operate the platform's core entities with the tools of the plugin's `webrobot` MCP server. That server is the full, authenticated MCP: every tool is a REST operation, named by its OpenAPI `operationId` (the names below). The caller's API key decides the organization and the role, so tools only see what that key can see.

## Access

- REST base: `https://api.webrobot.eu/api/webrobot/api/...` (the old `/webrobot/api/...` prefix without `/api` returns 404).
- Auth: header `X-API-Key: <key>` or `Authorization: Bearer <JWT>`.
- First call in a session: `getCurrentUser` — confirms user, organization and role.

Areas owned by other skills (use them instead of this one):

| Area | Skill |
|------|-------|
| Connecting the MCP/API key, which tool for which task | `webrobot-setup` |
| Uploading, querying, indexing datasets | `webrobot-datasets` |
| Writing pipeline YAML, stages, manifests, engines | `webrobot-pipeline` |
| Agent Studio profiles, teams, background runs, schedules, triggers | `webrobot-agents` |
| Vertical apps (App Studio / App Builder) | `webrobot-app-builder` |

## Entity model

```
Organization ── Users, Invites, API keys, Cloud credentials, Billing/credits
└── Projects (optional cron schedule, assignees, end customer)
    └── Jobs  (agentId + inputDatasetId + cloudCredentialIds)
        └── Executions / Tasks (status, logs, output dataset)
Categories
└── Agents  (ETL agents: carry the pipeline YAML a job runs)
Datasets    (inputs and job outputs)
```

## Entity → tools

### Projects
| Action | Tool |
|--------|------|
| List / get / by name | `getAllProjects`, `getProject`, `getProjectFromName` |
| Create / update / delete | `createProject`, `updateProject`, `deleteProject` |
| Schedule (cron, timezone, job) | `getProjectSchedule`, `setProjectSchedule` |
| Metrics | `getProjectMetrics` |
| Assignees | `listAssignees`, `assign`, `unassign` |
| End customer | `getEndCustomer`, `setEndCustomer` |
| Export / import | `start_export_project`, `start_import_project_with_options` |

### Jobs and executions
| Action | Tool |
|--------|------|
| List jobs (org / project) | `getAllJobs`, `getProjectJobs` |
| Get | `getJob_1` (project scoped), `getJobById` |
| Create (inside a project) | `addJobToProject` — `name`, `agentId`, `inputDatasetId`, `cloudCredentialIds` |
| Update / delete | `updateJob`, `updateJobById`, `removeJobFromProject`, `deleteJobById` |
| **Run** | `executeJob_1` (`projectId`, `jobId`; optional `engine`, e.g. `"scrapy"` for ingestion-only pipelines; default is Spark) → returns the execution id |
| Wait for completion | `waitForExecution` (`timeoutSec`, `logTail`) |
| Status | `getExecutionStatus_1`, or `executionStatus` (by execution id only) |
| Logs | `getExecutionLogs_1`, `executionLogs`, `getJobLogs` |
| Output rows | `executionOutput` (`executionId`, `limit`) |
| Stop | `stopJob`, `cancelExecution_2`, `cancelExecution_1` |
| Tasks (one per run) | `getAllTasks`, `list_13` (filter by `jobId`, `status`), `getTaskStatus`, `getTaskMetrics` |
| Job metrics | `getJobMetrics` |

Typical run: `getAllProjects` → `getProjectJobs` → `executeJob_1` → `waitForExecution` → `executionOutput`. On failure read `getExecutionLogs_1` before retrying.

### ETL agents and categories
| Action | Tool |
|--------|------|
| Categories | `getAllCategories`, `getCategory`, `getCategoryFromName`, `createCategory`, `updateCategory`, `deleteCategory` |
| List agents | `getAllAgentsAcrossCategories`, `getAllAgents` (by `categoryId`) |
| Get | `getAgent` (`categoryId`, `agentId`), `getAgentById`, `getAgentFromName` |
| Create / update / delete | `createAgent`, `updateAgent`, `deleteAgent` |
| Copy to other orgs | `copyAgent` |
| Pipeline YAML actually run | `getResolvedPipelineYaml` |
| Python extensions | `getAgentPythonExtensions`, `updateAgentPythonExtensions` |
| Linked agentic profile | `getAgenticProfileLink`, `setAgenticProfileLink` |

For authoring the pipeline itself, prefer `manifestValidate` / `manifestApply` (see `webrobot-pipeline`).

### Datasets (inventory only)
`getAllDatasets`, `getDataset`, `getDatasetFields`, `updateDataset`, `deleteDataset`. Upload, SQL queries and indexing → `webrobot-datasets`.

### Cloud credentials
| Action | Tool |
|--------|------|
| List / get / by provider | `getAllCloudCredentials`, `getCloudCredentialById`, `getCloudCredentialsByProvider` |
| **Create** | `createCloudCredential` |
| Update / delete | `updateCloudCredential`, `deleteCloudCredential` |
| Test | `testCloudCredential` |
| LLM providers available | `listProviders` |

`createCloudCredential` takes flat camelCase fields: `name`, `provider` (lowercase, e.g. `"hetzner"`, `"anthropic"`, `"openai"`), `apiKey`, optional `apiSecret`, `region`, `endpoint`, `model`, and provider-specific fields (`accessKeyId`, `secretAccessKey`, ...). Run `testCloudCredential` after creating one. Never echo secret values back to the user.

### API keys
`listApiKeys`, `createApiKey`, `deleteApiKey`. The key value is shown only once at creation — tell the user to store it.

### Users, invites, roles, MFA
| Action | Tool |
|--------|------|
| Users | `list_15`, `getOne_2`, `create_7`, `update_6`, `delete_5` |
| Roles | `roles` |
| Invites | `getUserInvites`, `getUserInvite`, `createUserInvite`, `updateUserInvite`, `resendUserInvite`, `deleteUserInvite` |
| MFA | `mfaStatus`, `mfaEnroll`, `mfaConfirmEnroll`; admin reset `resetMfa` |

MFA (TOTP) is mandatory for admin and super-admin roles.

### Organizations (super admin)
| Action | Tool |
|--------|------|
| List / get | `listOrganizations`, `getOrganization`, `getOrganizationUsers` |
| Create / update / delete | `createOrganization`, `updateOrganization`, `deleteOrganization` |
| Members | `assignUserToOrganization`, `unassignUserFromOrganization` |
| Branding (white label) | `updateOrganizationBranding`, `uploadLogo` |
| Delivery mode | `setTenantServiceMode`, `updateByocSoftPreferences` |
| Audit events | `list_1` |
| Export / import | `start_export_organization_with_options`, `start_import_organization_with_options` |

### Billing and credits (read)
| Action | Tool |
|--------|------|
| Credit balance / usage | `balance`, `usage` |
| Credit packs / cost estimate | `packs`, `estimate` |
| Plans and entitlements | `getBillingPlans`, `getEffectiveEntitlements`, `getTenantPricing` |

Buying credits (`checkout`) and running marketplace charges/payouts (`runCharges`, `runPayouts`) move real money: do them only on an explicit request, and run marketplace billing with `dryRun=true` first.

## Output

List resources as a table with ID, name and the key status field (execution status, enabled, created date). Always include the IDs the user needs for the next command.

## Safety

- Never delete projects, jobs, agents, datasets, credentials, users or organizations without explicit confirmation of the specific item.
- Never stop a running execution unless asked.
- For "clean up" requests, list what would be removed and ask first.
- Do not decrypt or print stored secrets.
