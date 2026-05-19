"""
Bogotá Economic Observatory — FastAPI Analytical Endpoints

Serves pre-computed metrics and accepts query parameters
for locality, sector, time range, and company size filtering.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from math import isfinite
from src.api.database import get_db


def safe_round(val, decimals=2):
    """Round a numeric value, returning None for NaN/Inf/None."""
    if val is None:
        return None
    try:
        if not isfinite(val):
            return None
        return round(val, decimals)
    except (TypeError, ValueError):
        return None

app = FastAPI(
    title="Bogotá Economic Observatory",
    description="Analytical API over open economic data from Bogotá's SDDE",
    version="0.1.0",
    root_path="/analytics",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/health")
def health():
    """Check API and database connectivity."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fact_business_dynamics")
        count = cur.fetchone()[0]
    return {"status": "ok", "fact_business_dynamics_rows": count}


# ------------------------------------------------------------------
# Dimensions (reference data)
# ------------------------------------------------------------------

@app.get("/dimensions/localities")
def list_localities():
    """List all available localities."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT locality_id, locality_code, locality_name
            FROM dim_locality ORDER BY locality_name
        """)
        return [
            {"id": r[0], "code": r[1], "name": r[2]}
            for r in cur.fetchall()
        ]


@app.get("/dimensions/sectors")
def list_sectors(rama: Optional[str] = None):
    """List economic sectors. Optionally filter by rama (branch)."""
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT sector_id, rama_name, ciiu_code, ciiu_description FROM dim_economic_sector"
        params = []
        if rama:
            query += " WHERE rama_name ILIKE %s"
            params.append(f"%{rama}%")
        query += " ORDER BY ciiu_code"
        cur.execute(query, params)
        return [
            {"id": r[0], "rama": r[1], "ciiu_code": r[2], "description": r[3]}
            for r in cur.fetchall()
        ]


@app.get("/dimensions/sizes")
def list_company_sizes():
    """List company size categories."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT size_id, size_name FROM dim_company_size ORDER BY size_id")
        return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]


@app.get("/dimensions/time-periods")
def list_time_periods():
    """List available time periods."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT year, quarter, month
            FROM dim_time ORDER BY year, quarter, month
        """)
        return [
            {"year": r[0], "quarter": r[1], "month": r[2]}
            for r in cur.fetchall()
        ]


# ------------------------------------------------------------------
# Business dynamics analytics
# ------------------------------------------------------------------

@app.get("/business/by-locality")
def business_by_locality(
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    """
    Aggregate business metrics by locality.
    Returns: vigentes, creadas, canceladas per locality.
    """
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []
        if year:
            conditions.append("t.year = %s")
            params.append(year)
        if month:
            conditions.append("t.month = %s")
            params.append(month)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT l.locality_name,
                   SUM(f.empresas_vigentes) as vigentes,
                   SUM(f.empresas_creadas) as creadas,
                   SUM(f.empresas_canceladas) as canceladas
            FROM fact_business_dynamics f
            JOIN dim_locality l ON f.locality_id = l.locality_id
            JOIN dim_time t ON f.time_id = t.time_id
            {where}
            GROUP BY l.locality_name
            ORDER BY vigentes DESC
        """, params)

        return [
            {
                "locality": r[0],
                "empresas_vigentes": r[1],
                "empresas_creadas": r[2],
                "empresas_canceladas": r[3],
            }
            for r in cur.fetchall()
        ]


@app.get("/business/by-size")
def business_by_size(
    year: Optional[int] = None,
    locality: Optional[str] = None,
):
    """Aggregate business metrics by company size."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []
        if year:
            conditions.append("t.year = %s")
            params.append(year)
        if locality:
            conditions.append("l.locality_name ILIKE %s")
            params.append(f"%{locality}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT s.size_name,
                   SUM(f.empresas_vigentes) as vigentes,
                   SUM(f.empresas_creadas) as creadas,
                   SUM(f.empresas_canceladas) as canceladas
            FROM fact_business_dynamics f
            JOIN dim_company_size s ON f.size_id = s.size_id
            JOIN dim_time t ON f.time_id = t.time_id
            JOIN dim_locality l ON f.locality_id = l.locality_id
            {where}
            GROUP BY s.size_name
            ORDER BY vigentes DESC
        """, params)

        return [
            {
                "size": r[0],
                "empresas_vigentes": r[1],
                "empresas_creadas": r[2],
                "empresas_canceladas": r[3],
            }
            for r in cur.fetchall()
        ]


