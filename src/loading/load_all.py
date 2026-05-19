"""
Loading: Read raw CSVs from Day 1 ingestion and populate the
PostgreSQL dimensional model (dim_* and fact_* tables).

Usage:
  python -m src.loading.load_all

Requires:
  - PostgreSQL running (docker-compose up -d)
  - Raw CSVs in data/raw/ (from ingestion step)
"""

import os
import logging
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "observatory"),
    "user": os.getenv("DB_USER", "observatory"),
    "password": os.getenv("DB_PASSWORD", "observatory_dev_2026"),
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ------------------------------------------------------------------
# Dimension loaders
# ------------------------------------------------------------------

def load_dim_time(conn, df_din: pd.DataFrame, df_pib: pd.DataFrame, df_lab: pd.DataFrame):
    """Build dim_time from all three sources."""
    time_records = set()

    # From dinámica empresarial: year + month
    for _, row in df_din[["PERIODO", "MES"]].drop_duplicates().iterrows():
        y, m = int(row["PERIODO"]), int(row["MES"])
        q = (m - 1) // 3 + 1
        time_records.add((y, q, m, None))

    # From PIB: year + quarter (periodo may contain suffixes like "2023p" for provisional)
    for _, row in df_pib[["periodo", "trimestre"]].drop_duplicates().iterrows():
        y = int(str(row["periodo"]).strip().rstrip("abcdefghijklmnopqrstuvwxyzAPpr*"))
        q = int(row["trimestre"])
        time_records.add((y, q, None, None))

    # From mercado laboral: parse year from trimestre_móvil_cronológico and quarter
    for _, row in df_lab.iterrows():
        year_val = row.get("trimestre_móvil_cronológico")
        periodo_val = row.get("periodo", "")
        if pd.notna(year_val):
            # Handle "2021 - 2022" format: take the last year (end of trimester)
            year_str = str(year_val).strip()
            if " - " in year_str:
                year_str = year_str.split(" - ")[-1]
            y = int(year_str.rstrip("abcdefghijklmnopqrstuvwxyzAPpr*"))
            # Derive quarter from the periodo text (e.g. "ene mar" -> Q1)
            trimester_label = str(periodo_val).strip()
            month_map = {
                "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
                "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
            }
            parts = trimester_label.lower().split()
            if len(parts) >= 2 and parts[-1] in month_map:
                end_month = month_map[parts[-1]]
                q = (end_month - 1) // 3 + 1
            else:
                q = None
            time_records.add((y, q, None, trimester_label))

    cur = conn.cursor()
    for y, q, m, label in time_records:
        cur.execute(
            """INSERT INTO dim_time (year, quarter, month, trimester_label)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (year, quarter, month) DO NOTHING""",
            (y, q, m, label),
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM dim_time")
    count = cur.fetchone()[0]
    logger.info(f"dim_time: {count} rows")
    return count


def load_dim_locality(conn, df_din: pd.DataFrame):
    """Load localities from dinámica empresarial."""
    localities = df_din[["LOCCODIGO", "LOCNOMBRE"]].drop_duplicates()
    cur = conn.cursor()
    for _, row in localities.iterrows():
        cur.execute(
            """INSERT INTO dim_locality (locality_code, locality_name)
               VALUES (%s, %s)
               ON CONFLICT (locality_code) DO NOTHING""",
            (int(row["LOCCODIGO"]), row["LOCNOMBRE"]),
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM dim_locality")
    count = cur.fetchone()[0]
    logger.info(f"dim_locality: {count} rows")
    return count


def load_dim_economic_sector(conn, df_din: pd.DataFrame, df_pib: pd.DataFrame):
    """Load economic sectors from both dinámica empresarial and PIB."""
    cur = conn.cursor()

    # From dinámica: CIIU codes + rama
    sectors = df_din[["RAMAACTIVIDADECONOMICA", "CODIGOCIIU"]].drop_duplicates()
    for _, row in sectors.iterrows():
        ciiu = str(row["CODIGOCIIU"]).strip() if pd.notna(row["CODIGOCIIU"]) else None
        rama = str(row["RAMAACTIVIDADECONOMICA"]).strip() if pd.notna(row["RAMAACTIVIDADECONOMICA"]) else None
        if ciiu:
            cur.execute(
                """INSERT INTO dim_economic_sector (rama_name, ciiu_code)
                   VALUES (%s, %s)
                   ON CONFLICT (ciiu_code) DO NOTHING""",
                (rama, ciiu),
            )

    # From PIB: actividad_economica as a sector without CIIU
    pib_sectors = df_pib["actividad_economica"].dropna().unique()
    for sector_name in pib_sectors:
        # Use a synthetic CIIU code prefixed with PIB_ to avoid conflicts
        synthetic_code = f"PIB_{sector_name[:30].strip()}"
        cur.execute(
            """INSERT INTO dim_economic_sector (rama_name, ciiu_code, ciiu_description)
               VALUES (%s, %s, %s)
               ON CONFLICT (ciiu_code) DO NOTHING""",
            (None, synthetic_code, sector_name),
        )

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM dim_economic_sector")
    count = cur.fetchone()[0]
    logger.info(f"dim_economic_sector: {count} rows")
    return count


def load_dim_company_size(conn, df_din: pd.DataFrame):
    """Load company size categories."""
    sizes = df_din["TAMANIOEMPRESARIAL"].dropna().unique()
    cur = conn.cursor()
    for i, size_name in enumerate(sorted(sizes), 1):
        cur.execute(
            """INSERT INTO dim_company_size (size_code, size_name)
               VALUES (%s, %s)
               ON CONFLICT (size_code) DO NOTHING""",
            (str(i), str(size_name).strip()),
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM dim_company_size")
    count = cur.fetchone()[0]
    logger.info(f"dim_company_size: {count} rows")
    return count


def load_dim_legal_form(conn, df_din: pd.DataFrame):
    """Load legal form categories."""
    forms = df_din["ORGANIZACIONJURIDICA"].dropna().unique()
    cur = conn.cursor()
    for i, form_name in enumerate(sorted(forms), 1):
        cur.execute(
            """INSERT INTO dim_legal_form (legal_form_code, legal_form_name)
               VALUES (%s, %s)
               ON CONFLICT (legal_form_code) DO NOTHING""",
            (str(i), str(form_name).strip()),
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM dim_legal_form")
    count = cur.fetchone()[0]
    logger.info(f"dim_legal_form: {count} rows")
    return count


# ------------------------------------------------------------------
# Lookup helpers
# ------------------------------------------------------------------

def build_lookups(conn) -> dict:
    """Build in-memory lookup dicts for dimension FK resolution."""
    cur = conn.cursor()

    cur.execute("SELECT time_id, year, quarter, month FROM dim_time")
    time_lookup = {(r[1], r[2], r[3]): r[0] for r in cur.fetchall()}

    cur.execute("SELECT locality_id, locality_code FROM dim_locality")
    locality_lookup = {r[1]: r[0] for r in cur.fetchall()}

    cur.execute("SELECT sector_id, ciiu_code FROM dim_economic_sector")
    sector_lookup = {r[1]: r[0] for r in cur.fetchall()}

    cur.execute("SELECT size_id, size_name FROM dim_company_size")
    size_lookup = {r[1]: r[0] for r in cur.fetchall()}

    cur.execute("SELECT legal_form_id, legal_form_name FROM dim_legal_form")
    legal_form_lookup = {r[1]: r[0] for r in cur.fetchall()}

    return {
        "time": time_lookup,
        "locality": locality_lookup,
        "sector": sector_lookup,
        "size": size_lookup,
        "legal_form": legal_form_lookup,
    }


# ------------------------------------------------------------------
# Fact loaders
# ------------------------------------------------------------------

def load_fact_business_dynamics(conn, df: pd.DataFrame, lookups: dict):
    """Load the main fact table from dinámica empresarial data."""
    cur = conn.cursor()

    # Truncate for idempotent reloads
    cur.execute("TRUNCATE TABLE fact_business_dynamics RESTART IDENTITY")

    rows = []
    skipped = 0
    for _, r in df.iterrows():
        y = int(r["PERIODO"])
        m = int(r["MES"])
        q = (m - 1) // 3 + 1

        time_id = lookups["time"].get((y, q, m))
        locality_id = lookups["locality"].get(int(r["LOCCODIGO"]))
        ciiu = str(r["CODIGOCIIU"]).strip() if pd.notna(r["CODIGOCIIU"]) else None
        sector_id = lookups["sector"].get(ciiu)
        size_name = str(r["TAMANIOEMPRESARIAL"]).strip() if pd.notna(r["TAMANIOEMPRESARIAL"]) else None
        size_id = lookups["size"].get(size_name)
        legal_name = str(r["ORGANIZACIONJURIDICA"]).strip() if pd.notna(r["ORGANIZACIONJURIDICA"]) else None
        legal_form_id = lookups["legal_form"].get(legal_name)
        gender = str(r["SEXORL"]).strip() if pd.notna(r["SEXORL"]) else None

        if not all([time_id, locality_id, sector_id, size_id, legal_form_id]):
            skipped += 1
            continue

        rows.append((
            time_id, locality_id, sector_id, size_id, legal_form_id, gender,
            int(r["EMPRESASVIGENTES"]) if pd.notna(r["EMPRESASVIGENTES"]) else 0,
            int(r["EMPRESASCREADAS"]) if pd.notna(r["EMPRESASCREADAS"]) else 0,
            int(r["EMPRESASCANCELADAS"]) if pd.notna(r["EMPRESASCANCELADAS"]) else 0,
        ))

    execute_values(
        cur,
        """INSERT INTO fact_business_dynamics
           (time_id, locality_id, sector_id, size_id, legal_form_id,
            gender_legal_rep, empresas_vigentes, empresas_creadas, empresas_canceladas)
           VALUES %s""",
        rows,
        page_size=5000,
    )
    conn.commit()
    logger.info(f"fact_business_dynamics: {len(rows):,} inserted, {skipped:,} skipped")


def load_fact_labor_market(conn, df: pd.DataFrame, lookups: dict):
    """Load labor market fact table."""
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE fact_labor_market RESTART IDENTITY")

    rows = []
    for _, r in df.iterrows():
        year_val = r.get("trimestre_móvil_cronológico")
        if pd.isna(year_val):
            continue

        year_str = str(year_val).strip()
        if " - " in year_str:
            year_str = year_str.split(" - ")[-1]
        y = int(year_str.rstrip("abcdefghijklmnopqrstuvwxyzAPpr*"))
        periodo_str = str(r.get("periodo", "")).strip().lower()
        month_map = {
            "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
            "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
        }
        parts = periodo_str.split()
        end_month = month_map.get(parts[-1]) if len(parts) >= 2 else None
        q = ((end_month - 1) // 3 + 1) if end_month else None

        time_id = lookups["time"].get((y, q, None))
        if not time_id:
            continue

        rows.append((
            time_id,
            r.get("poblacion_total_geih_dane"),
            r.get("poblacion_en_edad_de_trabajar"),
            r.get("fuerza_de_trabajo"),
            r.get("ocupados"),
            r.get("desocupados"),
            r.get("poblacion_fuera_de_la_fuerza_laboral"),
            r.get("subocupados"),
            r.get("fuerza_de_trabajo_potencial"),
            r.get("ocupados__asalariados"),
            r.get("ocupados_no_asalariados"),
            r.get("total_informales_dane"),
            r.get("tasa_global_de_participacion"),
            r.get("tasa_de_ocupacion"),
            r.get("tasa_de_desocupacion"),
            r.get("tasa_de_subocupados"),
            r.get("tasa_ocupados_asalariados"),
            r.get("tasa_ocupados__no_asalariados"),
            r.get("tasa_de_inactividad"),
            r.get("tasa__de_informalidad_dane"),
        ))

    execute_values(
        cur,
        """INSERT INTO fact_labor_market
           (time_id, poblacion_total, poblacion_edad_trabajar, fuerza_trabajo,
            ocupados, desocupados, poblacion_fuera_fuerza_laboral, subocupados,
            fuerza_trabajo_potencial, ocupados_asalariados, ocupados_no_asalariados,
            total_informales, tasa_global_participacion, tasa_ocupacion,
            tasa_desocupacion, tasa_subocupados, tasa_asalariados,
            tasa_no_asalariados, tasa_inactividad, tasa_informalidad)
           VALUES %s""",
        rows,
    )
    conn.commit()
    logger.info(f"fact_labor_market: {len(rows)} inserted")


def load_fact_gdp(conn, df: pd.DataFrame, lookups: dict):
    """Load GDP fact table."""
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE fact_gdp RESTART IDENTITY")

    rows = []
    for _, r in df.iterrows():
        y = int(str(r["periodo"]).strip().rstrip("abcdefghijklmnopqrstuvwxyzAPpr*"))
        q = int(r["trimestre"])
        time_id = lookups["time"].get((y, q, None))

        sector_name = str(r["actividad_economica"]).strip()
        synthetic_code = f"PIB_{sector_name[:30]}"
        sector_id = lookups["sector"].get(synthetic_code)

        if not time_id:
            continue

        rows.append((
            time_id,
            sector_id,
            r.get("pib_a_precios_corrientes"),
            r.get("pib_a_precios_constantes_del_2015"),
            r.get("variación_anual_precios_constantes_2015"),
            r.get("variacion_trimestral_precios_constantes_2015"),
            r.get("variacion_anual_precios_corrientes"),
            r.get("variacion_trimestral_precios_corrientes"),
        ))

    execute_values(
        cur,
        """INSERT INTO fact_gdp
           (time_id, sector_id, pib_precios_corrientes, pib_precios_constantes_2015,
            variacion_anual_constantes, variacion_trimestral_constantes,
            variacion_anual_corrientes, variacion_trimestral_corrientes)
           VALUES %s""",
        rows,
        page_size=5000,
    )
    conn.commit()
    logger.info(f"fact_gdp: {len(rows):,} inserted")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    logger.info("Reading raw CSVs...")
    df_din = pd.read_csv("data/raw/dinamica_empresarial.csv")
    df_lab = pd.read_csv("data/raw/mercado_laboral_bogota.csv")
    df_pib = pd.read_csv("data/raw/pib_bogota.csv")

    logger.info(f"Dinámica: {len(df_din):,} rows | Laboral: {len(df_lab)} rows | PIB: {len(df_pib):,} rows")

    conn = get_conn()
    try:
        logger.info("Loading dimensions...")
        load_dim_time(conn, df_din, df_pib, df_lab)
        load_dim_locality(conn, df_din)
        load_dim_economic_sector(conn, df_din, df_pib)
        load_dim_company_size(conn, df_din)
        load_dim_legal_form(conn, df_din)

        lookups = build_lookups(conn)

        logger.info("Loading facts...")
        load_fact_business_dynamics(conn, df_din, lookups)
        load_fact_labor_market(conn, df_lab, lookups)
        load_fact_gdp(conn, df_pib, lookups)

        logger.info("✓ All tables loaded successfully")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
