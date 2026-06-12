#!/usr/bin/env python3
"""WebRobot MCP Server — auto-generated from the live OpenAPI spec.

Two deployment modes via env vars:

  MCP_TRANSPORT  stdio|http   default: stdio (local plugin)
                              http for online k8s deploy.
  MCP_SCOPE      full|demo    default: full (all 216 paths, requires auth).
                              demo = only /webrobot/api/demo/* (public, no auth).
  MCP_HOST       host         default: 0.0.0.0   (only used when transport=http)
  MCP_PORT       port         default: 8080      (only used when transport=http)
  MCP_PATH       path prefix  default: /mcp      (only used when transport=http)

Spec source: <WEBROBOT_API_ENDPOINT>/api/openapi.json, fetched at startup.

Auth (for MCP_SCOPE=full only):
  1. Env: WEBROBOT_API_ENDPOINT, WEBROBOT_API_KEY, WEBROBOT_JWT
  2. ~/.claude/plugins/webrobot/config.json
  3. ~/.config/webrobot/config.cfg | ~/.webrobot/config.cfg | ./config.cfg (HOCON-ish)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.openapi import MCPType, RouteMap
from starlette.requests import Request
from starlette.responses import JSONResponse

# ── Config loading ────────────────────────────────────────────────────────────


def _parse_hocon_credentials(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("api_endpoint", "apikey", "jwt", "bearer", "token"):
        m = re.search(rf'{key}\s*=\s*"([^"]*)"', text)
        if m:
            out[key] = m.group(1)
    return out


def _parse_json_credentials(text: str) -> dict[str, str]:
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return {
        k: v
        for k, v in data.items()
        if k in ("api_endpoint", "apikey", "jwt", "bearer", "token")
        and isinstance(v, str)
        and v
    }


PLUGIN_CONFIG_DIR = Path.home() / ".claude" / "plugins" / "webrobot"
PLUGIN_CONFIG_FILE = PLUGIN_CONFIG_DIR / "config.json"


def _load_config() -> tuple[str, str, str]:
    """Returns (base_url, auth_header, source_label)."""
    endpoint = os.environ.get("WEBROBOT_API_ENDPOINT", "")
    api_key = os.environ.get("WEBROBOT_API_KEY", "")
    jwt = os.environ.get("WEBROBOT_JWT", "")
    source = "env" if (endpoint or api_key or jwt) else ""

    def _absorb(creds: dict[str, str], label: str) -> None:
        nonlocal endpoint, api_key, jwt, source
        endpoint = endpoint or creds.get("api_endpoint", "")
        api_key = api_key or creds.get("apikey", "")
        jwt = jwt or creds.get("jwt") or creds.get("bearer") or creds.get("token", "")
        if not source and (endpoint or api_key or jwt):
            source = label

    if not (endpoint and (api_key or jwt)) and PLUGIN_CONFIG_FILE.exists():
        _absorb(_parse_json_credentials(PLUGIN_CONFIG_FILE.read_text()), str(PLUGIN_CONFIG_FILE))

    if not (endpoint and (api_key or jwt)):
        for candidate in (
            Path.home() / ".config" / "webrobot" / "config.cfg",
            Path.home() / ".webrobot" / "config.cfg",
            Path("config.cfg"),
        ):
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


# ── Server bootstrap ──────────────────────────────────────────────────────────


async def _forward_client_auth(request: httpx.Request) -> None:
    """Per-request PROXY hook: copy the END-USER's credential from the incoming
    MCP HTTP request onto the upstream API call. The MCP holds NO key of its own
    — authentication + per-org RBAC are entirely the REST API's job
    (UnifiedAuthFilter). Forwards both `Authorization: Bearer <jwt>` (platform
    OAuth) and `X-API-Key` (WebRobot key); whichever the client sent."""
    try:
        incoming = get_http_headers(include_all=True)
    except Exception:
        incoming = {}
    auth = incoming.get("authorization")
    api_key = incoming.get("x-api-key")
    if auth:
        request.headers["Authorization"] = auth
    if api_key:
        request.headers["X-API-Key"] = api_key


def _build_httpx_client(base_url: str, scope: str) -> httpx.AsyncClient:
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "webrobot-mcp/2.0",
    }
    # full scope = PROXY: forward the caller's own credential per-request (no
    # baked-in key, so safe to expose publicly). demo scope = public endpoints,
    # no auth at all.
    event_hooks = {"request": [_forward_client_auth]} if scope == "full" else {}
    return httpx.AsyncClient(
        base_url=f"{base_url}/api",
        headers=headers,
        timeout=httpx.Timeout(60.0, connect=15.0),
        event_hooks=event_hooks,
    )


def _deopacify_spec(spec: dict) -> int:
    """Remove request-body OPACITY across the WHOLE spec.

    Jersey endpoints that read a raw `Map<String,Object>` emit a requestBody
    schema of `{type: object, additionalProperties: {type: object}}`. That
    constraint forces every body VALUE to itself be an object, so plain string
    fields (e.g. `yaml`, `csv`, `content`) get dropped before the request is
    sent — the API then sees an empty/invalid body ("Missing 'yaml' field").

    Relax every such opaque map to `additionalProperties: true` (any JSON value
    allowed) so free-form bodies pass through unchanged. One pass, all endpoints
    — no per-endpoint typed wrapper needed. Returns the count relaxed."""
    count = 0

    def walk(node):
        nonlocal count
        if isinstance(node, dict):
            ap = node.get("additionalProperties")
            # opaque map: additionalProperties is an object-typed schema with no
            # own properties (i.e. "any object") → allow any JSON value instead.
            if isinstance(ap, dict) and ap.get("type") == "object" and "properties" not in ap:
                node["additionalProperties"] = True
                count += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(spec.get("paths", {}))
    walk(spec.get("components", {}))
    return count


def _fetch_spec(base_url: str) -> dict:
    spec_url = f"{base_url}/api/openapi.json"
    print(f"  → fetching OpenAPI spec from {spec_url}", file=sys.stderr)
    resp = httpx.get(spec_url, timeout=30.0)
    resp.raise_for_status()
    spec = resp.json()
    # WebRobot's Jersey OpenAPI emitter currently omits the required `info`
    # block (only "openapi" + "paths" + "components" come through). Pydantic
    # in fastmcp rejects the spec with a hard "missing field info" error.
    # Inject a synthetic block defensively so the MCP boots regardless of
    # what the server-side emitter chooses to include.
    if "info" not in spec or not isinstance(spec.get("info"), dict):
        spec["info"] = {
            "title": "WebRobot API",
            "version": str(spec.get("openapi", "1.0.0")),
            "description": "Auto-injected — Jersey emitter did not provide an info block.",
        }
        print("  ! `info` missing from spec — injected synthetic block", file=sys.stderr)
    relaxed = _deopacify_spec(spec)
    paths = len((spec.get("paths") or {}))
    print(f"  ✓ spec loaded ({paths} paths, de-opacified {relaxed} map bodies)", file=sys.stderr)
    return spec


# Demo POST endpoints whose Jersey handlers read a raw Map → their OpenAPI
# requestBody is an opaque generic object ({additionalProperties}), so the
# auto-generated tools don't tell the agent which fields to send. We EXCLUDE
# them from from_openapi and register explicit, typed replacements below.
_DEMO_OPAQUE_EXCLUDE = [
    r"^/webrobot/api/demo/generate-pipeline$",
    r"^/webrobot/api/demo/save-generated-pipeline$",
    r"^/webrobot/api/demo/wizard/validate$",
    r"^/webrobot/api/demo/execute/.*",
    r"^/webrobot/api/demo/wizard/cmf/open$",
    r"^/webrobot/api/demo/wizard/infer-selector$",
    r"^/webrobot/api/demo/wizard/infer-fields$",
    r"^/webrobot/api/demo/wizard/infer-segment$",
    r"^/webrobot/api/demo/wizard/infer-variables$",
    r"^/webrobot/api/demo/wizard/apply-variables$",
    # Multipart file upload: its Jersey signature is FormDataMultiPart, so the
    # auto-generated tool serializes the whole multipart object and the MCP
    # (JSON-RPC, no multipart boundary) hits HTTP 415. Excluded here; replaced
    # by the typed JSON `uploadDataset` tool below (create-dataset).
    r"^/webrobot/api/demo/upload-dataset/.*",
]


# Full-scope (authenticated main API) endpoints whose auto-generated tool is
# unusable, EXCLUDED and replaced by typed tools in _register_full_tools:
#  - upload-dataset/* : Jersey FormDataMultiPart -> multipart, MCP hits HTTP 415.
#  - datasets/upload-json : reads a raw Map<String,Object> -> opaque OpenAPI body
#    ({additionalProperties}), so the agent isn't told which fields to send.
_FULL_OPAQUE_EXCLUDE = [
    r"^/webrobot/api/demo/upload-dataset/.*",
    r"^/webrobot/api/datasets/upload-json$",
    # Manifest apply/validate read a raw Map<String,Object> {yaml:...}. FastMCP
    # models that as a single free-form `body` param and wraps it, so the API
    # never sees a top-level `yaml` ("Missing 'yaml' field"). De-opacifying the
    # spec isn't enough (the wrapper remains) — replaced by typed tools below.
    r"^/webrobot/api/manifest/apply$",
    r"^/webrobot/api/manifest/validate$",
    # Job execute reads a raw Map<String,Object> -> opaque OpenAPI body, so FastMCP
    # serializes it per the (empty) schema and DROPS unknown fields like `engine`
    # (the engine selector never reaches Jersey -> always Spark). Replaced by a typed
    # executeJob_1 tool below that explicitly carries `engine`.
    r"^/webrobot/api/projects/id/[^/]+/jobs/[^/]+/execute$",
]


def _route_maps_for_scope(scope: str) -> list[RouteMap]:
    """First match wins. EXCLUDE drops the operation entirely."""
    if scope == "demo":
        maps = [RouteMap(pattern=p, mcp_type=MCPType.EXCLUDE) for p in _DEMO_OPAQUE_EXCLUDE]
        maps += [
            RouteMap(pattern=r"^/webrobot/api/demo/.*", mcp_type=MCPType.TOOL),
            RouteMap(pattern=r".*", mcp_type=MCPType.EXCLUDE),
        ]
        return maps
    # full: keep everything as Tool (don't promote GETs to Resources — most
    # MCP clients today drive Tools well and Resources less so), minus the
    # opaque/multipart endpoints replaced by typed tools below.
    maps = [RouteMap(pattern=p, mcp_type=MCPType.EXCLUDE) for p in _FULL_OPAQUE_EXCLUDE]
    maps += [RouteMap(pattern=r".*", mcp_type=MCPType.TOOL)]
    return maps


def _register_full_tools(mcp: FastMCP, client) -> None:
    """Typed replacements for the opaque/multipart endpoints in FULL scope
    (authenticated main API). Field names match DatasetCrudApiV10.uploadDatasetJson."""
    async def _post(path: str, payload: dict):
        r = await client.post(path, json=payload)
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "detail": r.text[:600]}
        try:
            return r.json()
        except Exception:
            return {"raw": r.text[:1000]}

    @mcp.tool(name="uploadDatasetJson")
    async def upload_dataset_json(name: str, content: str | None = None,
                                  content_base64: str | None = None,
                                  filename: str = "dataset.csv",
                                  dataset_type: str = "input",
                                  organization_id: str | None = None) -> dict:
        """Upload a dataset to the authenticated main API via JSON (NOT multipart).
        Pass the CSV either as raw text in `content` (first line = header) or
        base64 in `content_base64` (use base64 for large/binary files). `dataset_type`
        is 'input' or 'output'. `organization_id` scopes the dataset to a concrete
        org — REQUIRED when calling as super_admin; ignored otherwise (taken from the
        auth context). Stored under the per-org MinIO prefix with a random dir.
        Returns {datasetId, name, organizationId, storagePath, filePath}.

        This is the real (non-demo, no size-cap) upload path; the demo create-dataset
        tool is size-capped and unscoped."""
        body: dict = {"name": name, "filename": filename, "datasetType": dataset_type}
        if content_base64:
            body["contentBase64"] = content_base64
        elif content is not None:
            body["content"] = content
        else:
            return {"error": "BAD_REQUEST", "detail": "pass `content` (CSV text) or `content_base64`"}
        if organization_id:
            body["organizationId"] = organization_id
        return await _post("/webrobot/api/datasets/upload-json", body)

    @mcp.tool(name="manifestApply")
    async def manifest_apply(yaml: str) -> dict:
        """Apply a multi-document WebRobot manifest (the declarative way to create
        Project / Pipeline / Job / Dataset). `yaml` is the full multi-doc YAML
        string (docs separated by `---`). Dependency-ordered tiers: Project (tier0)
        -> Dataset (tier1) -> Pipeline (tier2, metadata.project = category id, spec
        holds the pipeline stages + output) -> Job (tier3, spec.agent: ref:<name>,
        spec.input.dataset: <id|ref>). Cross-doc refs via `ref:<name>`.
        Returns {applied:[{kind,name,status,id...}], errors:[]}. Use manifestValidate
        first for a dry-run. POSTs {yaml} to /webrobot/api/manifest/apply."""
        return await _post("/webrobot/api/manifest/apply", {"yaml": yaml})

    @mcp.tool(name="executeJob_1")
    async def execute_job(projectId: str, jobId: str, engine: str | None = None,
                          options: dict | None = None) -> dict:
        """Execute a job in a project (POST /webrobot/api/projects/id/{projectId}/jobs/{jobId}/execute).
        `engine`: set to "scrapy" to run the pipeline on the lightweight Scrapy ingestion
        engine (Ray job) instead of the default distributed Spark engine — only valid for
        ingestion-only pipelines (fetch/explore/join/flatSelect/extract); pipelines using
        analytics/LLM stages are rejected and must use Spark. Omit `engine` for the default.
        `options`: extra execution-request fields merged into the body (e.g. iextractVisionValidate,
        hitlAwait). Returns the submission result (executionId + status)."""
        body: dict = dict(options or {})
        if engine:
            body["engine"] = engine
        return await _post(f"/webrobot/api/projects/id/{projectId}/jobs/{jobId}/execute", body)

    @mcp.tool(name="manifestValidate")
    async def manifest_validate(yaml: str) -> dict:
        """Dry-run a manifest YAML (no DB writes): parses + reports what would change.
        NB cross-doc refs to not-yet-created entities (e.g. a Pipeline referencing a
        Project defined in the same manifest) report 'not found' in validate — that's
        expected; they resolve at apply time via tier ordering. POSTs to
        /webrobot/api/manifest/validate."""
        return await _post("/webrobot/api/manifest/validate", {"yaml": yaml})


def _register_demo_tools(mcp: FastMCP, client) -> None:
    """Explicit, TYPED replacements for the opaque demo POST endpoints (whose
    OpenAPI body is a generic object). Field names match the Jersey handlers."""
    from urllib.parse import quote

    async def _post(path: str, payload: dict):
        r = await client.post(path, json=payload)
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "detail": r.text[:600]}
        try:
            return r.json()
        except Exception:
            return {"raw": r.text[:1000]}

    async def _get(path: str, params: dict | None = None):
        r = await client.get(path, params={k: v for k, v in (params or {}).items() if v is not None})
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "detail": r.text[:600]}
        try:
            return r.json()
        except Exception:
            return {"raw": r.text[:1000]}

    @mcp.tool(name="uploadDataset")
    async def upload_dataset(name: str, csv: str) -> dict:
        """Upload a CSV dataset via JSON (NOT multipart) and create a demo input
        dataset. Pass the raw CSV text in `csv` (first line = header). Returns
        {datasetId, name, ...}; pass the returned datasetId to executeDemo /
        saveGeneratedPipeline as the pipeline input.

        Replaces the auto-generated multipart upload-dataset tool, which fails
        over MCP with HTTP 415 (JSON-RPC can't send multipart/form-data). Demo
        scope is size-capped; for large/org-scoped uploads use the authenticated
        main API (/webrobot/api/datasets/upload-json)."""
        return await _post("/webrobot/api/demo/create-dataset", {"name": name, "csv": csv})

    @mcp.tool(name="generatePipeline")
    async def generate_pipeline(prompt: str) -> dict:
        """Generate a pipeline manifest from a natural-language description.
        Returns {pipeline_name, pipeline_yaml}."""
        return await _post("/webrobot/api/demo/generate-pipeline", {"prompt": prompt})

    @mcp.tool(name="saveGeneratedPipeline")
    async def save_generated_pipeline(pipeline_name: str, pipeline_yaml: str,
                                      execute: bool = False, dataset_id: int | None = None) -> dict:
        """Save a pipeline (upsert by name as 'Generated: <name>'). execute=True also
        runs it; dataset_id attaches a pre-uploaded input dataset."""
        body = {"pipeline_name": pipeline_name, "pipeline_yaml": pipeline_yaml, "execute": execute}
        if dataset_id is not None:
            body["datasetId"] = dataset_id
        return await _post("/webrobot/api/demo/save-generated-pipeline", body)

    @mcp.tool(name="wizardValidate")
    async def wizard_validate(yaml: str, session_id: str | None = None) -> dict:
        """VALIDATE a pipeline YAML on Camoufox (dry-run) and return sample rows.
        NB the field is `yaml` (full pipeline YAML), not pipeline_yaml. session_id
        reuses a live designer session. Returns {valid, records, record_count, steps}."""
        body = {"yaml": yaml}
        if session_id:
            body["session_id"] = session_id
        return await _post("/webrobot/api/demo/wizard/validate", body)

    @mcp.tool(name="executeDemo")
    async def execute_demo(pipeline_name: str, limit: int = 10, dataset_id: int | None = None,
                           execution_mode: str = "shared", hetzner_api_key: str | None = None) -> dict:
        """Run a saved demo pipeline. limit clamped 5–10. execution_mode 'shared'
        (default) or 'byoc' (needs hetzner_api_key → runs on the user's Hetzner VMs).
        Returns an execution map with execution_id (poll the output/status tools)."""
        params: dict = {"limit": limit}
        if dataset_id is not None:
            params["datasetId"] = dataset_id
        body: dict = {"parameters": params, "executionMode": execution_mode}
        if execution_mode.lower() == "byoc" and hetzner_api_key:
            body["cloudCredentials"] = {"hetznerApiKey": hetzner_api_key}
        return await _post(f"/webrobot/api/demo/execute/{quote(pipeline_name)}", body)

    @mcp.tool(name="inferVariables")
    async def infer_variables(pipeline_yaml: str, dataset_columns: list[str] | None = None) -> dict:
        """Detect templatizable variables (keywords in url/selectors) to bind to a
        dataset column for a per-row sweep. Returns {variables:[...]}."""
        body: dict = {"pipeline_yaml": pipeline_yaml}
        if dataset_columns:
            body["dataset_columns"] = dataset_columns
        return await _post("/webrobot/api/demo/wizard/infer-variables", body)

    @mcp.tool(name="applyVariables")
    async def apply_variables(pipeline_name: str, pipeline_yaml: str) -> dict:
        """Persist a templatized pipeline (rewrites + saves the parameterized YAML)."""
        return await _post("/webrobot/api/demo/wizard/apply-variables",
                           {"pipeline_name": pipeline_name, "pipeline_yaml": pipeline_yaml})

    @mcp.tool(name="cmfOpen")
    async def cmf_open(url: str, country: str | None = None) -> dict:
        """Open a URL in a fresh Camoufox designer session (returns session_id +
        rewritten html). country = ISO-2 geo (DataImpulse __cr.<country> proxy)."""
        body = {"url": url}
        if country:
            body["country"] = country
        return await _post("/webrobot/api/demo/wizard/cmf/open", body)

    @mcp.tool(name="wizardInferSelector")
    async def wizard_infer_selector(intent: str, url: str | None = None,
                                    html: str | None = None, stage_name: str | None = None) -> dict:
        """Infer a CSS selector for `intent` on a page (pass url OR pre-rendered html)."""
        body = {"intent": intent}
        for k, v in (("url", url), ("html", html), ("stage_name", stage_name)):
            if v:
                body[k] = v
        return await _post("/webrobot/api/demo/wizard/infer-selector", body)

    @mcp.tool(name="wizardInferFields")
    async def wizard_infer_fields(intent: str, url: str | None = None, html: str | None = None,
                                  container_selector: str | None = None, stage_name: str | None = None) -> dict:
        """Infer field selectors (comma-list `intent`) within an optional
        container_selector (flatSelect segment → relative selectors)."""
        body = {"intent": intent}
        for k, v in (("url", url), ("html", html),
                     ("container_selector", container_selector), ("stage_name", stage_name)):
            if v:
                body[k] = v
        return await _post("/webrobot/api/demo/wizard/infer-fields", body)

    @mcp.tool(name="wizardInferSegment")
    async def wizard_infer_segment(url: str | None = None, html: str | None = None,
                                   segmentation_prompt: str | None = None) -> dict:
        """Infer the repeating-row segment selector (PTA) for flatSelect. url OR html."""
        body: dict = {}
        for k, v in (("url", url), ("html", html), ("segmentation_prompt", segmentation_prompt)):
            if v:
                body[k] = v
        return await _post("/webrobot/api/demo/wizard/infer-segment", body)

    @mcp.tool(name="ragQuery")
    async def rag_query(question: str, index_name: str, top_k: int = 5,
                        project_name: str | None = None,
                        filters: dict | None = None) -> dict:
        """Retrieve the top-k most relevant knowledge/style chunks from an external
        RAG index (LlamaCloud) to GROUND the answer in uploaded documents — pure
        retrieval, the agent itself reasons over the returned chunks.

        index_name selects the per-profile knowledge index (e.g. a founder's own
        index). top_k clamps how many chunks to return (default 5). Optional
        project_name (default 'webrobot') and metadata filters {key: value}.
        Returns {hits: [{text, score, metadata}], count, index_name}. The provider
        API key is resolved server-side from cloud_credentials — NEVER pass keys here."""
        body: dict = {"question": question, "index_name": index_name, "top_k": top_k}
        if project_name:
            body["project_name"] = project_name
        if filters:
            body["filters"] = filters
        return await _post("/webrobot/api/demo/rag/query", body)

    # ragEnsureIndex (RAG index creation) is intentionally NOT exposed to the agent.
    # Creating/writing RAG indexes is admin-only: the public demo /rag/index (and
    # /rag/ingest) write endpoints were removed to prevent RAG poisoning. The agent
    # gets READ-ONLY RAG access (ragQuery + ragIndexStatus); writes go through the
    # authenticated main API (RagQueryApiV10), admin only.

    @mcp.tool(name="webSearch")
    async def web_search(query: str, num: int = 5) -> dict:
        """Search the web (Google) to find pages/sites/context that SUPPORT setting
        up a scrape — locate a target listing/detail page, find docs, or verify a
        fact. Returns {results:[{title, link, snippet, source}]}. This is discovery
        only; scrape the chosen URL with the WebRobot pipeline/Camoufox tools."""
        return await _get("/webrobot/api/demo/search", {"q": query, "num": num})

    @mcp.tool(name="ragIndexStatus")
    async def rag_index_status(index_name: str, project_name: str | None = None) -> dict:
        """Indexing status of the documents in a RAG index (LlamaCloud parses +
        embeds asynchronously). Returns {total, indexed, ready, by_status,
        files:[{name,status}]}. Poll until ready=true before relying on ragQuery."""
        return await _get("/webrobot/api/demo/rag/status",
                          {"index_name": index_name, "project_name": project_name})


def build_server() -> FastMCP:
    scope = os.environ.get("MCP_SCOPE", "full").lower()
    if scope not in ("full", "demo"):
        print(f"  ! unknown MCP_SCOPE={scope!r}, falling back to 'full'", file=sys.stderr)
        scope = "full"

    base_url, _auth, _auth_source = _load_config()

    # full scope is a PROXY: the end-user's credential is forwarded per-request
    # (see _forward_client_auth), so no server-side key is loaded or required.
    auth_mode = "proxy (per-request client credential)" if scope == "full" else "public/no-auth"

    print(
        f"  ┌─ WebRobot MCP\n"
        f"  │  base_url:    {base_url}\n"
        f"  │  scope:       {scope}\n"
        f"  │  auth:        {auth_mode}\n"
        f"  └─",
        file=sys.stderr,
    )

    spec = _fetch_spec(base_url)
    client = _build_httpx_client(base_url, scope)

    server_name = "WebRobot Demo" if scope == "demo" else "WebRobot"
    mcp = FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name=server_name,
        route_maps=_route_maps_for_scope(scope),
    )

    # The opaque/multipart endpoints were EXCLUDED above; add typed replacements.
    if scope == "demo":
        _register_demo_tools(mcp, client)
    else:
        _register_full_tools(mcp, client)

    # Liveness — used by k8s probes when transport=http.
    @mcp.custom_route("/health", methods=["GET"])
    async def health(_req: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "scope": scope, "base_url": base_url})

    return mcp


def main() -> None:
    mcp = build_server()
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "8080"))
        path = os.environ.get("MCP_PATH", "/mcp")
        # Stateless HTTP → each request is self-contained (no per-pod in-memory
        # MCP session). Required to run >1 replica without sticky routing: a
        # stateful server keeps the session in RAM, so initialize on pod A and
        # follow-up calls on pod B fail with "session not found". Default ON so
        # the deployment scales horizontally; set MCP_STATELESS=0 to revert.
        # (FastMCP ≥2.3.4 takes transport settings on run(), not the ctor.)
        stateless = os.environ.get("MCP_STATELESS", "true").lower() not in ("0", "false", "")
        print(
            f"  → starting HTTP transport on {host}:{port}{path} (stateless={stateless})",
            file=sys.stderr,
        )
        mcp.run(transport="http", host=host, port=port, path=path,
                stateless_http=stateless)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
