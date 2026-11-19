---
name: "webrobot-agents"
description: "Build and run WebRobot Agent Studio agents and teams — agentic profiles (crews + orchestration), chat vs background surface, the profile draft channel, starting runs and reading results/logs, cron schedules, webhook triggers, and knowledge-base (RAG) access. Use when the user wants to create, edit, run, schedule or debug an AI agent or multi-agent team on WebRobot."
argument-hint: "[what the agent/team should do, or \"run/schedule profile N\"]"
user-invocable: true
---

# WebRobot Agent Studio (agentic profiles)

An **agentic profile** is a JSON spec (the `agent_definition`) stored in the org. It declares one or more
**crews** (agents) and an **orchestration** (how they hand work to each other). A run executes the profile as a
Ray job and stores the outputs of every node.

- REST base: `https://api.webrobot.eu/api/webrobot/api/agentic/...`. Auth: `X-API-Key: <key>` or `Authorization: Bearer <JWT>`.
- Plugin MCP tools = OpenAPI operationIds (names below). First call: `getCurrentUser` (org + role).
- UI: Cloud Dashboard › `/dashboard/agent-studio`.

## Roles

| Action | Roles |
|---|---|
| list/get profiles, executions, status, logs; profile draft | viewer, developer, admin |
| create/update/delete profiles, `start`, `cancel`, versions | developer, admin |
| schedules (`scheduleAgentic`, `deleteAgenticSchedule`), triggers (`createTrigger`, `listTriggers`, `deleteTrigger`) | admin |

## The spec

```jsonc
{
  "profile": "clinic-desk",                // code name
  "display_name": "Clinic desk",           // optional
  "chat_mode": "team",                     // only for multi-crew teams used as chat
  "crews": [
    {
      "id": "reception",                   // crew id = node id
      "engine": "agent_sdk",               // agent_sdk | crewai | autogen
      "model": "claude-sonnet-5-5",        // agent_sdk/autogen: model; crewai uses "llm_default" (LiteLLM id, e.g. "anthropic/claude-sonnet-5-5")
      "system_prompt": "...",
      "goal_template": "{goal}",           // optional; default "{goal}". Placeholders = the node's inputs
      "mcp_servers": [ { "name": "webrobot", "type": "http", "url": "https://mcp.webrobot.eu/mcp", "allow": "all" } ],
      "max_turns": 8, "max_budget_usd": 0.5,
      "permission_mode": "bypassPermissions",          // '' | default | acceptEdits | bypassPermissions
      "disallowed_tools": ["Bash", "Write", "Edit"],
      "variables": [ { "name": "CLINIC_NAME", "label": "Clinic name", "default": "Fisio Milano", "bind": "prompt" } ],  // bind: env | prompt | both; or "secret": true
      "local_tools": [ { "name": "...", "description": "...", "params": {}, "code": "..." } ]
    }
  ],
  "orchestration": { "type": "dag", "entry": "reception",
                     "nodes": [ { "id": "reception", "crew": "reception" } ],
                     "edges": [] }
}
```

Models offered by the studio: agent_sdk → `claude-sonnet-5-5` (default), `claude-opus-5-5`, `claude-haiku-5-5`, `claude-fable-5-1`;
autogen also `openai/gpt-oss-120b`, `openai/gpt-oss-20b`; crewai `anthropic/...`, `groq/openai/gpt-oss-120b`, or `""` (model served in the job, HPC).

**Orchestration**
- `dag`: `nodes` (one per crew, `id == crew`), `edges` `{from, to, pass?}`, `entry`. Nodes run in topological order.
  A node with no incoming edge receives the run's `inputs` (e.g. `{goal}`); a node with incoming edges receives its
  parents' **outputs** instead — `{"<parent crew id>": "<parent text>"}` — so its `goal_template` must use `{<parent id>}`,
  not `{goal}`. `pass: {"src_field": "dst_field"}` renames fields. No conditional routing: every edge fires.
  Always write `nodes` explicitly. If `orchestration` is missing, the server adds a linear DAG over the crews in order.
- `swarm`: `{type: "swarm", agents: [{crew, replicas}], lead?, seed_tasks?: [..], max_seconds}` — parallel agents on a shared task board.

**Surface** (profile field, not in the spec): `chat` (appears in the chat picker; a team needs `chat_mode: "team"`, agent_sdk crews only),
`background` (runs, schedules, triggers), `both`.

