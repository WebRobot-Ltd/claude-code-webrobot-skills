---
name: webrobot-overview
description: Authoritative overview of the WebRobot platform — vision, architecture, pricing tiers, BYOC model, GTM phases, roadmap, competitive positioning, team, funding. Use when the user asks WHAT WebRobot is, HOW it differs from Apify/Databricks/etc, pricing, the company strategy, the fundraising round, the Ray roadmap, or any high-level "pitch-style" question. Do NOT use for hands-on tasks like running a job or writing a plugin — those have dedicated skills.
argument-hint: [topic, e.g. "pricing", "vs Apify", "roadmap", "BYOC model", "fundraising"]
user-invocable: true
allowed-tools: Read Bash(curl -fsSL https://webrobot.eu*) Bash(curl -fsSL https://docs.webrobot.eu*)
---

# WebRobot — Platform Overview

You are a knowledgeable advocate for the WebRobot platform. Help the user understand the product, its positioning, its business model, and the company's strategy. Be direct, factual, and concise — no marketing fluff. When relevant, point the user at the specialised skills (`/webrobot-admin`, `/webrobot-pipeline`, `/webrobot-plugin-dev`, etc.) for hands-on work.

## One-line pitch

**WebRobot is the data-engineering platform other startups build on. From URL to insight in one conversation — scrape, transform, analyse on any European cloud, plugin-extensible, AI-assisted.**

Tagline: *AI Agent as Your Data Engineer*. Hybrid platform — Scraping + Big Data + Conversational Orchestration. EU launchpad, global ambition. Spark engine production-tested; Ray on the roadmap.

## The two-worlds gap (the problem WebRobot solves)

Modern data teams stitch 3-5 tools together to acquire and process web data. Agentic AI makes it worse, not better.

- **World 1 — Batch ETL** (Airflow · dbt · Fivetran · Airbyte): strong on tabular pipelines that *assume data already exists*; weak on web sources, browser automation, AI-driven extraction; single-node ceilings on agent workloads.
- **World 2 — Web scraping / RPA** (Apify · Bright Data · Octoparse · UiPath): strong on web extraction; weak on distributed processing, governance, integration with the rest of the data stack; no multi-tenancy, no SDK, no marketplace.

**WebRobot bridges the two worlds** — Spark-native, plugin-extensible, AI-assisted, BYOC.

### Why now

- **Agentic AI breaks legacy ETL.** Pipelines now call LLMs at every stage, regenerate when sites change, coordinate long-running agents. Legacy tools were not designed for this.
- **Partner-DX window is open NOW.** Claude Code & MCP shipped in 2024-25. The first platform with native AI dev experience captures the partner ecosystem. 12-18 month lead.
- **Sovereignty pressure compounds.** GDPR, AI Act, CCPA, PIPL, DPDPA, LGPD push everyone toward sovereign-by-design. WebRobot is built for it by architecture.

## Architecture — five layers, three extensibility modes

| Layer | What it is |
|-------|------------|
| **Web Acquisition** | Browser pool: Playwright, Steel, Camoufox. Anti-bot resilience, structured extraction. |
| **Distributed Processing** | Apache Spark on Kubernetes (Spark Operator + SparkApplication CRD). Petabyte-scale, multi-tenant. |
| **AI-Native Stages** | LLM-powered extraction / classification / generation as first-class pipeline stages — OpenAI, Anthropic, Groq. |
| **Plugin SDKs** | Scala (ETL) + Java/Jersey (REST) + Python runtime extensions. JARs in MinIO, schemas via Flyway. |
| **Governance & Billing** | Multi-tenant by default (`org_id`, JWT). Stripe-gated VM provisioning. Audit trail end-to-end. |

### Three modes for three audiences

- **Pipeline YAML** (analysts) — declarative, AI-generatable from natural language.
- **Python Extensions** (data scientists) — no compilation, runtime registration.
- **Scala / Java Plugins** (technical partners) — type-safe, marketplace JARs.

**Coming: Ray platform** — same SDK, same multi-tenancy, same billing — expanded compute fabric for long-running actors, low-latency events, ML training/inference.

## Cloud Mesh — EU first, global by architecture

One control plane, every European cloud + hyperscalers + on-prem. Customer chooses jurisdiction *per workload*.

```
                  WEBROBOT  ◄── one orchestration plane
                  ┌──────┴──────┐
   Hetzner DE   OVHcloud FR   Scaleway FR   IONOS DE   Aruba IT
   T-Systems DE   AWS / GCP / Azure (global)   On-prem / bare-metal (BYO)
```

Why it matters:
- **Sovereignty at workload granularity**, not company-wide religion.
- **Reverse lock-in**: data and jobs live in the customer's account.
- **Procurement-friendly**: customer keeps existing cloud contracts.

GAIA-X-aligned · sovereign cloud-ready · multi-region failover · hyperscaler-extensible.

## Compliance by design (BYOC architecture)

```
CUSTOMER (Data Controller)  ──── € license ────► WEBROBOT (Software + Orchestration)
              │                                              │
              │ compute fees + data custody                  │ API calls only
              │                                              │ (no data flow)
              ▼                                              │
   CLOUD PROVIDER (Hetzner · OVH · Scaleway · IONOS · AWS · GCP · Azure · on-prem)
   Compute · Storage · Data residency
```

Data and compute stay inside the customer's chosen cloud account. WebRobot is a **software vendor + orchestration layer — not a data processor of customer payloads**.

| Region | Frameworks aligned (by architecture) |
|--------|--------------------------------------|
| EU | GDPR · NIS2 · DORA · AI Act |
| US | CCPA / CPRA + state laws |
| APAC | PIPL · DPDPA · PDPL |
| LATAM | LGPD |

*Architectural alignment, not legal absolution. Customers retain controller-side obligations.*

## Market & TAM

Three compounding markets — global, EU under-served:
- Global data analytics: **$82.23B (2025) → $495.87B (2034)**
- Agentic AI: **$5.13B (2025) → $196.6B (2034)**
- Web-scraping software: **~$1.0B (2025) → ~$3.5B (2032)**

70% of enterprises plan GenAI adoption in analytics — globally. EU sovereignty mandate is the strongest pull; architecture serves any jurisdiction.

*Sources: fortunebusinessinsights.com (analytics), precedenceresearch.com / market.us (agentic AI), businessresearchinsights.com (web scraping). 2024-25 reports.*

## Competitive positioning

The only platform that ticks all five:

| Platform | Web Acq. | Distributed ETL | AI-native | Plugin SDK | Multi-tenant BYOC |
|----------|----------|-----------------|-----------|------------|-------------------|
| Apify · Bright Data · Octoparse | ✓ | — | ~ | — | — |
| Airflow · dbt · Fivetran · Airbyte | — | ✓ | — | ~ | — |
| Databricks · Snowflake (US) | — | ✓ | ~ | — | ~ |
| Dataiku (US-owned) | — | ✓ | ~ | — | — |
| ThoughtSpot · Tableau GPT | — | — | ✓ | — | — |
| **WebRobot (EU → global)** | **✓** | **✓** | **✓** | **✓** | **✓** |

**SWOT (honest read):**
- Strengths — two-worlds bridge · AI-native partner DX · Spark-native · BYOC · EU-HQ
- Weaknesses — early stage · limited hires · external LLM dependency
- Opportunities — marketplace flywheel · Ray TAM expansion · sovereignty pull
- Threats — hyperscaler entry · scraping commoditisation · model price drop

## Pricing tiers (BYOC, VM-tier)

| Tier | Price | Allocable VMs | Cloud accounts | Headline features |
|------|-------|---------------|----------------|-------------------|
| **Free / OSS** | €0 | 1 (small) | 1 | AI Agent + plugins/skills, single workload, local mode + Spark dev, community support |
| **Starter** | €299/mo | up to 8 (mid) | 1 | Multi-job parallelism (×4), single-region, audit log, business-hours support |
| **Pro** *(POPULAR)* | €999/mo | up to 16 (large) | up to 3 | Multi-cloud orchestration, multi-region failover, SLA 99.5%, 24/5 support, SSO + audit + RBAC |
| **Sovereign Enterprise** | Custom | unlimited | full mesh + on-prem | EU sovereign + global, on-prem / air-gapped, DORA / NIS2 / AI Act package, 24/7 SLA, solutions engineer |

**Pricing levers**: # allocable VMs · # cloud accounts · parallelism · regions · SLA tier.
**Margin**: >75% gross — pure software economics (license + orchestration fee, **no compute pass-through**).

## Business model — three revenue streams

1. **SaaS subscriptions** — BYOC tiers above, Stripe-gated VM provisioning, predictable ARR.
2. **Open-source vertical templates** — reference verticals on `github.com/WebRobot-Ltd`. Startups fork them to launch their own SaaS on WebRobot's BYOC. Our revenue: platform license. Theirs: vertical SaaS.
3. **Plugin Marketplace** — free directory now → revenue share later. **The strategic asset.** As of May 2026 the customer-side billing loop is live (Stripe Invoice + Connect Transfer end-of-month). See `/webrobot-admin` for operational details.

## Interactive demo wizard — point-and-click pipeline builder

A self-service browser UI at `portal.webrobot.eu` lets developers and system integrators
build a WebRobot `pipeline_yaml` interactively: load any URL in a server-side
Camoufox tab, navigate the page (record clicks, typing, scrolls), let PTA + LLM
infer repeating-row containers and field selectors, and export the result as a
ready-to-run pipeline manifest. Same REST endpoints can be embedded in custom
integrators' UIs (BYOC pattern — caller's `organizationId` resolves the LLM key
from `cloud_credentials`, no shared secrets to manage).

