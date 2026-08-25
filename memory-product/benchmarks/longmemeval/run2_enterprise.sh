#!/bin/bash
# RUN 2: Enterprise Tier (Sonnet extraction + Sonnet recall)

set -a
source .env.benchmark
set +a

# Explicitly set Sonnet 4.5 extraction
export EXTRACTION_MODEL=claude-sonnet-4-6

echo "=== LONGMEMEVAL RUN 2: ENTERPRISE TIER ==="
echo "Extraction: Sonnet ($EXTRACTION_MODEL)"
echo "Recall: Sonnet (default)"
echo "Dataset: n=500"
echo "Timeout: 90s extraction, 30s recall"
echo "Start: $(date)"
echo ""

# Set Sonnet extraction in main .env
echo "Configuring API to use Sonnet extraction..."
cd ../../
cp .env .env.backup-before-run2
sed -i.bak "s/^EXTRACTION_MODEL=.*/EXTRACTION_MODEL=claude-sonnet-4-6/" .env

# Restart API
sudo systemctl restart zerolatency-api
sleep 10
echo "API restarted with Sonnet extraction"

# Run benchmark
cd benchmarks/longmemeval
python3 run_benchmark.py   ../../bench/longmemeval/upstream/data/longmemeval_s_cleaned.json   -n 500   -o results_run2_enterprise_$(date +%Y%m%d_%H%M%S).json

echo ""
echo "Completed: $(date)"

# Restore .env and API
cd ../../
mv .env.backup-before-run2 .env
sudo systemctl restart zerolatency-api
echo "API restored to Haiku extraction"
