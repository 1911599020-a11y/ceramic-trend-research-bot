#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CERAMIC_PYTHON:-/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
STATE_FILE="${CERAMIC_RUN_STATE_FILE:-$ROOT_DIR/local_outputs/run_state.json}"
# Mock mode no longer needs the external last30days-skill; the variable is
# still forwarded (same style as run_live.sh) so both scripts honour the same
# configuration surface.
LAST30DAYS_SCRIPT_PATH="${CERAMIC_LAST30DAYS_SCRIPT:-}"

cd "$ROOT_DIR"
if [[ -n "$LAST30DAYS_SCRIPT_PATH" ]]; then
  set -- --last30days-script "$LAST30DAYS_SCRIPT_PATH" "$@"
fi
"$PYTHON_BIN" -B ceramic_report.py \
  --mode mock \
  --output reports/report.md \
  --state-file "$STATE_FILE" \
  "$@"