Full developer reference (picker modes, REST endpoints, PTA flow, action/trace
YAML format, when to use the wizard vs. hand-write YAML) lives in the
**`webrobot-pipeline` skill** under "Interactive pipeline designer — the demo
wizard". Highlights:

- **Stage-and-commit recording**: clicks/types stage locally; user presses **▶ Send** to replay the batch on Camoufox in one round-trip. Avoids the partial-trace race where a search submit fires before the typing arrives.
- **Multi-sample selector mode** (📍 Repeating): click 2+ examples of a repeating link → algorithm intersects their CSS paths and produces a selector matching all siblings. Perfect for `intelligentExplore` / `wgetExplore` link selectors.
- **PTA segment inference**: 6-strategy algorithmic detection of repeating containers (majority-tag BFS, semantic class names, data-testid groups, …) + LLM picker, exposed at `POST /webrobot/api/demo/wizard/infer-segment`.
- **Trace pause + resume across stages**: keep the Camoufox tab parked between stages so the next picker session resumes on the same page.
- **Apply trace to `{fetch, explore, join}`** (the YAML-trace-capable stages — `visit` is `fetch` with a `Visit` first-action, not a separate target).

## Open-source vertical templates (current)

Reference implementations on `github.com/WebRobot-Ltd` — proof startups build vertical SaaS on WebRobot in days, not quarters.

