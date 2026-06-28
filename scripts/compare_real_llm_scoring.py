#!/usr/bin/env python3
"""Compare rule scoring with DeepSeek on real small-sample Reddit evidence.

V0.7.3 keeps this as an opt-in side experiment. It can fetch a small
ScrapeCreators Reddit sample, score the same evidence with rules and DeepSeek,
then write a sample quality radar, partial quality gate, and analysis report
only to local_outputs/.
"""

from __future__ import annotations

import argparse
import json
import re
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

from ceramic_report import (  # noqa: E402
    Evidence,
    apply_relevance_ranking,
    collect_evidence,
    load_config,
    load_relevance_config,
    load_topics,
    suggested_keywords_for_topic,
)
from compare_llm_scoring import (  # noqa: E402
    aggregate_counts,
    build_row,
    escape_cell,
    render_comparison_markdown,
)
from probe_llm_scoring import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    LOCAL_OUTPUTS_DIR,
    classify_http_error,
    classify_url_error,
    configured_deepseek_key,
    effective_env,
    project_path,
    parse_deepseek_score_response,
    redact_secret,
    request_deepseek_score,
    resolve_base_url,
    resolve_llm_scoring_switch,
    resolve_model,
    utc_now_iso,
    validate_deepseek_base_url,
    write_json,
)
from scoring.llm_scorer import (  # noqa: E402
    LLMScoringInput,
    build_llm_scoring_prompt,
    load_llm_scoring_config,
)
from sources.scrapecreators_source import (  # noqa: E402
    ScrapeCreatorsSource,
    configured_scrapecreators_env_var,
)


SOURCE_ID = "deepseek_real_sample_scoring_comparison"
DEFAULT_TOPICS_PATH = PROJECT_ROOT / "config" / "scrapecreators_quality_topics.json"
DEFAULT_SAMPLE_COUNT = 10
MAX_SAMPLE_COUNT = 12
DEFAULT_PER_TOPIC_LIMIT = 4
EXPECTED_OUTPUTS = {
    "state-file": LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison_state.json",
    "output": LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison.md",
    "json-output": LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison.json",
    "error-file": LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison_error.md",
}
SAMPLING_STRATEGY = "risk_prioritized_quality_check"
SAMPLING_STRATEGY_NOTE = (
    "本报告优先抽查 AI 意图风险、边缘相关、低把握高分和跑偏信号样本；"
    "它用于质检，不代表关键词整体分布。"
)