**Knowledge base.** The org's documents (console › Knowledge) live in the RAG index `org-<orgId>-knowledge`. At run time
every crew whose `mcp_servers` contains an entry **named `webrobot`** gets a note in its system prompt telling it to call
`ragQuery` with `index_name: "org-<orgId>-knowledge"`. Crews without that MCP entry cannot read the knowledge base.
(From the plugin's own MCP the same query is `ragQuery_1` with `question`, `index_name`, `top_k`.)

## Profile CRUD

| Action | Tool | Notes |
|---|---|---|
| List | `listProfiles` | `surface` filter (chat / background; a specific filter also returns `both`), `enabledOnly` |
| Get / rendered / its ETL agents | `getProfile`, `getRenderedProfile`, `listAgentsForProfile` | |
| Create | `createProfile` | **`name` + `spec` required**; `spec` is the JSON **as a string**; also `surface`, `version`, `description`, `enabled` |
| Update | `updateProfile` | full replace: send `id__path`, `name` and `spec` again. Locked marketplace clones refuse spec edits |
| Version history | `profileVersions` | previous states are kept when spec or version change |
| Delete | `deleteProfile` | `force` optional |
| MCP servers of the org | `listMcpServers`, `createMcpServer`, `updateMcpServer`, `callMcpTool` | |

### Draft channel (proposal shown in Agent Studio)

`agentProfileDraftPut` `{context: "agentic:agent-studio", profileSpec: "<agent_definition JSON string>", note}` writes a
**proposal**, not a profile. Agent Studio polls it every 4 s and shows Apply / Discard. Read with `agentProfileDraftGet`
(204 = none), clear with `agentProfileDraftDelete`. Scope: per org + per user + context (`agentic:agent-studio` is the default).
Use it when the user wants to review in the studio; use `createProfile` when they want it saved.

## Running

`start` → `POST /agentic/start`:

```json
{ "profileId": 123, "inputs": { "goal": "Patient asks: can I move my Thursday 10:00 knee session, and how much is a 5-session pack?" } }
```

Returns HTTP 202 with `executionId` (the run is async). What the code requires (`AgenticApiV10.startInternal`):

1. **Where it runs.** The shared in-cluster Ray cluster is only for the platform org, super_admin and demo orgs.
   - Managed (SaaS shared-infra) orgs: the server **adds** `useEphemeralVms: true, vmCount: 1` itself.
   - Any other org must send `"useEphemeralVms": true, "vmCount": 1` (or `hpcCredentialId` for EuroHPC; not both),
     otherwise **403** *"In-cluster agentic runs are reserved for the platform and demo orgs…"*.
   - Ephemeral VMs need a Hetzner token: `hetznerCredentialId`, or `cloudCredentials.hetznerApiKey`, or an enabled
     HETZNER cloud credential in the org (auto-resolved); else **400** *"useEphemeralVms requested but no Hetzner token resolved"*.
2. Profile must belong to the caller's org (else 404) and be `enabled` (else 400). System profiles
   (`webrobot-agent-designer`, `webrobot-app-builder`, …) may be started by any org and run in the caller's org.
3. Metered org with no credits → **402** `credits_exhausted`.

Follow the run:

| Tool | Returns |
|---|---|
| `status` (`eid`) | `persistedStatus` (PENDING → RUNNING → COMPLETED / FAILED), `result`, `errorMessage`, `tokens`, `rayJob` |
| `executionLogs_1` (`eid`, `tail`) | runner transcript (AGENTIC-TRACE lines: assistant text, tool calls/results) |
| `listExecutions` (`limit`) | the org's recent runs |
| `cancel` (`eid`) | stops the run |

`result` is a **JSON string**: `{"<node id>": {"<crew id>": "<text>"}}`, one entry per DAG node. Parse it and read the
terminal node(s). Poll `status` every 5–10 s; a run on a fresh VM takes minutes to start.

## Schedules (cron)

`scheduleAgentic` (admin) creates a Kubernetes CronJob that POSTs `startRequestJson` to the trigger webhook:

```json
{
  "name": "weekly-clinic-report",
  "cronExpr": "0 7 * * 1",
  "startRequestJson": "{\"profileId\":124,\"inputs\":{\"goal\":\"Weekly report for the week that just ended\"},\"useEphemeralVms\":true,\"vmCount\":1}",
  "enabled": true
}
```

- `cronExpr` is standard 5-field cron, **UTC**.
- `startRequestJson` is a StartRequest **as a string** and must carry a `profileId` the caller owns (else 404).
  Put the same placement fields you would give `start` (`useEphemeralVms` + `vmCount` for non-managed paid orgs).
- Same `name` again = update. A name owned by another org → 409.
- `enabled: false` **deletes** the CronJob (same as `deleteAgenticSchedule` `{name}`). There is no list tool for schedules: keep the names.

## Triggers (webhook per integration)

`createTrigger` (admin) `{label, engine: "agentic", profileId}` (or `engine: "etl"` + `projectId` + `jobId`) returns a
token `wrtrg_…` **once**. An external system fires the profile with:

```bash
curl -X POST https://api.webrobot.eu/api/webrobot/api/agentic/trigger \
  -H "Authorization: Bearer wrtrg_..." -H "Content-Type: application/json" \
  -d '{"inputs":{"goal":"New lead: Mario Rossi, knee pain"}}'
```

The token binds profile and org; the body may add `inputs` (and placement fields). Same in-cluster rule as `start`
(403 without `useEphemeralVms` + `vmCount` for non-managed paid orgs). `listTriggers`, `deleteTrigger` (revokes).

## Example 1 — 3-agent team: reception → bookings / prices-from-knowledge

Reception triages the request; both specialists receive reception's text as `{reception}`.

```json
{
  "profile": "clinic-desk",
  "display_name": "Clinic desk",
  "chat_mode": "team",
  "crews": [
    {
      "id": "reception", "engine": "agent_sdk", "model": "claude-haiku-5-5", "max_turns": 3, "max_budget_usd": 0.1,
      "permission_mode": "bypassPermissions", "disallowed_tools": ["Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch"],
      "system_prompt": "You are the reception of a physiotherapy clinic. Read the patient's message and write a short brief with two labelled parts: BOOKING: what they want to book, move or cancel (or 'none'); PRICES: which prices or packages they ask about (or 'none'). Keep the patient's own details (name, dates, times). No answer to the patient yet."
    },
    {
      "id": "bookings", "engine": "agent_sdk", "model": "claude-sonnet-5-5", "max_turns": 6, "max_budget_usd": 0.3,
      "permission_mode": "bypassPermissions", "disallowed_tools": ["Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch"],
      "goal_template": "Reception brief:\n{reception}\n\nHandle only the BOOKING part.",
      "system_prompt": "You handle bookings. If BOOKING is 'none', answer exactly 'No booking request.'. Otherwise propose the change in one or two sentences, listing the details still missing (date, time, therapist). Never confirm a slot you have not been given."
    },
    {
      "id": "prices", "engine": "agent_sdk", "model": "claude-sonnet-5-5", "max_turns": 6, "max_budget_usd": 0.3,
      "permission_mode": "bypassPermissions", "disallowed_tools": ["Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch"],
      "mcp_servers": [ { "name": "webrobot", "type": "http", "url": "https://mcp.webrobot.eu/mcp", "allow": "all" } ],
      "goal_template": "Reception brief:\n{reception}\n\nHandle only the PRICES part.",
      "system_prompt": "You answer price questions ONLY from the clinic's price list in the knowledge base: call ragQuery once with the question. Quote prices exactly as found, with the package name. If PRICES is 'none' answer 'No price question.'. If the knowledge base has no answer, say so; never invent a price."
    }
  ],
  "orchestration": {
    "type": "dag",
    "entry": "reception",
    "nodes": [ { "id": "reception", "crew": "reception" }, { "id": "bookings", "crew": "bookings" }, { "id": "prices", "crew": "prices" } ],
    "edges": [ { "from": "reception", "to": "bookings" }, { "from": "reception", "to": "prices" } ]
  }
}
```

Steps:
1. Upload the price list in console › Knowledge (index `org-<orgId>-knowledge`).
2. `createProfile` `{name: "clinic-desk", surface: "both", description: "...", spec: "<the JSON above, stringified>"}` → `id`.
3. `start` `{profileId: <id>, inputs: {goal: "..."}}` (+ `useEphemeralVms: true, vmCount: 1` if required) → `executionId`.
4. Poll `status`; `JSON.parse(result)` → `result.bookings.bookings`, `result.prices.prices` (and `result.reception.reception`).

## Example 2 — background weekly report + schedule

```json
{
  "profile": "clinic-weekly-report",
  "crews": [
    {
      "id": "reporter", "engine": "agent_sdk", "model": "claude-sonnet-5-5", "max_turns": 10, "max_budget_usd": 0.5,
      "permission_mode": "bypassPermissions", "disallowed_tools": ["Bash", "Read", "Write", "Edit"],
      "mcp_servers": [ { "name": "webrobot", "type": "http", "url": "https://mcp.webrobot.eu/mcp", "allow": "all" } ],
      "goal_template": "{goal}",
      "system_prompt": "You write the clinic's weekly report in Markdown: # Week of <date>, ## Highlights, ## Numbers (a small table), ## Next week. Use ragQuery on the knowledge base for policies and targets; use only figures you retrieved. Under 400 words."
    }
  ],
  "orchestration": { "type": "dag", "entry": "reporter", "nodes": [ { "id": "reporter", "crew": "reporter" } ], "edges": [] }
}
```

1. `createProfile` `{name: "clinic-weekly-report", surface: "background", spec: "<stringified>"}` → `id` (say 124).
2. Test once with `start` and read `JSON.parse(result).reporter.reporter`.
3. `scheduleAgentic` with the body shown in **Schedules** (Monday 07:00 UTC). Remove with `deleteAgenticSchedule` `{name: "weekly-clinic-report"}`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 403 *In-cluster agentic runs are reserved…* | add `useEphemeralVms: true, vmCount: 1` (or `hpcCredentialId`) |
| 400 *no Hetzner token resolved* | add an enabled HETZNER cloud credential, or pass `hetznerCredentialId` |
| 402 `credits_exhausted` | org wallet empty: buy credits |
| Downstream node got `{reception}` literally / empty | its `goal_template` must name the parent crew id; `{goal}` reaches only entry nodes |
| Team SUCCEEDED with no outputs | old specs without `nodes`; always write `orchestration.nodes` |
| Agent cannot see uploaded documents | the crew needs an `mcp_servers` entry named `webrobot` |
| Chat team ignores a crew | chat teams run agent_sdk crews only |