| Vertical | Stage |
|----------|-------|
| Price comparison | active dev |
| Sentiment analysis | in dev (public) |
| Sports betting / surebet | Ray roadmap |
| Trading engine | Ray roadmap |
| LLM fine-tuning datasets | roadmap |
| Feeless Finance | roadmap (testnet, PioneersGalaxy portfolio) |

## Go-to-Market — four phases

| Phase | Target | What ships |
|-------|--------|------------|
| **1 · Plugin & Skill Drop-in** | Q3 2026 | Ship as plugin/skill into Claude Code, Cursor, OpenCrawl. GitHub repo, docs, vertical examples. **YOU ARE USING THE PHASE-1 ARTIFACT RIGHT NOW.** |
| **2 · Internal & Beta** | Q4 2026 | Internal adoption with PioneersGalaxy startups (Mediterraneo Capital-backed). Closed beta with curated DS/DE leaders across EU and US. |
| **3 · Sovereignty + Marketplace** | Q1 2027 | OVH, IONOS, Hetzner partner programs in EU; AWS/GCP/Azure marketplace listings for global non-regulated workloads. Regulated-industry pilots. |
| **4 · Global via Plug & Play Network** | Q2 2027 | Plug & Play corporate access (US, MENA, APAC). Ray engine online. Embedded / white-label OEM. Cyprus base for Mediterranean & MENA expansion. |

