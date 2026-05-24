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


def _build_httpx_client(base_url: str, auth: str, scope: str) -> httpx.AsyncClient:
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "webrobot-mcp/2.0",
    }
    # Auth is meaningful only in `full` scope; demo endpoints don't need it.
    if scope == "full" and auth:
        headers["Authorization"] = auth
        if auth.startswith("ApiKey "):
            headers["X-API-Key"] = auth[len("ApiKey "):]
    return httpx.AsyncClient(
        base_url=f"{base_url}/api",
        headers=headers,
        timeout=httpx.Timeout(60.0, connect=15.0),
    )


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
    paths = len((spec.get("paths") or {}))
    print(f"  ✓ spec loaded ({paths} paths)", file=sys.stderr)
    return spec


def _route_maps_for_scope(scope: str) -> list[RouteMap]:
    """First match wins. EXCLUDE drops the operation entirely."""
    if scope == "demo":
        return [
            RouteMap(pattern=r"^/webrobot/api/demo/.*", mcp_type=MCPType.TOOL),
            RouteMap(pattern=r".*", mcp_type=MCPType.EXCLUDE),
        ]
    # full: keep everything as Tool (don't promote GETs to Resources — most
    # MCP clients today drive Tools well and Resources less so).
    return [RouteMap(pattern=r".*", mcp_type=MCPType.TOOL)]


def build_server() -> FastMCP:
    scope = os.environ.get("MCP_SCOPE", "full").lower()
    if scope not in ("full", "demo"):
        print(f"  ! unknown MCP_SCOPE={scope!r}, falling back to 'full'", file=sys.stderr)
        scope = "full"

    base_url, auth, auth_source = _load_config()

    if scope == "full" and not auth:
        print(
            "  ⚠ MCP_SCOPE=full but no credentials found.\n"
            "    Authenticated endpoints will fail with 401. Set WEBROBOT_API_KEY\n"
            "    or run with MCP_SCOPE=demo for the public surface only.",
            file=sys.stderr,
        )

    print(
        f"  ┌─ WebRobot MCP\n"
        f"  │  base_url:    {base_url}\n"
        f"  │  scope:       {scope}\n"
        f"  │  auth source: {auth_source}\n"
        f"  └─",
        file=sys.stderr,
    )

    spec = _fetch_spec(base_url)
    client = _build_httpx_client(base_url, auth, scope)

    server_name = "WebRobot Demo" if scope == "demo" else "WebRobot"
    mcp = FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name=server_name,
        route_maps=_route_maps_for_scope(scope),
    )

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
        print(
            f"  → starting HTTP transport on {host}:{port}{path}",
            file=sys.stderr,
        )
        mcp.run(transport="http", host=host, port=port, path=path)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
