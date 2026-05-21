# Bogotá Economic Observatory

An end-to-end data + AI system that ingests open economic data from Bogotá, models it into a star schema, serves analytical endpoints, visualizes it in an interactive dashboard, and answers natural language questions through an AI agent.

**Live demo:** [Dashboard](https://brainit.run/observatory.html) · [AI Agent Chat](https://brainit.run/agent.html) · [API Docs](https://api.brainit.run/analytics/docs)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                 │
│  ArcGIS REST API (76K+ records)  ·  XLSX downloads (labor + GDP)   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER                                 │
│  Python scripts with pagination (2K batches), XLSX parsing          │
│  3 sources → CSV staging files                                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  POSTGRESQL (Star Schema)                            │
│  5 dimensions: time · locality · sector · size · legal form         │
│  3 fact tables: business dynamics · labor market · GDP               │
│  76,816 + 58 + 3,240 records                                       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI (REST API)                                │
│  14 GET endpoints (analytical queries with optional filters)        │
│  1 POST endpoint (AI agent)                                         │
│  Connection pooling · CORS · root_path for nginx                    │
└──────────────┬───────────────────────────────┬──────────────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────┐   ┌──────────────────────────────────────┐
│       DASHBOARD          │   │           AI AGENT                   │
│  Chart.js · 6 charts     │   │  LangGraph ReAct · 10 tools         │
│  Year filter · KPI cards │   │  Groq (Llama 3.3 70B)               │
│  brainit.run/observatory │   │  brainit.run/agent                   │
└──────────────────────────┘   └──────────────────────────────────────┘
```

## What it does

**Data pipeline:** Three Python scripts ingest data from Bogotá's Secretaría Distrital de Desarrollo Económico (SDDE). The main source — Dinámica Empresarial — is consumed via ArcGIS REST API with automatic pagination across 39 batches of 2,000 records. Two supplementary sources (labor market indicators and quarterly GDP) are downloaded as XLSX files. All data is cleaned, transformed, and loaded into a PostgreSQL star schema with 5 dimension tables and 3 fact tables.

**Analytical API:** 14 REST endpoints serve pre-computed metrics with optional filters for year, locality, sector, and company size. Queries execute JOINs across the dimensional model and return JSON. A connection pool manages database access efficiently.

**Interactive dashboard:** A self-contained HTML page fetches data from the API and renders 6 visualizations: KPI cards, business by locality, company size distribution, gender of legal representative, labor market trends, and GDP by sector. Year buttons re-filter all business charts dynamically.

**AI agent:** A LangGraph agent that accepts natural language questions in Spanish or English. The agent uses the ReAct pattern: an LLM (Llama 3.3 70B via Groq) reasons about which of 10 available tools to call, LangGraph executes the tool (which queries the API internally), and the LLM synthesizes a human-readable answer from the JSON results.

## AI agent flow

```
User: "¿Cuántas empresas hay en Suba?"
  │
  ▼
agent.html → POST /analytics/agent/ask
  │
  ▼
LangGraph sends question + 10 tool definitions to Groq
  │
  ▼
Llama 3.3 70B decides: call get_business_by_locality(locality="Suba")
  │
  ▼
Tool executes HTTP GET → FastAPI → PostgreSQL → JSON result
  │
  ▼
LangGraph sends history + JSON back to Groq
  │
  ▼
Llama 3.3 synthesizes: "Hay 104,330 empresas activas en Suba"
```

## Data sources

| Dataset | Records | Source | Access method |
|---|---|---|---|
| Dinámica Empresarial | 76,919 | Datos Abiertos Bogotá | ArcGIS REST API (paginated) |
| Mercado Laboral | 58 | Datos Abiertos Bogotá | XLSX download |
| PIB Bogotá | 3,240 | Datos Abiertos Bogotá | XLSX download |

**Dinámica Empresarial** covers business creation, cancellation, and active companies across 20 localities, 5 company sizes, 503 CIIU economic sectors, 12 legal forms, and gender of legal representative. Periods: 2023–2024.

**Mercado Laboral** tracks employment, unemployment, informality, and subemployment rates. Quarterly rolling trimesters, 2021–2025.

**PIB Bogotá** provides GDP at current and constant (2015) prices across 25 economic sectors. Quarterly, 2005–2025.

## Stack

| Layer | Technology |
|---|---|
| Ingestion | Python, requests, pandas, openpyxl |
| Storage | PostgreSQL 16 (Docker) |
| API | FastAPI, psycopg2, uvicorn |
| Dashboard | HTML, Chart.js |
| AI Agent | LangGraph, langchain-core, langchain-groq |
| LLM | Llama 3.3 70B (Groq cloud, free tier) |
| Infrastructure | Docker, nginx, systemd, Oracle Cloud ARM |
| DNS/TLS | Let's Encrypt, certbot |

## Project structure

```
src/
  ingestion/
    dinamica_empresarial.py     # ArcGIS REST API with pagination
    mercado_laboral.py          # XLSX ingestion
    pib_bogota.py               # XLSX ingestion
    ingest_all.py               # Orchestrator
  loading/
    load_all.py                 # Dimension + fact table loader (idempotent)
    validate.py                 # Post-load validation queries
  api/
    main.py                     # FastAPI: 14 analytical + 1 agent endpoint
    database.py                 # Connection pool
  agent/
    graph.py                    # LangGraph ReAct agent
    tools.py                    # 10 tools mapped to API endpoints
    llm.py                      # LLM config (Groq, model-agnostic)
    test_agent.py               # CLI test script
sql/
  init.sql                      # DDL: star schema (5 dims, 3 facts)
dashboard.html                  # Interactive frontend
docker-compose.yml              # PostgreSQL container
```

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/analytics/health` | API + DB connectivity check |
| GET | `/analytics/summary` | High-level overview across all datasets |
| GET | `/analytics/business/by-locality` | Business metrics by locality |
| GET | `/analytics/business/by-size` | Business metrics by company size |
| GET | `/analytics/business/by-sector` | Top N sectors by active businesses |
| GET | `/analytics/business/time-series` | Monthly creation/cancellation trends |
| GET | `/analytics/business/gender` | Metrics by gender of legal representative |
| GET | `/analytics/labor/overview` | Labor market time series |
| GET | `/analytics/gdp/by-sector` | GDP by economic sector |
| GET | `/analytics/gdp/time-series` | Quarterly GDP evolution |
| GET | `/analytics/dimensions/*` | Reference data (localities, sectors, sizes, periods) |
| POST | `/analytics/agent/ask` | Natural language query via AI agent |

Most GET endpoints accept optional query params: `year`, `month`, `locality`, `sector`, `top_n`.

## Running locally

```bash
# Clone and setup
git clone https://github.com/BrianGonzalezBeltran/bogota-econ-observatory.git
cd bogota-econ-observatory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL
docker compose up -d

# Ingest data
python -m src.ingestion.ingest_all

# Load into dimensional model
python -m src.loading.load_all

# Validate
python -m src.loading.validate

# Start API
uvicorn src.api.main:app --reload --port 8003

# (Optional) Test AI agent — requires GROQ_API_KEY
export GROQ_API_KEY=your_key_here
python -m src.agent.test_agent "¿Cuántas empresas activas hay en Bogotá?"
```

## Infrastructure

Deployed on Oracle Cloud Free Tier (ARM Ampere Altra, 4 OCPUs, 24GB RAM, Ubuntu 24.04).

```
Internet → nginx (443/HTTPS)
              ├── brainit.run/observatory.html  → static dashboard
              ├── brainit.run/agent.html        → AI agent chat
              └── api.brainit.run/analytics/    → FastAPI (systemd, port 8003)
                    └── PostgreSQL (Docker, port 5432)
```

All services auto-restart on reboot (Docker restart policies + systemd).

## Author

**Brian González Beltrán** — [brainit.run](https://brainit.run) · [GitHub](https://github.com/BrianGonzalezBeltran) · [LinkedIn](https://linkedin.com/in/briangonzalezbeltran)
