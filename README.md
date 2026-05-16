# WebRobot — Claude Code plugin

Claude Code plugin for the [WebRobot ETL](https://webrobot.eu) platform.
Bundles:

- **10 skills** — invokable as slash commands inside Claude Code — that
  document pipelines, the CLI, the public SDKs, plugin development,
  and the platform overview.
- A **Model Context Protocol (MCP) server** that exposes the WebRobot
  REST API as a set of typed tools Claude can call directly (list /
  create / execute / inspect projects, jobs, pipelines, agents,
  datasets, cloud credentials, LLM providers, plus manifest
  validate/apply and ETL stage discovery).

The plugin lives at
[github.com/WebRobot-Ltd/webrobot-claude-plugin](https://github.com/WebRobot-Ltd/webrobot-claude-plugin)
and ships as `.claude-plugin/plugin.json` + `skills/` + `mcp-server/`.

---

## Install

In Claude Code, add this repository as a plugin source and install the
`webrobot` plugin:

```
/plugin marketplace add https://github.com/WebRobot-Ltd/webrobot-claude-plugin
/plugin install webrobot
```

Claude Code will pick up the skills (under `/`) and start the MCP server
on demand using the `mcpServers.webrobot` entry in `plugin.json`. The
server is a single Python process — `mcp-server/server.py` — with only
one runtime dependency (`mcp>=1.0.0`).

If your environment doesn't have `python3` and `pip install mcp`
available, install once:

```
pip install -r mcp-server/requirements.txt
```

---

## Configure credentials

The MCP server reads credentials from, in priority order:

1. Environment variables: `WEBROBOT_API_ENDPOINT`, `WEBROBOT_API_KEY`,
   `WEBROBOT_JWT`.
2. Plugin-scoped JSON config: `~/.claude/plugins/webrobot/config.json`
   — preferred when you don't have the CLI installed.
3. CLI HOCON configs, looked up in this order:
   - `~/.config/webrobot/config.cfg`
   - `~/.webrobot/config.cfg`
   - `./config.cfg` (current working directory)

Minimal plugin config:

```json
{
  "api_endpoint": "https://api.webrobot.eu",
  "apikey":       "your-api-key:your-secret"
}
```

`apikey` is sent as `Authorization: ApiKey …` and `X-API-Key`. A `jwt`
field is also honored and overrides the API key when present.

Default endpoint when nothing is configured: `https://api.webrobot.eu`.

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

The server (`mcp-server/server.py`) exposes the WebRobot REST API as
~30 MCP tools, grouped by domain:

- **Auth**: `auth_me`, `auth_check`, `auth_set`.
- **Projects**: `list_projects`, `get_project`, `create_project`, `delete_project`.
- **Jobs**: `list_jobs`, `get_job`, `create_job`, `delete_job`, `execute_job`, `stop_job`.
- **Executions**: `list_executions`, `get_execution_logs`.
- **Stages (ETL catalog)**: `list_stages`, `describe_stage`, `search_stages`, `suggest_pipeline_stages`.
- **Manifests**: `validate_manifest`, `apply_manifest`, `run_pipeline`.
- **Categories + agents**: `list_categories`, `list_agents`, `get_agent`, `create_agent`, `get_agent_code`.
- **Datasets**: `list_datasets`, `delete_dataset`.
- **Cloud credentials**: `list_cloud_credentials`.
- **LLM**: `list_llm_providers`, `llm_infer`.
- **Escape hatch**: `api_call` — call any WebRobot endpoint by path/method when no typed tool fits.

All tools return JSON strings. The MCP server has no business logic of
its own; it's a thin, typed wrapper over the REST API + a config
loader.

---

## Repository layout

```
.claude-plugin/plugin.json     Plugin manifest read by Claude Code
.mcp.json                       Stand-alone MCP server entry (for local dev)
skills/
  webrobot-overview/            Platform overview skill
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
  server.py                     FastMCP server, ~30 tools
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
