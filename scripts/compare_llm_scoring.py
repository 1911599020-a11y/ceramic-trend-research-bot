#!/usr/bin/env python3
"""Compare rule scoring with a tiny opt-in DeepSeek scoring run.

This stays outside the formal report pipeline. It writes only to local_outputs/
so DeepSeek can be evaluated before any production report integration.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scoring.llm_scorer import (  # noqa: E402
    LLMScoringResult,
    build_llm_scoring_prompt,
    combine_rule_and_llm,
    load_llm_scoring_config,
)
from probe_llm_scoring import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    LOCAL_OUTPUTS_DIR,
    MAX_SAMPLE_COUNT,
    SAMPLE_ITEMS,
    classify_http_error,
    classify_url_error,
    configured_deepseek_key,
    effective_env,
    escape_cell,
    project_path,
    parse_deepseek_score_response,
    redact_secret,
    request_deepseek_score,
    resolve_base_url,
    resolve_llm_scoring_switch,
    resolve_model,
    result_to_dict,
    sample_to_dict,
    utc_now_iso,
    validate_deepseek_base_url,
    write_json,
)


SOURCE_ID = "deepseek_llm_scoring_comparison"
DEFAULT_SAMPLE_COUNT = 5
EXPECTED_OUTPUTS = {
    "state-file": LOCAL_OUTPUTS_DIR / "llm_scoring_comparison_state.json",
    "output": LOCAL_OUTPUTS_DIR / "llm_scoring_comparison.md",
    "json-output": LOCAL_OUTPUTS_DIR / "llm_scoring_comparison.json",
    "error-file": LOCAL_OUTPUTS_DIR / "llm_scoring_comparison_error.md",
}


@dataclass(frozen=True)
class ComparisonPaths:
    state_file: Path
    output_file: Path
    json_file: Path
    error_file: Path
    report_file: Path
    latest_file: Path
    archive_dir: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a tiny opt-in rule-vs-DeepSeek scoring comparison. "
            "Without --confirm-live-api this command does not call the network."
        )
    )
    parser.add_argument("--confirm-live-api", action="store_true")
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--config", default="config/llm_scoring.json")
    parser.add_argument("--prompt", default="prompts/llm_scoring_prompt.md")
    parser.add_argument("--state-file", default="local_outputs/llm_scoring_comparison_state.json")
    parser.add_argument("--output", default="local_outputs/llm_scoring_comparison.md")
    parser.add_argument("--json-output", default="local_outputs/llm_scoring_comparison.json")
    parser.add_argument("--error-file", default="local_outputs/llm_scoring_comparison_error.md")
    parser.add_argument("--dotenv-file", default=None)

    # Test-only guard paths. The comparison never writes these files.
    parser.add_argument("--report-file", default="reports/report.md", help=argparse.SUPPRESS)
    parser.add_argument("--latest-file", default="reports/latest.md", help=argparse.SUPPRESS)
    parser.add_argument("--archive-dir", default="reports/archive", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def clamp_sample_count(value: int) -> int:
    if value < 1:
        return 1
    return min(value, MAX_SAMPLE_COUNT)


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def validate_local_output_paths(paths: ComparisonPaths) -> str:
    for label, path in (
        ("state-file", paths.state_file),
        ("output", paths.output_file),
        ("json-output", paths.json_file),
        ("error-file", paths.error_file),
    ):
        if not is_within_directory(path, LOCAL_OUTPUTS_DIR):
            return f"{label} 必须位于 local_outputs/ 目录内：{path}"
        expected = EXPECTED_OUTPUTS[label]
        if path.resolve() != expected.resolve():
            return f"{label} 必须固定为 {expected.relative_to(PROJECT_ROOT)}"
    return ""


def base_state(
    *,
    status: str,
    error_type: str,
    model: str,
    sample_count: int,
    requested_at: str,
    network_request_attempted: bool,
    key_status: str,
    llm_scoring_enabled: bool,
    switch_env_var: str,
    switch_source: str,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": status,
        "error_type": error_type,
        "model": model,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "network_request_attempted": network_request_attempted,
        "report_files_updated": False,
        "report_paths": {
            "report": "reports/report.md",
            "latest": "reports/latest.md",
            "archive": "reports/archive/",
        },
        "key_status": key_status,
        "llm_scoring_enabled": llm_scoring_enabled,
        "switch_env_var": switch_env_var,
        "switch_source": switch_source,
    }


def write_error_markdown(
    path: Path,
    *,
    state: Mapping[str, Any],
    message: str,
    next_step: str,
    secret: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "# DeepSeek 评分对照报告错误",
            "",
            f"- 错误类型：{state.get('error_type', 'unknown_error')}",
            f"- 发生时间：{state.get('requested_at', '')}",
            f"- 样本数量：{state.get('sample_count', '')}",
            f"- 是否已发起网络请求：{state.get('network_request_attempted', False)}",
            "- 保护动作：未覆盖 reports/report.md、reports/latest.md 或 reports/archive/",
            f"- 错误说明：{redact_secret(message, secret)}",
            f"- 建议下一步：{redact_secret(next_step, secret)}",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def failure_summary(
    *,
    error_type: str,
    model: str,
    sample_count: int,
    requested_at: str,
    network_request_attempted: bool,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "failure",
        "error_type": error_type,
        "model": model,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "network_request_attempted": network_request_attempted,
        "results": [],
        "report_files_updated": False,
    }


def alignment_label(rule_level: str, result: LLMScoringResult) -> str:
    if result.is_noise or result.ceramic_relevance == "low":
        if rule_level == "high":
            return "DeepSeek 降级：规则疑似误判"
        return "一致低相关或噪音"
    if (
        rule_level == "high"
        and result.ceramic_relevance == "high"
        and result.can_support_trend
        and result.keyword_intent_match in {"high", "medium"}
    ):
        return "一致高相关"
    if rule_level != "high" and result.can_support_trend:
        return "DeepSeek 提醒：可能漏判"
    if result.ceramic_relevance == "high":
        return "陶瓷相关但不宜入趋势"
    if result.ceramic_relevance == "edge":
        return "边缘相关，建议人工复核"
    return "需要人工复核"


def aggregate_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(rows),
        "agree_high": 0,
        "llm_demoted": 0,
        "llm_promoted": 0,
        "agree_low_or_noise": 0,
        "edge_review": 0,
        "ceramic_but_not_trend": 0,
        "review": 0,
    }
    for row in rows:
        alignment = str(row["alignment"])
        if alignment == "一致高相关":
            counts["agree_high"] += 1
        elif alignment.startswith("DeepSeek 降级"):
            counts["llm_demoted"] += 1
        elif alignment.startswith("DeepSeek 提醒"):
            counts["llm_promoted"] += 1
        elif alignment == "一致低相关或噪音":
            counts["agree_low_or_noise"] += 1
        elif alignment == "边缘相关，建议人工复核":
            counts["edge_review"] += 1
        elif alignment == "陶瓷相关但不宜入趋势":
            counts["ceramic_but_not_trend"] += 1
        elif alignment == "需要人工复核":
            counts["review"] += 1
    return counts


def comparison_success_summary(
    *,
    model: str,
    base_url: str,
    sample_count: int,
    requested_at: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "success",
        "model": model,
        "base_url": base_url,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "counts": aggregate_counts(rows),
        "results": rows,
        "report_files_updated": False,
    }


def render_comparison_markdown(
    *,
    requested_at: str,
    model: str,
    base_url: str,
    rows: list[dict[str, Any]],
) -> str:
    counts = aggregate_counts(rows)
    lines = [
        "# DeepSeek 与规则评分对照报告",
        "",
        f"- 生成时间：{requested_at}",
        f"- 模型：{model}",
        f"- Base URL：{base_url}",
        "- 说明：这是 V0.6.9 旁路对照报告，不是正式趋势报告。",
        "- 保护动作：未覆盖 reports/report.md、reports/latest.md 或 reports/archive/。",
        "",
        "## 对照结论摘要",
        "",
        f"- 本轮对照样本：{counts['total']} 条。",
        f"- 规则与 DeepSeek 一致认为高相关：{counts['agree_high']} 条。",
        f"- DeepSeek 将规则高分样本降级为噪音或低相关：{counts['llm_demoted']} 条。",
        f"- DeepSeek 提醒规则可能漏判：{counts['llm_promoted']} 条。",
        f"- 一致认为低相关或噪音：{counts['agree_low_or_noise']} 条。",
        f"- 陶瓷相关但不宜进入趋势：{counts['ceramic_but_not_trend']} 条。",
        f"- 边缘相关，建议人工复核：{counts['edge_review']} 条。",
        f"- 仍建议人工复核：{counts['review']} 条。",
        "- 这份报告只用于判断 DeepSeek 是否值得接入正式流程，不代表正式趋势结论。",
        "",
        "## 对照明细",
        "",
        "| 关键词 | 标题 | 规则判断 | DeepSeek 判断 | 对照结果 | 合并建议 | DeepSeek 理由 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        sample = row["sample"]
        result = row["llm_result"]
        combined = row["combined"]
        lines.append(
            "| {topic} | {title} | {rule} | {llm} | {alignment} | {combined} | {reason} |".format(
                topic=escape_cell(sample["topic"]),
                title=escape_cell(sample["title"]),
                rule=escape_cell(
                    f"{sample['rule_level']} / {sample['rule_score']}；{sample['rule_notes']}"
                ),
                llm=escape_cell(
                    "{relevance}/{intent}；{etype}；趋势={trend}；噪音={noise}；置信度={confidence}".format(
                        relevance=result["ceramic_relevance"],
                        intent=result["keyword_intent_match"],
                        etype=result["evidence_type"],
                        trend="是" if result["can_support_trend"] else "否",
                        noise="是" if result["is_noise"] else "否",
                        confidence=result["confidence"],
                    )
                ),
                alignment=escape_cell(row["alignment"]),
                combined=escape_cell(f"{combined['level']} / {combined['confidence']}；{combined['reason']}"),
                reason=escape_cell(result["reason"]),
            )
        )
    lines.extend(
        [
            "",
            "## 怎么使用这份对照",
            "",
            "- 如果 DeepSeek 经常把规则高分样本降级，说明关键词规则容易被表面词误导。",
            "- 如果 DeepSeek 和规则稳定一致，可以考虑下一步只把它用于低置信度样本复核。",
            "- 如果 DeepSeek 判断不稳定或成本不划算，就继续保持规则评分为主。",
            "- 当前阶段不要把这份对照直接写入正式报告。",
        ]
    )
    return "\n".join(lines) + "\n"


def combined_to_dict(level: str, confidence: int, reason: str) -> dict[str, Any]:
    return {"level": level, "confidence": confidence, "reason": reason}


def build_row(item: Any, result: LLMScoringResult) -> dict[str, Any]:
    combined = combine_rule_and_llm(
        rule_level=item.rule_level,
        rule_score=item.rule_score,
        llm_result=result,
    )
    return {
        "sample": sample_to_dict(item),
        "llm_result": result_to_dict(result),
        "alignment": alignment_label(item.rule_level, result),
        "combined": combined_to_dict(combined.level, combined.confidence, combined.reason),
    }


def next_step_for(error_type: str) -> str:
    return {
        "unauthorized_401": "检查 DEEPSEEK_API_KEY 是否有效，或是否需要重新生成 key。",
        "forbidden_403": "检查 DeepSeek 账号权限、模型权限或 API 访问策略。",
        "rate_limited_429": "已被限流，请等待后再试，不要连续重复请求。",
        "quota_or_billing": "检查 DeepSeek 后台余额、额度或账单状态。",
        "timeout": "检查网络或代理状态，稍后再试。",
        "network_error": "检查网络、DNS、代理或 DeepSeek API 服务状态。",
        "parse_error": "模型返回不是预期 JSON，需要检查 prompt 或 JSON Output 支持情况。",
        "switch_off": "确认要消耗 DeepSeek 额度时，将 LLM_SCORING_ENABLED=on 写入 .env，或仅本次临时打开。",
        "missing_key": "确认 .env 或系统环境变量里已配置 DEEPSEEK_API_KEY，然后再运行对照报告。",
        "unknown_error": "保留错误文件后再排查，不要重复发起请求。",
    }.get(error_type, "保留错误文件后再排查，不要重复发起请求。")


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    allow_outside_local_outputs: bool = False,
) -> int:
    args = parse_args(argv)
    requested_at = utc_now_iso()
    sample_count = clamp_sample_count(args.sample_count)
    paths = ComparisonPaths(
        state_file=project_path(args.state_file),
        output_file=project_path(args.output),
        json_file=project_path(args.json_output),
        error_file=project_path(args.error_file),
        report_file=project_path(args.report_file),
        latest_file=project_path(args.latest_file),
        archive_dir=project_path(args.archive_dir),
    )
    if not allow_outside_local_outputs:
        path_error = validate_local_output_paths(paths)
        if path_error:
            print("DeepSeek 评分对照：输出路径不安全，未发起网络请求。")
            print(path_error)
            print("请使用默认 local_outputs/ 路径，避免误写正式报告或其他文件。")
            return 2

    values = effective_env(env, args.dotenv_file)
    config = load_llm_scoring_config(project_path(args.config))
    model = resolve_model(args, values, config.model or DEFAULT_MODEL)
    base_url = resolve_base_url(args, values) or DEFAULT_BASE_URL
    api_key = configured_deepseek_key(values)
    llm_switch_enabled, switch_source = resolve_llm_scoring_switch(
        values,
        switch_env_var=config.switch_env_var,
        enabled_values=config.enabled_values,
    )
    prompt_template = project_path(args.prompt).read_text(encoding="utf-8")
    base_url_error = validate_deepseek_base_url(base_url)
    common_state = {
        "model": model,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "key_status": "configured" if api_key else "missing",
        "llm_scoring_enabled": llm_switch_enabled,
        "switch_env_var": config.switch_env_var,
        "switch_source": switch_source,
    }
    if base_url_error:
        state = base_state(
            status="invalid_base_url",
            error_type="invalid_base_url",
            network_request_attempted=False,
            **common_state,
        )
        write_json(paths.state_file, state)
        write_error_markdown(
            paths.error_file,
            state=state,
            message=base_url_error,
            next_step="删除 DEEPSEEK_BASE_URL 或使用默认官方 API 地址后再试。",
            secret=api_key,
        )
        print("DeepSeek 评分对照：base URL 不安全，未发起网络请求。")
        print(base_url_error)
        return 2

    if not args.confirm_live_api:
        state = base_state(
            status="not_confirmed",
            error_type="not_confirmed",
            network_request_attempted=False,
            **common_state,
        )
        write_json(paths.state_file, state)
        print("DeepSeek 评分对照：未发起网络请求。")
        print(
            "如需真实对照报告，请同时打开 "
            f"{config.switch_env_var}=on 并显式添加 --confirm-live-api。"
        )
        print(f"状态已写入：{paths.state_file}")
        return 0

    if not llm_switch_enabled:
        state = base_state(
            status="switch_off",
            error_type="switch_off",
            network_request_attempted=False,
            **common_state,
        )
        write_json(paths.state_file, state)
        write_json(
            paths.json_file,
            failure_summary(
                error_type="switch_off",
                model=model,
                sample_count=sample_count,
                requested_at=requested_at,
                network_request_attempted=False,
            ),
        )
        write_error_markdown(
            paths.error_file,
            state=state,
            message=(
                f"{config.switch_env_var} 未开启。虽然已收到 --confirm-live-api，"
                "但没有发起 DeepSeek 网络请求。"
            ),
            next_step=next_step_for("switch_off"),
            secret=api_key,
        )
        print("DeepSeek 评分对照：开关未开启，未发起网络请求。")
        print(f"请先打开 {config.switch_env_var}=on，再运行真实对照。")
        print(f"错误详情见：{paths.error_file}")
        return 0

    if not api_key:
        state = base_state(
            status="missing_key",
            error_type="missing_key",
            network_request_attempted=False,
            **common_state,
        )
        write_json(paths.state_file, state)
        write_json(
            paths.json_file,
            failure_summary(
                error_type="missing_key",
                model=model,
                sample_count=sample_count,
                requested_at=requested_at,
                network_request_attempted=False,
            ),
        )
        write_error_markdown(
            paths.error_file,
            state=state,
            message="未找到 DEEPSEEK_API_KEY。没有发起网络请求。",
            next_step=next_step_for("missing_key"),
        )
        print("DeepSeek 评分对照：未找到 API key，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0

    try:
        rows: list[dict[str, Any]] = []
        for item in SAMPLE_ITEMS[:sample_count]:
            prompt = build_llm_scoring_prompt(prompt_template, item)
            payload, _status_code = request_deepseek_score(
                api_key=api_key,
                base_url=base_url,
                model=model,
                prompt=prompt,
                timeout=args.timeout,
            )
            result = parse_deepseek_score_response(payload)
            rows.append(build_row(item, result))

        state = base_state(
            status="success",
            error_type="",
            network_request_attempted=True,
            **common_state,
        )
        state["result_count"] = len(rows)
        summary = comparison_success_summary(
            model=model,
            base_url=base_url,
            sample_count=sample_count,
            requested_at=requested_at,
            rows=rows,
        )
        write_json(paths.json_file, summary)
        paths.output_file.parent.mkdir(parents=True, exist_ok=True)
        paths.output_file.write_text(
            render_comparison_markdown(
                requested_at=requested_at,
                model=model,
                base_url=base_url,
                rows=rows,
            ),
            encoding="utf-8",
        )
        write_json(paths.state_file, state)
        print("DeepSeek 评分对照报告生成成功。")
        print(f"对照报告已写入：{paths.output_file}")
        print("正式报告未更新。")
        return 0
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        error_type = classify_http_error(error, body)
        message = f"HTTP {error.code}: {redact_secret(body[:500], api_key)}"
    except (socket.timeout, TimeoutError) as error:
        error_type = "timeout"
        message = str(error)
    except URLError as error:
        error_type = classify_url_error(error)
        message = str(error)
    except (json.JSONDecodeError, ValueError) as error:
        error_type = "parse_error"
        message = str(error)
    except Exception as error:  # pragma: no cover - safety net
        error_type = "unknown_error"
        message = str(error)

    state = base_state(
        status="failure",
        error_type=error_type,
        network_request_attempted=True,
        **common_state,
    )
    write_json(paths.state_file, state)
    write_json(
        paths.json_file,
        failure_summary(
            error_type=error_type,
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            network_request_attempted=True,
        ),
    )
    write_error_markdown(
        paths.error_file,
        state=state,
        message=message,
        next_step=next_step_for(error_type),
        secret=api_key,
    )
    print("DeepSeek 评分对照报告生成失败。")
    print("正式报告未更新。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
