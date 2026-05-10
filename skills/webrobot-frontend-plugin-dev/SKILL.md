---
name: webrobot-frontend-plugin-dev
description: Build a partner-authored UI plugin for the WebRobot dashboard (Next.js). Plugins ship as a ZIP with ESM bundles, are uploaded to MinIO, and hot-load in the dashboard via blob-URL import() — no rebuild of the host app required. Use when the user wants to add a custom dashboard view, configuration page, or vertical UI to the WebRobot host shell.
argument-hint: [plugin description, e.g. "sentiment dashboard with timeseries chart"]
user-invocable: true
allowed-tools: Read Write Edit Bash(npm *) Bash(npx *) Bash(yarn *) Bash(pnpm *) Bash(node *) Bash(curl -fsSL https://api.webrobot.eu/webrobot/api/catalog/stages*)
---

# WebRobot Frontend Plugin Developer

You help the user build a partner UI plugin for the **clouddashboard** Next.js host shell. Unlike ETL or REST plugins (server-side, JVM), frontend plugins run in the browser inside the host's origin — they ship as ESM bundles in a ZIP, get uploaded to MinIO, and hot-load when an admin enables them. No host rebuild needed.

For ETL stages or REST API plugins (server-side), see `/webrobot-plugin-dev`.

---

## Architecture (host-side contracts the user inherits)

```
Partner ZIP on MinIO  ──►  GET /api/ui-plugins/<id>/file/<path>     (host-side proxy)
                            │
                            ▼
                          Blob URL  +  await import(/* webpackIgnore */ blobUrl)
                            │
                            ▼
                          mod.default   (or named export, or `Component`)
                            │
                            ▼
                          rendered inside /dashboard/extensions/<pluginId>/<viewId>
```

**Key host files** (read-only for the partner — they're documented here for context):
- `frontend/plugins/ui/load-plugin-component.tsx` — the bundle executor
- `frontend/plugins/ui/registry.ts` — static + dynamic plugin definitions
- `frontend/plugins/ui/render-plugin-view.tsx` — picks the component from the registry
- `frontend/plugins/ui/DYNAMIC_PLUGINS.md` — full contract reference

The partner does NOT modify the host code. They ship a ZIP that conforms to the contract below.

---

## ZIP layout the host expects

```
my-plugin-ui.zip
├── manifest.json          # plugin definition (synced to DB on upload)
└── dist/
    ├── Overview.js        # ESM bundle for view "overview"
    ├── Settings.js        # ESM bundle for view "settings"
    └── …                  # one .js per view declared in manifest.json
```

The host tries multiple path variants per view: `<View>.js`, `<View>.mjs`, `dist/<View>.js`, `build/<View>.js`. Stick with `dist/` for predictability.

---

## manifest.json shape

```json
{
  "pluginId": "sentiment-ui",
  "displayName": "Sentiment Analytics",
  "menuGroup": "Verticals",
  "views": [
    {
      "viewId": "overview",
      "title":  "Overview",
      "component": "dist/Overview.js",
      "rolesAllowed": ["admin", "developer"],
      "isSettings": false
    },
    {
      "viewId": "timeseries",
      "title":  "Timeseries",
      "component": "dist/Timeseries.js",
      "rolesAllowed": ["admin", "developer", "viewer"]
    },
    {
      "viewId": "settings",
      "title":  "Settings",
      "component": "dist/Settings.js",
      "rolesAllowed": ["admin"],
      "isSettings": true
    }
  ],
  "menuItems": [],
  "zipPath": "s3a://webrobot-plugins/sentiment-ui-v0.2.0.zip"
}
```

`rolesAllowed` controls which user roles see the tab inside the extension page. `isSettings: true` flags a config view (rendered with a `config` badge).

### `ui.menu[]` — sidebar contributions (May 2026+)

A plugin can contribute sidebar entries beyond the legacy `Extensions`
group via the new `ui.menu[]` array. Each entry attaches to a
**whitelisted slot**; unknown slots are silently dropped at render.

```json
{
  "ui": {
    "menu": [
      {
        "slot": "main",                      // top-level new group (super_admin approval gating)
        "label": "AI Training",
        "icon": "sparkle",
        "path": "/dashboard/ext/ml-intern",
        "rolesAllowed": ["super_admin", "admin", "developer"],
        "order": 250
      },
      {
        "slot": "settings",
        "parent": "security",                 // nest under existing Settings → Security
        "label": "API Audit",
        "path": "/dashboard/profile/security/api-audit"
      },
      {
        "slot": "marketplace",
        "label": "Featured Models",
        "path": "/dashboard/marketplace/ml-models"
      }
    ],
    "homeWidgets": [
      {
        "id": "spend-summary",
        "title": "Cost This Month",
        "size": "small",                      // small | medium | large | full
        "component": "dist/widgets/SpendSummary.js",
        "rolesAllowed": ["admin", "super_admin"]
      }
    ]
  }
}
```

**Slot whitelist (V0)**:

| Slot | Where it lands | Approval |
|------|----------------|----------|
| `extensions` | Legacy Extensions group (default if `slot` omitted) | auto |
| `marketplace` | Under Infrastructure / Configuration | auto |
| `settings` | Under Settings (use `parent` to drill in) | auto |
| `partner` | Partner Dashboard standalone group | auto |
| `infrastructure` / `development` / `management` | Existing top-level categories | auto |
| `ai-automation` / `business` / `user` | Existing standalone groups | auto |
| `main` / `admin` | New top-level area | **super_admin gating at upload review** |

`rolesAllowed[]` and `requiresScope` are evaluated at render — entries
the user cannot access stay invisible. The host renders a small
`(plugin)` tag next to every plugin-contributed entry to mitigate
phishing-style injections that mimic platform entries.

Reference schema (full validation): `webrobot-elt-clouddashboard/frontend/app/api/_utils/plugin-manifest-schema.json`.
Design: `docs/PLUGIN_UI_FLEXIBLE_MENU.md`.

---

## Bundle contract — v1

The dashboard executes the bundle via `await import()` from a blob URL. This means:

1. **Format must be ESM** (`type: "module"`, `format: "es"` in Vite/Rollup).
2. **The bundle's `import` statements cannot reference bare specifiers** (`import "react"`) because the browser cannot resolve them from a blob URL without an import map. v1 ships React **bundled inline**.
3. **Export must be**: `default`, OR a named export with the same name as the bare filename (`Overview` from `Overview.js`), OR `Component`. The host tries them in that order.

### Vite config (recommended toolchain)

```js
// vite.config.js
import react from '@vitejs/plugin-react';

export default {
  plugins: [react()],
  build: {
    lib: {
      entry: {
        Overview:    'src/Overview.tsx',
        Timeseries:  'src/Timeseries.tsx',
        Settings:    'src/Settings.tsx',
      },
      formats: ['es'],
      fileName: (_format, name) => `${name}.js`,
    },
    // NIENTE rollupOptions.external in v1 — bundle React inline.
    // (v2 con import maps userà: external: ['react', 'react-dom'])
  },
};
```

Output: `dist/Overview.js`, `dist/Timeseries.js`, `dist/Settings.js`. Each ~200–300KB (React + your code). Acceptable for v1; v2 import maps will reduce to ~30KB per view.

### Component example

```tsx
// src/Overview.tsx
import { useEffect, useState } from 'react';

interface PluginViewProps {
  pluginId: string;
  viewId: string;
  installations: Array<{ id: number; organization_id: string | null; enabled: boolean }>;
  token: string | null;
}

export default function Overview({ token }: PluginViewProps) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    fetch('/api/proxy/sentiment/timeseries?bucket=day', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.json())
      .then(setData);
  }, [token]);

  if (!data) return <div className="p-4">Loading…</div>;
  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold">Sentiment Overview</h2>
      <pre className="text-sm mt-4">{JSON.stringify(data.series, null, 2)}</pre>
    </div>
  );
}
```

Props passed by the host: `pluginId`, `viewId`, `installations` (per-org enable rows), `token` (current user JWT). Use `token` when calling backend endpoints from the bundle.

---

## Calling backend from your plugin

Three options, in order of preference:

1. **Direct API call** to the public catalog or your vertical's endpoints:
   ```ts
   fetch('https://api.webrobot.eu/webrobot/api/sentiment/timeseries', {
     headers: { 'X-API-Key': /* never embed in bundle — see #3 */ },
   })
   ```
2. **Through the dashboard's proxy routes** under `/api/...` (when one exists for your vertical) — re-uses the user's session cookie automatically, no need to handle auth in the bundle.
3. **Server-side rendered data**: have the host pass it via props (you'd need a host-side change for this; not v1).

**Never embed credentials** in the bundle — it ships to every browser. Always proxy via the dashboard's API routes (which have the JWT) or use the user's `token` prop.

---

## Public catalog access — no auth

```ts
const res = await fetch('https://api.webrobot.eu/webrobot/api/catalog/stages?plugin_type=etl');
const { data } = await res.json();
// Useful for stage-pickers in your plugin's settings views
```

The catalog endpoint is public (read-only). Same coordinates the CLI / MCP server use.

---

## Local development workflow

1. Scaffold a Vite React-TS project:
   ```bash
   npm create vite@latest my-sentiment-ui -- --template react-ts
   cd my-sentiment-ui && npm i
   ```
2. Replace `vite.config.ts` with the lib-mode config above.
3. Write your views under `src/<View>.tsx`. Stick to default exports.
4. Build:
   ```bash
   npm run build
   ```
5. Package: zip `dist/` + your `manifest.json`:
   ```bash
   cp manifest.json dist/
   (cd dist && zip -r ../my-sentiment-ui.zip .)
   ```
6. Upload via the dashboard's plugins admin or via the CLI's `webrobot cli plugins install` (TODO: confirm CLI support; today the upload happens via Jersey API).
7. Toggle the plugin to enabled — the dashboard hot-loads it on the next page load.

The dashboard caches the ZIP for 1 hour in-memory. To force-refresh during dev: disable + re-enable the plugin (clears the cache).

---

## Common pitfalls

- **Bundle uses `import "react"` and fails to load**: you forgot to bundle React inline. Remove `rollupOptions.external` from your Vite config in v1.
- **Component doesn't mount, no error**: check `mod.default` exists. Named exports are tried in fallback order — use `default` to be explicit.
- **Auth errors when calling `/webrobot/api/...` from the bundle**: pass the `token` prop in the `Authorization` header, OR proxy through `/api/...` dashboard routes.
- **CSS not applied**: include CSS via `import "./styles.css"` in the entry — Vite inlines it into the JS bundle by default. External `<link>` tags don't reach the host.
- **Hot reload not working in dev**: the dashboard caches ZIPs 1h. Disable + re-enable the plugin to clear cache, or use the `static` plugin path (compile your component into the dashboard's bundle) for tighter dev loops.

---

## Roadmap (planned, NOT yet shipped)

- **v2 import maps** — share React between dashboard and plugin (`external: ['react', 'react-dom']` becomes valid; bundle drops to ~30KB).
- **v3 Module Federation** (Webpack 5) — full micro-frontend with hot reload, runtime React sharing, inter-bundle imports.
- **iframe sandbox** — for plugins from less-trusted authors who shouldn't share the host's origin.

When the user asks "can I share React with the host?" — the answer for v1 is "no, bundle it inline; v2 will add import maps."

---

## Rules of thumb

- **Always default-export** your view component. Named exports work but are fragile.
- **Never embed API keys** in the bundle source — proxy via dashboard routes or use the `token` prop.
- **Bundle ESM only** — no UMD, no CJS. The blob-URL `import()` only handles ESM in v1.
- **Keep views independent** — each view is loaded as a separate bundle, no shared state between bundles unless you go through the host.
- **Test with the actual host** — the local Vite dev server can't simulate the dashboard's render context (props, layout, theme, auth). Always validate against a deployed dashboard.

## On $ARGUMENTS

- If the user describes the plugin: scaffold the directory, write a starter `Overview.tsx`, fill in the `manifest.json`, configure Vite.
- If the user passes an existing plugin path: check the bundle/manifest contract and propose fixes.
- If unclear: ask whether the user is targeting v1 (React inline) or wants to wait for v2 (import maps).
