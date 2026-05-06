#!/usr/bin/env python3
"""WebRobot MCP Server — exposes all WebRobot API operations as Claude Code tools.

Config is read in this priority order:
  1. Environment variables: WEBROBOT_API_ENDPOINT, WEBROBOT_API_KEY, WEBROBOT_JWT
  2. ~/.config/webrobot/config.cfg   (HOCON-style)
  3. ~/.webrobot/config.cfg
  4. ./config.cfg  (webrobot-cli directory)
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode

from mcp.server.fastmcp import FastMCP

# ── Config loading ─────────────────────────────────────────────────────────────

def _parse_hocon_credentials(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("api_endpoint", "apikey", "jwt", "bearer", "token"):
        m = re.search(rf'{key}\s*=\s*"([^"]*)"', text)
        if m:
            result[key] = m.group(1)
    return result


def _parse_json_credentials(text: str) -> dict[str, str]:
    """Plugin-style config: {"api_endpoint": "...", "apikey": "...", "jwt": "..."}"""
    try:
        data = json.loads(text)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for k in ("api_endpoint", "apikey", "jwt", "bearer", "token"):
        v = data.get(k)
        if isinstance(v, str) and v:
            out[k] = v
    return out


# Where the plugin stores its own credentials, scoped to this Claude Code plugin.
# Highest priority after env vars, so the plugin works standalone without the CLI installed.
PLUGIN_CONFIG_DIR  = Path.home() / ".claude" / "plugins" / "webrobot"
PLUGIN_CONFIG_FILE = PLUGIN_CONFIG_DIR / "config.json"


def _load_config() -> tuple[str, str, str]:
    """Returns (base_url, auth_header, source_label).

    Priority order:
      1. Environment vars (WEBROBOT_API_ENDPOINT, WEBROBOT_API_KEY, WEBROBOT_JWT)
      2. Plugin config:    ~/.claude/plugins/webrobot/config.json   (JSON, plugin-scoped)
      3. CLI configs:      ~/.config/webrobot/config.cfg            (HOCON)
                           ~/.webrobot/config.cfg                   (HOCON)
                           ./config.cfg                             (HOCON, working dir)

    The plugin-scoped JSON config is preferred over CLI configs so that users
    who haven't installed the CLI can still authenticate the MCP server by
    dropping a config.json under ~/.claude/plugins/webrobot/.
    """
    endpoint = os.environ.get("WEBROBOT_API_ENDPOINT", "")
    api_key  = os.environ.get("WEBROBOT_API_KEY", "")
    jwt      = os.environ.get("WEBROBOT_JWT", "")
    source   = "env" if (endpoint or api_key or jwt) else ""

    def _absorb(creds: dict[str, str], label: str) -> None:
        nonlocal endpoint, api_key, jwt, source
        endpoint = endpoint or creds.get("api_endpoint", "")
        api_key  = api_key  or creds.get("apikey", "")
        jwt      = jwt      or creds.get("jwt") or creds.get("bearer") or creds.get("token", "")
        if not source and (endpoint or api_key or jwt):
            source = label

    # Step 2: plugin-scoped JSON config
    if not (endpoint and (api_key or jwt)) and PLUGIN_CONFIG_FILE.exists():
        _absorb(_parse_json_credentials(PLUGIN_CONFIG_FILE.read_text()), str(PLUGIN_CONFIG_FILE))

    # Step 3: CLI HOCON configs
    if not (endpoint and (api_key or jwt)):
        for candidate in [
            Path.home() / ".config" / "webrobot" / "config.cfg",
            Path.home() / ".webrobot" / "config.cfg",
            Path("config.cfg"),
        ]:
            if candidate.exists():
                _absorb(_parse_hocon_credentials(candidate.read_text()), str(candidate))
                if api_key or jwt:
                    break

    base_url = (endpoint or "https://api.webrobot.eu").rstrip("/")
    if jwt:
        auth = f"Bearer {jwt}"
    elif api_key:
        auth = f"ApiKey {api_key}"
    else:
        auth = ""
    return base_url, auth, source or "none"


BASE_URL, AUTH_HEADER, AUTH_SOURCE = _load_config()


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
    if AUTH_HEADER:
        h["Authorization"] = AUTH_HEADER
        if AUTH_HEADER.startswith("ApiKey "):
            h["X-API-Key"] = AUTH_HEADER[len("ApiKey "):]
    return h


def _call(method: str, path: str, body: Any = None, params: dict[str, Any] | None = None) -> Any:
    url = BASE_URL + path
    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            url += "?" + urlencode(filtered)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:400]
        raise RuntimeError(f"HTTP {e.code}: {msg}") from e


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    return _call("GET", path, params=params)

def _post(path: str, body: Any = None) -> Any:
    return _call("POST", path, body=body)

def _put(path: str, body: Any = None) -> Any:
    return _call("PUT", path, body=body)

def _delete(path: str) -> Any:
    return _call("DELETE", path)


def _fmt(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


# ── MCP server ─────────────────────────────────────────────────────────────────

mcp = FastMCP("webrobot")


# ── Auth ───────────────────────────────────────────────────────────────────────

@mcp.tool()
def auth_me() -> str:
    """Return current authenticated user information."""
    return _fmt(_get("/webrobot/api/auth/me"))


# ── Projects ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_projects() -> str:
    """List all WebRobot projects."""
    return _fmt(_get("/webrobot/api/projects"))


@mcp.tool()
def get_project(project_id: str) -> str:
    """Get details for a specific project by ID."""
    return _fmt(_get(f"/webrobot/api/projects/id/{quote(project_id)}"))


@mcp.tool()
def create_project(name: str, description: str = "", organization_id: Optional[str] = None) -> str:
    """Create a new WebRobot project."""
    body: dict[str, Any] = {"name": name, "description": description}
    if organization_id:
        body["organizationId"] = organization_id
    return _fmt(_post("/webrobot/api/projects", body))


@mcp.tool()
def delete_project(project_id: str) -> str:
    """Delete a project by ID."""
    return _fmt(_delete(f"/webrobot/api/projects/id/{quote(project_id)}"))


# ── Jobs ───────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_jobs(project_id: str) -> str:
    """List all jobs in a project."""
    return _fmt(_get(f"/webrobot/api/projects/id/{quote(project_id)}/jobs"))


@mcp.tool()
def get_job(project_id: str, job_id: str) -> str:
    """Get details for a specific job."""
    return _fmt(_get(f"/webrobot/api/projects/id/{quote(project_id)}/jobs/{quote(job_id)}"))


@mcp.tool()
def create_job(project_id: str, name: str, description: str = "") -> str:
    """Create a new job in a project."""
    body = {"name": name, "description": description}
    return _fmt(_post(f"/webrobot/api/projects/id/{quote(project_id)}/jobs", body))


@mcp.tool()
def delete_job(project_id: str, job_id: str) -> str:
    """Delete a job."""
    return _fmt(_delete(f"/webrobot/api/projects/id/{quote(project_id)}/jobs/{quote(job_id)}"))


@mcp.tool()
def execute_job(project_id: str, job_id: str) -> str:
    """Trigger an execution of a job. Returns execution details including execution_id."""
    return _fmt(_post(f"/webrobot/api/projects/id/{quote(project_id)}/jobs/{quote(job_id)}/executions"))


@mcp.tool()
def stop_job(project_id: str, job_id: str, execution_id: str) -> str:
    """Stop a running job execution."""
    return _fmt(_post(
        f"/webrobot/api/projects/id/{quote(project_id)}/jobs/{quote(job_id)}/executions/{quote(execution_id)}/stop"
    ))


# ── Executions ─────────────────────────────────────────────────────────────────

@mcp.tool()
def list_executions(project_id: str, job_id: str) -> str:
    """List all executions for a job, most recent first."""
    return _fmt(_get(
        f"/webrobot/api/projects/id/{quote(project_id)}/jobs/{quote(job_id)}/executions"
    ))


@mcp.tool()
def get_execution_logs(project_id: str, job_id: str, execution_id: str) -> str:
    """Get the logs/output for a specific job execution."""
    return _fmt(_get(
        f"/webrobot/api/projects/id/{quote(project_id)}/jobs/{quote(job_id)}/executions/{quote(execution_id)}/logs"
    ))


# ── Stage catalog ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_stages(extension_type: Optional[str] = None) -> str:
    """List the stage catalog.

    extension_type: filter by 'stage' (ETL), 'action' (browser), or 'resolver' (attribute extractor).
    Leave empty to get all types.
    """
    catalog = _get("/webrobot/api/manifest/stages")
    if extension_type and isinstance(catalog, list):
        catalog = [s for s in catalog if s.get("extensionType") == extension_type]
    return _fmt(catalog)


@mcp.tool()
def describe_stage(stage_id: str) -> str:
    """Get full details and argument definitions for a stage by its ID."""
    catalog = _get("/webrobot/api/manifest/stages")
    if isinstance(catalog, list):
        for s in catalog:
            if s.get("id") == stage_id or s.get("name") == stage_id:
                return _fmt(s)
    return json.dumps({"error": f"Stage '{stage_id}' not found"})


@mcp.tool()
def search_stages(query: str) -> str:
    """Search stages by keyword in name, description, or category."""
    catalog = _get("/webrobot/api/manifest/stages")
    q = query.lower()
    if isinstance(catalog, list):
        matches = [
            s for s in catalog
            if q in str(s.get("name", "")).lower()
            or q in str(s.get("description", "")).lower()
            or q in str(s.get("category", "")).lower()
            or q in str(s.get("label", "")).lower()
        ]
        return _fmt(matches)
    return _fmt(catalog)


# ── Manifests / pipelines ──────────────────────────────────────────────────────

@mcp.tool()
def validate_manifest(yaml_path: str) -> str:
    """Validate a pipeline YAML manifest file without executing it.

    yaml_path: absolute path to the .yaml manifest file.
    """
    path = Path(yaml_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {yaml_path}"})
    content = path.read_text()
    try:
        result = _post("/webrobot/api/manifest/validate", {"yaml": content})
        return _fmt(result)
    except RuntimeError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def apply_manifest(yaml_path: str, project_id: Optional[str] = None, job_id: Optional[str] = None) -> str:
    """Apply (deploy) a pipeline YAML manifest to a project/job.

    yaml_path: absolute path to the .yaml manifest file.
    project_id / job_id: if omitted, the manifest's own metadata is used.
    """
    path = Path(yaml_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {yaml_path}"})
    content = path.read_text()
    body: dict[str, Any] = {"yaml": content}
    if project_id:
        body["projectId"] = project_id
    if job_id:
        body["jobId"] = job_id
    return _fmt(_post("/webrobot/api/manifest/apply", body))


@mcp.tool()
def run_pipeline(yaml_path: str, project_id: Optional[str] = None, job_id: Optional[str] = None) -> str:
    """Apply a manifest and immediately trigger its execution. Returns execution details."""
    path = Path(yaml_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {yaml_path}"})
    content = path.read_text()
    body: dict[str, Any] = {"yaml": content}
    if project_id:
        body["projectId"] = project_id
    if job_id:
        body["jobId"] = job_id
    return _fmt(_post("/webrobot/api/manifest/run", body))


# ── Categories ─────────────────────────────────────────────────────────────────

@mcp.tool()
def list_categories() -> str:
    """List all agent categories."""
    return _fmt(_get("/webrobot/api/categories"))


# ── Agents ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_agents(category_id: str) -> str:
    """List all agents in a category."""
    return _fmt(_get(f"/webrobot/api/agents/{quote(category_id)}"))


@mcp.tool()
def get_agent(category_id: str, agent_id: str) -> str:
    """Get details of a specific agent."""
    return _fmt(_get(f"/webrobot/api/agents/{quote(category_id)}/{quote(agent_id)}"))


@mcp.tool()
def create_agent(category_id: str, name: str, description: str = "", config: Optional[dict] = None) -> str:
    """Create a new agent in a category."""
    body: dict[str, Any] = {"name": name, "description": description}
    if config:
        body["config"] = config
    return _fmt(_post(f"/webrobot/api/agents/{quote(category_id)}", body))


@mcp.tool()
def get_agent_code(category_id: str, agent_id: str) -> str:
    """Get the Python extension code for an agent."""
    return _fmt(_get(f"/webrobot/api/agents/{quote(category_id)}/{quote(agent_id)}/code"))


# ── Datasets ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_datasets(project_id: Optional[str] = None) -> str:
    """List datasets, optionally filtered by project."""
    params = {"projectId": project_id} if project_id else None
    return _fmt(_get("/webrobot/api/datasets", params=params))


@mcp.tool()
def delete_dataset(dataset_id: str) -> str:
    """Delete a dataset by ID."""
    return _fmt(_delete(f"/webrobot/api/datasets/{quote(dataset_id)}"))


# ── Cloud credentials ──────────────────────────────────────────────────────────

@mcp.tool()
def list_cloud_credentials() -> str:
    """List all cloud credentials (API keys, storage, LLM providers, etc.)."""
    return _fmt(_get("/webrobot/api/cloud-credentials"))


# ── LLM inference ──────────────────────────────────────────────────────────────

@mcp.tool()
def llm_infer(
    prompt: str,
    system_prompt: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Call the WebRobot LLM inference endpoint.

    provider: groq | openai | anthropic | togetherai (auto-detected if omitted).
    model: specific model name (uses provider default if omitted).
    Returns the LLM response text.
    """
    body: dict[str, Any] = {"prompt": prompt}
    if system_prompt:
        body["systemPrompt"] = system_prompt
    if provider:
        body["provider"] = provider
    if model:
        body["model"] = model
    result = _post("/webrobot/api/llm/infer", body)
    if isinstance(result, dict):
        return result.get("result", _fmt(result))
    return str(result)


