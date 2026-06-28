#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${CERAMIC_PYTHON:-/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"

"$PYTHON_BIN" -B scripts/summarize_keyword_convergence.py "$@"