@app.get("/business/by-sector")
def business_by_sector(
    year: Optional[int] = None,
    locality: Optional[str] = None,
    top_n: int = Query(default=10, ge=1, le=50),
):
    """Top N economic sectors by empresas vigentes."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []
        if year:
            conditions.append("t.year = %s")
            params.append(year)
        if locality:
            conditions.append("l.locality_name ILIKE %s")
            params.append(f"%{locality}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT sec.rama_name,
                   SUM(f.empresas_vigentes) as vigentes,
                   SUM(f.empresas_creadas) as creadas,
                   SUM(f.empresas_canceladas) as canceladas
            FROM fact_business_dynamics f
            JOIN dim_economic_sector sec ON f.sector_id = sec.sector_id
            JOIN dim_time t ON f.time_id = t.time_id
            JOIN dim_locality l ON f.locality_id = l.locality_id
            {where}
            GROUP BY sec.rama_name
            ORDER BY vigentes DESC
            LIMIT %s
        """, params + [top_n])

        return [
            {
                "sector": r[0],
                "empresas_vigentes": r[1],
                "empresas_creadas": r[2],
                "empresas_canceladas": r[3],
            }
            for r in cur.fetchall()
        ]


@app.get("/business/time-series")
def business_time_series(
    locality: Optional[str] = None,
    size: Optional[str] = None,
):
    """Monthly time series of business creation and cancellation."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []
        if locality:
            conditions.append("l.locality_name ILIKE %s")
            params.append(f"%{locality}%")
        if size:
            conditions.append("sz.size_name ILIKE %s")
            params.append(f"%{size}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT t.year, t.month,
                   SUM(f.empresas_vigentes) as vigentes,
                   SUM(f.empresas_creadas) as creadas,
                   SUM(f.empresas_canceladas) as canceladas
            FROM fact_business_dynamics f
            JOIN dim_time t ON f.time_id = t.time_id
            JOIN dim_locality l ON f.locality_id = l.locality_id
            JOIN dim_company_size sz ON f.size_id = sz.size_id
            {where}
            GROUP BY t.year, t.month
            ORDER BY t.year, t.month
        """, params)

        return [
            {
                "year": r[0], "month": r[1],
                "empresas_vigentes": r[2],
                "empresas_creadas": r[3],
                "empresas_canceladas": r[4],
            }
            for r in cur.fetchall()
        ]


@app.get("/business/gender")
def business_by_gender(
    year: Optional[int] = None,
    locality: Optional[str] = None,
):
    """Business metrics by gender of legal representative."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []
        if year:
            conditions.append("t.year = %s")
            params.append(year)
        if locality:
            conditions.append("l.locality_name ILIKE %s")
            params.append(f"%{locality}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT f.gender_legal_rep,
                   SUM(f.empresas_vigentes) as vigentes,
                   SUM(f.empresas_creadas) as creadas,
                   SUM(f.empresas_canceladas) as canceladas
            FROM fact_business_dynamics f
            JOIN dim_time t ON f.time_id = t.time_id
            JOIN dim_locality l ON f.locality_id = l.locality_id
            {where}
            GROUP BY f.gender_legal_rep
            ORDER BY vigentes DESC
        """, params)

        return [
            {
                "gender": r[0],
                "empresas_vigentes": r[1],
                "empresas_creadas": r[2],
                "empresas_canceladas": r[3],
            }
            for r in cur.fetchall()
        ]


# ------------------------------------------------------------------
# Labor market analytics
# ------------------------------------------------------------------

@app.get("/labor/overview")
def labor_overview():
    """Full labor market time series."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.year, t.quarter, t.trimester_label,
                   f.tasa_ocupacion, f.tasa_desocupacion,
                   f.tasa_informalidad, f.tasa_asalariados,
                   f.ocupados, f.desocupados, f.total_informales
            FROM fact_labor_market f
            JOIN dim_time t ON f.time_id = t.time_id
            ORDER BY t.year, t.quarter
        """)

        return [
            {
                "year": r[0], "quarter": r[1], "trimester": r[2],
                "tasa_ocupacion": r[3], "tasa_desocupacion": r[4],
                "tasa_informalidad": r[5], "tasa_asalariados": r[6],
                "ocupados": r[7], "desocupados": r[8],
                "informales": r[9],
            }
            for r in cur.fetchall()
        ]


