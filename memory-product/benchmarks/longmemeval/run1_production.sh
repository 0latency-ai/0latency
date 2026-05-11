#!/bin/bash
# RUN 1: Production Tier (Haiku extraction + Sonnet recall)
# No EXTRACTION_MODEL override = uses default Haiku

set -a
source .env.benchmark
set +a

echo "=== LONGMEMEVAL RUN 1: PRODUCTION TIER ==="
echo "Extraction: Haiku (claude-haiku-4-5-20251001)"
echo "Recall: Sonnet (default)"
echo "Dataset: n=500"
echo "Timeout: 90s extraction, 30s recall"
echo "Start: $(date)"
echo ""

python3 run_benchmark.py   ../../bench/longmemeval/upstream/data/longmemeval_s_cleaned.json   -n 500   -o results_run1_production_$(date +%Y%m%d_%H%M%S).json

echo ""
echo "Completed: $(date)"
