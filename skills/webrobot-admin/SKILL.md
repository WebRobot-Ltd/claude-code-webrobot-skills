---
name: webrobot-admin
description: Manage WebRobot resources — projects, jobs, executions, agents, datasets, cloud credentials, LLM providers. Use when the user wants to list, create, delete, execute, or inspect any WebRobot entity.
argument-hint: [entity type and action, e.g. "list jobs for project X" or "stop execution Y"]
user-invocable: true
allowed-tools: mcp__webrobot__auth_me mcp__webrobot__list_projects mcp__webrobot__get_project mcp__webrobot__create_project mcp__webrobot__delete_project mcp__webrobot__list_jobs mcp__webrobot__get_job mcp__webrobot__create_job mcp__webrobot__delete_job mcp__webrobot__execute_job mcp__webrobot__stop_job mcp__webrobot__list_executions mcp__webrobot__get_execution_logs mcp__webrobot__list_categories mcp__webrobot__list_agents mcp__webrobot__get_agent mcp__webrobot__create_agent mcp__webrobot__get_agent_code mcp__webrobot__list_datasets mcp__webrobot__delete_dataset mcp__webrobot__list_cloud_credentials mcp__webrobot__list_llm_providers mcp__webrobot__llm_infer
---

# WebRobot Administration

You are an expert in WebRobot platform administration. Help the user manage all platform resources efficiently.

## Entity hierarchy

```
Organization
└── Projects
    └── Jobs
        └── Executions (logs, status)
Categories
└── Agents (browser automation agents)
Datasets (input/output data files)
Cloud Credentials (API keys, storage, LLM)
```

## Common administration tasks

### Viewing current state
- Start with `auth_me` to confirm who is authenticated and what org they belong to.
- Use `list_projects` to see all projects, then `list_jobs` for a specific project.
- Use `list_executions` to see recent runs for a job.

### Running a job
1. `list_projects` → pick project ID
2. `list_jobs(project_id)` → pick job ID
3. `execute_job(project_id, job_id)` → get execution ID
4. `get_execution_logs(project_id, job_id, execution_id)` → check output

### Monitoring
- `list_executions` returns status for all runs — look for `status: RUNNING`, `FAILED`, `COMPLETED`.
- If a job is stuck: `stop_job(project_id, job_id, execution_id)`.
- Always show execution status and timestamps clearly.

### Agent management
- Agents belong to categories. Always `list_categories` first to get category IDs.
- `list_agents(category_id)` lists agents in that category.
- `get_agent_code` returns the Python extension code (useful for debugging or customization).

### Dataset management
- `list_datasets` with optional `project_id` filter.
- Datasets have types: `input` (uploaded CSV/JSON for pipeline) or `output` (pipeline results).
- Deletion is permanent — confirm with user before calling `delete_dataset`.

### Cloud credentials
- `list_cloud_credentials` shows all configured credentials (LLM providers, cloud storage, etc.).
- These are managed in the WebRobot admin panel; you cannot create/update them via API here.

### LLM providers
- `list_llm_providers` shows which LLM providers are available (have credentials configured).
- `llm_infer(prompt)` lets you test the LLM endpoint or generate content.

## Partner program & marketplace billing (added May 2026)

The partner program is **invitation-only**. Offline KYC happens before
the invite is sent; the platform records the outcome on the
`organization` row. MFA TOTP is **mandatory** for `super_admin`,
`tech_provider`, `cloud_provider`, and `admin` roles — login does NOT
issue a full JWT until MFA is confirmed.

### Partner onboarding lifecycle
Resources mostly managed via the Strapi REST API + super_admin UI;
useful curl reference for ops:

| Step | Endpoint / surface |
|------|---------------------|
| Invite | `POST /api/user-invites` (Strapi) — role can be any of `tech_provider`, `cloud_provider`, `referral_agency`, `marketing_agency`, `semi_managed_agency`, `white_label_agency`, `browser_provider`, `proxy_provider` |
| Accept | `POST /api/user-invites/accept/:token` (public) |
| KYC record (super_admin) | `PUT /api/organizations/:id` with `kyc_completed_at`, `kyc_method` (offline / stripe_identity / sumsub / onfido), `business_registration_number`, `vat_number`, `iban`, `kyc_notes` (super_admin internal) |
| Stripe Connect onboarding | `POST /api/partners/tech-provider/stripe-connect/connect` — Express account; partner returns to dashboard after Stripe collects details |
| MFA enroll (any logged-in user) | `POST /api/mfa/enroll` → returns base32 secret + QR + 8 recovery codes |
| MFA confirm | `POST /api/mfa/confirm-enroll` `{ token: "123456" }` |
| MFA challenge (login flow) | `POST /api/mfa/challenge` `{ mfa_token, code }` |
| MFA disable | `POST /api/mfa/disable[/:userId]` (self or super_admin reset) |

