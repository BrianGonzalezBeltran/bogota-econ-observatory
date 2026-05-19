"""
Orchestrator: Run all data ingestions.
Usage: python -m src.ingestion.ingest_all
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    results = {}

    # 1. Dinámica Empresarial (ArcGIS REST API)
    logger.info("=" * 60)
    logger.info("INGESTING: Dinámica Empresarial")
    logger.info("=" * 60)
    try:
        from src.ingestion.dinamica_empresarial import ingest as ingest_dinamica
        df = ingest_dinamica()
        results["dinamica_empresarial"] = {"status": "OK", "rows": len(df)}
    except Exception as e:
        logger.error(f"Failed: {e}")
        results["dinamica_empresarial"] = {"status": "FAILED", "error": str(e)}

    # 2. Mercado Laboral (XLSX)
    logger.info("=" * 60)
    logger.info("INGESTING: Mercado Laboral")
    logger.info("=" * 60)
    try:
        from src.ingestion.mercado_laboral import ingest as ingest_mercado
        df = ingest_mercado()
        results["mercado_laboral"] = {"status": "OK", "rows": len(df)}
    except Exception as e:
        logger.error(f"Failed: {e}")
        results["mercado_laboral"] = {"status": "FAILED", "error": str(e)}

    # 3. PIB Bogotá (XLSX)
    logger.info("=" * 60)
    logger.info("INGESTING: PIB Bogotá")
    logger.info("=" * 60)
    try:
        from src.ingestion.pib_bogota import ingest as ingest_pib
        df = ingest_pib()
        results["pib_bogota"] = {"status": "OK", "rows": len(df)}
    except Exception as e:
        logger.error(f"Failed: {e}")
        results["pib_bogota"] = {"status": "FAILED", "error": str(e)}

    # Summary
    logger.info("=" * 60)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 60)
    for name, result in results.items():
        status = result["status"]
        detail = f"{result['rows']:,} rows" if status == "OK" else result["error"]
        logger.info(f"  {name}: {status} ({detail})")

    # Exit with error if any failed
    if any(r["status"] == "FAILED" for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
