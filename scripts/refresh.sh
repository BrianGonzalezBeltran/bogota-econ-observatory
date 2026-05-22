#!/bin/bash
# Monthly data refresh — Bogotá Economic Observatory
set -e

LOG="/home/ubuntu/bogota-econ-observatory/logs/refresh_$(date +%Y%m%d_%H%M).log"
mkdir -p /home/ubuntu/bogota-econ-observatory/logs
cd /home/ubuntu/bogota-econ-observatory
source venv/bin/activate

echo "=== Refresh started: $(date) ===" | tee -a "$LOG"

echo "--- Ingestion ---" | tee -a "$LOG"
python -m src.ingestion.ingest_all 2>&1 | tee -a "$LOG"

echo "--- Loading ---" | tee -a "$LOG"
python -m src.loading.load_all 2>&1 | tee -a "$LOG"

echo "--- Validation ---" | tee -a "$LOG"
python -m src.loading.validate 2>&1 | tee -a "$LOG"

echo "=== Refresh complete: $(date) ===" | tee -a "$LOG"
