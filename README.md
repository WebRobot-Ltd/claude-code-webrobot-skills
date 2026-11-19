<div align="center">

# 🤖 WebRobot — Claude Code plugin &amp; MCP server

### Turn Claude Code into a data engineer — scrape the web, build Spark ETL pipelines, and run them, all by conversation.

[![MCP](https://img.shields.io/badge/MCP-server-7c4fb5)](https://mcp-full.webrobot.eu/mcp)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-5b54ec)](https://github.com/WebRobot-Ltd/claude-code-webrobot-skills)
[![Live demo](https://img.shields.io/badge/%E2%96%B6-live%20demo-00bcd4)](https://portal.webrobot.eu/chat.html)
[![Docs](https://img.shields.io/badge/docs-webrobot.eu-333)](https://docs.webrobot.eu)

<!-- DEMO GIF — drop docs/media/demo.gif here once recorded. Shot list: docs/media/README.md -->
<!-- ![WebRobot in Claude Code](docs/media/demo.gif) -->
**🎬 Demo GIF coming soon** — meanwhile try the **[▶ live demo](https://portal.webrobot.eu/chat.html)**.

</div>

> **WebRobot is "ETL for AI Agents"** — a **Spark-native**, **EU-sovereign (BYOC)**
> data platform that AI agents operate end to end: *from a URL to an insight in a
> conversation.* This plugin is the front door from Claude Code.

It bundles:

- **14 skills** — invokable as slash commands inside Claude Code — covering setup,
  datasets and SQL, pipelines, Agent Studio agents and teams, background runs and
  schedules, vertical apps, admin, the CLI, the public SDKs and plugin development.
- A hosted **Model Context Protocol (MCP) server** that exposes the WebRobot
  REST API as typed tools Claude can call directly (list / create / execute /
  inspect datasets, pipelines, jobs, agents and teams, schedules, knowledge, analytics
  reports and admin entities).

Repo: [github.com/WebRobot-Ltd/claude-code-webrobot-skills](https://github.com/WebRobot-Ltd/claude-code-webrobot-skills)
— ships as `.claude-plugin/plugin.json` + `skills/` + `mcp-server/`.

> ⭐ **If this is useful, star the repo** — it helps other data &amp; AI engineers find it.

---

## Install

In Claude Code, add this repository as a plugin source and install the
`webrobot` plugin:

```
/plugin marketplace add WebRobot-Ltd/claude-code-webrobot-skills
/plugin install webrobot@webrobot
```

From a terminal the same is `claude plugin marketplace add WebRobot-Ltd/claude-code-webrobot-skills`
then `claude plugin install webrobot@webrobot`.

Claude Code picks up the skills and connects the `webrobot` MCP server from
`plugin.json`: the **hosted, authenticated** endpoint
`https://mcp-full.webrobot.eu/mcp`. Nothing to install locally.

## Configure credentials

The MCP server authenticates every call with your **WebRobot API key**, sent as
the `X-API-Key` header. The plugin reads it from the environment, so export it
**before** starting Claude Code:

```bash
export WEBROBOT_API_KEY="<key_id>:<secret>"   # Console → Developer → API → Request New API Key
claude
```

The value is the key id and the secret joined by a colon, as the console shows them.

Everything the key does is scoped to the key's organization and role. Check the
connection by asking Claude to run the `getCurrentUser` tool (start with the
`webrobot-setup` skill).

> The bundled `mcp-server/` (a local Python MCP that wraps the REST API) is kept
> for offline/self-hosted use. To run it instead, set `mcpServers.webrobot` to
> `{ "command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/mcp-server/server.py"] }`,
> `pip install -r mcp-server/requirements.txt`, and set `WEBROBOT_API_ENDPOINT`
> (`https://api.webrobot.eu`) and `WEBROBOT_API_KEY`.

---

## Skills

| Slash command | What it covers |
| --- | --- |
| `/webrobot-overview` | Platform overview: vision, architecture, pricing tiers, BYOC model, GTM phases, roadmap, competitive positioning. The "what is this" entry point. |
| `/webrobot-pipeline` | Build, validate, deploy pipeline manifests. Stage catalog, positional `args`, the LLM-driven e-commerce flow (`auto_internal_search` → `intelligentExplore` / `intelligentJoin` → `iextract`), and the agentic `browser_use` stage. |
| `/webrobot-cli` | Use the `webrobot` CLI to manage projects, jobs, agents, datasets, plugins, pipeline execution. |
| `/webrobot-admin` | Direct admin operations against the WebRobot API: projects, jobs, executions, agents, datasets, cloud credentials, LLM providers. |
| `/webrobot-plugin-dev` | Build WebRobot plugins — custom ETL stages (Scala SDK) and REST API endpoints (Java JAX-RS). |
| `/webrobot-python-extension` | Write, register, and embed Python Extension functions for pipelines without writing Scala. |
| `/webrobot-frontend-plugin-dev` | Build a partner-authored UI plugin for the WebRobot dashboard (Next.js). Plugins ship as a ZIP of ESM bundles, upload to MinIO, hot-load at runtime. |
| `/webrobot-sdk-java` | Consume the WebRobot REST API from JVM apps using the public `webrobot-sdk` JAR. |
| `/webrobot-sdk-nodejs` | Consume the WebRobot REST API from Node.js / TypeScript using the public npm package. |
| `/webrobot-sdk-python` | Consume the WebRobot REST API from Python using the public package. |

Each skill is a self-contained markdown file under `skills/<name>/SKILL.md`
plus optional companion files (examples, scripts) in the same directory.

---

## MCP server tools

The hosted server (`https://mcp-full.webrobot.eu/mcp`) exposes the WebRobot REST API
as **~500 typed tools**, one per API operation (tool name = the OpenAPI operationId).
The ones you use most, by area:

- **Account**: `getCurrentUser`, `getHealth`, `createApiKey`, `listApiKeys`.
- **Datasets**: `getAllDatasets`, `getDataset`, `getDatasetFields`, `uploadCsv`,
  `uploadDatasetJson`, `executeQuery` (SQL with the `[datasetId]` shortcut),
  `queryDatasetByTask` (SQL with `{table}`).
- **Pipelines**: `listStages`, `getStage`, `suggestStages_1`, `manifestValidate`,
  `manifestApply`, `saveGeneratedPipeline`, `pipelineDraftPut` (Pipeline Designer draft slot).
- **Projects & jobs**: `getAllProjects`, `createProject`, `getProjectJobs`, `executeJob_1`
  (Spark by default; `engine` = scrapy, hybrid, temporal, slurm), `executionStatus`,
  `executionLogs`, `executionOutput`.
- **Agents (Agent Studio)**: `listProfiles`, `getProfile`, `createProfile`, `updateProfile`,
  `agentProfileDraftPut`, `start` (run as a Ray job), `listExecutions`,
  `scheduleAgentic`, `deleteAgenticSchedule`.
- **Knowledge & analytics**: `ragQuery_1`, `ragStatus_1`, `createAnalyticsReport`,
  `getAnalyticsReport`, `listAnalyticsReports`.
- **Admin**: `createCloudCredential`, `getAllCloudCredentials`, `getAllAgents`, `createAgent`, …

Vertical apps (App Builder) and AI Agent Deploy (dedicated chat servers) are used
through the REST API (`https://api.webrobot.eu/api/webrobot/api/...`), as the
`webrobot-app-builder` skill shows.

---

## Repository layout

```
.claude-plugin/plugin.json     Plugin manifest read by Claude Code
.mcp.json                       Stand-alone MCP server entry (for local dev)
skills/
  webrobot-setup/               Connect + task → tool map (start here)
  webrobot-overview/            Platform overview skill
  webrobot-datasets/            Datasets, upload, SQL
  webrobot-agents/              Agent Studio: agents, teams, background runs, schedules
  webrobot-app-builder/         Vertical apps: manifest, publish
  webrobot-pipeline/            Pipeline authoring skill
  webrobot-cli/                 CLI usage skill
  webrobot-admin/               Admin operations skill
  webrobot-plugin-dev/          ETL stage + REST plugin dev skill
  webrobot-python-extension/    Python Extensions skill
  webrobot-frontend-plugin-dev/ Dashboard UI plugin skill
  webrobot-sdk-java/            Java/JVM SDK skill
  webrobot-sdk-nodejs/          Node SDK skill
  webrobot-sdk-python/          Python SDK skill
mcp-server/
  server.py                     Local FastMCP server (offline/self-hosted alternative)
  requirements.txt              Single dep: mcp>=1.0.0
```

---

## Development

The plugin has no build step. Local iteration:

1. Edit a `skills/<name>/SKILL.md` or `mcp-server/server.py`.
2. In Claude Code, reload the plugin (`/plugin reload webrobot`).
3. Try the slash command or call the MCP tool.

The MCP server can also be run stand-alone for debugging:

```
python3 mcp-server/server.py
```

(Stdio MCP transport; pipe a `tools/list` request to confirm the tools
load and credentials resolve.)

To add a new skill, create `skills/<new-name>/SKILL.md` with the
standard frontmatter:

```yaml
---
name: <slug>
description: <one-line description of when this skill applies>
---
```

Pull requests welcome — see the [WebRobot organization](https://github.com/WebRobot-Ltd)
for related repositories (ETL engine, CLI, SDKs, dashboard, portal).

---

## License

MIT. See `LICENSE` (or `.claude-plugin/plugin.json` `license` field).

Maintained by [WebRobot Ltd](https://webrobot.eu) — ceo@webrobot.eu.