@mcp.tool()
def list_llm_providers() -> str:
    """List available LLM providers that have credentials configured in WebRobot."""
    return _fmt(_get("/webrobot/api/llm/providers"))


# ── Pipeline YAML builder helper ───────────────────────────────────────────────

@mcp.tool()
def suggest_pipeline_stages(description: str) -> str:
    """Given a natural language description of a pipeline goal, suggest suitable stages from the catalog.

    Uses the WebRobot LLM endpoint to analyze the description and match it against the stage catalog.
    Returns a JSON array of suggested stage IDs with explanations.
    """
    catalog = _get("/webrobot/api/manifest/stages")
    if not isinstance(catalog, list):
        return json.dumps({"error": "Could not load stage catalog"})

    summary_lines = []
    for s in catalog:
        ext = s.get("extensionType", "stage")
        summary_lines.append(f"- {s.get('id','?')} [{ext}]: {s.get('description') or s.get('label','')}")
    catalog_summary = "\n".join(summary_lines[:120])

    system = (
        "You are an expert in WebRobot ETL pipeline configuration. "
        "Given a user description and a stage catalog, return ONLY a JSON array of objects: "
        '[{"id":"stage_id","reason":"why this stage fits"}]. No prose, no markdown.'
    )
    user_prompt = (
        f"Pipeline goal: {description}\n\n"
        f"Available stages:\n{catalog_summary}\n\n"
        "Return the most relevant stages as JSON array."
    )
    try:
        result = _post("/webrobot/api/llm/infer", {"prompt": user_prompt, "systemPrompt": system})
        text = result.get("result", "") if isinstance(result, dict) else str(result)
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end != -1:
            return text[start:end+1]
        return json.dumps({"raw": text})
    except RuntimeError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def auth_check() -> str:
    """Diagnose how the MCP server is authenticated against the WebRobot API.

    Returns a JSON object reporting:
      - authenticated: bool — whether an API key or JWT was found
      - source:        str  — "env" / plugin config path / CLI config path / "none"
      - api_endpoint:  str  — the resolved base URL
      - mode:          "apikey" | "jwt" | "none"
      - hint:          str  — when not authenticated, instructions to fix

    Always works (does not call the WebRobot API). Use this before anything else
    when the user reports 401 errors or asks "am I logged in?".
    """
    info: dict[str, Any] = {
        "authenticated": bool(AUTH_HEADER),
        "api_endpoint":  BASE_URL or "(not configured)",
        "source":        AUTH_SOURCE,
    }
    if AUTH_HEADER:
        info["mode"] = "jwt" if AUTH_HEADER.lower().startswith("bearer ") else "apikey"
    else:
        info["mode"] = "none"
        info["hint"] = (
            "No credentials found. Three ways to fix:\n"
            "  1. Plugin-scoped (recommended for users without the CLI):\n"
            f"     Call auth_set(api_key=\"...\", api_endpoint=\"https://api.webrobot.eu\") to write {PLUGIN_CONFIG_FILE}\n"
            "  2. Environment variables:\n"
            "     export WEBROBOT_API_KEY=...  WEBROBOT_API_ENDPOINT=https://api.webrobot.eu\n"
            "  3. CLI config (if webrobot CLI installed):\n"
            "     `webrobot config init`\n"
            "Public endpoints (e.g. /webrobot/api/catalog/stages) work without credentials."
        )
    return _fmt(info)


