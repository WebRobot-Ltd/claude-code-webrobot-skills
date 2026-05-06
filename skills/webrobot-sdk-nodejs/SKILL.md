---
name: webrobot-sdk-nodejs
description: Consume the WebRobot REST API from a Node.js / TypeScript application using the public webrobot-sdk npm package. Use when the user wants to integrate WebRobot into a Node service, build automation, browser/electron app, or partner backend.
argument-hint: [task description, e.g. "list projects from a TypeScript backend"]
user-invocable: true
allowed-tools: Read Write Edit Bash(node *) Bash(npm *) Bash(npx *) Bash(yarn *) Bash(pnpm *) Bash(curl -fsSL https://api.webrobot.eu/webrobot/api/catalog/stages*)
---

# WebRobot Node.js / TypeScript SDK (client)

You help the user consume the WebRobot REST API as a CLIENT from a Node.js or TypeScript application. The package ships TypeScript-first with a hand-curated `WebRobotClient` (covering the most-used 30+ endpoints) plus type definitions for the request/response DTOs.

For full coverage of all 138 endpoints (including admin / billing / ai-providers paths not on the curated client), drop down to `fetch` against the documented URLs — the client-side type system stays intact via `unknown` returns that you cast as needed.

---

## Install

Until npm publication, install directly from GitHub:

```bash
npm install "git+https://github.com/WebRobot-Ltd/webrobot-sdk.git#main:nodejs-sdk"
# or
yarn add "git+https://github.com/WebRobot-Ltd/webrobot-sdk.git#main"
```

Once published to npm:

```bash
npm install webrobot-sdk
```

Node 18+ (uses native `fetch`). TypeScript 5+ recommended.

---

## Auth

Two modes. Pick one — never both.

```typescript
import { WebRobotClient } from "webrobot-sdk";

// Option A — API key
const client = new WebRobotClient({
  baseUrl: "https://api.webrobot.eu",
  apiKey:  process.env.WEBROBOT_API_KEY,
});

// Option B — JWT bearer
const client = new WebRobotClient({
  baseUrl: "https://api.webrobot.eu",
  jwt:     process.env.WEBROBOT_JWT,
});
```

CommonJS works too:

```javascript
const { WebRobotClient } = require("webrobot-sdk");
const client = new WebRobotClient({ baseUrl: "...", apiKey: "..." });
```

For local dev, share `~/.webrobot/config.cfg` with the WebRobot CLI by parsing it manually:

```typescript
import fs from "fs";
import path from "path";
import os from "os";

function loadCliCredentials(): Record<string, string> {
  const cfg = path.join(os.homedir(), ".webrobot", "config.cfg");
  if (!fs.existsSync(cfg)) return {};
  const text = fs.readFileSync(cfg, "utf8");
  const out: Record<string, string> = {};
  for (const key of ["api_endpoint", "apikey", "jwt"]) {
    const m = text.match(new RegExp(`${key}\\s*=\\s*"([^"]*)"`));
    if (m) out[key] = m[1];
  }
  return out;
}
```

---

## Quick start — curated WebRobotClient

```typescript
import { WebRobotClient } from "webrobot-sdk";

const client = new WebRobotClient({
  baseUrl: "https://api.webrobot.eu",
  apiKey:  process.env.WEBROBOT_API_KEY!,
});

// List projects
const projects = await client.projectsList();
projects.forEach(p => console.log((p as any).id, (p as any).name));

// Get one project
const project = await client.projectGet("42");

// Create a project
const created = await client.projectCreate({
  name:        "price-comparison",
  description: "...",
});

// Execute a job, then poll until done
await client.jobExecute("42", "7", {});
let status = "RUNNING";
while (!["COMPLETED", "FAILED", "CANCELLED"].includes(status)) {
  const job = await client.jobGet("42", "7");
  status = (job as any).status;
  if (status === "RUNNING") await new Promise(r => setTimeout(r, 10_000));
}
console.log("Final:", status);

