"""
Ingestion: PIB Bogotá
Source: Datos Abiertos Bogotá - XLSX download
Period: Quarterly, IV Trim 2005 - I Trim 2025
Content: GDP at current and constant prices (base year 2015),
         25 economic activity branches (ramas de actividad económica)
"""

import requests
import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DOWNLOAD_URL = (
    "https://datosabiertos.bogota.gov.co/dataset/"
    "ad0730fe-18c6-43ed-94b9-e67c4d55f48a/resource/"
    "90c4869f-0111-40f0-b3ff-f4f4a89e4067/download/"
    "conjunto-pib-bogota-24022026.xlsx"
)


def download_xlsx(output_dir: str = "data/raw") -> Path:
    """Download the XLSX file from Datos Abiertos Bogotá."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / "pib_bogota.xlsx"

    logger.info("Downloading PIB Bogotá XLSX...")
    resp = requests.get(DOWNLOAD_URL, timeout=60)
    resp.raise_for_status()

    file_path.write_bytes(resp.content)
    logger.info(f"Downloaded {len(resp.content):,} bytes to {file_path}")
    return file_path


def read_and_clean(file_path: Path) -> pd.DataFrame:
    """Read the XLSX and standardize it."""
    xlsx = pd.ExcelFile(file_path)
    logger.info(f"Sheets found: {xlsx.sheet_names}")

    # Read first sheet, explore structure
    df = pd.read_excel(file_path, sheet_name=0)
    logger.info(f"Raw shape: {df.shape}")
    logger.info(f"Columns: {list(df.columns)}")
    logger.info(f"First 3 rows:\n{df.head(3).to_string()}")

    # Standardize column names
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    logger.info(f"Cleaned columns: {list(df.columns)}")

    return df


def ingest(output_dir: str = "data/raw") -> pd.DataFrame:
    """Main ingestion entry point."""
    xlsx_path = download_xlsx(output_dir)
    df = read_and_clean(xlsx_path)

    # Save as CSV
    csv_path = Path(output_dir) / "pib_bogota.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved {len(df):,} records to {csv_path}")

    return df


if __name__ == "__main__":
    df = ingest()
    print(df.info())
