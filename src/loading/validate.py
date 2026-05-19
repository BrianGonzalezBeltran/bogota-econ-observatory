"""
Quick validation queries after loading.
Usage: python -m src.loading.validate
"""

import os
import psycopg2

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "observatory"),
    "user": os.getenv("DB_USER", "observatory"),
    "password": os.getenv("DB_PASSWORD", "observatory_dev_2026"),
}


def run():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("=" * 60)
    print("TABLE ROW COUNTS")
    print("=" * 60)
    tables = [
        "dim_time", "dim_locality", "dim_economic_sector",
        "dim_company_size", "dim_legal_form",
        "fact_business_dynamics", "fact_labor_market", "fact_gdp",
    ]
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t:35s} {cur.fetchone()[0]:>10,}")

    print("\n" + "=" * 60)
    print("SAMPLE: Top 5 localities by empresas vigentes")
    print("=" * 60)
    cur.execute("""
        SELECT l.locality_name, SUM(f.empresas_vigentes) as total
        FROM fact_business_dynamics f
        JOIN dim_locality l ON f.locality_id = l.locality_id
        GROUP BY l.locality_name
        ORDER BY total DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:25s} {row[1]:>12,}")

    print("\n" + "=" * 60)
    print("SAMPLE: Latest unemployment rate")
    print("=" * 60)
    cur.execute("""
        SELECT t.year, t.trimester_label, f.tasa_desocupacion
        FROM fact_labor_market f
        JOIN dim_time t ON f.time_id = t.time_id
        ORDER BY t.year DESC, t.quarter DESC
        LIMIT 3
    """)
    for row in cur.fetchall():
        print(f"  {row[0]} {row[1]:20s} → {row[2]:.2f}%")

    print("\n" + "=" * 60)
    print("SAMPLE: Top 3 GDP sectors (latest quarter, constant prices)")
    print("=" * 60)
    cur.execute("""
        SELECT s.ciiu_description, f.pib_precios_constantes_2015
        FROM fact_gdp f
        JOIN dim_time t ON f.time_id = t.time_id
        JOIN dim_economic_sector s ON f.sector_id = s.sector_id
        WHERE t.year = (SELECT MAX(year) FROM dim_time WHERE quarter IS NOT NULL)
          AND t.quarter = (SELECT MAX(quarter) FROM dim_time
                           WHERE year = (SELECT MAX(year) FROM dim_time WHERE quarter IS NOT NULL)
                             AND quarter IS NOT NULL)
          AND s.ciiu_description IS NOT NULL
        ORDER BY f.pib_precios_constantes_2015 DESC
        LIMIT 3
    """)
    for row in cur.fetchall():
        print(f"  {row[0][:45]:45s} {row[1]:>12,.2f}")

    conn.close()
    print("\n✓ Validation complete")


if __name__ == "__main__":
    run()
