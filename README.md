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
  ingestion/
    dinamica_empresarial.py   # ArcGIS REST API ingestion
    mercado_laboral.py        # XLSX ingestion
    pib_bogota.py             # XLSX ingestion
    ingest_all.py             # Orchestrator
data/
  raw/                        # Downloaded files
  processed/                  # Cleaned CSVs
```
