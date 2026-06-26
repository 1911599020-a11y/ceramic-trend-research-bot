#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CERAMIC_PYTHON:-/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
TOPICS_FILE="$ROOT_DIR/config/scrapecreators_quality_topics.json"
DEFAULT_OUTPUT_DIR="$ROOT_DIR/local_outputs"
OUTPUT_DIR="${KEYWORD_QUALITY_OUTPUT_DIR:-$DEFAULT_OUTPUT_DIR}"
REPORT_FILE="$OUTPUT_DIR/keyword_quality_report.md"
LATEST_FILE="$OUTPUT_DIR/keyword_quality_latest.md"
ARCHIVE_DIR="$OUTPUT_DIR/keyword_quality_archive"
STATE_FILE="$OUTPUT_DIR/keyword_quality_state.json"
ERROR_FILE="$OUTPUT_DIR/keyword_quality_error.md"
SUMMARY_FILE="$OUTPUT_DIR/keyword_quality_summary.md"
COOLDOWN_MINUTES="${CERAMIC_LIVE_COOLDOWN_MINUTES:-30}"
DRY_RUN=1
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_keyword_quality_check.sh [options]

默认只做 dry-run，不联网、不消耗 API。真实小批量测试必须显式添加 --confirm-live-api。
输出写入 local_outputs/，不会污染 reports/latest.md 或 reports/archive/。

Options:
  --confirm-live-api      明确同意运行 ScrapeCreators 小批量关键词测试
  --dry-run               只打印将要执行的命令，不联网、不消耗 API
  --force                 绕过 30 分钟 live 冷却
  --include-prompt-template
                          在测试报告末尾附加 prompt 模板，用于调试
  --no-research-evidence  不把本地研究证据写入测试报告
  --cooldown-minutes N    设置冷却分钟数
  -h, --help              显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm-live-api)
      DRY_RUN=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --force)
      EXTRA_ARGS+=("--force")
      shift
      ;;
    --include-prompt-template)
      EXTRA_ARGS+=("--include-prompt-template")
      shift
      ;;
    --no-research-evidence)
      EXTRA_ARGS+=("--no-research-evidence")
      shift
      ;;
    --cooldown-minutes)
      if [[ $# -lt 2 ]]; then
        echo "缺少 --cooldown-minutes 的数值。" >&2
        exit 2
      fi
      COOLDOWN_MINUTES="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

COMMAND=(
  "$PYTHON_BIN"
  -B
  ceramic_report.py
  --mode
  live
  --data-source
  scrapecreators_reddit
  --topics
  "$TOPICS_FILE"
  --output
  "$REPORT_FILE"
  --latest
  "$LATEST_FILE"
  --archive-dir
  "$ARCHIVE_DIR"
  --state-file
  "$STATE_FILE"
  --error-file
  "$ERROR_FILE"
  --cooldown-minutes
  "$COOLDOWN_MINUTES"
)

if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
  COMMAND+=("${EXTRA_ARGS[@]}")
fi

echo "关键词质量测试：默认小批量配置 config/scrapecreators_quality_topics.json。"
echo "测试报告和摘要只写入 local_outputs/，不会更新正式 reports/latest.md 或 reports/archive/。"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'Dry run，未联网、未消耗 API。将执行命令：\n'
  printf '%q ' "${COMMAND[@]}"
  printf '\n'
  echo "真实运行请加：--confirm-live-api"
  exit 0
fi

OUTPUT_SAFETY="$("$PYTHON_BIN" - "$OUTPUT_DIR" "$DEFAULT_OUTPUT_DIR" <<'PY'
import sys
from pathlib import Path

output_dir = Path(sys.argv[1]).expanduser().resolve(strict=False)
default_dir = Path(sys.argv[2]).expanduser().resolve(strict=False)
if output_dir == default_dir:
    print("default")
else:
    try:
        relative = output_dir.relative_to(default_dir)
    except ValueError:
        print("outside")
    else:
        if len(relative.parts) == 1 and relative.name.startswith("keyword_quality_test_"):
            print("test_subdir")
        else:
            print("outside")
PY
)"

if [[ "$OUTPUT_SAFETY" == "outside" ]]; then
  echo "安全保护：真实关键词质量测试只允许写入 ${DEFAULT_OUTPUT_DIR}。" >&2
  echo "请取消 KEYWORD_QUALITY_OUTPUT_DIR 后重试；如果只是检查命令，请使用 --dry-run。" >&2
  exit 2
fi

state_fingerprint() {
  "$PYTHON_BIN" - "$STATE_FILE" <<'PY'
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("missing")
else:
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"{stat.st_mtime_ns}:{stat.st_size}:{digest}")
PY
}

PRE_STATE_FINGERPRINT="$(state_fingerprint)"
RUN_STARTED_AT="$("$PYTHON_BIN" - <<'PY'
from datetime import datetime
print(datetime.now().astimezone().isoformat(timespec="seconds"))
PY
)"

mkdir -p "$OUTPUT_DIR" "$ARCHIVE_DIR"
"${COMMAND[@]}"

POST_STATE_FINGERPRINT="$(state_fingerprint)"
RUN_STATUS="$("$PYTHON_BIN" - "$STATE_FILE" "$RUN_STARTED_AT" "$PRE_STATE_FINGERPRINT" "$POST_STATE_FINGERPRINT" <<'PY'
from datetime import datetime
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
started_at = sys.argv[2]
pre_fingerprint = sys.argv[3]
post_fingerprint = sys.argv[4]
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception:
    print("unknown")
else:
    status = state.get("last_status") or state.get("status") or "unknown"
    if post_fingerprint == "missing" or post_fingerprint == pre_fingerprint:
        print(f"{status}:stale")
        raise SystemExit
    last_run_at = state.get("last_run_at") or ""
    try:
        last_dt = datetime.fromisoformat(last_run_at)
        started_dt = datetime.fromisoformat(started_at)
    except ValueError:
        print(f"{status}:unknown_time")
    else:
        freshness = "fresh" if last_dt >= started_dt else "stale"
        print(f"{status}:{freshness}")
PY
)"

if [[ "$RUN_STATUS" != "success:fresh" ]]; then
  echo "关键词质量 live 未成功，本次不生成摘要，避免误读旧报告。详情见 $ERROR_FILE"
  exit 0
fi

"$PYTHON_BIN" -B scripts/summarize_keyword_quality.py \
  --report "$REPORT_FILE" \
  --topics "$TOPICS_FILE" \
  --output "$SUMMARY_FILE"
