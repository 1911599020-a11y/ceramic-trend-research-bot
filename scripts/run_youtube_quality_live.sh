#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CERAMIC_PYTHON:-/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
STATE_FILE="${CERAMIC_YOUTUBE_QUALITY_RUN_STATE_FILE:-$ROOT_DIR/local_outputs/youtube_quality_run_state.json}"
ERROR_FILE="${CERAMIC_YOUTUBE_QUALITY_LAST_ERROR_FILE:-$ROOT_DIR/local_outputs/youtube_quality_error.md}"
COOLDOWN_MINUTES="${CERAMIC_LIVE_COOLDOWN_MINUTES:-30}"
TOPICS_FILE="$ROOT_DIR/config/youtube_quality_topics.json"
CONFIRM_LIVE_API=0
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_youtube_quality_live.sh [options]

默认 dry-run，只检查 YouTube 多关键词小样本命令，不联网、不消耗 API。
真实运行必须显式加 --confirm-live-api；默认只跑 config/youtube_quality_topics.json 的 3 个关键词。

Options:
  --confirm-live-api      明确同意发起 ScrapeCreators YouTube Search 真实请求
  --force                 绕过 30 分钟 live 冷却
  --include-prompt-template
                          在报告末尾附加 prompt 模板，用于调试
  --no-research-evidence  不把本地研究证据写入报告
  --cooldown-minutes N    设置冷却分钟数
  -h, --help              显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm-live-api)
      CONFIRM_LIVE_API=1
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

echo "YouTube quality live：默认使用 3 个关键词的小样本配置 config/youtube_quality_topics.json。"

if [[ "$CONFIRM_LIVE_API" -ne 1 ]]; then
  printf 'Dry run，未联网、未消耗 API。真实运行请加 --confirm-live-api。将执行命令：\n'
  printf '%q ' "${COMMAND[@]}"
  printf '\n'
  exit 0
fi

echo "YouTube quality live：已确认真实运行，可能消耗 ScrapeCreators API 额度。"
"${COMMAND[@]}"