// Tail logs
const logs = await client.jobGetLogs("42", "7", { tail: 200 });
```

Available methods (curated subset, ~40):

```
health, projectsList/Get/Create/Update/Delete/GetByName/GetMetrics/GetSchedule/SetSchedule
jobsList, jobCreate/Get/Update/Delete/Execute/Stop/GetLogs/GetMetrics/CompletionWebhook
tasksList, taskCreate/Get/Update/Delete/Start/Stop/GetStatus/GetMetrics
agentsList, agent{Get/Create/Update/Delete/Copy}
datasets…, cloudCredentials…, llmProviders…
```

Inspect the live surface:
```typescript
import { WebRobotClient } from "webrobot-sdk";
console.log(Object.getOwnPropertyNames(WebRobotClient.prototype).filter(n => n !== "constructor"));
```

---

## Generic call — endpoint-agnostic escape hatch

For partner-vertical endpoints (e.g. `/webrobot/api/sentiment/timeseries`) or the 100+ endpoints not on the curated client, use raw `fetch`:

```typescript
async function apiCall<T = unknown>(
  method: string,
  path: string,
  init: { params?: Record<string, unknown>, body?: unknown } = {},
): Promise<T> {
  // Path templating: {placeholder} substituted from params, matching keys removed
  let p = path;
  const remaining: Record<string, unknown> = { ...(init.params ?? {}) };
  for (const k of Object.keys(remaining)) {
    if (p.includes(`{${k}}`)) {
      p = p.replace(`{${k}}`, String(remaining[k]));
      delete remaining[k];
    }
  }
  const url = new URL(`https://api.webrobot.eu${p}`);
  for (const [k, v] of Object.entries(remaining)) {
    if (v !== undefined && v !== null) url.searchParams.append(k, String(v));
  }
  const res = await fetch(url.toString(), {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key":    process.env.WEBROBOT_API_KEY!,
    },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 400)}`);
  }
  return res.headers.get("content-length") === "0" ? (undefined as T) : await res.json();
}

// Usage
const series = await apiCall<{series: any[]}>("GET",
  "/webrobot/api/sentiment/timeseries",
  { params: { bucket: "day", from: "2026-01-01" } });

const newProject = await apiCall("POST", "/webrobot/api/projects", {
  body: { name: "demo", description: "..." },
});
```

---

## Public catalog endpoint — no auth required

```typescript
const res = await fetch(
  "https://api.webrobot.eu/webrobot/api/catalog/stages?plugin_type=etl",
);
const { data } = await res.json();
data.forEach((s: any) => console.log(s.stage_name, "—", s.description));
```

Useful for stage-pickers in UIs and AI-driven pipeline construction.

---

## Error handling

```typescript
import { WebRobotError } from "webrobot-sdk";

try {
  await client.projectGet("9999");
} catch (e) {
  if (e instanceof WebRobotError) {
    console.error(e.status, e.body);   // status code + raw response
  } else {
    throw e;                            // network / unexpected
  }
}
```

For `fetch`-based generic calls, the `Error` thrown by `apiCall` carries the status code in its message — wrap in your own error type if you want structured handling.

---

## When to use the Node.js SDK vs alternatives

| Need | Tool |
|------|------|
| Node service / Express / Fastify / Next.js backend | **Node.js SDK** (this) |
| Browser / Electron app | The same client works (`fetch`-based, no node-specific deps) |
| Shell script / CI | `webrobot` CLI |
| Claude Code / Cursor inline | MCP tools (`mcp__webrobot__*`) |
| Browser-side, when you don't want to expose API keys | Use a thin server proxy that owns the credentials |

---

## Common patterns

### Run a pipeline manifest from code

```typescript
import fs from "fs/promises";

const yaml = await fs.readFile("pipeline.yaml", "utf8");
const result = await apiCall<{ executionId: string }>("POST",
  "/webrobot/api/pipelines/run", {
    body: { yaml, follow: true },
  });
console.log("Execution:", result.executionId);
```

### Batch via Promise.all

```typescript
const projectIds = ["1", "2", "3"];
const allJobs = await Promise.all(projectIds.map(id => client.jobsList(id)));
console.log(allJobs.flat().length, "jobs total");
```

### Streaming logs (Server-Sent Events)

```typescript
const res = await fetch(
  `https://api.webrobot.eu/webrobot/api/projects/42/jobs/7/logs?stream=true`,
  { headers: { "X-API-Key": process.env.WEBROBOT_API_KEY! } },
);
const reader = res.body!.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  process.stdout.write(decoder.decode(value));
}
```

---

## TypeScript types

The package exports the most common DTOs for compile-time safety. Cast `unknown` returns from the curated client to typed shapes when needed:

```typescript
import { WebRobotClient, JobDto, JobProjectDto } from "webrobot-sdk";

const client = new WebRobotClient({ apiKey: "..." });
const projects = (await client.projectsList()) as JobProjectDto[];
```

---

## Rules of thumb

- **Curated `WebRobotClient`** for the 40 most-common operations — type-friendly, less boilerplate.
- **Generic `apiCall`** for partner-vertical endpoints and the long tail (100+ endpoints not on the curated client).
- **Never put API keys in browser bundles.** Use a server-side proxy or short-lived JWT.
- **Use env vars or a server-side secret manager.** Don't commit credentials.
- **Catch `WebRobotError`** explicitly for the curated client, status-code checks for `apiCall`.
- **Catalog is public.** Don't waste an auth header on `/webrobot/api/catalog/stages`.

## On $ARGUMENTS

- If the user passed a task: scaffold the TypeScript code, with auth setup and types where they help.
- If the user passed a file path: read it, propose the SDK call to integrate.
- If the user is unclear: ask whether they want the curated client (~40 methods, type-friendly) or generic `fetch` (full coverage).
