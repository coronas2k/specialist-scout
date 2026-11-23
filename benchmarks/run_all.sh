#!/usr/bin/env bash
# Run every benchmark and save the output to results/<date>-run.txt.
# Usage (from anywhere):  benchmarks/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${AGENCY_VENV:-${CLAUDE_PLUGIN_DATA:-$HOME/.cache/agency-skill}/.venv}/bin/python"
OUT="benchmarks/results/$(date +%Y-%m-%d)-run.txt"
{
  echo "# search (keyword, embeddings, hybrid) on eval, holdout and holdout2"
  $PY benchmarks/search_eval.py --all
  echo
  echo "# orchestration (3 projects, 37 subtasks)"
  $PY benchmarks/orchestration_eval.py
  echo
  echo "# fusion weightings (76 queries combined)"
  $PY benchmarks/fusion_experiment.py
} | tee "$OUT"
echo "saved $OUT"
