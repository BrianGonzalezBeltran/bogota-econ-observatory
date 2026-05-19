"""
Ingestion: Dinámica Empresarial (Bogotá)
Source: ArcGIS REST API - Catastro Bogotá
Table: Empresas (ID: 2)
MaxRecordCount: 2000 (requires pagination)

Fields:
  OBJECTID, IDENTIFICADOR, PERIODO (year), MES (month 1-12),
  LOCNOMBRE (locality name), LOCCODIGO (locality code),
  TAMANIOEMPRESARIAL (1-5: Micro/Pequeña/Mediana/Grande/No determinado),
  RAMAACTIVIDADECONOMICA (1-5: Agropecuaria/Comercio/Industria/Servicios/Construcción),
  CODIGOCIIU (CIIU code, 500+ values),
  ORGANIZACIONJURIDICA (1-11: Persona Natural, SAS, etc.),
  EMPRESASVIGENTES, EMPRESASCREADAS, EMPRESASCANCELADAS,
  SEXORL (1: Masculino, 2: Femenino, 3: Indeterminado)
"""

import requests
import pandas as pd
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = (
    "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services"
    "/desarrolloeconomico/dinamicaempresarial/MapServer/2/query"
)

MAX_RECORDS = 2000  # Server limit per request

# Coded value mappings from the ArcGIS service metadata
TAMANO_MAP = {
    "1": "Microempresa",
    "2": "Pequeña",
    "3": "Mediana",
    "4": "Grande",
    "5": "No determinado",
}

RAMA_MAP = {
    "1": "Agropecuaria y minera",
    "2": "Comercio",
    "3": "Industria",
    "4": "Servicios",
    "5": "Construcción",
}

ORG_JURIDICA_MAP = {
    "1": "Persona Natural",
    "2": "SAS",
    "3": "Sociedad en Comandita Simple",
    "4": "Sociedad Limitada",
    "5": "Sociedad Anónima",
    "6": "Sociedad en Comandita por Acciones",
    "7": "Empresa Unipersonal",
    "8": "Sociedad Colectiva",
    "9": "Empresa Asociativa de Trabajo",
    "10": "Sociedad Agraria de Transformación",
    "11": "Otra",
}

SEXO_MAP = {
    "1": "Masculino",
    "2": "Femenino",
    "3": "Indeterminado",
}

MES_MAP = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def fetch_record_count() -> int:
    """Get total number of records in the table."""
    params = {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json",
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "count" not in data:
        raise ValueError(f"Unexpected response: {data}")
    return data["count"]


def fetch_page(offset: int) -> list[dict]:
    """Fetch a single page of records from the ArcGIS REST API."""
    params = {
        "where": "1=1",
        "outFields": "*",
        "orderByFields": "OBJECTID ASC",
        "resultOffset": str(offset),
        "resultRecordCount": str(MAX_RECORDS),
        "f": "json",
    }
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise ValueError(f"API error: {data['error']}")

    features = data.get("features", [])
    return [f["attributes"] for f in features]


def fetch_all_records() -> list[dict]:
    """Fetch all records with pagination."""
    total = fetch_record_count()
    logger.info(f"Total records to fetch: {total:,}")

    all_records = []
    offset = 0

    while offset < total:
        logger.info(f"Fetching offset {offset:,} / {total:,} ...")
        page = fetch_page(offset)

        if not page:
            logger.warning(f"Empty page at offset {offset}, stopping.")
            break

        all_records.extend(page)
        offset += len(page)

        # Be respectful to the server
        time.sleep(0.5)

    logger.info(f"Fetched {len(all_records):,} total records")
    return all_records


def decode_values(df: pd.DataFrame) -> pd.DataFrame:
    """Apply coded value mappings to create human-readable columns."""
    df = df.copy()

    # Decode coded fields
    df["TAMANO_NOMBRE"] = df["TAMANIOEMPRESARIAL"].astype(str).map(TAMANO_MAP)
    df["RAMA_NOMBRE"] = df["RAMAACTIVIDADECONOMICA"].astype(str).map(RAMA_MAP)
    df["ORG_JURIDICA_NOMBRE"] = df["ORGANIZACIONJURIDICA"].astype(str).map(ORG_JURIDICA_MAP)
    df["SEXO_NOMBRE"] = df["SEXORL"].astype(str).map(SEXO_MAP)
    df["MES_NOMBRE"] = df["MES"].map(MES_MAP)

    return df


def to_dataframe(records: list[dict]) -> pd.DataFrame:
    """Convert raw API records to a clean DataFrame."""
    df = pd.DataFrame(records)

    # Standardize column names to lowercase
    df.columns = [c.upper() for c in df.columns]

    # Ensure numeric types
    for col in ["PERIODO", "MES", "LOCCODIGO", "EMPRESASVIGENTES", "EMPRESASCREADAS", "EMPRESASCANCELADAS"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Decode coded values
    df = decode_values(df)

    return df


def ingest(output_dir: str = "data/raw") -> pd.DataFrame:
    """Main ingestion entry point. Fetches, transforms, and saves."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    records = fetch_all_records()
    df = to_dataframe(records)

    # Save raw data
    csv_path = output_path / "dinamica_empresarial.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved {len(df):,} records to {csv_path}")

    # Print summary
    logger.info(f"Periods: {sorted(df['PERIODO'].unique())}")
    logger.info(f"Months: {sorted(df['MES'].unique())}")
    logger.info(f"Localities: {df['LOCNOMBRE'].nunique()}")
    logger.info(f"CIIU codes: {df['CODIGOCIIU'].nunique()}")
    logger.info(f"Shape: {df.shape}")

    return df


if __name__ == "__main__":
    df = ingest()
    print(df.head())
    print(f"\n{df.dtypes}")