### Audit trail (`partner-audit-events`)
Append-only log of every partner lifecycle event. 16 event types:
`partner_invited` / `partner_accepted` / `partner_kyc_started` /
`partner_kyc_verified` / `partner_kyc_rejected` /
`partner_stripe_connect_started` / `partner_stripe_connect_completed` /
`partner_stripe_disconnected` / `partner_first_bundle_uploaded` /
`partner_bundle_approved` / `partner_bundle_rejected` /
`partner_suspended` / `partner_reactivated` /
`partner_mfa_enrolled` / `partner_mfa_disabled` / `partner_mfa_reset` /
`partner_bundle_payout_created` / `customer_charge_created` /
`customer_charge_paid` / `customer_charge_failed`.

Read with `GET /api/partner-audit-events?filters[organization]=:id&sort=createdAt:desc`.

### Marketplace billing
Two K8s CronJobs run end-of-month against Jersey:
- `monthly-run-charges` (day 5) creates one Stripe Invoice per
  `(customer × currency)` with one `InvoiceItem` per plugin used in
  the previous month.
- `monthly-run-payouts` (day 12) transfers each tech_provider's net
  share via Stripe Connect.

Endpoints (all `RequiresScopes("super_admin")`):
- `POST /webrobot/api/admin/marketplace-billing/run-charges?period=YYYY-MM&dryRun=true|false`
- `POST /webrobot/api/admin/marketplace-billing/run-payouts?period=YYYY-MM&dryRun=true|false`
- `GET  /webrobot/api/admin/marketplace-billing/charges?period=YYYY-MM`
- `GET  /webrobot/api/admin/marketplace-billing/payouts?period=YYYY-MM`
- `POST /webrobot/api/admin/marketplace-billing/charges/by-invoice/{invoiceId}/mark-paid` (called by Stripe webhook)
- `POST /webrobot/api/admin/marketplace-billing/charges/by-invoice/{invoiceId}/mark-failed?reason=...`

**Always run `dryRun=true` first** — produces the would-be invoices /
transfers without hitting Stripe. Tables `marketplace_charges` and
`marketplace_payouts` are populated either way (status `dry_run`).

### Price comparison plugin

The price comparison plugin exposes domain endpoints under `/webrobot/api/price-comparison/`. Use `curl` or the platform API client — these are not MCP tools.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/bootstrap` | Create ETL project + agents for the calling org (one-time setup) |
| GET | `/products` | List monitored EAN catalog |
| POST | `/products` | Add EAN: `{"ean":"...", "product_name":"...", "brand":"...", "image_url":"..."}` |
| DELETE | `/products/{ean}` | Remove EAN from catalog |
| GET | `/competitors` | List active competitor domains |
| POST | `/competitors` | Add competitor: `{"site_domain":"amazon.it", "site_name":"Amazon Italy", "country_code":"IT"}` |
| DELETE | `/competitors/{id}` | Soft-delete competitor |
| POST | `/jobs/discovery` | Run phase 1: search → match → persist URLs. Body: `{"cloudCredentialIds":["uuid"]}` |
| POST | `/jobs/monitoring` | Run phase 2: re-fetch prices from saved URLs |
| GET | `/prices` | Current prices (`?ean=&competitor_site=&limit=200`) |
| GET | `/matches` | Confirmed product matches (`?ean=&competitor_site=`) |

Typical setup sequence:
1. `POST /bootstrap` — creates project + discovery + monitoring agents for the org
2. `POST /products` × N — populate EAN catalog
3. `POST /competitors` × N — add competitor domains
4. `POST /jobs/discovery` — run phase 1, passing cloud credential IDs for GROQ + Google Search
5. `GET /matches` — verify match confidence scores
6. `POST /jobs/monitoring` — run phase 2 to collect prices
7. `GET /prices` — query current prices

## Output formatting

When listing resources, always present them in a clear table or list with:
- ID (for use in subsequent commands)
- Name
- Key status field (e.g., execution status, creation date)

Always copy relevant IDs into your response so the user can use them in follow-up commands.

## Safety rules

- **Never delete** a project or job without explicit user confirmation ("please delete project X").
- **Never stop** a running execution without being asked.
- If the user asks to "clean up" or "remove everything", list what would be deleted first and ask for confirmation.
