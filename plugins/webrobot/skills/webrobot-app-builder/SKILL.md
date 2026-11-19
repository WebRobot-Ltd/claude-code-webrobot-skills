---
name: "webrobot-app-builder"
description: "Design, validate and publish WebRobot vertical apps (App Studio / App Builder) — the VerticalApp manifest (agents, views, data, approvals, triggers, schedules, serviceHours, auth, branding, billing), the draft → validate → publish flow to <slug>.webrobot.eu, and the app-builder co-pilot. Use when the user wants to build or change an AI-agent web app served by WebRobot."
argument-hint: "[app description, or \"publish/validate app <slug>\"]"
user-invocable: true
---

# WebRobot App Builder (vertical apps)

A **vertical app** is a web app built around AI agents, described by one **VerticalApp manifest** and served by a
shared multi-tenant runtime at `https://<slug>.webrobot.eu` (plus custom domains). End users sign in by email link,
use the app's agents, and pay the tenant through Stripe Connect.

- UI: Cloud Dashboard › `/dashboard/app-studio` (apps list: `/dashboard/app-studio/apps`). Public docs: `https://www.webrobot.eu/docs/app-builder`.
- REST base: `https://api.webrobot.eu/api/webrobot/api/vertical-apps`. Auth: `X-API-Key` or `Authorization: Bearer <JWT>`.
- **The plugin MCP has no vertical-app tools.** Use the REST calls below (curl) or App Studio. Agent profiles the app
  creates are normal agentic profiles (see the `webrobot-agents` skill: `getProfile`, `status`, `executionLogs_1`).

## Flow

```
describe ─▶ co-pilot proposal ─▶ draft (inline agents) ─▶ validate ─▶ publish ─▶ <slug>.webrobot.eu
                                     │                                   │
                                     └─ preview-<slug>.webrobot.eu       └─ inline profiles → profile refs, app API key
```

| Step | What happens |
|---|---|
| Co-pilot | System profile `webrobot-app-builder`, started with `inputs: {goal: <description or change>, current_spec: <current manifest JSON or "{}">}`. Its result is ONE manifest JSON (or a question when it needs a detail). App Studio validates it, auto-retries once with the problems, then shows a diff to Apply. It never saves or publishes. |
| Save draft | `PUT /vertical-apps/{slug}/draft` `{manifest: "<JSON string>", layout?}`. Only the envelope is checked (`kind`, `apiVersion`, `metadata.slug` == path slug). First save claims the slug for the org (409 *slug already taken* otherwise) and routes the preview. |
| Preview | `https://preview-<slug>.webrobot.eu` = the saved draft, admins only. Agents do **not** run (*publish the app first*), payments and webhooks off, separate data. |
| Validate | JSON Schema + reference checks (`validateManifest` in `webrobot-vertical-kit`). Publish refuses any error; warnings do not block. |
| Publish | App Studio **Publish** (or console `POST /api/vertical-apps/{slug}/publish`): validate → create/update one agent profile per inline agent (`<slug>-<agent key>`), one per team (`<slug>-team-<key>`), apply inline pipelines (project `<slug>`, job `<slug>-<key>-job`), first publish only: app API key + cloud credential `vertical-app-<slug>` → validate again → store with `profile: {ref: <id>}` → version +1 → route `<slug>.webrobot.eu`, preview and `spec.domains`. |