# ------------------------------------------------------------------
# GDP analytics
# ------------------------------------------------------------------

@app.get("/gdp/by-sector")
def gdp_by_sector(
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    top_n: int = Query(default=10, ge=1, le=30),
):
    """GDP by economic sector at constant 2015 prices."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []
        if year:
            conditions.append("t.year = %s")
            params.append(year)
        if quarter:
            conditions.append("t.quarter = %s")
            params.append(quarter)

        where = f"WHERE s.ciiu_description IS NOT NULL"
        if conditions:
            where += f" AND {' AND '.join(conditions)}"

        cur.execute(f"""
            SELECT s.ciiu_description,
                   SUM(f.pib_precios_constantes_2015) as pib_constante,
                   AVG(f.variacion_anual_constantes) as var_anual_avg
            FROM fact_gdp f
            JOIN dim_time t ON f.time_id = t.time_id
            JOIN dim_economic_sector s ON f.sector_id = s.sector_id
            {where}
            GROUP BY s.ciiu_description
            ORDER BY pib_constante DESC
            LIMIT %s
        """, params + [top_n])

        return [
            {
                "sector": r[0],
                "pib_constante_2015": safe_round(r[1]),
                "variacion_anual_avg": safe_round(r[2]),
            }
            for r in cur.fetchall()
        ]


@app.get("/gdp/time-series")
def gdp_time_series(sector: Optional[str] = None):
    """Quarterly GDP time series, optionally filtered by sector."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = ["s.ciiu_description IS NOT NULL"]
        params = []
        if sector:
            conditions.append("s.ciiu_description ILIKE %s")
            params.append(f"%{sector}%")

        where = f"WHERE {' AND '.join(conditions)}"

        cur.execute(f"""
            SELECT t.year, t.quarter,
                   SUM(f.pib_precios_constantes_2015) as pib_constante,
                   SUM(f.pib_precios_corrientes) as pib_corriente
            FROM fact_gdp f
            JOIN dim_time t ON f.time_id = t.time_id
            JOIN dim_economic_sector s ON f.sector_id = s.sector_id
            {where}
            GROUP BY t.year, t.quarter
            ORDER BY t.year, t.quarter
        """, params)

        return [
            {
                "year": r[0], "quarter": r[1],
                "pib_constante_2015": safe_round(r[2]),
                "pib_corriente": safe_round(r[3]),
            }
            for r in cur.fetchall()
        ]


# ------------------------------------------------------------------
# Summary / overview
# ------------------------------------------------------------------

@app.get("/summary")
def summary():
    """High-level summary across all datasets."""
    with get_db() as conn:
        cur = conn.cursor()

        # Business dynamics totals
        cur.execute("""
            SELECT SUM(empresas_vigentes), SUM(empresas_creadas), SUM(empresas_canceladas)
            FROM fact_business_dynamics
        """)
        biz = cur.fetchone()

        # Latest unemployment
        cur.execute("""
            SELECT t.year, t.trimester_label, f.tasa_desocupacion, f.tasa_informalidad
            FROM fact_labor_market f
            JOIN dim_time t ON f.time_id = t.time_id
            ORDER BY t.year DESC, t.quarter DESC
            LIMIT 1
        """)
        labor = cur.fetchone()

        # Latest GDP total
        cur.execute("""
            SELECT t.year, t.quarter, SUM(f.pib_precios_constantes_2015)
            FROM fact_gdp f
            JOIN dim_time t ON f.time_id = t.time_id
            WHERE t.year = (SELECT MAX(year) FROM dim_time)
            GROUP BY t.year, t.quarter
            ORDER BY t.quarter DESC
            LIMIT 1
        """)
        gdp = cur.fetchone()

        return {
            "business": {
                "total_vigentes": biz[0] if biz else None,
                "total_creadas": biz[1] if biz else None,
                "total_canceladas": biz[2] if biz else None,
            },
            "labor": {
                "year": labor[0] if labor else None,
                "trimester": labor[1] if labor else None,
                "tasa_desocupacion": labor[2] if labor else None,
                "tasa_informalidad": labor[3] if labor else None,
            } if labor else None,
            "gdp": {
                "year": gdp[0] if gdp else None,
                "quarter": gdp[1] if gdp else None,
                "pib_constante_total": safe_round(gdp[2]) if gdp else None,
            } if gdp else None,
        }