@mcp.tool()
def auth_set(
    api_key: Optional[str] = None,
    jwt: Optional[str] = None,
    api_endpoint: str = "https://api.webrobot.eu",
) -> str:
    """Write the plugin-scoped credentials file at ~/.claude/plugins/webrobot/config.json.

    This is the recommended way to authenticate the plugin standalone, without depending
    on the webrobot CLI being installed. Pass either an api_key OR a jwt (not both); the
    plugin uses whichever is present, preferring jwt.

    Restart Claude Code (or reconnect the MCP server) after calling this so the change
    takes effect — config is read once at MCP startup.
    """
    if not api_key and not jwt:
        return json.dumps({"error": "either api_key or jwt is required"})
    PLUGIN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config: dict[str, str] = {"api_endpoint": api_endpoint}
    if jwt:     config["jwt"]    = jwt
    if api_key: config["apikey"] = api_key
    PLUGIN_CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        PLUGIN_CONFIG_FILE.chmod(0o600)
    except Exception:
        pass
    return _fmt({
        "saved":         str(PLUGIN_CONFIG_FILE),
        "mode":          "jwt" if jwt else "apikey",
        "api_endpoint":  api_endpoint,
        "next_step":     "Restart Claude Code (or reconnect the MCP server) for the change to take effect.",
    })


