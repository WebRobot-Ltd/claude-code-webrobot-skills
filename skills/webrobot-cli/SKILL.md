---
name: webrobot-cli
description: Use the WebRobot command-line tool to manage projects, jobs, agents, datasets, plugins and pipeline execution. Use when the user wants to run a command-line operation, install a plugin JAR, deploy a manifest, or batch-process resources via shell.
argument-hint: [command or task, e.g. "list jobs for project X" or "run pipeline yaml"]
user-invocable: true
allowed-tools: Bash(webrobot *) Read Write Edit
---

# WebRobot CLI

You drive the `webrobot` CLI on the user's behalf. The CLI is a Java JAR (Java 17+) at `~/.local/bin/webrobot` (or wherever the user installed it). Every command is documented via `webrobot --help` and `webrobot <group> --help`.

## When to use the CLI vs MCP tools vs `api_call`

| Need | Tool | Reason |
|------|------|--------|
| Conversational ad-hoc query | `mcp__webrobot__*` (curated tool) | Typed, returns structured JSON inline |
| Fallback for un-wrapped endpoint | `mcp__webrobot__api_call` | Generic, same auth as MCP |
| Batch / shell-driven flow | `webrobot <group> <subcommand>` | Pipes, glob, error-code-aware shell scripts |
| Pipeline manifest deploy + execute | `webrobot pipeline run -f x.yaml --follow` | Streams logs back to terminal, exit code = job result |
| Plugin JAR install on user machine | `webrobot cli plugins install <coords>` | The user's local plugin folder is `~/.webrobot/plugins/` |
| Anything requiring shell context (env vars, working dir) | CLI | MCP runs in a sandboxed Python process |

The CLI and the MCP server share the same `~/.webrobot/config.cfg` for credentials, so they're interchangeable from an auth perspective.

## Auth model — same config the MCP shares

```ini
# ~/.webrobot/config.cfg  (HOCON)
api_endpoint = "https://api.webrobot.eu"
apikey       = "wr_..."
# OR (mutually exclusive):
# jwt        = "eyJ..."
```

`webrobot config init` walks the user through this. To verify: `webrobot auth me` returns the resolved org_id + user_id when authenticated.

## Command groups (top-level)

Always run `webrobot <group> --help` to see the live subcommand surface. The groups present today (verify with `webrobot --help`):

| Group | Purpose |
|-------|---------|
| `project` | List / create / get / delete projects |
| `category` / `agent` | Manage agents (web automation orchestrators) |
| `job` | Create / list / execute / stop / log jobs |
| `task` / `execution` | Inspect spawned tasks and execution history |
| `dataset` | Upload, list, delete datasets |
| `pipeline` / `manifest` | Build, validate, apply, run pipeline YAMLs |
| `wizard` | Interactive scaffolds — `wizard agent`, `wizard pipeline` |
| `auth` | `auth me`, `auth login`, etc. |
| `billing` | Plan + subscription state |
| `cloud` / `cloud-credentials` | Cloud provider credentials, spark cluster info |
| `admin` | Super-admin operations (system logs, org bootstrap, cronjobs, plans, etl-versions, plugin-installations, plugins) |
| `ai-providers` | LLM provider configuration |
| `python-ext` | Manage Python Extensions registered in DB (Mode B/C) |
| `ean` | EAN sourcing vertical (legacy plugin) |
| `package` | Import/export project archives |
| `plugin` | **Factory** — scaffold partner plugin source trees (`plugin new`, `plugin add stage`, …) |
| `cli` | **Self-management** — install/list/remove CLI plugin JARs (`cli plugins …`) |
| `config` | `config init`, `config show`, `config set` |
| `browser` | Local browser automation status |

Two distinct things named "plugin":
- `webrobot plugin` = scaffolding new plugin SOURCE TREES (factory)
- `webrobot cli plugins` = installing/managing already-built plugin JARs into `~/.webrobot/plugins/`

## Common workflows

### Run a pipeline manifest end-to-end
```bash
webrobot pipeline run -f my-pipeline.yaml --follow
```
- `apply` (validate + register) + `execute` (run job) + stream logs.
- Exit code 0 on `COMPLETED`, non-zero on failure — script-friendly.

### Just validate without running
```bash
webrobot manifest validate -f my-pipeline.yaml
webrobot pipeline apply -f my-pipeline.yaml      # register without executing
```

### Install a partner CLI plugin
```bash
webrobot cli plugins install com.github.WebRobot-Ltd:webrobot-sentimental-plugin-cli:v0.2.1
webrobot cli plugins list
webrobot sentiment timeseries --bucket day      # newly-registered subcommand
```
Plugins from local builds: `webrobot cli plugins install ./target/my-plugin.jar`. Direct URL: `webrobot cli plugins install https://example.com/plugin.jar`.

### Generate a pipeline interactively
```bash
webrobot wizard pipeline    # asks goals → suggests stages → writes yaml
webrobot wizard agent       # scaffolds an agent
```

### Browse projects / jobs
```bash
webrobot project list
webrobot job list -p <projectId>
webrobot job execute -p <projectId> -j <jobId> --follow
webrobot job logs -p <projectId> -j <jobId> --tail 200
```

### Output format
Many commands accept `--output table|json|yaml`. Default is table. Use `json` when piping to `jq` in shell scripts.

### Dataset upload
```bash
webrobot dataset add -n "trigger-input"
webrobot dataset upload -d <datasetId> --file ./input.csv
```

### Manage Python Extensions registered in DB (Mode B)
```bash
webrobot python-ext list -a <agentId>
webrobot python-ext register -a <agentId> --name parse_price --code @./parse_price.py
webrobot python-ext delete -a <agentId> --name parse_price
```

## Catalog discovery — same endpoint as the MCP

```bash
# Public, no auth required
curl -fsSL https://api.webrobot.eu/webrobot/api/catalog/stages
curl -fsSL "https://api.webrobot.eu/webrobot/api/catalog/stages?plugin_id=sentimental-plugin"
```

The CLI's stage catalog uses this exact endpoint with a 1-hour disk cache at `~/.webrobot/stage-cache.json`. To force-refresh: delete the cache file or run any `pipeline apply` (writes a fresh fetch on each apply).

## Scripting patterns

The CLI is shell-friendly:

```bash
# Run a manifest, exit non-zero on failure
webrobot pipeline run -f pipeline.yaml --follow || { echo "Pipeline failed"; exit 1; }

# Loop over projects
for p in $(webrobot project list --output json | jq -r '.[].id'); do
  webrobot job list -p "$p" --output json
done

# Wait until a job is COMPLETED
until [ "$(webrobot job get -p $P -j $J --output json | jq -r .status)" = "COMPLETED" ]; do
  sleep 10
done
```

## Rules of thumb

- **Always verify auth first** when commands fail with 401: `webrobot auth me` (or call `auth_check` MCP tool).
- **Always run `--help`** before assuming a command's options. The skill is a map; `--help` is the truth.
- **Prefer `pipeline run --follow`** for one-shot batch jobs — it deploys + executes + streams in one call.
- **Use `--output json`** when the user asks for machine-readable output or you need to pipe to `jq`.
- **Don't shell out to curl** for catalog or platform endpoints when an MCP tool exists. Reach for `curl` only for things outside the wrapper, and even then prefer `mcp__webrobot__api_call`.

## On $ARGUMENTS

- If the user gave a specific command, run it.
- If the user gave a task ("list my projects", "deploy this yaml"), translate to the right CLI invocation and run it.
- If the user is unclear, run `webrobot --help` first to confirm the current command surface, then ask.
