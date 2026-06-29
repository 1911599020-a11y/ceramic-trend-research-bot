#!/usr/bin/env python3
"""Analyze YouTube video details and optionally review them with DeepSeek."""

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

from compare_llm_scoring import escape_cell  # noqa: E402
from probe_llm_scoring import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    LOCAL_OUTPUTS_DIR,
    classify_http_error,
    classify_url_error,
    configured_deepseek_key,
    effective_env,
    parse_deepseek_score_response,
    project_path,
    redact_secret,
    request_deepseek_score,
    resolve_base_url,
    resolve_llm_scoring_switch,
    resolve_model,
    result_to_dict,
    utc_now_iso,
    validate_deepseek_base_url,
    write_json,
)
from scoring.llm_scorer import (  # noqa: E402
    LLMScoringInput,
    LLMScoringResult,
    build_llm_scoring_prompt,
    combine_rule_and_llm,
    load_llm_scoring_config,
)


SOURCE_ID = "youtube_video_details_field_and_llm_review"
DEFAULT_INPUT_FILE = LOCAL_OUTPUTS_DIR / "youtube_video_probe.json"
DEFAULT_SAMPLE_COUNT = 1
MAX_SAMPLE_COUNT = 3
EXPECTED_OUTPUTS = {
    "state-file": LOCAL_OUTPUTS_DIR / "youtube_video_review_state.json",
    "output": LOCAL_OUTPUTS_DIR / "youtube_video_review.md",
    "json-output": LOCAL_OUTPUTS_DIR / "youtube_video_review.json",
    "error-file": LOCAL_OUTPUTS_DIR / "youtube_video_review_error.md",
}
REQUIRED_FIELDS = ("title", "url", "id", "channel.title")
OPTIONAL_FIELDS = (
    "description_excerpt",
    "view_count_int",
    "like_count_int",
    "comment_count_int",
    "duration_formatted",
    "publish_date_text",
    "keywords",
    "caption_tracks.count",
)