@mcp.tool()
def api_call(
    method: str,
    path: str,
    query_params: Optional[dict] = None,
    body: Optional[dict] = None,
) -> str:
    """Generic WebRobot REST API call — escape hatch for endpoints not wrapped by a curated tool.

    Use this when the user asks to call an endpoint that doesn't have a dedicated MCP tool
    (typical case: a partner plugin's vertical endpoints like
    /webrobot/api/sentiment/timeseries, /webrobot/api/<my-plugin>/...). The call uses the
    same auth, base URL and serde as every curated tool.

    Args:
      method:        HTTP method (GET, POST, PUT, PATCH, DELETE).
      path:          Path component starting with "/" (e.g. "/webrobot/api/sentiment/timeseries").
                     Public endpoints like /webrobot/api/catalog/stages also work without auth.
      query_params:  Optional dict of query string parameters; null/None values are dropped.
      body:          Optional JSON-serialisable body (POST/PUT/PATCH).

    Returns: pretty-printed JSON of the response, or {"error": ...} on HTTP error.

    Examples:
      api_call("GET",  "/webrobot/api/catalog/stages", {"plugin_type": "etl"})
      api_call("GET",  "/webrobot/api/sentiment/timeseries", {"bucket": "day"})
      api_call("POST", "/webrobot/api/sentiment/analyze", body={"text": "I love this"})
    """
    method_norm = method.upper().strip() if method else "GET"
    if method_norm not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return json.dumps({"error": f"unsupported method: {method}"})
    if not path or not path.startswith("/"):
        return json.dumps({"error": "path must start with '/'"})
    try:
        result = _call(method_norm, path, body=body, params=query_params)
        return _fmt(result) if not isinstance(result, str) else result
    except RuntimeError as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    if not AUTH_HEADER:
        print(
            "WARNING: No WebRobot credentials found.\n"
            "Set WEBROBOT_API_KEY and WEBROBOT_API_ENDPOINT environment variables,\n"
            "or create ~/.config/webrobot/config.cfg",
            file=sys.stderr,
        )
    mcp.run(transport="stdio")
