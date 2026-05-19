"""
Ingestion: Mercado Laboral Bogotá
Source: Datos Abiertos Bogotá - XLSX download
Period: Quarterly rolling trimesters, Jan-Mar 2021 to Oct-Dec 2025

Expected fields (from metadata):
  Periodo (year), Trimestre_movil (e.g. "Enero - Marzo"),
  Poblacion_en_edad_de_trabajar, Poblacion_economicamente_activa,
  Ocupados, Desocupados, Inactivos, Asalariados, No_asalariados,
  Informales, Tasa_global_participacion, Tasa_de_ocupacion,
  Tasa_de_desempleo, Tasa_de_asalariados, Tasa_de_informalidad
"""

import requests
import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DOWNLOAD_URL = (
    "https://datosabiertos.bogota.gov.co/dataset/"
    "199722a1-e999-422e-8214-cac75264efec/resource/"
    "51ae1760-fc6d-47d1-9c7c-669b0f3bc517/download/"
    "conjunto-mercado-laboral-bogota-24022026.xlsx"
)


def download_xlsx(output_dir: str = "data/raw") -> Path:
    """Download the XLSX file from Datos Abiertos Bogotá."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / "mercado_laboral_bogota.xlsx"

    logger.info(f"Downloading mercado laboral XLSX...")
    resp = requests.get(DOWNLOAD_URL, timeout=60)
    resp.raise_for_status()

    file_path.write_bytes(resp.content)
    logger.info(f"Downloaded {len(resp.content):,} bytes to {file_path}")
    return file_path


def read_and_clean(file_path: Path) -> pd.DataFrame:
    """Read the XLSX and standardize it."""
    # The file might have multiple sheets or header rows — explore first
    xlsx = pd.ExcelFile(file_path)
    logger.info(f"Sheets found: {xlsx.sheet_names}")

    # Try reading the first sheet, auto-detecting header
    df = pd.read_excel(file_path, sheet_name=0)
    logger.info(f"Raw shape: {df.shape}")
    logger.info(f"Columns: {list(df.columns)}")

    # Print first few rows for inspection
    logger.info(f"First 3 rows:\n{df.head(3).to_string()}")

    # Standardize column names: strip whitespace, lowercase, replace spaces
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    logger.info(f"Cleaned columns: {list(df.columns)}")

    return df


def ingest(output_dir: str = "data/raw") -> pd.DataFrame:
    """Main ingestion entry point."""
    xlsx_path = download_xlsx(output_dir)
    df = read_and_clean(xlsx_path)

    # Save as CSV for pipeline consistency
    csv_path = Path(output_dir) / "mercado_laboral_bogota.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved {len(df):,} records to {csv_path}")

    return df


if __name__ == "__main__":
    df = ingest()
    print(df.info())
