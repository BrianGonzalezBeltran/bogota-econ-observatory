# Bogotá Economic Observatory

End-to-end analytics pipeline ingesting open data from Bogotá's Secretaría Distrital de Desarrollo Económico (SDDE).

## Data Sources

| Dataset | Source | Access | Granularity |
|---|---|---|---|
| Dinámica Empresarial | Datos Abiertos Bogotá | ArcGIS REST API | Monthly × Locality × Sector × Size |
| Mercado Laboral | Datos Abiertos Bogotá | XLSX download | Quarterly rolling trimester |
| PIB Bogotá | Datos Abiertos Bogotá | XLSX download | Quarterly × 25 economic sectors |

## Architecture

```
[ArcGIS REST API / XLSX files]
        │
        ▼
  Ingestion (Python)
        │
        ▼
  PostgreSQL (dimensional model)
        │
        ▼
  FastAPI (analytical endpoints)
        │
        ▼
  Dashboard (brainit.run)
        │
        ▼
  AI Agent (natural language queries) ← Phase 2
```

## Stack

- Python 3.11+, requests, openpyxl, pandas
- PostgreSQL 16 (Docker)
- FastAPI
- Nginx reverse proxy (brainit.run)

## Project Structure

```
src/
  ingestion/                      # Data extraction
    dinamica_empresarial.py       # ArcGIS REST API (76K+ records, paginated)
    mercado_laboral.py            # XLSX download
    pib_bogota.py                 # XLSX download
    ingest_all.py                 # Orchestrator
  loading/                        # Data loading into PostgreSQL
    load_all.py                   # Dimension + fact table loader
    validate.py                   # Post-load validation queries
  api/                            # Analytical API
    main.py                       # FastAPI endpoints
    database.py                   # Connection pool
sql/
  init.sql                        # DDL: star schema (5 dims, 3 facts)
data/
  raw/                            # Downloaded files (gitignored)
```

## API Endpoints

Run locally: `uvicorn src.api.main:app --reload --port 8003`

| Endpoint | Description |
|---|---|
| `GET /analytics/health` | API + DB health check |
| `GET /analytics/summary` | High-level overview across all datasets |
| `GET /analytics/business/by-locality` | Business metrics aggregated by locality |
| `GET /analytics/business/by-size` | Business metrics by company size |
| `GET /analytics/business/by-sector` | Top N sectors by empresas vigentes |
| `GET /analytics/business/time-series` | Monthly business creation/cancellation |
| `GET /analytics/business/gender` | Metrics by gender of legal representative |
| `GET /analytics/labor/overview` | Labor market time series (employment rates) |
| `GET /analytics/gdp/by-sector` | GDP by economic sector |
| `GET /analytics/gdp/time-series` | Quarterly GDP evolution |
| `GET /analytics/dimensions/*` | Reference data (localities, sectors, sizes) |

Most endpoints accept optional query params: `year`, `month`, `locality`, `sector`, `top_n`.
