#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CERAMIC_PYTHON:-/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
STATE_FILE="${CERAMIC_RUN_STATE_FILE:-$ROOT_DIR/local_outputs/run_state.json}"

cd "$ROOT_DIR"
"$PYTHON_BIN" -B ceramic_report.py \
  --mode mock \
  --output reports/report.md \
  --state-file "$STATE_FILE" \
  "$@"