@dataclass(frozen=True)
class ReviewPaths:
    input_file: Path
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
            "Analyze local YouTube video details and optionally ask DeepSeek "
            "to review them. Without --confirm-live-api this command does not "
            "call the network."
        )
    )
    parser.add_argument("--confirm-live-api", action="store_true")
    parser.add_argument("--input-file", default="local_outputs/youtube_video_probe.json")
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--config", default="config/llm_scoring.json")
    parser.add_argument("--prompt", default="prompts/llm_scoring_prompt.md")
    parser.add_argument("--state-file", default="local_outputs/youtube_video_review_state.json")
    parser.add_argument("--output", default="local_outputs/youtube_video_review.md")
    parser.add_argument("--json-output", default="local_outputs/youtube_video_review.json")
    parser.add_argument("--error-file", default="local_outputs/youtube_video_review_error.md")
    parser.add_argument("--dotenv-file", default=None)

    # Test-only guard paths. The review never writes these files.
    parser.add_argument("--report-file", default="reports/report.md", help=argparse.SUPPRESS)
    parser.add_argument("--latest-file", default="reports/latest.md", help=argparse.SUPPRESS)
    parser.add_argument("--archive-dir", default="reports/archive", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def validate_local_output_paths(paths: ReviewPaths) -> str:
    if paths.input_file.resolve() != DEFAULT_INPUT_FILE.resolve():
        return f"input-file 必须固定为 {DEFAULT_INPUT_FILE.relative_to(PROJECT_ROOT)}"
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


def clamp_sample_count(value: int) -> int:
    if value < 1:
        return 1
    return min(value, MAX_SAMPLE_COUNT)


def nested_value(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return ""
        current = current.get(part)
    return current


def value_present(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, int):
        return True
    return bool(str(value or "").strip())


def load_video_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("YouTube video probe JSON is not an object")
    if payload.get("status") != "success":
        raise ValueError("YouTube video probe JSON is not a successful probe result")
    details = payload.get("details")
    if not isinstance(details, Mapping):
        raise ValueError("YouTube video probe JSON missing object field: details")
    return payload


def field_presence(details: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        present = value_present(nested_value(details, field))
        summary[field] = {
            "present": 1 if present else 0,
            "missing": 0 if present else 1,
            "status": "stable" if present else "missing",
        }
    return summary


def safe_text(value: Any, max_length: int = 500) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value[:10])[:max_length]
    return str(value or "").strip()[:max_length]


def rule_review_details(details: Mapping[str, Any]) -> dict[str, Any]:
    text = " ".join(
        [
            safe_text(details.get("title")),
            safe_text(details.get("description_excerpt")),
            safe_text(details.get("keywords")),
            safe_text(nested_value(details, "channel.title")),
        ]
    ).lower()
    ceramic_terms = ("ceramic", "pottery", "clay", "glaze", "glazing", "kiln", "porcelain")
    intent_terms = ("glaze", "glazing", "chemistry", "low-fire", "high-fire", "food-safe", "dinnerware-safe")
    noise_terms = ("coating", "automotive", "car detailing", "cookware", "tile floor")
    ceramic_hits = [term for term in ceramic_terms if term in text]
    intent_hits = [term for term in intent_terms if term in text]
    noise_hits = [term for term in noise_terms if term in text]
    score = len(ceramic_hits) * 2 + len(intent_hits) * 2 - len(noise_hits) * 3
    if noise_hits and score <= 3:
        level = "low"
    elif ceramic_hits and intent_hits and score >= 5:
        level = "high"
    elif ceramic_hits:
        level = "edge"
    else:
        level = "low"
    notes = []
    if ceramic_hits:
        notes.append(f"陶瓷信号：{', '.join(ceramic_hits[:4])}")
    if intent_hits:
        notes.append(f"关键词意图：{', '.join(intent_hits[:4])}")
    if noise_hits:
        notes.append(f"跑偏风险：{', '.join(noise_hits[:4])}")
    if not notes:
        notes.append("未发现明显陶瓷信号")
    return {"rule_level": level, "rule_score": score, "rule_notes": "；".join(notes)}


def build_sample(payload: Mapping[str, Any]) -> tuple[dict[str, Any], LLMScoringInput]:
    details = payload["details"]
    assert isinstance(details, Mapping)
    rule = rule_review_details(details)
    sample = {
        "topic": "ceramic glaze",
        "source": "youtube_video_details",
        "title": safe_text(details.get("title"), max_length=240),
        "channel": safe_text(nested_value(details, "channel.title"), max_length=160),
        "url": safe_text(details.get("url"), max_length=500),
        "video_id": safe_text(details.get("id"), max_length=120),
        "description_excerpt": safe_text(details.get("description_excerpt"), max_length=500),
        "duration": safe_text(details.get("duration_formatted"), max_length=80),
        "views": safe_text(details.get("view_count_text") or details.get("view_count_int"), max_length=80),
        "likes": safe_text(details.get("like_count_text") or details.get("like_count_int"), max_length=80),
        "comments": safe_text(details.get("comment_count_text") or details.get("comment_count_int"), max_length=80),
        **rule,
    }
    body = (
        f"频道：{sample['channel']}；时长：{sample['duration']}；播放量：{sample['views']}；"
        f"点赞：{sample['likes']}；评论数：{sample['comments']}；简介摘要：{sample['description_excerpt']}"
    )
    llm_input = LLMScoringInput(
        topic=sample["topic"],
        title=sample["title"],
        subreddit=sample["channel"],
        body=body,
        url=sample["url"],
        source="youtube_video_details",
        rule_level=sample["rule_level"],
        rule_score=int(sample["rule_score"]),
        rule_notes=sample["rule_notes"],
    )
    return sample, llm_input


def combined_to_dict(level: str, confidence: int, reason: str) -> dict[str, Any]:
    return {"level": level, "confidence": confidence, "reason": reason}


def llm_result_to_dict(result: LLMScoringResult) -> dict[str, Any]:
    return result_to_dict(result)


def review_label(result: LLMScoringResult) -> str:
    if result.is_noise or result.ceramic_relevance == "low":
        return "DeepSeek 判断为低相关或噪音"
    if result.ceramic_relevance == "high" and result.can_support_trend and result.keyword_intent_match in {"high", "medium"}:
        return "可作为详情层趋势候选"
    if result.ceramic_relevance == "high":
        return "陶瓷相关但更像背景内容"
    if result.ceramic_relevance == "edge":
        return "边缘相关，建议人工复核"
    return "建议人工复核"


def analyze_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    details = payload["details"]
    assert isinstance(details, Mapping)
    sample, _llm_input = build_sample(payload)
    return {
        "video_url": payload.get("video_url", ""),
        "requested_at": payload.get("requested_at", ""),
        "field_presence": field_presence(details),
        "sample": sample,
        "details_summary": {
            "description_char_count": details.get("description_char_count", 0),
            "description_excerpt_saved": bool(details.get("description_excerpt")),
            "caption_tracks": details.get("caption_tracks", {}),
            "chapters_count": details.get("chapters_count", 0),
            "watch_next_count": details.get("watch_next_count", 0),
        },
        "field_notes": [
            "description_excerpt 可辅助语义判断，但不保存完整简介。",
            "caption_tracks 只保存数量和语言，不保存字幕链接，也不拉字幕内容。",
            "comment_count 可作为热度参考，但本阶段不拉评论。",
        ],
    }


def aggregate_review_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": len(rows), "trend_candidates": 0, "background": 0, "noise_or_low": 0, "needs_review": 0}
    for row in rows:
        label = str(row.get("review_label", ""))
        if label == "可作为详情层趋势候选":
            counts["trend_candidates"] += 1
        elif label == "陶瓷相关但更像背景内容":
            counts["background"] += 1
        elif label == "DeepSeek 判断为低相关或噪音":
            counts["noise_or_low"] += 1
        else:
            counts["needs_review"] += 1
    return counts


def render_markdown(
    *,
    requested_at: str,
    analysis: Mapping[str, Any],
    model: str,
    base_url: str,
    llm_status: str,
    llm_rows: list[dict[str, Any]],
) -> str:
    sample = analysis.get("sample", {})
    sample = sample if isinstance(sample, Mapping) else {}
    counts = aggregate_review_counts(llm_rows)
    lines = [
        "# YouTube Video Details 字段与 DeepSeek 旁路审核",
        "",
        f"- 生成时间：{requested_at}",
        f"- 视频：{analysis.get('video_url', '')}",
        f"- DeepSeek 状态：{llm_status}",
        f"- 模型：{model if llm_status == 'success' else '未调用'}",
        f"- Base URL：{base_url if llm_status == 'success' else '未调用'}",
        "- 说明：这是 V0.8.5/V0.8.6 旁路分析，不是正式趋势报告。",
        "- 保护动作：未覆盖 reports/report.md、reports/latest.md 或 reports/archive/。",
        "",
        "## 字段质量",
        "",
        "| 字段 | 状态 | 有值 | 缺失 |",
        "|---|---|---:|---:|",
    ]
    for field, info in dict(analysis.get("field_presence", {})).items():
        if not isinstance(info, Mapping):
            continue
        lines.append(f"| {escape_cell(field)} | {escape_cell(info.get('status', ''))} | {info.get('present', 0)} | {info.get('missing', 0)} |")
    lines.extend(
        [
            "",
            "## 本地规则初筛",
            "",
            f"- 标题：{sample.get('title', '')}",
            f"- 频道：{sample.get('channel', '')}",
            f"- 规则判断：{sample.get('rule_level', '')} / {sample.get('rule_score', '')}；{sample.get('rule_notes', '')}",
            f"- 简介摘要：{sample.get('description_excerpt', '')}",
        ]
    )
    if llm_status == "success":
        lines.extend(
            [
                "",
                "## DeepSeek 旁路审核摘要",
                "",
                f"- 审核样本：{counts['total']} 条。",
                f"- 可作为详情层趋势候选：{counts['trend_candidates']} 条。",
                f"- 陶瓷相关但更像背景内容：{counts['background']} 条。",
                f"- 低相关或噪音：{counts['noise_or_low']} 条。",
                f"- 需要人工复核：{counts['needs_review']} 条。",
                "",
                "| 标题 | DeepSeek 判断 | 合并建议 | 理由 |",
                "|---|---|---|---|",
            ]
        )
        for row in llm_rows:
            row_sample = row["sample"]
            result = row["llm_result"]
            combined = row["combined"]
            lines.append(
                "| {title} | {label} | {combined} | {reason} |".format(
                    title=escape_cell(row_sample.get("title", "")),
                    label=escape_cell(row.get("review_label", "")),
                    combined=escape_cell(f"{combined['level']} / {combined['confidence']}；{combined['reason']}"),
                    reason=escape_cell(result.get("reason", "")),
                )
            )
    else:
        lines.extend(
            [
                "",
                "## DeepSeek 旁路审核摘要",
                "",
                "- 本次未调用 DeepSeek。默认模式只做字段整理和本地规则初筛。",
                "- 如需真实审核，需要同时打开 LLM_SCORING_ENABLED=on 并显式添加 --confirm-live-api。",
            ]
        )
    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
            "- 如果 details 让判断更稳定，可以规划 transcript tiny probe。",
            "- 如果 details 没有明显增益，应继续优化 Search 查询词，而不是急着拉字幕或评论。",
            "- 暂时不要把这份旁路分析直接写入正式报告。",
        ]
    )
    return "\n".join(lines) + "\n"


