# Bogotá Economic Observatory — Technical Architecture

## Overview

End-to-end data and AI system that ingests open economic data from Bogotá's Secretaría Distrital de Desarrollo Económico (SDDE), models it into a PostgreSQL star schema, serves analytical endpoints via FastAPI, renders an interactive dashboard, and answers natural language queries through a LangGraph AI agent with full observability via Langfuse.

**Live at:** [brainit.run](https://brainit.run)

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        NGINX (reverse proxy)                     │
│                  brainit.run / api.brainit.run                   │
│                     HTTPS via Let's Encrypt                      │
└──────────┬──────────────────────────────┬────────────────────────┘
           │                              │
     Static files                   /analytics/*
  ┌────────▼────────┐          ┌──────────▼──────────┐
  │  Landing Page   │          │   Observatory API    │
  │  Dashboard      │          │   FastAPI :8003      │
  │  Agent Chat UI  │          │   (systemd service)  │
  │  /var/www/      │          └───┬─────────────┬────┘
  └─────────────────┘              │             │
                          ┌────────▼───┐   ┌─────▼──────────┐
                          │ PostgreSQL │   │  AI Agent       │
                          │ Star Schema│   │  LangGraph +    │
                          │ Docker     │   │  Groq (Llama    │
                          │ :5432      │   │  3.3 70B)       │
                          └────────────┘   └─────┬───────────┘
                                                 │
                                          ┌──────▼──────────┐
                                          │    Langfuse     │
                                          │    (cloud)      │
                                          │    Tracing &    │
                                          │    Observability│
                                          └─────────────────┘
```

## Data Pipeline

### Sources

| Dataset | Records | Source | Access Method |
|---|---|---|---|
| Dinámica Empresarial | 76,919 | SDDE Open Data | ArcGIS REST API (paginated, 39 batches × 2K) |
| Mercado Laboral | 49 | SDDE Open Data | XLSX download |
| PIB Bogotá | 3,320 | SDDE Open Data | XLSX download |

### Ingestion

Three Python scripts in `src/ingestion/`, each tailored to its source format. An orchestrator (`ingest_all.py`) runs all three sequentially. The ArcGIS ingestion handles pagination automatically, requesting 2,000 records per batch across 39 pages.

### Star Schema (PostgreSQL 16, Docker)

```
           ┌──────────────┐
           │   dim_time    │
           │  (273 rows)   │
           └──────┬───────┘
                  │
┌──────────────┐  │  ┌────────────────────┐
│ dim_locality │──┼──│ dim_economic_sector │
│  (20 rows)   │  │  │    (533 rows)      │
└──────────────┘  │  └────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼──────┐ ┌───▼──────┐ ┌───▼──────┐
│  fact_   │ │  fact_   │ │  fact_   │
│ business │ │  labor   │ │   gdp    │
│ dynamics │ │  market  │ │          │
│ (76,816) │ │   (49)   │ │ (3,320)  │
└──────────┘ └──────────┘ └──────────┘
                  │
┌──────────────┐  │  ┌────────────────┐
│dim_company_  │──┘  │ dim_legal_form │
│   size (5)   │     │    (12 rows)   │
└──────────────┘     └────────────────┘
```

Dimensions: `dim_time`, `dim_locality`, `dim_economic_sector`, `dim_company_size`, `dim_legal_form`

Facts: `fact_business_dynamics`, `fact_labor_market`, `fact_gdp`

Loading is idempotent — `load_all.py` can be re-run safely. Validation via `validate.py` checks row counts and referential integrity.

### Automated Refresh

A monthly cron job (`scripts/refresh.sh`) runs on the 1st of each month at 6:00 AM, re-ingesting all sources and reloading the star schema.

## API Layer

**FastAPI** application serving 15 endpoints (14 GET + 1 POST) at `api.brainit.run/analytics/`.

### Endpoint Groups

**Health:** `/health` — database connectivity check.

**Dimensions:** `/dimensions/localities`, `/dimensions/sectors` — reference data for filtering.

**Business Dynamics:** `/business/by-locality`, `/business/by-size`, `/business/by-sector`, `/business/time-series`, `/business/gender` — all support optional year, locality, and size filters.

**Labor Market:** `/labor/overview` — full quarterly time series (2021–2025).

**GDP:** `/gdp/by-sector`, `/gdp/time-series` — filterable by year, quarter, sector. Covers 2005–2025.

**Summary:** `/summary` — aggregated high-level indicators across all datasets.

**Agent:** `POST /agent/ask` — natural language interface (see AI Agent section).

All endpoints use a connection pool (`database.py`) and return JSON. Numeric values are safely rounded to handle NaN/Inf from source data.

### Deployment

Runs as a **systemd service** (`observatory-api`), using a dedicated Python virtual environment. Environment variables (DB credentials, API keys) loaded via `EnvironmentFile`. Nginx reverse proxies external HTTPS traffic to `localhost:8003`.

## AI Agent

### Architecture: ReAct Pattern (LangGraph)

```
User Question
     │
     ▼
┌─────────────┐
│  FastAPI     │  POST /agent/ask
│  Endpoint    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  LangGraph  │────▶│  Groq API    │
│  ReAct Loop │     │  Llama 3.3   │
│             │◀────│  70B         │
└──────┬──────┘     └──────────────┘
       │                    │
       │              ┌─────▼─────┐
       │              │ Langfuse  │
       │              │ Tracing   │
       │              └───────────┘
       ▼
┌─────────────┐
│  10 Tools   │  Each wraps HTTP GET → localhost:8003/analytics/*
│  (tools.py) │
└─────────────┘
```

### Flow (per query)

1. User sends question via `POST /agent/ask`
2. LangGraph invokes Groq (1st LLM call): model selects tool + parameters
3. Tool executes HTTP GET to the appropriate analytics endpoint
4. LangGraph invokes Groq (2nd LLM call): model synthesizes answer from tool results
5. Response returned with answer, tools used, step count, latency, and Langfuse trace URL

### Tools

10 tools, each a thin wrapper around an API endpoint:

| Tool | Endpoint | Purpose |
|---|---|---|
| `get_summary` | `/summary` | High-level overview |
| `get_business_by_locality` | `/business/by-locality` | Business metrics by locality |
| `get_business_by_size` | `/business/by-size` | Business metrics by company size |
| `get_business_by_sector` | `/business/by-sector` | Top sectors by active businesses |
| `get_business_time_series` | `/business/time-series` | Monthly business trends |
| `get_business_by_gender` | `/business/gender` | Gender distribution in business ownership |
| `get_labor_overview` | `/labor/overview` | Employment/unemployment time series |
| `get_gdp_by_sector` | `/gdp/by-sector` | GDP by economic sector |
| `get_gdp_time_series` | `/gdp/time-series` | Quarterly GDP trends |
| `get_localities` | `/dimensions/localities` | Reference list of 20 localities |

### Guardrails

- System prompt limits tool calls to 2 per question
- `recursion_limit=10` in LangGraph prevents infinite loops
- Response truncation: lists capped at 10 items to prevent token overflow
- Retry logic with exponential backoff for Groq rate limits (free tier)

### LLM Configuration

Provider-agnostic design (`llm.py`): currently Groq with Llama 3.3 70B, switchable via environment variables (`LLM_PROVIDER`, `LLM_MODEL`). Temperature set to 0 for deterministic tool selection.

## Observability (Langfuse)

Integrated via `langfuse.langchain.CallbackHandler` (SDK v4.7.0), injected into the LangGraph `invoke()` call.

### What is traced

- Full agent execution timeline per query
- Each LLM call: prompt, completion, input/output tokens, latency
- Each tool call: name, parameters, result, duration
- Error traces (e.g., malformed tool calls from Llama 3.3)

### Response metadata

Every `/agent/ask` response includes:
- `latency_ms`: end-to-end execution time
- `trace_url`: direct link to the Langfuse trace for debugging

### Configuration

Three environment variables: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. Module: `src/agent/observability.py`.

## Frontend

### Dashboard (`brainit.run/observatory.html`)

Interactive Chart.js dashboard with 6 visualizations covering business dynamics, labor market, and GDP. Data fetched from the API at runtime.

### Agent Chat (`brainit.run/agent.html`)

Chat interface for natural language queries. Sends questions to `POST /agent/ask` and displays responses.

### Landing Page (`brainit.run`)

Portfolio page featuring the Observatory and other projects.

## Infrastructure

### Server

Oracle Cloud Free Tier — ARM/Ampere Altra, 4 OCPUs, 24GB RAM, ~200GB storage, Ubuntu 24.04.

### Services

| Component | Type | Port | Restart Policy |
|---|---|---|---|
| Observatory API | systemd | 8003 | on-failure |
| PostgreSQL 16 | Docker Compose | 5432 | unless-stopped |
| Nginx | system | 80/443 | system default |

### Security

- All external traffic routed through Nginx (HTTPS only)
- Raw ports closed; only 80/443 exposed via Oracle Cloud Security List + iptables
- API keys stored in `.env`, loaded via systemd `EnvironmentFile`
- CORS enabled for dashboard access

## Evaluation Suite

30 test cases across 5 categories (business, labor, GDP, overview, reference) and 3 difficulty levels, supporting both English and Spanish queries.

### Scoring dimensions

- `tool_correct`: did the agent select the right tool?
- `answer_contains`: does the answer include expected data points?
- `no_crash`: did the query complete without errors?
- `steps_ok`: did the agent stay within step limits?

Results saved to `evals/results.json`. Current performance: tool accuracy 100%, answer quality ~40% (synthesis limitations, actively being improved via prompt engineering).

## Project Structure

```
bogota-econ-observatory/
├── src/
│   ├── ingestion/          # 3 source-specific scripts + orchestrator
│   ├── loading/            # load_all.py (idempotent), validate.py
│   ├── api/                # main.py (15 endpoints), database.py
│   └── agent/              # graph.py, tools.py, llm.py, observability.py
├── evals/                  # dataset.json (30 cases), run_evals.py
├── sql/init.sql            # DDL for star schema
├── scripts/refresh.sh      # Monthly cron script
├── docker-compose.yml      # PostgreSQL
├── ARCHITECTURE.md         # This document
├── KNOWN_ISSUES.md         # Tracked bugs and limitations
└── README.md
```

## Tech Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 (Docker) |
| API | FastAPI + Uvicorn |
| AI Agent | LangGraph (ReAct pattern) |
| LLM | Llama 3.3 70B via Groq |
| Observability | Langfuse (cloud) |
| Frontend | Chart.js, vanilla HTML/JS |
| Infrastructure | Oracle Cloud, Nginx, systemd, Let's Encrypt |
| Language | Python 3.12 |
