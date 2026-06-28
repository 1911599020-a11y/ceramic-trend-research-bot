#!/usr/bin/env python3
"""Create a keyword convergence plan from the V0.7.3 real-sample comparison."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_OUTPUTS_DIR = PROJECT_ROOT / "local_outputs"
DEFAULT_INPUT_PATH = LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison.json"
DEFAULT_OUTPUT_PATH = LOCAL_OUTPUTS_DIR / "keyword_convergence_plan.md"
DEFAULT_JSON_OUTPUT_PATH = LOCAL_OUTPUTS_DIR / "keyword_convergence_plan.json"
DEFAULT_TOPICS_PATH = PROJECT_ROOT / "config" / "scrapecreators_quality_topics.json"
REPORTS_DIR = PROJECT_ROOT / "reports"
SOURCE_ID = "keyword_convergence_plan"


@dataclass(frozen=True)
class ConvergencePaths:
    input_file: Path
    output_file: Path
    json_file: Path
    topics_file: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize V0.7.3 real-sample DeepSeek comparison into a local "
            "keyword convergence plan. This command never calls the network."
        )
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT_PATH))
    parser.add_argument("--topics", default=str(DEFAULT_TOPICS_PATH))
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    allow_outside_local_outputs: bool = False,
) -> int:
    args = parse_args(argv)
    paths = ConvergencePaths(
        input_file=project_path(args.input),
        output_file=project_path(args.output),
        json_file=project_path(args.json_output),
        topics_file=project_path(args.topics),
    )
    if not allow_outside_local_outputs:
        path_error = validate_output_paths(paths)
        if path_error:
            print("关键词收敛计划：输出路径不安全，未写入文件。", file=sys.stderr)
            print(path_error, file=sys.stderr)
            return 2

    topics = load_topics(paths.topics_file)
    if not paths.input_file.exists():
        payload = missing_input_payload(paths, topics)
        write_json(paths.json_file, payload)
        write_text(paths.output_file, render_missing_input(payload))
        print(f"尚未找到 V0.7.3 对照结果，已写入说明：{display_path(paths.output_file)}")
        return 0

    try:
        source_payload = json.loads(paths.input_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        payload = error_payload(paths, topics, "parse_error", f"JSON 解析失败：{exc}")
        write_json(paths.json_file, payload)
        write_text(paths.output_file, render_error(payload))
        print(f"关键词收敛计划生成失败：{payload['error_type']}", file=sys.stderr)
        return 1

    payload = build_convergence_payload(
        source_payload=source_payload,
        input_file=paths.input_file,
        topics=topics,
    )
    write_json(paths.json_file, payload)
    write_text(paths.output_file, render_convergence_markdown(payload))
    print(f"已生成关键词收敛计划：{display_path(paths.output_file)}")
    return 0


def build_convergence_payload(
    *,
    source_payload: Mapping[str, Any],
    input_file: Path,
    topics: list[str],
) -> dict[str, Any]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    profiles = normalize_profiles(source_payload.get("topic_quality") or [], topics)
    actions = normalize_actions(source_payload.get("next_keyword_actions") or [], profiles)
    proposed_topics = proposed_next_round_topics(actions)
    review_items = manual_review_items(source_payload.get("results") or [])
    counts = source_payload.get("counts") if isinstance(source_payload.get("counts"), dict) else {}
    source_sample_count = safe_int(source_payload.get("sample_count") or counts.get("total"))
    return {
        "source_id": SOURCE_ID,
        "status": "success",
        "generated_at": generated_at,
        "input_file": display_path(input_file),
        "source_status": source_payload.get("status", "unknown"),
        "source_sample_count": source_sample_count,
        "sampling_strategy": source_payload.get("sampling_strategy", ""),
        "sampling_strategy_note": source_payload.get("sampling_strategy_note", ""),
        "cost_note": cost_note(topics, source_sample_count),
        "topic_quality": profiles,
        "keyword_actions": actions,
        "proposed_next_round_topics": proposed_topics,
        "manual_review_items": review_items,
        "report_files_updated": False,
        "config_files_updated": False,
    }


def normalize_profiles(raw_profiles: Any, topics: list[str]) -> list[dict[str, Any]]:
    profiles_by_topic: dict[str, dict[str, Any]] = {}
    if isinstance(raw_profiles, list):
        for item in raw_profiles:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip()
            if not topic:
                continue
            profiles_by_topic[topic] = {
                "topic": topic,
                "sample_count": safe_int(item.get("sample_count")),
                "agree_high": safe_int(item.get("agree_high")),
                "support_trend": safe_int(item.get("support_trend")),
                "bad_sample_count": safe_int(item.get("bad_sample_count")),
                "review_required": safe_int(item.get("review_required")),
                "average_confidence": safe_int(item.get("average_confidence")),
                "quality_label": str(item.get("quality_label", "继续观察")).strip() or "继续观察",
                "recommendation": str(item.get("recommendation", "")).strip(),
                "suggested_keywords": clean_terms(item.get("suggested_keywords") or []),
            }
    for topic in topics:
        profiles_by_topic.setdefault(
            topic,
            {
                "topic": topic,
                "sample_count": 0,
                "agree_high": 0,
                "support_trend": 0,
                "bad_sample_count": 0,
                "review_required": 0,
                "average_confidence": 0,
                "quality_label": "未采样",
                "recommendation": "本轮没有 V0.7.3 样本，建议下一轮继续小样本测试。",
                "suggested_keywords": [],
            },
        )
    ordered_topics = topics + [topic for topic in profiles_by_topic if topic not in topics]
    return [profiles_by_topic[topic] for topic in ordered_topics]


def normalize_actions(raw_actions: Any, profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_by_topic: dict[str, dict[str, Any]] = {}
    if isinstance(raw_actions, list):
        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip()
            if topic:
                raw_by_topic[topic] = item

    actions: list[dict[str, Any]] = []
    for profile in profiles:
        topic = str(profile["topic"])
        raw = raw_by_topic.get(topic, {})
        action = str(raw.get("action") or action_from_quality_label(str(profile["quality_label"]))).strip()
        suggested = clean_terms(raw.get("suggested_keywords") or profile.get("suggested_keywords") or [])
        actions.append(
            {
                "topic": topic,
                "action": action,
                "action_label": action_label(action),
                "quality_label": profile["quality_label"],
                "suggested_keywords": suggested,
                "reason": str(raw.get("reason") or profile.get("recommendation") or "").strip(),
            }
        )
    return actions


def proposed_next_round_topics(actions: list[dict[str, Any]], *, limit: int = 10) -> list[str]:
    proposed: list[str] = []
    for action in actions:
        action_id = str(action["action"])
        topic = str(action["topic"])
        suggestions = clean_terms(action.get("suggested_keywords") or [])
        if action_id == "keep":
            candidates = [topic, *suggestions[:2]]
        elif action_id in {"narrow", "de-noise"}:
            candidates = suggestions[:4] or [topic]
        elif action_id == "sample_next":
            candidates = [topic, *suggestions[:2]]
        else:
            candidates = suggestions[:2] or [topic]
        for term in candidates:
            if term not in proposed:
                proposed.append(term)
            if len(proposed) >= limit:
                return proposed
    return proposed


def manual_review_items(raw_results: Any) -> list[dict[str, str]]:
    review_items: list[dict[str, str]] = []
    if not isinstance(raw_results, list):
        return review_items
    for row in raw_results:
        if not isinstance(row, dict):
            continue
        gate = row.get("quality_gate") if isinstance(row.get("quality_gate"), dict) else {}
        if not gate.get("review_required"):
            continue
        sample = row.get("sample") if isinstance(row.get("sample"), dict) else {}
        review_items.append(
            {
                "topic": str(sample.get("topic", "")).strip(),
                "title": str(sample.get("title", "")).strip(),
                "action": str(gate.get("action", "")).strip(),
                "policy": str(gate.get("formal_report_policy", "")).strip(),
            }
        )
    return review_items[:8]


def render_convergence_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 陶瓷关键词收敛计划",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 来源文件：{payload['input_file']}",
        f"- 来源状态：{payload['source_status']}",
        f"- 来源样本数：{payload['source_sample_count']}",
        f"- 成本说明：{payload['cost_note']}",
        "- 输入性质：来自 V0.7.3 真实小样本质检报告，用于决定下一轮关键词怎么收敛。",
        "- 保护动作：未修改正式报告，未修改关键词配置。",
        "- 说明：这是 V0.7.4 本地收敛计划，不是正式趋势结论。",
        "",
    ]
    sampling_note = str(payload.get("sampling_strategy_note", "")).strip()
    if sampling_note:
        lines.extend(["## 抽样说明", "", f"- {sampling_note}", ""])

    lines.extend(
        [
            "## 关键词动作表",
            "",
            "| 关键词 | 质量判断 | 建议动作 | 样本数 | 高相关一致 | 坏样本 | 需复核 | 建议替换/补充词 | 原因 |",
            "|---|---|---|---:|---:|---:|---:|---|---|",
        ]
    )
    profiles = {item["topic"]: item for item in payload["topic_quality"]}
    for action in payload["keyword_actions"]:
        profile = profiles.get(action["topic"], {})
        lines.append(
            "| {topic} | {quality} | {action_label} | {sample_count} | {agree_high} | {bad} | {review} | {terms} | {reason} |".format(
                topic=escape_cell(action["topic"]),
                quality=escape_cell(str(action["quality_label"])),
                action_label=escape_cell(str(action["action_label"])),
                sample_count=profile.get("sample_count", 0),
                agree_high=profile.get("agree_high", 0),
                bad=profile.get("bad_sample_count", 0),
                review=profile.get("review_required", 0),
                terms=escape_cell("、".join(action["suggested_keywords"][:5]) or "暂无"),
                reason=escape_cell(str(action["reason"] or "暂无")),
            )
        )

    lines.extend(["", "## 下一轮建议测试关键词", ""])
    proposed = payload.get("proposed_next_round_topics") or []
    if proposed:
        for index, topic in enumerate(proposed, start=1):
            lines.append(f"{index}. `{topic}`")
    else:
        lines.append("- 暂无。请先生成 V0.7.3 真实小样本对照结果。")

    lines.extend(["", "## 需要人工复核的样本", ""])
    review_items = payload.get("manual_review_items") or []
    if review_items:
        for item in review_items:
            lines.append(
                f"- **{item['topic']}**：{item['title']} - {item['action']}；{item['policy']}"
            )
    else:
        lines.append("- 本轮没有需要人工复核的样本，或尚未生成真实对照结果。")

    lines.extend(
        [
            "",
            "## 如何使用",
            "",
            "- 先人工阅读本计划，不要直接把所有建议词写进正式配置。",
            "- 如果某个关键词连续两轮都是 `降噪优先`，下一轮应替换成更具体的建议词。",
            "- 如果某个关键词连续两轮都是 `可保留`，可以考虑把它放进正式 live 关键词池。",
            "- 修改关键词配置前，先保留原始词和建议词之间的对应关系，方便复盘。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_missing_input(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 陶瓷关键词收敛计划",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 来源文件：{payload['input_file']}",
        "- 状态：尚未找到 V0.7.3 真实小样本对照 JSON。",
        "- 保护动作：未修改正式报告，未修改关键词配置。",
        "",
        "## 下一步",
        "",
        "- 先运行 `bash scripts/compare_real_llm_scoring.sh` 做 dry-run。",
        "- 确认愿意消耗 ScrapeCreators 和 DeepSeek 额度后，再运行真实 V0.7.3 对照。",
        "- 有了 `local_outputs/llm_scoring_real_sample_comparison.json` 后，再运行本脚本生成收敛计划。",
        "",
        "## 当前待观察关键词",
        "",
    ]
    lines.extend(f"- {topic}" for topic in payload.get("topics", []))
    return "\n".join(lines) + "\n"


def render_error(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# 陶瓷关键词收敛计划",
            "",
            f"- 生成时间：{payload['generated_at']}",
            f"- 来源文件：{payload['input_file']}",
            f"- 状态：{payload['status']}",
            f"- 错误类型：{payload['error_type']}",
            f"- 错误说明：{payload['message']}",
            "- 保护动作：未修改正式报告，未修改关键词配置。",
            "",
        ]
    )


def missing_input_payload(paths: ConvergencePaths, topics: list[str]) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "missing_input",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "input_file": display_path(paths.input_file),
        "topics": topics,
        "report_files_updated": False,
        "config_files_updated": False,
    }


def error_payload(
    paths: ConvergencePaths,
    topics: list[str],
    error_type: str,
    message: str,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "failure",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "input_file": display_path(paths.input_file),
        "topics": topics,
        "error_type": error_type,
        "message": message,
        "report_files_updated": False,
        "config_files_updated": False,
    }


def load_topics(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw_topics = payload.get("topics", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_topics, list):
        return []
    return clean_terms(raw_topics)


def clean_terms(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    terms: list[str] = []
    for value in values:
        term = str(value).strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def action_from_quality_label(label: str) -> str:
    return {
        "可保留": "keep",
        "保留但需收窄": "narrow",
        "降噪优先": "de-noise",
        "未采样": "sample_next",
    }.get(label, "observe")


def action_label(action: str) -> str:
    return {
        "keep": "保留",
        "narrow": "收窄",
        "de-noise": "降噪",
        "observe": "继续观察",
        "sample_next": "下轮补测",
    }.get(action, action or "继续观察")


def cost_note(topics: list[str], sample_count: int) -> str:
    return (
        f"ScrapeCreators 请求数约等于关键词数（当前 {len(topics)} 个）；"
        f"DeepSeek 分析数约等于样本数（当前 {sample_count} 条）。"
    )


def validate_output_paths(paths: ConvergencePaths) -> str:
    for label, path in (("output", paths.output_file), ("json-output", paths.json_file)):
        if is_inside_path(path, REPORTS_DIR):
            return f"{label} 不能写入 reports/：{path}"
        if not is_inside_path(path, LOCAL_OUTPUTS_DIR):
            return f"{label} 必须写入 local_outputs/：{path}"
    return ""


def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def is_inside_path(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def escape_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
