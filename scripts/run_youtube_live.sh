#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CERAMIC_PYTHON:-/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
STATE_FILE="${CERAMIC_YOUTUBE_RUN_STATE_FILE:-$ROOT_DIR/local_outputs/youtube_run_state.json}"
ERROR_FILE="${CERAMIC_YOUTUBE_LAST_ERROR_FILE:-$ROOT_DIR/local_outputs/youtube_live_error.md}"
COOLDOWN_MINUTES="${CERAMIC_LIVE_COOLDOWN_MINUTES:-30}"
TOPICS_FILE="$ROOT_DIR/config/youtube_probe_topics.json"
DRY_RUN=0
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_youtube_live.sh [options]

默认只跑 config/youtube_probe_topics.json 的单关键词配置，避免误消耗 API 额度。
这是显式 opt-in 的 YouTube Search live；不会改变 --data-source auto 的 Reddit 默认源。

Options:
  --dry-run                只打印将要执行的命令，不联网、不消耗 API
  --force                  绕过 30 分钟 live 冷却
  --confirm-full-api       明确同意使用完整 config/ceramic_topics.json 跑全量关键词
  --include-prompt-template
                           在报告末尾附加 prompt 模板，用于调试
  --no-research-evidence   不把本地研究证据写入报告
  --cooldown-minutes N     设置冷却分钟数
  -h, --help               显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --force)
      EXTRA_ARGS+=("--force")
      shift
      ;;
    --confirm-full-api)
      TOPICS_FILE="$ROOT_DIR/config/ceramic_topics.json"
      EXTRA_ARGS+=("--confirm-full-api")
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
  scrapecreators_youtube_search
  --topics
  "$TOPICS_FILE"
  --output
  reports/report.md
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

if [[ "$TOPICS_FILE" == "$ROOT_DIR/config/ceramic_topics.json" ]]; then
  echo "YouTube live：已显式确认全量关键词运行，可能消耗更多 ScrapeCreators API 额度。"
else
  echo "YouTube live：默认安全模式，只运行单关键词配置 config/youtube_probe_topics.json。"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'Dry run，未联网、未消耗 API。将执行命令：\n'
  printf '%q ' "${COMMAND[@]}"
  printf '\n'
  exit 0
fi

"${COMMAND[@]}"
