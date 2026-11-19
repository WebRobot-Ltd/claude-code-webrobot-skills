---
name: webrobot-overview
description: Overview of the WebRobot platform — what it is, the three studios (Pipeline Designer, Agent Studio, App Studio), Knowledge, Analytics, AI Agent Deploy, Marketplace, execution engines, SaaS vs BYOC delivery, API/CLI/MCP access, and pricing. Use when the user asks WHAT WebRobot is, how it differs from other tools, which plan fits, or how the pieces fit together. Hands-on tasks go to the dedicated skills.
argument-hint: [topic, e.g. "pricing", "BYOC", "Agent Studio", "engines", "vs Apify"]
user-invocable: true
---

# WebRobot — Platform Overview

Answer high-level questions from the facts below; be direct and concise. For hands-on work, hand off to the dedicated skill.

## In one line

WebRobot turns data from any source — web pages, databases, files, APIs, documents — into pipelines, AI agents and published apps, described in plain language and run on ephemeral machines that exist only while a job runs. The point for the customer is a sharp cut in the cost and time of building and running data and agent workloads.

## The three studios

| Studio | What it does | Skill |
|--------|--------------|-------|
| **Pipeline Designer** | Builds ETL pipelines (pipeline YAML) from a conversation or point-and-click on a live page; runs them as jobs on Spark, Scrapy or hybrid engines. | `webrobot-pipeline` |
| **Agent Studio** | Builds AI agents and multi-agent teams (agentic profiles) with tools, MCP servers and knowledge. Agents run in chat, in the background, on a schedule or on an event trigger. | `webrobot-agents` |
| **App Studio / App Builder** | Generates a vertical app from a description (declarative manifest + runtime) and publishes it at `<slug>.webrobot.eu`; exportable to GitHub (web, Android, iOS). | `webrobot-app-builder` |

## Other product areas

- **Knowledge** — organization documents indexed for retrieval, so agents answer grounded on the customer's own material.
- **Analytics** — an analyst agent produces reports over the organization's datasets; reports are saved and can be re-run.
- **AI Agent Deploy** — a dedicated chat server deployed on the customer's own VMs, with a JavaScript embed for their website (and Telegram).
- **Marketplace** — published agent profiles, pipelines and plugins that other organizations can install.
- **Datasets** — uploaded inputs and job outputs, queryable with SQL and indexable for search (`webrobot-datasets`).

## Execution engines

| Engine | Use |
|--------|-----|
| **Apache Spark** (default) | Distributed ETL on Kubernetes, for volumes one machine cannot hold. |
| **Scrapy / hybrid** | Lightweight ingestion (and scrape + analyse in one job) for small and medium workloads, at lower cost. |
| **Ray** (live) | Agent runs (Agent Studio, background and scheduled runs), plus model serving and training jobs. |
| **Temporal** | Durable, long-running workflows. |
| **Slurm / EuroHPC** | HPC jobs (e.g. training, local inference) on supercomputer allocations. |

Browser-heavy steps run on a pool of anti-detection browsers; elastic browser and executor VMs are created per run and destroyed at the end.

## Delivery modes

| Mode | What it means |
|------|---------------|
| **SaaS** | WebRobot runs everything on its cloud. Monthly base plus prepaid, metered credits for the compute, storage and AI a run actually uses. |
| **BYOC** (`byoc_soft`) | The ephemeral VMs are created in the customer's own Hetzner account for each run and destroyed when it ends; the customer pays the provider directly and WebRobot adds no mark-up on compute. Data stays in the customer's infrastructure. |
| **BYOC Hard / dedicated cluster** | A dedicated cluster with its own control plane on the customer's servers, for enterprises and institutions, after security checks. |

BYOC is the cheapest way to run at scale; SaaS needs no infrastructure on the customer's side.

## Pricing (self-serve, per month)

| Plan | Price | Highlights |
|------|-------|-----------|
| **Starter** (SaaS) | €9 | Up to 3 machines on the lightweight engine, scheduled web monitors, a conversational agent for site and Telegram grounded on the customer's documents. |
| **Growth** (SaaS or BYOC) | €99 | Any source on distributed Spark, up to 10 ephemeral VMs, single agents in the background / on schedule / on events, all three studios, REST API, CLI and MCP, email support. |
| **Pro** (SaaS or BYOC) | €299 | Up to 25 ephemeral VMs, multi-agent teams, Python extensions and plugins, business-hours support. |
| **BYOC Hard / dedicated cluster** | On request | No public price; enterprises and institutions. |

SaaS usage is billed as prepaid credits (1 credit = €0.01) on top of the base; on BYOC the base is an orchestration fee and compute is paid to the customer's own provider. Registration is currently by invite. Do not quote other prices, SLAs or certifications.

## Access: API, CLI, MCP

- **REST API**: `https://api.webrobot.eu/api/webrobot/api/...`, auth with `X-API-Key` or a Bearer JWT.
- **MCP**: the plugin's `webrobot` server is the full authenticated MCP; each tool is a REST operation named by its OpenAPI operationId. Setup and task map: `webrobot-setup`.
- **CLI and SDKs**: `webrobot-cli`, `webrobot-sdk-python`, `webrobot-sdk-java`, `webrobot-sdk-nodejs`.
- **Extensibility**: Python extensions (`webrobot-python-extension`), Scala/Java plugins (`webrobot-plugin-dev`), console UI plugins (`webrobot-frontend-plugin-dev`).
- **Administration** of projects, jobs, credentials, users: `webrobot-admin`.

## How it differs

Web-scraping tools (Apify, Bright Data) extract web data but do not offer distributed processing, multi-tenant BYOC or agents over the rest of the data stack. Batch ETL tools (Airflow, dbt, Fivetran) assume the data already exists and do not acquire it from the web. WebRobot covers acquisition, distributed processing, agents and published apps in one platform, on the customer's cloud if they want, with multi-tenant isolation per organization.

## Rules

- Ground answers in this document; if something is not covered, say so and offer `curl -fsSL https://docs.webrobot.eu/<topic>`.
- Frame benefits as cost and time reduction. Never describe the product or any usage as "free" or say that "no one pays".
- Do not invent customers, partners, figures, timelines or certifications.
- Do not attempt hands-on tasks from this skill; route to the skills above.