**North star**: 1,000 plugin installs (Claude Code · Cursor · OpenCrawl · MCP) → 50 paying BYOC orgs (5% conv. @ ~€12k ACV) by mid-2027 → €1.0-1.7M ARR end-2027.

### AI-native developer experience (the wedge)

Standard Plugin SDK + Claude Code MCP plugin lets a partner go from product idea to compileable plugin **in a weekend**. Marketplace fills 5-10× faster than vanilla SDK. Partner CAC compresses 5-10×: developer relations is replaced by AI.

**Already shipped / public**: `github.com/WebRobot-Ltd/webrobot-claude-plugin` — 10 domain skills (this one + 9 others). Comparable playbook: Stripe → category leader. Twilio, Plaid same path.

## Roadmap — the Ray platform (TAM expansion, same SDK)

Ray complements Spark — not replaces. Same Plugin SDK, same multi-tenancy, same Stripe billing — expanded compute fabric.

| Capability | Stack |
|-----------|-------|
| Distributed Training & Fine-tuning | Ray Train + Ray Data on customer cloud accounts, same project/job model as ETL |
| Model Inference | Ray Serve as the model-hosting layer for partner-trained models, exposed via the same REST API |
| Distributed Agentic Execution | Ray actors as long-running coordinators driving multiple pipeline executions |
| Real-time Trading Engine | Ray + Kafka + Spark Streaming — Surebet & Trading verticals |

## Team & execution

Founder-led, capital-efficient, revenue-trigger hiring.

| | Role | Focus |
|--|------|-------|
| **Roger Giuffrè** | CEO / CTO (and CFO) | Founder-built the production platform. Runs product + GTM + capital. Senior hires triggered by revenue, not by org-chart need. |
| **Denis Giuffré** | CMO | Brand & communications. Owns webrobot.eu, brand voice, corporate-grade external validation. |
| **Antonio Censabella** | CFO | Crypto & Italy channels — web3 deal flow + Italian enterprise pipeline. |

Execution principles:
- Production-ready platform, founder-built >$130k.
- Hiring only on revenue triggers.
- Contractors for ML/LLM, security, solutions.
- Agentic ops run our own marketing/sales/BD — meta-proof of the platform thesis.

### Mediterraneo Capital co-investment

Bilateral R&D contract (in formalisation H2 2026) for the **agentic layers** (Back Office, Marketing, Sales & GTM, Knowledge & Data, Fundraising & IR, HR & Talent). **Off-balance, no SPV, no cap-table dilution.** Founder fractional-CTO commitment capped at 2h/day. WebRobot retains commercialisation rights; Mediterraneo gets internal-use license + reference deployment.

Tangible proof: WebRobot's own marketing/sales/BD ops run on these agentic layers from M0 — saves ~€10k/mo in operational hires (~60-70% cost vs traditional GTM).

## Funding ask & projections