Publishing **must** go through the materialising step. The bare Jersey `POST /vertical-apps/{slug}/publish`
`{manifest, publishState, runtimeCredentialId}` stores whatever it gets: a manifest that still has `profile.inline`
would be published with agents that cannot run. Supported ways:
1. App Studio **Publish** (recommended).
2. The publish script of the `webrobot-vertical-kit` repository (`scripts/publish-file.mts`, see that
   repository's README): draft → materialise → publish, same gate as App Studio.

Roles: developer = save drafts + publish updates; **admin** = first publish (creates the app key), payments, export,
delete; super_admin = transfer to another org. A developer's first publish fails at step `api key:`.

## REST

```bash
API=https://api.webrobot.eu/api/webrobot/api; H="X-API-Key: <key_id>:<secret>"
curl -s "$API/vertical-apps" -H "$H"                                   # org's apps: slug, publishedVersion, hasDraft, url, previewUrl, domains
curl -s "$API/vertical-apps/visit-brief" -H "$H"                       # draftManifest, publishedManifest, publishState (strings)
jq -n --rawfile m app.json '{manifest:$m}' | \
  curl -s -X PUT "$API/vertical-apps/visit-brief/draft" -H "$H" -H 'Content-Type: application/json' -d @-   # save draft (manifest = JSON text)
curl -s "$API/vertical-apps/visit-brief/hook-secret?key=new_lead" -H "$H"   # secret + URL for a webhook trigger
curl -s "$API/vertical-apps/visit-brief/mcp-token" -H "$H"             # token for the app's MCP endpoint <slug>.webrobot.eu/api/mcp
curl -s -X DELETE "$API/vertical-apps/visit-brief" -H "$H"             # admin: stop serving, revoke app key; profiles/jobs stay
```

The stored manifest is **JSON**; convert YAML before saving (`yq -o=json app.vertical.yaml > app.json`). Do not
convert with PyYAML's default loader: YAML 1.1 turns the triggers' `on:` key into `true`.
Slug: `^[a-z][a-z0-9-]{1,38}[a-z0-9]$` (3–40 chars), fixed after the first save. Keys: lower case, digits, `_`, `-`.

## Manifest shape

```yaml
apiVersion: webrobot.eu/v1alpha1      # exact
kind: VerticalApp                     # exact
metadata: { slug, displayName, tagline?, description?, langs?, defaultLang?, timezone? }   # slug + displayName required
spec:                                 # pattern + agents required; unknown keys are errors
  pattern: report | chat | dashboard | pipeline
```

| `spec` key | Purpose |
|---|---|
| `agents[]` | `key`, `role` (main/helper/scheduled/analyst/designer/setup), `profile: {inline: <agent_definition>}` or `{ref: <profileId>}` (exactly one), `goalTemplate`, `output`, `appTools`, `mcpServers`, `delegates`, `awaits`, `memory`, `writesTo`, `context`, `when`, `limits` |
| `teams[]` | `mode: sequence` (`steps[{agent, after?}]`, acyclic) or `swarm` (`lead`, `members`); members must be inline agents |
| `inputForm` | `fields[]` (`name`, `type`, `required`, `options`, `dependsOn`…) for `report` runs |
| `views[]` | `type`: new_run, run, history, report, chat, review, table, cards, chart, dashboard, tabs, account, admin, page, list, approvals, instances; `source`: `run`, `agent:<k>`, `collection:<c>`, `job:<j>`; `roles`, `nav` |
| `data` | `collections[]` (`name`, `ownedBy`: user/instance/app/shared/org, `fields`), `jobs[]` (ETL pipelines: `pipeline.ref/inline`, `schedule`, `ingestTo`) |
| `auth` | `method: magic_link`, `roles[]` (`assignedBy`: admin_emails/admin/signup/invite/derived), `anonymous: {views, agents}` |
| `approvals[]` | human checkpoints: `key`, `role` (a staff role, never the signup role) or `decidedBy: requester`, `timeoutMinutes`, `onTimeout`; an agent must list it in `awaits` |
| `triggers[]` | `on`: exactly one of `cron` / `collection` (+`op`, `where`) / `webhook` / `payment` / `approval` / `call`; `start`: exactly one of `agent` / `team` / `job`; `goal` |
| `schedules[]` | `cron` (UTC), `agent` or `job`, `action`, `owner: app` (runtime cron) or `platform` (`scheduleAgentic`) |
| `templates[]` | per-user agent instances (`agent`, `params`, `schedule`), shown by an `instances` view |
| `serviceHours` | see the cost warning below |
| `billing` | `modes` (free/credits/subscription/per_transaction), `signupCredits`, `costs` (`agent:<key>`: credits), `packs`, `plans`, `metering`, `platformFeePct` |
| `branding`, `header`, `limits`, `channels`, `slots`, `egress`, `notifications`, `exports`, `mobile`, `domains`, `host`, `extensions` | look, rate limits, phone/voice, Python code slots, allowed outbound hosts, custom domains, … |

`goalTemplate` placeholders: form fields `{field}` and `{field_label}`, built-ins `{message}`, `{history}`, `{lang}`,
`{date}`, `{user}`, `{goal}`…; optional block `{?notes}…{/notes}` (must be closed).

**`serviceHours` costs money.** During these hours the org's **dedicated chat host VM is kept on** (started
`leadMinutes`, default 10, before each slot) so chat answers arrive in the same request. The VM runs — and costs the
org — for the whole slots, whether or not anyone chats; usage of messages answered there is metered to the org, not
charged to end users in credits. Outside the slots each chat message is one ordinary agent run.
Add it only for apps that need instant answers, with the narrowest slots.

```yaml
  serviceHours:
    timezone: Europe/Rome            # default: metadata.timezone, else Europe/Rome
    slots:
      - { days: [1, 2, 3, 4, 5], from: "09:00", to: "18:00" }   # 1 = Monday … 7 = Sunday
```