def base_state(
    *,
    status: str,
    error_type: str,
    requested_at: str,
    sample_count: int,
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
        "requested_at": requested_at,
        "sample_count": sample_count,
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
            "# YouTube Video Details Review Error",
            "",
            f"- 错误类型：{state.get('error_type', 'unknown_error')}",
            f"- 发生时间：{state.get('requested_at', '')}",
            f"- 是否已发起网络请求：{state.get('network_request_attempted', False)}",
            "- 保护动作：未覆盖 reports/report.md、reports/latest.md 或 reports/archive/",
            f"- 错误说明：{redact_secret(message, secret)}",
            f"- 建议下一步：{redact_secret(next_step, secret)}",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def next_step_for(error_type: str) -> str:
    return {
        "missing_input": "先运行 bash scripts/probe_scrapecreators_youtube_video.sh，生成 local_outputs/youtube_video_probe.json。",
        "invalid_input": "检查 local_outputs/youtube_video_probe.json 是否来自成功的 video details probe。",
        "unauthorized_401": "检查 DEEPSEEK_API_KEY 是否有效，或是否需要重新生成 key。",
        "forbidden_403": "检查 DeepSeek 账号权限、模型权限或 API 访问策略。",
        "rate_limited_429": "已被限流，请等待后再试，不要连续重复请求。",
        "quota_or_billing": "检查 DeepSeek 后台余额、额度或账单状态。",
        "timeout": "检查网络或代理状态，稍后再试。",
        "network_error": "检查网络、DNS、代理或 DeepSeek API 服务状态。",
        "parse_error": "模型返回不是预期 JSON，需要检查 prompt 或 JSON Output 支持情况。",
        "switch_off": "确认要消耗 DeepSeek 额度时，将 LLM_SCORING_ENABLED=on 写入 .env，或仅本次临时打开。",
        "missing_key": "确认 .env 或系统环境变量里已配置 DEEPSEEK_API_KEY，然后再运行详情层旁路审核。",
        "invalid_base_url": "删除 DEEPSEEK_BASE_URL 或使用默认官方 API 地址后再试。",
        "unknown_error": "保留错误文件后再排查，不要重复发起请求。",
    }.get(error_type, "保留错误文件后再排查，不要重复发起请求。")


def failure_summary(
    *,
    error_type: str,
    requested_at: str,
    sample_count: int,
    network_request_attempted: bool,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "failure",
        "error_type": error_type,
        "requested_at": requested_at,
        "sample_count": sample_count,
        "network_request_attempted": network_request_attempted,
        "analysis": {},
        "llm_results": [],
        "report_files_updated": False,
    }


def success_summary(
    *,
    requested_at: str,
    model: str,
    base_url: str,
    analysis: Mapping[str, Any],
    llm_status: str,
    llm_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "success",
        "requested_at": requested_at,
        "model": model if llm_status == "success" else "",
        "base_url": base_url if llm_status == "success" else "",
        "analysis": analysis,
        "llm_status": llm_status,
        "llm_counts": aggregate_review_counts(llm_rows),
        "llm_results": llm_rows,
        "report_files_updated": False,
    }


def run_llm_review(
    *,
    sample: Mapping[str, Any],
    llm_input: LLMScoringInput,
    prompt_template: str,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
) -> list[dict[str, Any]]:
    prompt = build_llm_scoring_prompt(prompt_template, llm_input)
    payload, _status_code = request_deepseek_score(
        api_key=api_key,
        base_url=base_url,
        model=model,
        prompt=prompt,
        timeout=timeout,
    )
    result = parse_deepseek_score_response(payload)
    combined = combine_rule_and_llm(
        rule_level=str(sample.get("rule_level", "")),
        rule_score=int(sample.get("rule_score", 0)),
        llm_result=result,
    )
    return [
        {
            "sample": dict(sample),
            "llm_result": result_to_dict(result),
            "review_label": review_label(result),
            "combined": combined_to_dict(combined.level, combined.confidence, combined.reason),
        }
    ]


def handle_llm_failure(
    paths: ReviewPaths,
    common_state: Mapping[str, Any],
    error_type: str,
    message: str,
    sample_count: int,
    api_key: str,
    *,
    network_request_attempted: bool = True,
) -> int:
    state = base_state(
        status="failure",
        error_type=error_type,
        network_request_attempted=network_request_attempted,
        **common_state,
    )
    write_json(paths.state_file, state)
    write_json(
        paths.json_file,
        failure_summary(
            error_type=error_type,
            requested_at=str(common_state.get("requested_at", "")),
            sample_count=sample_count,
            network_request_attempted=network_request_attempted,
        ),
    )
    write_error_markdown(
        paths.error_file,
        state=state,
        message=message,
        next_step=next_step_for(error_type),
        secret=api_key,
    )
    print("YouTube video details review：DeepSeek 旁路审核失败。")
    print("正式报告未更新。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return 1


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    allow_outside_local_outputs: bool = False,
) -> int:
    args = parse_args(argv)
    requested_at = utc_now_iso()
    sample_count = clamp_sample_count(args.sample_count)
    paths = ReviewPaths(
        input_file=project_path(args.input_file),
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
            print("YouTube video details review：输出路径不安全，未发起网络请求。")
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
    common_state = {
        "requested_at": requested_at,
        "sample_count": sample_count,
        "key_status": "configured" if api_key else "missing",
        "llm_scoring_enabled": llm_switch_enabled,
        "switch_env_var": config.switch_env_var,
        "switch_source": switch_source,
    }

    try:
        payload = load_video_payload(paths.input_file)
        analysis = analyze_payload(payload)
        sample, llm_input = build_sample(payload)
    except FileNotFoundError as error:
        state = base_state(status="missing_input", error_type="missing_input", network_request_attempted=False, **common_state)
        write_json(paths.state_file, state)
        write_json(paths.json_file, failure_summary(error_type="missing_input", requested_at=requested_at, sample_count=sample_count, network_request_attempted=False))
        write_error_markdown(paths.error_file, state=state, message=str(error), next_step=next_step_for("missing_input"), secret=api_key)
        print("YouTube video details review：未找到输入文件，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0
    except (json.JSONDecodeError, ValueError) as error:
        state = base_state(status="invalid_input", error_type="invalid_input", network_request_attempted=False, **common_state)
        write_json(paths.state_file, state)
        write_json(paths.json_file, failure_summary(error_type="invalid_input", requested_at=requested_at, sample_count=sample_count, network_request_attempted=False))
        write_error_markdown(paths.error_file, state=state, message=str(error), next_step=next_step_for("invalid_input"), secret=api_key)
        print("YouTube video details review：输入不是成功的 video details probe，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0

    base_url_error = validate_deepseek_base_url(base_url)
    if base_url_error:
        state = base_state(status="invalid_base_url", error_type="invalid_base_url", network_request_attempted=False, **common_state)
        write_json(paths.state_file, state)
        write_json(paths.json_file, failure_summary(error_type="invalid_base_url", requested_at=requested_at, sample_count=sample_count, network_request_attempted=False))
        write_error_markdown(paths.error_file, state=state, message=base_url_error, next_step=next_step_for("invalid_base_url"), secret=api_key)
        print("YouTube video details review：DeepSeek base URL 不安全，未发起网络请求。")
        print(base_url_error)
        return 2

    llm_rows: list[dict[str, Any]] = []
    llm_status = "not_confirmed"
    network_request_attempted = False
    if args.confirm_live_api:
        if not llm_switch_enabled:
            llm_status = "switch_off"
        elif not api_key:
            llm_status = "missing_key"
        else:
            try:
                prompt_template = project_path(args.prompt).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                return handle_llm_failure(
                    paths,
                    common_state,
                    "invalid_input",
                    str(error),
                    sample_count,
                    api_key,
                    network_request_attempted=False,
                )
            try:
                llm_rows = run_llm_review(
                    sample=sample,
                    llm_input=llm_input,
                    prompt_template=prompt_template,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    timeout=args.timeout,
                )
                llm_status = "success"
                network_request_attempted = True
            except HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")
                return handle_llm_failure(paths, common_state, classify_http_error(error, body), f"HTTP {error.code}: {redact_secret(body[:500], api_key)}", sample_count, api_key)
            except (socket.timeout, TimeoutError) as error:
                return handle_llm_failure(paths, common_state, "timeout", str(error), sample_count, api_key)
            except URLError as error:
                return handle_llm_failure(paths, common_state, classify_url_error(error), str(error), sample_count, api_key)
            except (json.JSONDecodeError, ValueError) as error:
                return handle_llm_failure(paths, common_state, "parse_error", str(error), sample_count, api_key)
            except Exception as error:  # pragma: no cover - safety net
                return handle_llm_failure(paths, common_state, "unknown_error", str(error), sample_count, api_key)

    state = base_state(
        status="success" if llm_status in {"success", "not_confirmed"} else llm_status,
        error_type="" if llm_status in {"success", "not_confirmed"} else llm_status,
        network_request_attempted=network_request_attempted,
        **common_state,
    )
    state["llm_status"] = llm_status
    state["field_analysis_completed"] = True
    summary = success_summary(
        requested_at=requested_at,
        model=model,
        base_url=base_url,
        analysis=analysis,
        llm_status=llm_status,
        llm_rows=llm_rows,
    )
    write_json(paths.json_file, summary)
    paths.output_file.parent.mkdir(parents=True, exist_ok=True)
    paths.output_file.write_text(
        render_markdown(
            requested_at=requested_at,
            analysis=analysis,
            model=model,
            base_url=base_url,
            llm_status=llm_status,
            llm_rows=llm_rows,
        ),
        encoding="utf-8",
    )
    write_json(paths.state_file, state)
    print("YouTube video details 字段分析完成。")
    if llm_status == "success":
        print("DeepSeek YouTube video details 旁路审核完成。")
    elif llm_status == "not_confirmed":
        print("未发起 DeepSeek 请求；如需真实审核，请打开 LLM_SCORING_ENABLED=on 并添加 --confirm-live-api。")
    else:
        print(f"DeepSeek 未执行：{llm_status}。")
    print(f"分析报告已写入：{paths.output_file}")
    print("正式报告未更新。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