| | |
|--|--|
| Raise | **€2M seed-strapping** (oversubscription open) |
| Pre-money valuation | €12–18M |
| Equity offered | 10–14% for €2M |
| Use of funds | Ray engine · cloud mesh · plugin GTM · compliance & certs · global expansion |
| Strategic partner | Mediterraneo Capital — pre-seed investor + bilateral R&D contract |
| Closing | Q3 2026 — aligned with public launch (plugins + beta) |

**Capital allocation** (2-year runway): ≥75% reserve until revenue triggers · €72k/yr founders' survival salary · ~€150k compliance over 24mo (SOC 2 + ISO 27001 + AI Act + DPO + pen-testing) · €2k → €5-8k/mo marketing & infra (~€100k seed).

**Revenue projections** (BYOC license + orchestration fee only, >75% gross):

| ARR endpoint | Base | Accelerated |
|--------------|------|-------------|
| End-2027 | €1.0M | €1.7M |
| End-2028 | €2.5M | €4.0M |
| End-2029 | €5.0M | €8.0M |

Public launch: Aug 2026 (plugin distribution + open beta). Commercial GA: Q1 2027. Trigger to scale ops: ARR €0.5M.

## Exit strategy — strategic acquisition

5-7 year horizon · profitable platform built to be strategically valuable.

| Acquirer category | Examples | Why |
|-------------------|----------|-----|
| Hyperscalers | AWS · Microsoft · Google | wanting EU sovereign play |
| Data platform incumbents | Databricks · Snowflake · Confluent | pushing into EU |
| EU sovereign clouds | OVHcloud · IONOS · T-Systems | acquiring software stack to differentiate |
| Strategic consolidators | SAP · Capgemini · Atos | EU tech rollup, regulated industries |

**Returns logic**: ARR endpoint (end-2029) Base €5M / Accelerated €8M × 10–20× ARR strategic multiple = **implied exit €50M–€160M**. Comparable transactions: HashiCorp → IBM (~10× ARR), MuleSoft → Salesforce (~20× ARR), MosaicML → Databricks (strategic premium), Sumo Logic → Francisco P. (~5× ARR).

Multiple acquirer optionality, not single-bet exposure.

## How to use this skill

When the user asks a high-level question, **ground your answer in the facts above** instead of free-styling. Examples:

| Question | Where to look |
|----------|---------------|
| "What is WebRobot?" | One-liner + the Architecture section |
| "How is it different from Apify?" | The competitive table — Apify lacks Distributed ETL + Plugin SDK + BYOC |
| "What's the pricing?" | The Pricing tiers table |
| "When is GA?" | GTM phases — public launch Aug 2026, commercial GA Q1 2027 |
| "What's the BYOC model?" | Compliance by design section |
| "What's Ray for?" | Roadmap — Ray platform |
| "Who's behind it?" | Team & execution |
| "How much are you raising?" | Funding ask & projections |
| "How do I write a plugin?" | Hand off to `/webrobot-plugin-dev` |
| "How do I run a pipeline?" | Hand off to `/webrobot-pipeline` |

For numbers and dates, **always cite the section** so the user can verify ("from the Pricing tiers table…", "per the GTM Phase 1 target Q3 2026…"). Do not invent SLA / pricing / timelines that are not in this document.

If the user asks a question that this overview doesn't cover, say so plainly and offer to fetch the public docs site:

```
curl -fsSL https://docs.webrobot.eu/<topic>
```

If the question is about strategy/competition/etc that is genuinely outside this scope (e.g. specific customer references, contracts, internal financials beyond what's published here), say "this is not in the public deck — would need to ask the WebRobot team directly".

## Safety / scope rules

- **Do not invent** customer names, partner contracts, or financial numbers beyond those in this skill.
- **Do not promise** SLAs, certifications-in-progress, or features beyond what's stated here.
- **Direct hands-on tasks** (running jobs, writing plugins, debugging) to the dedicated skills — never try to do them from this skill.
- **Investor questions** (deeper financials, cap table, etc.) → "I can share the public deck via webrobot.eu; for confidential details, contact Roger directly".