## Minimal manifest (validates)

```yaml
apiVersion: webrobot.eu/v1alpha1
kind: VerticalApp
metadata:
  slug: visit-brief
  displayName: Visit Brief
  tagline: A one-page pre-visit summary from the patient's own words.
  langs: [en]
  defaultLang: en
  timezone: Europe/Rome

spec:
  pattern: report

  branding:
    theme: light
    palette: { primary: "#14324a", accent: "#c0522b", background: "#faf7f2", foreground: "#1b1f24" }

  auth:
    method: magic_link
    anonymous: { views: [home] }
    roles:
      - { key: admin, assignedBy: admin_emails }
      - { key: user, assignedBy: signup }

  limits:
    - { action: run, per: user, max: 10, window: day, roles: [user] }

  agents:
    - key: writer
      role: main
      description: Turns the patient's notes into a structured pre-visit summary.
      profile:
        inline:
          display_name: Visit Brief writer
          crews:
            - id: writer
              engine: agent_sdk
              model: claude-sonnet-5-5
              max_turns: 4
              max_budget_usd: 0.3
              permission_mode: bypassPermissions
              disallowed_tools: [Bash, Read, Write, Edit, Glob, Grep, NotebookEdit, WebFetch, WebSearch]
              system_prompt: >-
                You write a one-page pre-visit summary for a physiotherapist. Title "# Pre-visit summary".
                Sections: ## Complaint, ## History, ## Red flags to check, ## Questions for the visit.
                Under 300 words. Never diagnose; say plainly what is missing.
      goalTemplate: |-
        Body area: {area_label}
        Patient notes: {notes}
        Write the summary in the language with ISO code {lang}.
      output: markdown

  inputForm:
    title: New summary
    fields:
      - name: area
        type: select
        required: true
        label: Body area
        options:
          - { value: back, label: Back }
          - { value: knee, label: Knee }
          - { value: shoulder, label: Shoulder }
      - { name: notes, type: textarea, required: true, maxLength: 1500, label: What happened and how it feels }

  views:
    - key: home
      type: page
      nav: false
      content: "# Visit Brief\nDescribe your problem before the visit: you get a one-page summary to bring along.\n\n[Sign in to start](/login)"
    - { key: new, type: new_run, title: New summary, roles: [user, admin] }
    - { key: history, type: history, title: My summaries, source: run, roles: [user, admin] }
    - { key: report, type: report, source: run, printable: true, nav: false }
    - { key: account, type: account, title: Credits, roles: [user] }

  billing:
    modes: [credits]
    signupCredits: 50
    costs:
      agent:writer: 10
    packs:
      - { key: small, credits: 200, price: 5 }
```

Optional blocks that also validate when added to `spec` of this app (with a second agent `digest`, `role: scheduled`,
`awaits: [refund]`, inline profile):

```yaml
  schedules:
    - { agent: digest, cron: "0 7 * * 1", goal: "Summarise last week's visit briefs for the clinic." }
  approvals:
    - { key: refund, title: Refund request, role: admin, fields: [reason, amount], timeoutMinutes: 1440, onTimeout: reject }
  triggers:
    - key: new_feedback
      on: { collection: feedback, op: insert }
      start: { agent: digest }
      goal: "New feedback {record.id}: {record.text}. Classify it in one line."
  data:
    collections:
      - { name: feedback, ownedBy: org, fields: [{ name: text, type: text }] }
```

## Common validation errors

| Message | Fix |
|---|---|
| `/spec: must NOT have additional properties` | typo or unknown key in `spec` |
| `/spec/agents/0/profile: must match exactly one schema in oneOf` | keep exactly one of `ref` / `inline` |
| `view <v>: unknown source '<src>'` | declare the agent / collection / job it names |
| `approval <a>: the approver role '<r>' is given at signup` | use an `admin_emails`/`admin`/`invite`/`derived` role, or `decidedBy: requester` |
| `approval <a>: no agent awaits it` | add it to an agent's `awaits` |
| `trigger <t>: <agent> writes <coll>, which starts it — add a where filter` | add `on.where` or use `op: update` |
| `agent <a>: tool <n> calls <host>, which is not in spec.egress.hosts` | add the host to `spec.egress.hosts` |
| `data.collections: '<c>' is a reserved name` | rename (users, runs, chats, sessions, memory, … are reserved) |
| `team <t>: agent <a> must be inline to be part of a team` | inline the member's profile |

References: `webrobot-vertical-kit/schema/vertical-app.schema.json`, `examples/city-brief.vertical.yaml` (report + templates),
`examples/ristorante.vertical.yaml` (chat, serviceHours, appTools, approvals, triggers, slots).
