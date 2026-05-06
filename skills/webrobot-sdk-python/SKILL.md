---
name: webrobot-sdk-python
description: Consume the WebRobot REST API from a Python application using the public webrobot-sdk Python package. Use when the user wants to integrate WebRobot into a Python script, ETL job, or backend — NOT for writing Python Extensions inside the ETL engine (those use a different mechanism; see /webrobot-python-extension).
argument-hint: [task description, e.g. "list projects from a Python script"]
user-invocable: true
allowed-tools: Read Write Edit Bash(python *) Bash(python3 *) Bash(pip *) Bash(curl -fsSL https://api.webrobot.eu/webrobot/api/catalog/stages*)
---

# WebRobot Python SDK (client)

You help the user consume the WebRobot REST API as a CLIENT from Python. The SDK is auto-generated from the OpenAPI spec (138 endpoints) and packaged as the `webrobot` Python module.

**Not for in-pipeline transforms.** If the user wants to add custom row-level Python logic that runs INSIDE the ETL engine as a Spark UDF, use `/webrobot-python-extension`. That has a different runtime contract (function takes a row dict, returns a row dict, no SDK calls).

---

## Install

Until PyPI publication, install directly from GitHub:

```bash
pip install "git+https://github.com/WebRobot-Ltd/webrobot-sdk.git#subdirectory=python-sdk"
```

Once published to PyPI:

```bash
pip install webrobot-sdk
```

The import name is `webrobot` (not `webrobot_sdk`). Python 3.9+.

---

## Auth

Two modes. Pick one — never both.

```python
import os
import webrobot
from webrobot.rest import ApiException

# Option A — API key (recommended for service-to-service)
configuration = webrobot.Configuration(
    host="https://api.webrobot.eu",
    api_key={"X-API-Key": os.environ["WEBROBOT_API_KEY"]},
)

# Option B — JWT bearer (recommended when user-context is needed)
configuration = webrobot.Configuration(
    host="https://api.webrobot.eu",
    access_token=os.environ["WEBROBOT_JWT"],
)

api_client = webrobot.ApiClient(configuration)
api        = webrobot.DefaultApi(api_client)
```

For development environments, the same `~/.webrobot/config.cfg` used by the WebRobot CLI works as a credential source. The Python SDK doesn't auto-load it; parse it manually if you want one source of truth:

```python
import re
from pathlib import Path

def load_cli_credentials() -> dict:
    cfg = Path.home() / ".webrobot" / "config.cfg"
    if not cfg.exists():
        return {}
    text = cfg.read_text()
    out = {}
    for key in ("api_endpoint", "apikey", "jwt"):
        m = re.search(rf'{key}\s*=\s*"([^"]*)"', text)
        if m:
            out[key] = m.group(1)
    return out
```

---

## Quick start — typed DefaultApi

```python
import webrobot

config = webrobot.Configuration(
    host="https://api.webrobot.eu",
    api_key={"X-API-Key": "wr_..."},
)

with webrobot.ApiClient(config) as client:
    api = webrobot.DefaultApi(client)

    # List projects
    projects = api.get_all_projects()
    for p in projects:
        print(p.id, p.name)

    # Get one project
    project = api.get_project_by_id("42")

    # Create a project
    new_project = webrobot.JobProjectDto(
        name="price-comparison",
        description="...",
    )
    api.create_project(job_project_dto=new_project)

    # Execute a job
    api.execute_job("42", "7")

    # Stream logs (returns an iterator over log entries)
    logs = api.get_job_logs("42", "7", tail=200)
```

Method names are snake_case versions of the OpenAPI operationId (`getAllProjects` → `get_all_projects`, `executeJob` → `execute_job`). Browse the full surface in `python-sdk/docs/DefaultApi.md` or via Python introspection:

```python
import webrobot
print([m for m in dir(webrobot.DefaultApi) if not m.startswith("_")])
```

---

## Generic call — endpoint-agnostic escape hatch

For partner-vertical endpoints not yet in `DefaultApi`, or dynamic JSON responses, use raw HTTP via `requests` (or any HTTP library) with the same auth headers:

```python
import os, requests

API = "https://api.webrobot.eu"
HEADERS = {"X-API-Key": os.environ["WEBROBOT_API_KEY"]}

# Sentiment plugin partner-vertical endpoint
r = requests.get(f"{API}/webrobot/api/sentiment/timeseries",
                 headers=HEADERS,
                 params={"bucket": "day", "from": "2026-01-01"})
r.raise_for_status()
series = r.json()["series"]
```

The SDK doesn't currently expose a generic-call helper analogous to the Java `GenericClient`. If you need path templating or structured retries, wrap `requests` in a thin helper:

```python
def api_call(method: str, path: str, *, params: dict | None = None,
             body: dict | None = None) -> dict:
    """Generic WebRobot REST call. Path templating: {placeholders} are
    substituted from `params`, matching keys removed from the query string."""
    if params:
        for key in list(params):
            placeholder = "{" + key + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(params.pop(key)))
    r = requests.request(method, f"{API}{path}", headers=HEADERS,
                         params=params, json=body, timeout=30)
    r.raise_for_status()
    return r.json() if r.content else {}
```

---

## Public catalog endpoint — no auth required

```python
import requests

# Discover available pipeline stages (zero auth — public read-only)
r = requests.get("https://api.webrobot.eu/webrobot/api/catalog/stages",
                 params={"plugin_type": "etl"})
stages = r.json()["data"]
for s in stages:
    print(s["stage_name"], "—", s["description"])
```

Useful for building tools that programmatically generate pipeline YAML.

---

## Error handling

```python
from webrobot.rest import ApiException

try:
    api.get_project_by_id("9999")
except ApiException as e:
    print(e.status)       # 404
    print(e.body)         # raw response JSON
    print(e.headers)      # {'X-Request-Id': '...', ...}
    print(e.reason)       # "Not Found"
```

For `requests`-based generic calls, use `requests.HTTPError`:

```python
try:
    r = requests.get(...)
    r.raise_for_status()
except requests.HTTPError as e:
    print(e.response.status_code, e.response.text[:400])
```

---

## When to use the Python SDK vs alternatives

| Need | Tool |
|------|------|
| Python script, FastAPI/Django backend, data-science notebook | **Python SDK** (this) |
| Shell script / CI pipeline | `webrobot` CLI |
| Conversational queries from Claude Code / Cursor | MCP tools (`mcp__webrobot__*`) |
| Custom row-level transform inside an ETL pipeline | `/webrobot-python-extension` (different runtime) |

---

## Common patterns

### Wait for a job to complete

```python
import time

api.execute_job(project_id, job_id)
while True:
    job = api.get_job(project_id, job_id)
    if job.status in {"COMPLETED", "FAILED", "CANCELLED"}:
        print(f"Final: {job.status}")
        break
    time.sleep(10)
```

### Iterate paginated lists

```python
projects = api.get_all_projects()
# Most list endpoints return all rows in one response (Strapi-style); for
# very large datasets use the OpenAPI pagination params if documented:
# api.get_all_projects(page=1, page_size=100)
```

### Batch create jobs from CSV

```python
import csv

with open("jobs.csv") as f:
    for row in csv.DictReader(f):
        dto = webrobot.JobDto(name=row["name"], description=row["description"])
        api.add_job_to_project(row["project_id"], job_dto=dto)
```

### Trigger a pipeline manifest run

```python
yaml_content = open("pipeline.yaml").read()
result = api_call("POST", "/webrobot/api/pipelines/run", body={
    "yaml":   yaml_content,
    "follow": True,
})
print("Execution ID:", result["executionId"])
```

---

## Rules of thumb

- **Use the typed `DefaultApi`** when the endpoint has a dedicated method — type-safe DTOs, IDE autocomplete.
- **Use raw `requests`** (or the `api_call` helper) for partner-vertical endpoints, when the response has dynamic shape, or you need path templating.
- **Never embed credentials in source.** Use env vars or a config file outside the repo.
- **Catch `webrobot.rest.ApiException`** for typed calls, `requests.HTTPError` for generic calls — both expose status + body.
- **The catalog endpoint is public.** Don't add auth headers to `/webrobot/api/catalog/stages` — wasteful, response is identical.

## On $ARGUMENTS

- If the user passed a task: scaffold the Python code that does it, with imports + auth setup.
- If the user passed a file path: read it, propose the SDK call to integrate.
- If the user is unclear: ask whether they need typed DTOs (`DefaultApi`) or a quick generic call (`requests`).