@dataclass(frozen=True)
class RealComparisonPaths:
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
            "Generate an opt-in real Reddit/ScrapeCreators rule-vs-DeepSeek "
            "small-sample comparison. Without --confirm-live-api this command "
            "does not call the network."
        )
    )
    parser.add_argument("--confirm-live-api", action="store_true")
    parser.add_argument("--topics", default=str(DEFAULT_TOPICS_PATH))
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--per-topic-limit", type=int, default=DEFAULT_PER_TOPIC_LIMIT)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--config", default="config/llm_scoring.json")
    parser.add_argument("--prompt", default="prompts/llm_scoring_prompt.md")
    parser.add_argument("--state-file", default="local_outputs/llm_scoring_real_sample_comparison_state.json")
    parser.add_argument("--output", default="local_outputs/llm_scoring_real_sample_comparison.md")
    parser.add_argument("--json-output", default="local_outputs/llm_scoring_real_sample_comparison.json")
    parser.add_argument("--error-file", default="local_outputs/llm_scoring_real_sample_comparison_error.md")
    parser.add_argument("--dotenv-file", default=None)

    # Test-only guard paths. The comparison never writes these files.
    parser.add_argument("--report-file", default="reports/report.md", help=argparse.SUPPRESS)
    parser.add_argument("--latest-file", default="reports/latest.md", help=argparse.SUPPRESS)
    parser.add_argument("--archive-dir", default="reports/archive", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def clamp_count(value: int, *, maximum: int) -> int:
    if value < 1:
        return 1
    return min(value, maximum)


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def validate_local_output_paths(paths: RealComparisonPaths) -> str:
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


def evidence_to_llm_input(evidence: Evidence) -> LLMScoringInput:
    return LLMScoringInput(
        topic=evidence.topic,
        title=evidence.title,
        subreddit=f"r/{evidence.subreddit}" if evidence.subreddit else "",
        body=evidence.snippet,
        url=evidence.url,
        source=evidence.source,
        rule_level=evidence.relevance_level,
        rule_score=evidence.relevance_score,
        rule_notes=evidence.relevance_notes,
    )


def evidence_risk_flags(evidence: Evidence) -> list[str]:
    text = " ".join(
        [
            evidence.topic,
            evidence.title,
            evidence.snippet,
            evidence.subreddit,
            evidence.relevance_notes,
        ]
    ).lower()
    flags: list[str] = []
    if evidence.relevance_level == "edge":
        flags.append("edge_relevance")
    if evidence.relevance_level == "low":
        flags.append("low_relevance")
    if "ai" in evidence.topic.lower():
        flags.append("ai_intent_risk")
    if evidence.relevance_level == "high" and evidence.relevance_score <= 6:
        flags.append("rule_high_low_margin")
    if "未命中当前关键词意图" in evidence.relevance_notes or "required" in text:
        flags.append("intent_mismatch")
    if "跑偏词" in evidence.relevance_notes or any(
        term in text for term in ("anime", "gaming", "cosplay", "fnaf", "naruto", "ordinary ai video")
    ):
        flags.append("noise_signal")
    return flags


def quality_gate_priority(evidence: Evidence) -> tuple[int, int]:
    flags = evidence_risk_flags(evidence)
    if evidence.relevance_level == "high" and "noise_signal" in flags:
        priority = 120
    elif evidence.relevance_level == "high" and flags:
        priority = 110
    elif evidence.relevance_level == "edge":
        priority = 100
    elif evidence.relevance_level == "low" and flags:
        priority = 85
    elif evidence.relevance_level == "high":
        priority = 70
    else:
        priority = 45
    return priority, evidence.relevance_score


def normalized_title_key(title: str) -> str:
    text = title.strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def select_evidence_samples(
    runs: list[tuple[str, list[Evidence]]],
    *,
    sample_count: int,
    per_topic_limit: int,
) -> list[LLMScoringInput]:
    buckets: list[list[Evidence]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for _topic, evidence_items in runs:
        topic_items = sorted(
            evidence_items,
            key=quality_gate_priority,
            reverse=True,
        )
        unique_topic_items: list[Evidence] = []
        for evidence in topic_items:
            url_key = evidence.url.strip().lower()
            title_key = normalized_title_key(evidence.title)
            if (url_key and url_key in seen_urls) or (title_key and title_key in seen_titles):
                continue
            if url_key:
                seen_urls.add(url_key)
            if title_key:
                seen_titles.add(title_key)
            unique_topic_items.append(evidence)
            if len(unique_topic_items) >= per_topic_limit:
                break
        if unique_topic_items:
            buckets.append(unique_topic_items)

    selected: list[LLMScoringInput] = []
    max_bucket_size = max((len(bucket) for bucket in buckets), default=0)
    for index in range(max_bucket_size):
        for bucket in buckets:
            if index >= len(bucket):
                continue
            selected.append(evidence_to_llm_input(bucket[index]))
            if len(selected) >= sample_count:
                return selected
    return selected


def base_state(
    *,
    status: str,
    error_type: str,
    model: str,
    sample_count: int,
    requested_at: str,
    network_request_attempted: bool,
    key_status: str,
    scrapecreators_key_status: str,
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
        "data_source": "scrapecreators_reddit",
        "key_status": key_status,
        "scrapecreators_key_status": scrapecreators_key_status,
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
            "# DeepSeek 真实小样本对照错误",
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


def success_summary(
    *,
    model: str,
    base_url: str,
    sample_count: int,
    requested_at: str,
    topics: list[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    quality_profiles = topic_quality_profiles(rows, topics)
    return {
        "source_id": SOURCE_ID,
        "status": "success",
        "model": model,
        "base_url": base_url,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "data_source": "scrapecreators_reddit",
        "topics": topics,
        "sampling_strategy": SAMPLING_STRATEGY,
        "sampling_strategy_note": SAMPLING_STRATEGY_NOTE,
        "counts": aggregate_counts(rows),
        "quality_gate_counts": quality_gate_counts(rows),
        "topic_quality": quality_profiles,
        "next_keyword_actions": next_keyword_actions(quality_profiles),
        "results": rows,
        "report_files_updated": False,
    }


def next_step_for(error_type: str) -> str:
    return {
        "missing_key": "确认 .env 中已配置 DEEPSEEK_API_KEY，再运行真实小样本对照。",
        "missing_scrapecreators_key": "确认 .env 中已配置 SCRAPECREATORS_API_KEY，再运行真实小样本对照。",
        "switch_off": "确认要消耗 DeepSeek 额度时，将 LLM_SCORING_ENABLED=on 写入 .env，或仅本次临时打开。",
        "no_evidence": "真实数据源没有返回可对照证据；可稍后重试或调整关键词配置。",
        "unauthorized_401": "检查 API key 是否有效，或是否需要重新生成 key。",
        "forbidden_403": "检查账号权限、模型权限、ScrapeCreators 权限或 API 访问策略。",
        "rate_limited_429": "已被限流，请等待后再试，不要连续重复请求。",
        "quota_or_billing": "检查 DeepSeek 或 ScrapeCreators 后台余额、额度或账单状态。",
        "timeout": "检查网络或代理状态，稍后再试。",
        "network_error": "检查网络、DNS、代理或 API 服务状态。",
        "parse_error": "模型返回不是预期 JSON，需要检查 prompt 或 JSON Output 支持情况。",
        "unknown_error": "保留错误文件后再排查，不要重复发起请求。",
    }.get(error_type, "保留错误文件后再排查，不要重复发起请求。")


def fetch_real_samples(
    *,
    topics_path: Path,
    env: Mapping[str, str],
    sample_count: int,
    per_topic_limit: int,
    timeout: float,
) -> tuple[list[str], list[LLMScoringInput]]:
    config = load_config(topics_path)
    topics = load_topics(topics_path)
    relevance_config = load_relevance_config(config)
    source = ScrapeCreatorsSource(env=env, timeout=timeout)
    runs: list[tuple[str, list[Evidence]]] = []
    for topic in topics:
        report = source.fetch(
            topic,
            recommended_subreddits=relevance_config.recommended_subreddits,
        )
        report = apply_relevance_ranking(report, relevance_config, topic)
        runs.append((topic, collect_evidence(topic, report)))
    return topics, select_evidence_samples(
        runs,
        sample_count=sample_count,
        per_topic_limit=per_topic_limit,
    )


def quality_gate_action(row: Mapping[str, Any]) -> str:
    alignment = str(row.get("alignment", ""))
    sample = row.get("sample") or {}
    result = row.get("llm_result") or {}
    combined = row.get("combined") or {}
    if alignment.startswith("DeepSeek 降级") or result.get("is_noise") or result.get("ceramic_relevance") == "low":
        return "降级为噪音/低相关"
    if alignment == "一致高相关" and combined.get("level") == "high":
        return "进入趋势候选"
    if alignment.startswith("DeepSeek 提醒"):
        return "人工复核：可能漏判"
    if alignment == "陶瓷相关但不宜入趋势":
        return "保留为背景，不进入趋势"
    if result.get("ceramic_relevance") == "edge" or alignment in {"边缘相关，建议人工复核", "需要人工复核"}:
        return "人工复核：边缘证据"
    if "ai" in str(sample.get("topic", "")).lower() and result.get("keyword_intent_match") != "high":
        return "人工复核：AI 意图不清"
    return "观察"


def add_quality_gate_fields(row: dict[str, Any]) -> dict[str, Any]:
    quality_gate = quality_gate_action(row)
    review_required = quality_gate.startswith("人工复核") or quality_gate.startswith("降级")
    row["quality_gate"] = {
        "action": quality_gate,
        "review_required": review_required,
        "formal_report_policy": formal_report_policy_for_action(quality_gate),
    }
    return row


def formal_report_policy_for_action(action: str) -> str:
    if action == "进入趋势候选":
        return "可进入正式报告趋势候选，但仍需满足高相关证据数量门槛。"
    if action.startswith("降级"):
        return "不进入趋势判断，只用于过滤规则复盘。"
    if action.startswith("人工复核"):
        return "暂不自动进入趋势判断，建议人工确认后再使用。"
    if action.startswith("保留为背景"):
        return "可作为背景观察，不作为趋势结论。"
    return "仅作为观察方向。"


def quality_gate_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        action = str((row.get("quality_gate") or {}).get("action") or quality_gate_action(row))
        counts[action] = counts.get(action, 0) + 1
    return counts


def topic_quality_profiles(rows: list[dict[str, Any]], topics: list[str]) -> list[dict[str, Any]]:
    by_topic: dict[str, list[dict[str, Any]]] = {topic: [] for topic in topics}
    for row in rows:
        topic = str((row.get("sample") or {}).get("topic", "")).strip()
        by_topic.setdefault(topic, []).append(row)

    profiles: list[dict[str, Any]] = []
    for topic, topic_rows in by_topic.items():
        sample_count = len(topic_rows)
        agree_high = sum(1 for row in topic_rows if row.get("alignment") == "一致高相关")
        demoted = sum(1 for row in topic_rows if str(row.get("alignment", "")).startswith("DeepSeek 降级"))
        noise = sum(1 for row in topic_rows if (row.get("llm_result") or {}).get("is_noise"))
        bad_sample_count = sum(1 for row in topic_rows if is_bad_sample(row))
        review = sum(1 for row in topic_rows if (row.get("quality_gate") or {}).get("review_required"))
        support_trend = sum(1 for row in topic_rows if (row.get("llm_result") or {}).get("can_support_trend"))
        confidence_values = [
            int((row.get("llm_result") or {}).get("confidence") or 0)
            for row in topic_rows
        ]
        avg_confidence = round(sum(confidence_values) / len(confidence_values)) if confidence_values else 0
        quality_label = topic_quality_label(
            sample_count=sample_count,
            agree_high=agree_high,
            bad_sample_count=bad_sample_count,
            review=review,
        )
        profiles.append(
            {
                "topic": topic,
                "sample_count": sample_count,
                "agree_high": agree_high,
                "support_trend": support_trend,
                "demoted": demoted,
                "noise": noise,
                "bad_sample_count": bad_sample_count,
                "review_required": review,
                "average_confidence": avg_confidence,
                "quality_label": quality_label,
                "recommendation": topic_quality_recommendation(topic, quality_label),
                "suggested_keywords": suggested_keywords_for_topic(topic),
            }
        )
    return profiles


def topic_quality_label(
    *,
    sample_count: int,
    agree_high: int,
    bad_sample_count: int,
    review: int,
) -> str:
    if sample_count == 0:
        return "未采样"
    if agree_high >= 2 and demoted == 0 and noise == 0:
        return "可保留"
    if bad_sample_count >= max(1, sample_count // 2):
        return "降噪优先"
    if agree_high >= 1:
        return "保留但需收窄"
    return "继续观察"


def topic_quality_recommendation(topic: str, label: str) -> str:
    lowered = topic.lower()
    if label == "可保留":
        return "保留当前关键词，下轮继续观察是否连续出现同类高相关证据。"
    if "ai" in lowered:
        return "把宽泛 AI 词收窄到陶瓷工作流、纹样、釉料预测、3D 打印或 prompt 到工艺落地。"
    if "business" in lowered or "studio" in lowered:
        return "增加定价、Etsy、commission、客户沟通、工作室营销等经营意图词。"
    if "kiln" in lowered or "firing" in lowered:
        return "保留烧成方向，并加入 cone、bisque、electric kiln、glaze defects 等更具体问题词。"
    if label == "降噪优先":
        return "先收窄关键词，不建议扩大样本；否则会继续放大噪音。"
    return "继续小样本观察，等出现更多高相关证据后再进入正式趋势判断。"


def next_keyword_actions(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for profile in profiles:
        label = str(profile["quality_label"])
        if label == "可保留":
            action = "keep"
        elif label == "保留但需收窄":
            action = "narrow"
        elif label == "降噪优先":
            action = "de-noise"
        elif label == "未采样":
            action = "sample_next"
        else:
            action = "observe"
        actions.append(
            {
                "topic": profile["topic"],
                "action": action,
                "suggested_keywords": profile["suggested_keywords"][:5],
                "reason": profile["recommendation"],
            }
        )
    return actions


def render_real_sample_markdown(
    *,
    requested_at: str,
    model: str,
    base_url: str,
    rows: list[dict[str, Any]],
    topics: list[str],
) -> str:
    base = render_comparison_markdown(
        requested_at=requested_at,
        model=model,
        base_url=base_url,
        rows=rows,
        title="DeepSeek 与真实 Reddit 小样本规则评分对照报告",
        description="这是 V0.7.3 报告 + 解析旁路对照，不是正式趋势报告。",
    ).rstrip()
    profiles = topic_quality_profiles(rows, topics)
    gate_counts = quality_gate_counts(rows)
    lines = [
        base,
        "",
        "## V0.7.1 质检样本质量雷达",
        "",
        f"> 抽样说明：{SAMPLING_STRATEGY_NOTE}",
        "",
        "| 关键词 | 样本数 | 一致高相关 | 可支撑趋势 | 降级/噪音 | 需复核 | 平均置信度 | 质量判断 | 建议 |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for profile in profiles:
        lines.append(
            "| {topic} | {sample_count} | {agree_high} | {support_trend} | {bad} | {review} | {confidence} | {label} | {recommendation} |".format(
                topic=escape_cell(str(profile["topic"])),
                sample_count=profile["sample_count"],
                agree_high=profile["agree_high"],
                support_trend=profile["support_trend"],
                bad=profile["bad_sample_count"],
                review=profile["review_required"],
                confidence=profile["average_confidence"],
                label=escape_cell(str(profile["quality_label"])),
                recommendation=escape_cell(str(profile["recommendation"])),
            )
        )

    lines.extend(
        [
            "",
            "## V0.7.2 DeepSeek 局部质检",
            "",
            "本轮 DeepSeek 只用于真实小样本旁路质检，不接管正式报告。质检动作统计：",
            "",
        ]
    )
    if gate_counts:
        for action, count in sorted(gate_counts.items()):
            lines.append(f"- {action}：{count} 条。")
    else:
        lines.append("- 暂无可质检样本。")

    lines.extend(
        [
            "",
            "| 关键词 | 标题 | 质检动作 | 正式报告策略 |",
            "|---|---|---|---|",
        ]
    )
    for row in rows:
        sample = row["sample"]
        gate = row.get("quality_gate") or {}
        lines.append(
            "| {topic} | {title} | {action} | {policy} |".format(
                topic=escape_cell(sample["topic"]),
                title=escape_cell(sample["title"]),
                action=escape_cell(str(gate.get("action") or quality_gate_action(row))),
                policy=escape_cell(str(gate.get("formal_report_policy") or "")),
            )
        )

    lines.extend(
        [
            "",
            "## V0.7.3 报告 + 解析",
            "",
        ]
    )
    analysis = report_analysis_lines(rows, profiles)
    for line in analysis:
        lines.append(f"- {line}")
    lines.extend(
        [
            "",
            "## 下一轮关键词动作",
            "",
        ]
    )
    for action in next_keyword_actions(profiles):
        keywords = "、".join(f"`{term}`" for term in action["suggested_keywords"])
        lines.append(
            f"- **{action['topic']}**：动作 `{action['action']}`。{action['reason']} 建议词：{keywords}。"
        )
    return "\n".join(lines) + "\n"


def report_analysis_lines(rows: list[dict[str, Any]], profiles: list[dict[str, Any]]) -> list[str]:
    counts = aggregate_counts(rows)
    lines: list[str] = []
    total = counts["total"]
    if total == 0:
        return ["本轮没有可解析样本，不适合做报告质量判断。"]
    lines.append(
        f"本轮解析 {total} 条真实 Reddit 小样本；其中一致高相关 {counts['agree_high']} 条，DeepSeek 降级 {counts['llm_demoted']} 条，一致低相关或噪音 {counts['agree_low_or_noise']} 条。"
    )
    lines.append(SAMPLING_STRATEGY_NOTE)
    strong_topics = [profile for profile in profiles if profile["quality_label"] == "可保留"]
    noisy_topics = [profile for profile in profiles if profile["quality_label"] == "降噪优先"]
    if strong_topics:
        lines.append(
            "可优先进入正式报告观察池的关键词是："
            + "、".join(str(profile["topic"]) for profile in strong_topics)
            + "。"
        )
    else:
        lines.append("本轮还没有足够稳定的关键词可以直接升级为确定趋势。")
    if noisy_topics:
        lines.append(
            "需要优先降噪的关键词是："
            + "、".join(str(profile["topic"]) for profile in noisy_topics)
            + "，下轮应先收窄搜索词。"
        )
    lines.append("跑偏样本和人工复核样本只能用于改进过滤规则，不能进入趋势判断。")
    lines.append("这份解析的作用是帮助你决定下一轮搜什么、少搜什么，而不是替代正式中文趋势报告。")
    return lines


def is_bad_sample(row: Mapping[str, Any]) -> bool:
    alignment = str(row.get("alignment", ""))
    result = row.get("llm_result") or {}
    return (
        alignment.startswith("DeepSeek 降级")
        or bool(result.get("is_noise"))
        or result.get("ceramic_relevance") == "low"
    )


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    allow_outside_local_outputs: bool = False,
) -> int:
    args = parse_args(argv)
    requested_at = utc_now_iso()
    sample_count = clamp_count(args.sample_count, maximum=MAX_SAMPLE_COUNT)
    per_topic_limit = clamp_count(args.per_topic_limit, maximum=MAX_SAMPLE_COUNT)
    paths = RealComparisonPaths(
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
            print("DeepSeek 真实小样本对照：输出路径不安全，未发起网络请求。")
            print(path_error)
            print("请使用默认 local_outputs/ 路径，避免误写正式报告或其他文件。")
            return 2

    values = effective_env(env, args.dotenv_file)
    config = load_llm_scoring_config(project_path(args.config))
    model = resolve_model(args, values, config.model or DEFAULT_MODEL)
    base_url = resolve_base_url(args, values) or DEFAULT_BASE_URL
    api_key = configured_deepseek_key(values)
    scrapecreators_env_var = configured_scrapecreators_env_var(values)
    scrapecreators_key = values.get(scrapecreators_env_var, "") if scrapecreators_env_var else ""
    llm_switch_enabled, switch_source = resolve_llm_scoring_switch(
        values,
        switch_env_var=config.switch_env_var,
        enabled_values=config.enabled_values,
    )
    topics_path = project_path(args.topics)
    prompt_template = project_path(args.prompt).read_text(encoding="utf-8")
    base_url_error = validate_deepseek_base_url(base_url)
    common_state = {
        "model": model,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "key_status": "configured" if api_key else "missing",
        "scrapecreators_key_status": "configured" if scrapecreators_key else "missing",
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
        print("DeepSeek 真实小样本对照：base URL 不安全，未发起网络请求。")
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
        print("DeepSeek 真实小样本对照：未发起网络请求。")
        print(
            "如需真实对照，请同时打开 "
            f"{config.switch_env_var}=on 并显式添加 --confirm-live-api。"
        )
        print(f"状态已写入：{paths.state_file}")
        return 0

    if not llm_switch_enabled:
        return write_guard_failure(
            paths,
            state=base_state(
                status="switch_off",
                error_type="switch_off",
                network_request_attempted=False,
                **common_state,
            ),
            error_type="switch_off",
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            api_key=api_key,
            message=(
                f"{config.switch_env_var} 未开启。虽然已收到 --confirm-live-api，"
                "但没有发起 ScrapeCreators 或 DeepSeek 网络请求。"
            ),
        )

    if not api_key:
        return write_guard_failure(
            paths,
            state=base_state(
                status="missing_key",
                error_type="missing_key",
                network_request_attempted=False,
                **common_state,
            ),
            error_type="missing_key",
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            api_key="",
            message="未找到 DEEPSEEK_API_KEY。没有发起网络请求。",
        )

    if not scrapecreators_key:
        return write_guard_failure(
            paths,
            state=base_state(
                status="missing_scrapecreators_key",
                error_type="missing_scrapecreators_key",
                network_request_attempted=False,
                **common_state,
            ),
            error_type="missing_scrapecreators_key",
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            api_key=api_key,
            message="未找到 SCRAPECREATORS_API_KEY。没有发起网络请求。",
        )

    try:
        topics, samples = fetch_real_samples(
            topics_path=topics_path,
            env=values,
            sample_count=sample_count,
            per_topic_limit=per_topic_limit,
            timeout=args.timeout,
        )
        if not samples:
            return write_guard_failure(
                paths,
                state=base_state(
                    status="no_evidence",
                    error_type="no_evidence",
                    network_request_attempted=True,
                    **common_state,
                ),
                error_type="no_evidence",
                model=model,
                sample_count=sample_count,
                requested_at=requested_at,
                api_key=api_key,
                message="ScrapeCreators 返回后没有可用于对照的 Reddit 证据。",
                exit_code=1,
            )

        rows: list[dict[str, Any]] = []
        for item in samples:
            prompt = build_llm_scoring_prompt(prompt_template, item)
            payload, _status_code = request_deepseek_score(
                api_key=api_key,
                base_url=base_url,
                model=model,
                prompt=prompt,
                timeout=args.timeout,
            )
            result = parse_deepseek_score_response(payload)
            rows.append(add_quality_gate_fields(build_row(item, result)))

        state = base_state(
            status="success",
            error_type="",
            network_request_attempted=True,
            **common_state,
        )
        state["result_count"] = len(rows)
        state["topics"] = topics
        summary = success_summary(
            model=model,
            base_url=base_url,
            sample_count=len(rows),
            requested_at=requested_at,
            topics=topics,
            rows=rows,
        )
        write_json(paths.json_file, summary)
        paths.output_file.parent.mkdir(parents=True, exist_ok=True)
        paths.output_file.write_text(
            render_real_sample_markdown(
                requested_at=requested_at,
                model=model,
                base_url=base_url,
                rows=rows,
                topics=topics,
            ),
            encoding="utf-8",
        )
        write_json(paths.state_file, state)
        print("DeepSeek 真实小样本对照报告生成成功。")
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
    print("DeepSeek 真实小样本对照报告生成失败。")
    print("正式报告未更新。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return 1


def write_guard_failure(
    paths: RealComparisonPaths,
    *,
    state: Mapping[str, Any],
    error_type: str,
    model: str,
    sample_count: int,
    requested_at: str,
    api_key: str,
    message: str,
    exit_code: int = 0,
) -> int:
    write_json(paths.state_file, state)
    write_json(
        paths.json_file,
        failure_summary(
            error_type=error_type,
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            network_request_attempted=bool(state.get("network_request_attempted", False)),
        ),
    )
    write_error_markdown(
        paths.error_file,
        state=state,
        message=message,
        next_step=next_step_for(error_type),
        secret=api_key,
    )
    print("DeepSeek 真实小样本对照：保护机制已拦截，未更新正式报告。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
