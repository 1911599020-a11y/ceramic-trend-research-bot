#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CERAMIC_PYTHON:-/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
STATE_FILE="${CERAMIC_RUN_STATE_FILE:-$ROOT_DIR/local_outputs/run_state.json}"
ERROR_FILE="${CERAMIC_LAST_ERROR_FILE:-$ROOT_DIR/local_outputs/last_error.md}"
COOLDOWN_MINUTES="${CERAMIC_LIVE_COOLDOWN_MINUTES:-30}"
# Optional override for the external last30days.py path (same style as
# CERAMIC_PYTHON). When unset, ceramic_report.py falls back to
# LAST30DAYS_SCRIPT (legacy env) and then the original Mac default path.
LAST30DAYS_SCRIPT_PATH="${CERAMIC_LAST30DAYS_SCRIPT:-}"

cd "$ROOT_DIR"
if [[ -n "$LAST30DAYS_SCRIPT_PATH" ]]; then
  set -- --last30days-script "$LAST30DAYS_SCRIPT_PATH" "$@"
fi
"$PYTHON_BIN" -B ceramic_report.py \
  --mode live \
  --data-source auto \
  --output reports/report.md \
  --state-file "$STATE_FILE" \
  --error-file "$ERROR_FILE" \
  --cooldown-minutes "$COOLDOWN_MINUTES" \
  "$@"

if [[ -f "$STATE_FILE" ]]; then
  "$PYTHON_BIN" - "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

if state.get("mode") != "live":
    raise SystemExit(0)

status = state.get("last_status") or state.get("status")
error_type = state.get("last_error_type") or state.get("error_type")
scrapecreators = state.get("scrapecreators_fallback") or "missing"
data_source = state.get("data_source") or "unknown"
data_source_label = state.get("data_source_label") or data_source
if status not in {"failed", "rate_limited"}:
    raise SystemExit(0)

messages = {
    "forbidden_403": "Reddit 已拒绝当前请求，通常是代理出口、IP、User-Agent 或 Reddit 访问策略导致。建议换代理节点，确认终端代理生效，稍后再试。代码和报告生成逻辑通常没有坏。可先运行 bash scripts/check_environment.sh 查看终端代理和 Reddit 状态。",
    "rate_limited_429": "Reddit 临时限流。请至少等待 30 分钟，不要连续使用 --force。可以先用 mock 模式调整报告结构。",
    "dns_error": "当前运行环境无法解析 Reddit 域名。请检查网络、代理、DNS，或换到本地终端运行。可先运行 bash scripts/check_environment.sh 对比 DNS、HTTPS 和代理状态。",
    "timeout": "网络连接不稳定或代理出口被重置。建议检查代理节点或稍后再试。可先运行 bash scripts/check_environment.sh 查看终端网络状态。",
    "network_error": "网络连接异常。请检查代理、DNS 和终端网络环境，稍后再试。可先运行 bash scripts/check_environment.sh 查看诊断结果。",
}

print("")
print("Live 运行提示：")
print(f"本次数据源：{data_source_label} ({data_source})")
print("判断：这是数据源访问失败，不是报告生成器或历史报告保护逻辑坏了。")
message = messages.get(error_type, "live 运行失败，已保留上一份成功报告。请查看 local_outputs/last_error.md。")
if error_type == "forbidden_403":
    if scrapecreators == "configured":
        message += " 当前检测到 ScrapeCreators 备份已配置；如果仍失败，请检查 key 是否有效、额度是否充足，以及当前数据源是否正确读取配置。"
    else:
        message += " 当前没有检测到 ScrapeCreators 备份；如果 public Reddit JSON 持续 403，下一步可以考虑配置 SCRAPECREATORS_API_KEY，或先切到其他更稳定数据源。"
print(message)
print("错误详情：local_outputs/last_error.md")
PY
fi
