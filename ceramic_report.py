#!/usr/bin/env python3
"""Local wrapper for ceramic trend research reports.

Supports mock reports and a minimal Reddit-only live mode. YouTube, Pinterest,
GitHub Actions, and API-key-backed sources are intentionally left for later
phases.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TOPICS_PATH = PROJECT_ROOT / "config" / "ceramic_topics.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "report.md"
DEFAULT_LATEST_PATH = PROJECT_ROOT / "reports" / "latest.md"
DEFAULT_ARCHIVE_DIR = PROJECT_ROOT / "reports" / "archive"
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "prompts" / "ceramic_report_prompt.md"
DEFAULT_STATE_FILE = PROJECT_ROOT / "local_outputs" / "run_state.json"
DEFAULT_ERROR_FILE = PROJECT_ROOT / "local_outputs" / "last_error.md"
DEFAULT_LAST30DAYS_SCRIPT = Path(
    "/Users/zhuyixiao/Documents/GitHub/last30days-skill/"
    "skills/last30days/scripts/last30days.py"
)
LAST30DAYS_REPO_HINT = "/Users/zhuyixiao/Documents/GitHub/last30days-skill"


@dataclass(frozen=True)
class Evidence:
    topic: str
    source: str
    title: str
    url: str
    snippet: str
    engagement: str
    subreddit: str
    relevance_level: str
    relevance_score: int
    relevance_notes: str


@dataclass(frozen=True)
class TopicRun:
    topic: str
    report: dict[str, Any]
    evidence: list[Evidence]
    error: str = ""


@dataclass(frozen=True)
class RelevanceConfig:
    recommended_subreddits: set[str]
    positive_terms: list[str]
    exclude_terms: list[str]
    topic_rules: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class RunControl:
    state_file: Path
    cooldown_minutes: int
    force: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Chinese ceramic trend intelligence report."
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "live"],
        default="mock",
        help="Run mode. live currently uses Reddit only.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--latest",
        default=os.environ.get("CERAMIC_LATEST_REPORT", str(DEFAULT_LATEST_PATH)),
        help="Latest successful live report path.",
    )
    parser.add_argument(
        "--archive-dir",
        default=os.environ.get("CERAMIC_REPORT_ARCHIVE_DIR", str(DEFAULT_ARCHIVE_DIR)),
        help="Archive directory for successful live reports.",
    )
    parser.add_argument(
        "--topics",
        default=str(DEFAULT_TOPICS_PATH),
        help="Path to ceramic topic config JSON.",
    )
    parser.add_argument(
        "--last30days-script",
        default=os.environ.get("LAST30DAYS_SCRIPT", str(DEFAULT_LAST30DAYS_SCRIPT)),
        help="Path to last30days.py.",
    )
    parser.add_argument(
        "--state-file",
        default=os.environ.get("CERAMIC_RUN_STATE_FILE", str(DEFAULT_STATE_FILE)),
        help="Path to local run-state JSON.",
    )
    parser.add_argument(
        "--error-file",
        default=os.environ.get("CERAMIC_LAST_ERROR_FILE", str(DEFAULT_ERROR_FILE)),
        help="Path to local live error Markdown.",
    )
    parser.add_argument(
        "--cooldown-minutes",
        type=int,
        default=int(os.environ.get("CERAMIC_LIVE_COOLDOWN_MINUTES", "30")),
        help="Minimum minutes between live runs. Use 0 to disable.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the live cooldown guard.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Topic config not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"topics": payload}
    return payload


def load_topics(path: Path) -> list[str]:
    payload = load_config(path)
    if isinstance(payload, list):
        topics = payload
    else:
        topics = payload.get("topics", [])
    cleaned = [str(topic).strip() for topic in topics if str(topic).strip()]
    if not cleaned:
        raise ValueError(f"No topics found in {path}")
    return cleaned


def load_relevance_config(config: dict[str, Any]) -> RelevanceConfig:
    relevance = config.get("relevance") or {}
    return RelevanceConfig(
        recommended_subreddits={
            normalize_subreddit(sub)
            for sub in config.get("recommended_subreddits", [])
            if normalize_subreddit(sub)
        },
        positive_terms=[
            str(term).strip().lower()
            for term in relevance.get("positive_terms", [])
            if str(term).strip()
        ],
        exclude_terms=[
            str(term).strip().lower()
            for term in relevance.get("exclude_terms", [])
            if str(term).strip()
        ],
        topic_rules=config.get("topic_rules") or {},
    )


def build_query_plan(topic: str, sources: list[str]) -> dict[str, Any]:
    source_weights = {source: 1.0 for source in sources}
    return {
        "intent": "opinion",
        "freshness_mode": "balanced_recent",
        "cluster_mode": "debate",
        "source_weights": source_weights,
        "subqueries": [
            {
                "label": "community discussion",
                "search_query": topic,
                "ranking_query": (
                    "What are makers, collectors, and viewers saying about "
                    f"{topic}, including trends, pain points, workflows, and content ideas?"
                ),
                "sources": sources,
                "weight": 1.0,
            }
        ],
        "notes": ["ceramic-trend-research-bot V0.2 plan"],
    }


def assert_last30days_script(script_path: Path) -> None:
    if not script_path.exists():
        raise FileNotFoundError(
            "找不到 last30days-skill 运行脚本。\n"
            f"当前查找路径：{script_path}\n"
            f"请确认 last30days-skill 已克隆到 {LAST30DAYS_REPO_HINT}"
        )


def run_last30days_mock(topic: str, script_path: Path) -> dict[str, Any]:
    return run_last30days(topic, script_path, mode="mock")


def run_last30days_live(
    topic: str,
    script_path: Path,
    recommended_subreddits: set[str] | None = None,
) -> dict[str, Any]:
    return run_last30days(
        topic,
        script_path,
        mode="live",
        recommended_subreddits=recommended_subreddits,
    )


def run_last30days(
    topic: str,
    script_path: Path,
    mode: str,
    recommended_subreddits: set[str] | None = None,
) -> dict[str, Any]:
    assert_last30days_script(script_path)
    if mode not in {"mock", "live"}:
        raise ValueError(f"Unsupported mode: {mode}")

    sources = ["reddit", "youtube"] if mode == "mock" else ["reddit"]
    command = [
        sys.executable,
        str(script_path),
        topic,
        "--quick",
        "--emit=json",
        f"--search={','.join(sources)}",
        "--plan",
        json.dumps(build_query_plan(topic, sources), ensure_ascii=False),
    ]
    if mode == "mock":
        command.insert(3, "--mock")
    if mode == "live" and recommended_subreddits:
        command.extend(["--subreddits", ",".join(sorted(recommended_subreddits))])

    env = os.environ.copy()
    env.setdefault("FROM_BROWSER", "off")
    env.setdefault("LAST30DAYS_CONFIG_DIR", "")

    result = subprocess.run(
        command,
        cwd=str(script_path.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"last30days {mode} run failed\n"
            f"topic: {topic}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return extract_json(result.stdout)


def check_reddit_connectivity() -> tuple[bool, str]:
    url = "https://www.reddit.com/search.json?q=ceramic%20art&sort=relevance&t=month&limit=1&raw_json=1"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ceramic-trend-research-bot/0.2"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return True, f"Reddit reachable, HTTP {response.status}"
    except urllib.error.URLError as exc:
        return False, f"当前网络无法访问 Reddit：{exc}"
    except Exception as exc:
        return False, f"当前网络无法访问 Reddit：{type(exc).__name__}: {exc}"


def load_run_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_run_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def cooldown_message(state: dict[str, Any], control: RunControl) -> str:
    if control.force or control.cooldown_minutes <= 0:
        return ""
    if state.get("mode") != "live":
        return ""
    last_run_at = str(state.get("last_run_at") or "")
    if not last_run_at:
        return ""
    try:
        last_dt = datetime.fromisoformat(last_run_at)
    except ValueError:
        return ""
    elapsed = datetime.now().astimezone() - last_dt
    cooldown = timedelta(minutes=control.cooldown_minutes)
    if elapsed >= cooldown:
        return ""
    remaining = cooldown - elapsed
    minutes = max(1, int(remaining.total_seconds() // 60) + 1)
    status = state.get("last_status") or state.get("status", "unknown")
    error_type = state.get("last_error_type") or state.get("error_type", "")
    cooldown_until = state.get("cooldown_until", "")
    return (
        f"刚刚跑过 live（状态：{status}{'，错误：' + error_type if error_type else ''}）。"
        f" 为了减少 Reddit 429，建议约 {minutes} 分钟后再跑。"
        f"{' 冷却到：' + cooldown_until + '。' if cooldown_until else ''}"
        " 如确实需要立即运行，请加 --force，但不要连续多次强制运行。"
    )


def classify_error(text: str) -> str:
    lowered = text.lower()
    if "429" in lowered or "too many requests" in lowered:
        return "rate_limited_429"
    if "403" in lowered or "forbidden" in lowered or "blocked" in lowered:
        return "forbidden_403"
    if "timed out" in lowered or "timeout" in lowered or "connection reset" in lowered:
        return "timeout"
    if (
        "nodename nor servname" in lowered
        or "name or service not known" in lowered
        or "temporary failure in name resolution" in lowered
        or "failed to resolve" in lowered
    ):
        return "dns_error"
    if (
        "无法访问 reddit" in text
        or "network is unreachable" in lowered
        or "connection refused" in lowered
    ):
        return "network_error"
    if text:
        return "error"
    return ""


def extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON payload found in last30days output:\n{stdout}")
    return json.loads(stdout[start : end + 1])


def apply_relevance_ranking(
    report: dict[str, Any],
    rules: RelevanceConfig,
    topic: str,
) -> dict[str, Any]:
    for source, items in (report.get("items_by_source") or {}).items():
        if source != "reddit" or not isinstance(items, list):
            continue
        for item in items:
            score, level, notes = score_reddit_item(item, rules, topic)
            metadata = item.setdefault("metadata", {})
            metadata["ceramic_relevance_score"] = score
            metadata["ceramic_relevance_level"] = level
            metadata["ceramic_relevance_notes"] = notes
        items.sort(
            key=lambda item: (
                item.get("metadata", {}).get("ceramic_relevance_score", 0),
                item.get("local_rank_score") or 0,
            ),
            reverse=True,
        )
    return report


def score_reddit_item(
    item: dict[str, Any],
    rules: RelevanceConfig,
    topic: str = "",
) -> tuple[int, str, str]:
    title = str(item.get("title") or "")
    body = str(item.get("body") or item.get("snippet") or "")
    subreddit = normalize_subreddit(str(item.get("container") or item.get("subreddit") or ""))
    haystack = " ".join([title, body, subreddit])
    topic_rule = find_topic_rule(topic, rules)

    score = 0
    notes = []
    if subreddit and subreddit in rules.recommended_subreddits:
        score += 4
        notes.append(f"来自推荐 subreddit r/{subreddit}")

    positive_hits = match_terms(haystack, rules.positive_terms)
    if positive_hits:
        score += min(5, len(set(positive_hits)))
        notes.append("命中陶瓷词：" + ", ".join(sorted(set(positive_hits))[:5]))

    title_or_sub = f"{title} {subreddit}"
    strong_hits = match_terms(title_or_sub, rules.positive_terms)
    if strong_hits:
        score += 2
        notes.append("标题或 subreddit 直接相关")

    exclude_hits = match_terms(haystack, rules.exclude_terms)
    rule_exclude_hits = match_terms(haystack, topic_rule.get("exclude_terms", [])) if topic_rule else []
    exclude_hits = sorted(set(exclude_hits + rule_exclude_hits))
    if exclude_hits:
        score -= 5 + min(4, len(set(exclude_hits)))
        notes.append("跑偏词：" + ", ".join(sorted(set(exclude_hits))[:5]))

    if topic_rule:
        required_hits = match_terms(haystack, topic_rule.get("required_terms", []))
        boost_hits = match_terms(haystack, topic_rule.get("boost_terms", []))
        if required_hits:
            score += min(4, len(set(required_hits)))
            notes.append("命中分类意图：" + ", ".join(sorted(set(required_hits))[:5]))
        else:
            if positive_hits:
                score = min(score, 4)
                notes.append("陶瓷相关，但未命中当前关键词意图")
            else:
                score -= 2
                notes.append("未命中当前关键词意图")
        if boost_hits:
            score += min(3, len(set(boost_hits)))
            notes.append("分类加权：" + ", ".join(sorted(set(boost_hits))[:5]))

    if score >= 5:
        level = "high"
    elif score >= 1:
        level = "edge"
    else:
        level = "low"
    return score, level, "；".join(notes) if notes else "未命中明确陶瓷相关信号"


def find_topic_rule(topic: str, rules: RelevanceConfig) -> dict[str, Any]:
    normalized_topic = topic.strip().lower()
    for rule_name, rule in rules.topic_rules.items():
        if normalized_topic == rule_name.lower():
            return rule if isinstance(rule, dict) else {}
    return {}


def match_terms(text: str, terms: list[str]) -> list[str]:
    text_lower = text.lower()
    hits = []
    for raw_term in terms:
        term = str(raw_term).strip().lower()
        if not term:
            continue
        if term_matches(text_lower, term):
            hits.append(term)
    return hits


def term_matches(text_lower: str, term: str) -> bool:
    if not term:
        return False
    escaped = re.escape(term)
    # Treat spaces, hyphens, and underscores in configured phrases as flexible
    # separators, while still requiring token boundaries at both ends.
    escaped = escaped.replace(r"\ ", r"[\s_-]+")
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, text_lower, flags=re.IGNORECASE) is not None


def collect_evidence(topic: str, report: dict[str, Any]) -> list[Evidence]:
    evidence: list[Evidence] = []
    for source, items in (report.get("items_by_source") or {}).items():
        for item in items[:6]:
            metadata = item.get("metadata") or {}
            evidence.append(
                Evidence(
                    topic=topic,
                    source=source,
                    title=item.get("title") or "(untitled)",
                    url=item.get("url") or "",
                    snippet=item.get("snippet") or item.get("body") or "",
                    engagement=format_engagement(item.get("engagement") or {}),
                    subreddit=normalize_subreddit(
                        str(item.get("container") or item.get("subreddit") or "")
                    ),
                    relevance_level=metadata.get("ceramic_relevance_level", "edge"),
                    relevance_score=int(metadata.get("ceramic_relevance_score", 0)),
                    relevance_notes=metadata.get("ceramic_relevance_notes", ""),
                )
            )
    return evidence


def format_engagement(engagement: dict[str, Any]) -> str:
    parts = []
    if engagement.get("score") is not None:
        parts.append(f"{engagement['score']} upvotes")
    if engagement.get("num_comments") is not None:
        parts.append(f"{engagement['num_comments']} comments")
    if engagement.get("views") is not None:
        parts.append(f"{engagement['views']} views")
    if engagement.get("likes") is not None:
        parts.append(f"{engagement['likes']} likes")
    return ", ".join(parts) if parts else "n/a"


def infer_pain_points(topic: str) -> list[str]:
    text = topic.lower()
    if "glaze" in text:
        return ["釉色结果不稳定，配方、厚度、窑温之间的变量难追踪。", "新手难判断流釉、针孔、开片等问题的成因。"]
    if "kiln" in text or "firing" in text:
        return ["烧成曲线和窑位差异带来高试错成本。", "缺少可复盘的烧成记录和失败案例库。"]
    if "business" in text or "studio" in text:
        return ["工作室经营同时面对定价、排课、库存和社媒获客压力。", "手作产品很难把时间成本清楚地转化成价格。"]
    if "ai" in text or "3d" in text:
        return ["数字设计与真实泥料、釉料、烧成之间存在落地断层。", "创作者需要把 AI/3D 灵感转译成可制作的工艺方案。"]
    if "texture" in text:
        return ["纹理灵感容易停留在图片收藏，缺少可执行的制作步骤。", "表面肌理与器型、釉色的搭配需要更多案例对照。"]
    return ["创作者需要更快发现用户真正感兴趣的题材。", "从灵感、制作、展示到销售之间缺少连续的决策工具。"]


def build_conclusion_summary(
    topics: list[str],
    high_evidence: list[Evidence],
    edge_evidence: list[Evidence],
    low_evidence: list[Evidence],
    *,
    mode: str,
) -> list[str]:
    high_sorted = sort_evidence(high_evidence)
    top_topics = unique_in_order([item.topic for item in high_sorted])

    if mode == "mock":
        return [
            "当前是 mock 报告，只用于检查结构、分区和中文表达，不代表真实 Reddit 趋势。",
            f"mock 中有 {len(high_evidence)} 条高相关样例，可用于验证趋势摘要、选题和小工具模块的展示方式。",
            f"高相关样例主要落在 {format_topic_list(top_topics[:3]) or '少数关键词'}，但这些不是实际社媒热度。",
            f"边缘相关 {len(edge_evidence)} 条、跑偏样本 {len(low_evidence)} 条，只用于测试相关性分层是否清楚。",
            "正式判断仍需要 live 模式拿到真实 Reddit 证据后再做。",
        ]

    if not high_evidence:
        return [
            "本轮没有获得高相关 Reddit 证据，不适合做趋势判断。",
            "本轮样本有限，当前结果只能说明搜索或网络状态需要继续调整。",
            f"边缘相关 {len(edge_evidence)} 条、跑偏样本 {len(low_evidence)} 条，均不进入趋势结论。",
            "内容选题和小工具灵感应先标记为观察方向，不应当作已验证机会。",
            "下一轮应优先收窄关键词，并确认 Reddit live 能稳定返回陶瓷相关帖子。",
        ]

    summary = []
    if len(high_evidence) < 4:
        summary.append("本轮样本有限，高相关证据少于 4 条，结论只适合作为早期观察。")
    elif len(high_evidence) < 8:
        summary.append("本轮高相关证据达到中等规模，可以提炼线索，但仍不宜过度外推。")
    else:
        summary.append("本轮高相关证据较充足，可以作为短期 Reddit 趋势简报参考。")

    lead = high_sorted[0]
    summary.append(f"最值得注意的线索来自 {evidence_ref(lead)}，它比普通热帖更贴近陶瓷创作者的真实语境。")
    if len(high_sorted) > 1:
        summary.append(f"另一个可跟进信号是 {evidence_ref(high_sorted[1])}，适合继续观察评论里的具体问题。")
    summary.append(f"高相关证据覆盖 {format_topic_list(top_topics[:4])}，这些方向可以优先进入内容选题池。")
    if edge_evidence:
        summary.append(f"边缘相关有 {len(edge_evidence)} 条，只能作为补充灵感，不足以单独支撑趋势结论。")
    if low_evidence:
        summary.append(f"跑偏样本有 {len(low_evidence)} 条，主要用于复盘过滤规则，不计入本轮趋势判断。")
    summary.append("下一轮应围绕证据不足的关键词改写搜索词，减少宽泛词带来的噪音。")
    return summary[:8]


def credibility_assessment(
    high_evidence: list[Evidence],
    edge_evidence: list[Evidence],
    low_evidence: list[Evidence],
    *,
    mode: str,
    connectivity_note: str = "",
) -> tuple[str, str]:
    high_count = len(high_evidence)
    edge_count = len(edge_evidence)
    low_count = len(low_evidence)

    if mode == "mock":
        return (
            "低",
            "当前是 mock 数据，只能验证报告流程，不能代表真实 Reddit 趋势。",
        )
    if connectivity_note and high_count == 0:
        return (
            "低",
            "live 未拿到可用证据，本轮不适合做趋势判断。",
        )
    if high_count >= 8:
        level = "高"
        reason = "高相关证据不少于 8 条，可以作为本轮 Reddit 陶瓷圈观察依据。"
    elif high_count >= 4:
        level = "中"
        reason = "高相关证据在 4 到 7 条之间，可以提炼方向，但仍需下一轮扩大样本。"
    else:
        level = "低"
        reason = "高相关证据少于 4 条，本轮不适合做确定性趋势判断。"

    if edge_count or low_count:
        reason += f" 边缘相关 {edge_count} 条、跑偏样本 {low_count} 条已从趋势判断中降权处理。"
    return level, reason


def trend_insights(
    topics: list[str],
    high_evidence: list[Evidence],
    *,
    mode: str,
) -> list[str]:
    if mode == "mock":
        return ["当前为 mock 模式，本节只展示报告结构，不从模拟数据生成真实趋势判断。"]
    if not high_evidence:
        return ["本轮未获得高相关 Reddit 证据，因此不生成确定性趋势判断。"]

    insights = ["本轮 Reddit 数据样本有限，趋势判断仅代表当前抓取结果。"]
    signal_rules = [
        (
            ("glaze", "underglaze", "recipe", "test tile", "defect"),
            "釉料与表面结果的讨论更像“问题求诊断”而不是单纯晒图，适合继续观察配方、测试片和缺陷排查内容。",
        ),
        (
            ("kiln", "firing", "cone", "temperature", "bisque", "schedule"),
            "烧成环节仍是高价值讨论点，用户更需要可复盘的温度、锥度、窑位和失败原因整理。",
        ),
        (
            ("business", "pricing", "etsy", "customer", "studio", "sell", "order"),
            "经营类问题如果持续出现，说明工作室定价、订单沟通和销售解释是中文内容可以切入的实用主题。",
        ),
        (
            ("ai", "generative", "digital", "prompt", "pattern", "computational"),
            "AI/数字设计目前需要看是否真的落到陶瓷制作流程；只有同时出现 AI 与陶瓷工艺语境时，才适合判断为趋势信号。",
        ),
        (
            ("3d", "printing", "printed", "extrusion", "paste"),
            "3D 打印陶瓷更适合作为技术观察线索，重点应放在材料、成型失败和可制作性，而不是只看视觉新鲜感。",
        ),
    ]

    for terms, analysis in signal_rules:
        matches = [item for item in sort_evidence(high_evidence) if evidence_has_any(item, terms)]
        if not matches:
            continue
        refs = ", ".join(evidence_ref(item) for item in matches[:2])
        qualifier = "目前更像观察信号，不足以判断为稳定趋势" if len(matches) < 2 else "可作为本轮优先跟进方向"
        insights.append(f"{analysis} 证据：{refs}；{qualifier}。")

    if len(insights) == 1 and high_evidence:
        lead = sort_evidence(high_evidence)[0]
        insights.append(
            f"本轮最强信号来自 {evidence_ref(lead)}，但还需要更多同类证据，暂时更适合做单篇内容切口。"
        )

    high_topics = {item.topic for item in high_evidence}
    unsupported = [topic for topic in topics if topic not in high_topics]
    if unsupported:
        insights.append("以下方向本轮高相关证据不足，暂不形成趋势判断：" + "、".join(unsupported) + "。")
    return insights


def supported_content_ideas(high_evidence: list[Evidence], *, mode: str) -> list[str]:
    if mode != "live":
        return []
    ideas = []
    seen_topics = set()
    for item in sort_evidence(high_evidence):
        if item.topic in seen_topics:
            continue
        seen_topics.add(item.topic)
        ideas.append(
            f"《{item.topic}：把一个 Reddit 真实问题讲透》 - 值得做：{content_reason(item)} 证据：{evidence_ref(item)}。"
        )
    return ideas


def observation_content_ideas(
    topics: list[str],
    high_evidence: list[Evidence],
    edge_evidence: list[Evidence],
) -> list[str]:
    high_topics = {item.topic for item in high_evidence}
    edge_by_topic = group_by_topic(edge_evidence)
    ideas = []
    for topic in topics:
        if topic in high_topics:
            continue
        if edge_by_topic.get(topic):
            sample = sort_evidence(edge_by_topic[topic])[0]
            ideas.append(
                f"观察方向：《{topic} 是否值得继续追？》 - 只有边缘证据 {evidence_ref(sample)}，下一轮需要更具体关键词验证。"
            )
        else:
            ideas.append(
                f"观察方向：《{topic} 最近 30 天是否形成趋势？》 - 本轮缺少高相关证据，建议扩大或改写搜索词后再判断。"
            )
    ideas.extend(
        [
            "观察方向：《陶瓷作品从灵感到烧成失败复盘》 - 长期内容方向，需用更多真实失败案例验证。",
            "观察方向：《釉色测试片如何变成可售卖系列》 - 适合等待更多 glaze / business 证据后展开。",
            "观察方向：《AI 生成纹样到真实陶瓷表面的完整流程》 - 只有在 AI 与陶瓷制作同时出现时，才可升级为证据支撑选题。",
        ]
    )
    return ideas


def evidence_backed_tool_ideas(high_evidence: list[Evidence], *, mode: str) -> list[str]:
    if mode != "live":
        return []
    ideas = []
    seen = set()
    for item in sort_evidence(high_evidence):
        text = evidence_text(item)
        if any(term in text for term in ("kiln", "firing", "cone", "temperature", "bisque", "schedule")):
            key = "kiln"
            idea = f"烧成失败诊断卡：本轮证据 {evidence_ref(item)} 指向烧成复盘需求，可记录温度、锥度、窑位和失败现象。"
        elif any(term in text for term in ("business", "etsy", "pricing", "customer", "sell", "studio", "order")):
            key = "business"
            idea = f"工作室定价与客户沟通表：本轮证据 {evidence_ref(item)} 指向经营解释成本，可整理定价、订单、瑕疵说明和售后话术。"
        elif any(term in text for term in ("glaze", "recipe", "test tile", "underglaze", "defect")):
            key = "glaze"
            idea = f"釉色实验记录器：本轮证据 {evidence_ref(item)} 指向釉料测试和缺陷排查，可记录配方、厚度、烧成条件和结果照片。"
        elif any(term in text for term in ("ai", "generative", "digital", "prompt", "pattern")):
            key = "ai"
            idea = f"AI 陶瓷纹样落地检查表：本轮证据 {evidence_ref(item)} 指向数字灵感到工艺执行的断层，可把 prompt、纹样、泥料和烧成限制放在同一页。"
        else:
            continue
        if key not in seen:
            seen.add(key)
            ideas.append(idea)
    return ideas


def long_term_tool_ideas() -> list[str]:
    return [
        "陶瓷内容选题雷达：长期产品方向，不是本轮数据直接证明，后续需要更多 Reddit/YouTube/Pinterest 证据验证。",
        "AI 陶瓷纹样 Prompt 生成器：长期产品方向，不是本轮数据直接证明，需等 AI ceramic design 出现真实高相关证据后优先化。",
        "釉色实验记录器：长期产品方向，不是本轮数据直接证明，可在更多 glaze / kiln 证据出现后优先化。",
        "工作室定价小工具：长期产品方向，不是本轮数据直接证明，可在更多 business / studio 证据出现后优先化。",
    ]


def next_search_suggestions(
    topics: list[str],
    high_evidence: list[Evidence],
    edge_evidence: list[Evidence],
    low_evidence: list[Evidence],
    *,
    mode: str,
) -> list[str]:
    high_by_topic = group_by_topic(high_evidence)
    edge_by_topic = group_by_topic(edge_evidence)
    suggestions = []

    if mode == "mock":
        suggestions.append("当前是 mock 报告，下一轮应使用 live 模式验证真实 Reddit 结果，再根据证据调整关键词。")

    for topic in topics:
        high_count = len(high_by_topic.get(topic, []))
        edge_count = len(edge_by_topic.get(topic, []))
        terms = suggested_keywords_for_topic(topic)
        if high_count == 0:
            suggestions.append(
                f"**{topic}**：本轮高相关证据不足，建议下一轮尝试更具体关键词：{format_code_terms(terms)}。"
            )
        elif high_count < 2:
            suggestions.append(
                f"**{topic}**：只有 {high_count} 条高相关证据、{edge_count} 条边缘证据，建议保留原词并加入：{format_code_terms(terms[:3])}。"
            )

    if low_evidence:
        samples = ", ".join(short_title(item.title, 24) for item in low_evidence[:3])
        suggestions.append(
            f"**过滤规则**：本轮跑偏样本包括 {samples}；下一轮继续把 anime、gaming、地区词和非陶瓷消费品降权。"
        )
    if not suggestions:
        suggestions.append("本轮高相关证据较稳定，下一轮可以保持关键词，同时增加 YouTube/Pinterest 后再比较跨平台一致性。")
    return suggestions


def suggested_keywords_for_topic(topic: str) -> list[str]:
    text = topic.lower()
    if "ai" in text:
        return ["AI pottery workflow", "generative ceramic pattern", "computational ceramics", "ceramic prompt design"]
    if "business" in text or "studio" in text:
        return ["Etsy pottery pricing", "pottery commission", "ceramic studio marketing", "handmade ceramics pricing"]
    if "kiln" in text or "firing" in text:
        return ["cone 6", "bisque firing", "electric kiln", "glaze defects", "kiln schedule"]
    if "glaze" in text:
        return ["ceramic glaze defects", "cone 6 glaze", "glaze test tiles", "underglaze technique"]
    if "3d" in text or "printed" in text:
        return ["ceramic 3D printing clay", "clay paste extrusion", "3D printed pottery", "ceramic printing failure"]
    if "texture" in text:
        return ["ceramic surface texture", "clay texture tools", "handbuilt texture", "carved pottery surface"]
    return ["handmade pottery process", "ceramic artist studio", "pottery critique", "clay handbuilding techniques"]


def sort_evidence(evidence: list[Evidence]) -> list[Evidence]:
    return sorted(evidence, key=lambda item: item.relevance_score, reverse=True)


def unique_in_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def format_topic_list(topics: list[str]) -> str:
    return "、".join(topics)


def group_by_topic(evidence: list[Evidence]) -> dict[str, list[Evidence]]:
    grouped: dict[str, list[Evidence]] = {}
    for item in evidence:
        grouped.setdefault(item.topic, []).append(item)
    return grouped


def evidence_ref(item: Evidence) -> str:
    subreddit = f"r/{item.subreddit}" if item.subreddit else "Reddit"
    return f"{subreddit} 的“{short_title(item.title, 42)}”"


def evidence_text(item: Evidence) -> str:
    return " ".join([item.topic, item.title, item.snippet, item.relevance_notes]).lower()


def evidence_has_any(item: Evidence, terms: tuple[str, ...]) -> bool:
    text = evidence_text(item)
    return any(term in text for term in terms)


def content_reason(item: Evidence) -> str:
    text = evidence_text(item)
    if any(term in text for term in ("kiln", "firing", "cone", "temperature", "bisque", "schedule")):
        return "它把烧成失败、温度控制或窑炉选择变成可拆解步骤，适合做避坑型内容。"
    if any(term in text for term in ("glaze", "recipe", "test tile", "underglaze", "defect")):
        return "它对应釉色测试和缺陷排查，读者通常会需要配方、变量和前后对照。"
    if any(term in text for term in ("business", "etsy", "pricing", "customer", "sell", "studio", "order")):
        return "它贴近工作室经营场景，能转成定价、客户沟通或销售复盘内容。"
    if any(term in text for term in ("ai", "generative", "digital", "prompt", "pattern", "computational")):
        return "它连接数字灵感与真实制作，适合讲清楚从图案到泥料、釉料和烧成的落地过程。"
    if any(term in text for term in ("3d", "printing", "printed", "extrusion")):
        return "它涉及新工艺落地，适合用案例解释材料、成型限制和失败成本。"
    return "它来自高相关陶瓷语境，适合围绕真实问题做解释、复盘或案例拆解。"


def format_code_terms(terms: list[str]) -> str:
    return "、".join(f"`{term}`" for term in terms)


def short_title(title: str, limit: int) -> str:
    cleaned = " ".join(str(title).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def render_report(
    runs: list[TopicRun],
    prompt_template: str,
    *,
    mode: str,
    connectivity_note: str = "",
) -> str:
    topics = [run.topic for run in runs]
    all_evidence = [item for run in runs for item in run.evidence]
    high_evidence = [item for item in all_evidence if item.relevance_level == "high"]
    edge_evidence = [item for item in all_evidence if item.relevance_level == "edge"]
    low_evidence = [item for item in all_evidence if item.relevance_level == "low"]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    credibility_level, credibility_reason = credibility_assessment(
        high_evidence,
        edge_evidence,
        low_evidence,
        mode=mode,
        connectivity_note=connectivity_note,
    )

    lines = [
        "# 陶瓷趋势情报报告",
        "",
        f"- 生成时间：{generated_at}",
        f"- 版本：V0.4 {'Reddit live' if mode == 'live' else 'mock'} 本地报告",
        f"- 数据模式：{data_mode_label(mode)}",
        f"- 关键词数量：{len(topics)}",
        f"- 相关性分层：高相关 {len(high_evidence)} 条，边缘相关 {len(edge_evidence)} 条，跑偏样本 {len(low_evidence)} 条",
        "",
        report_note(mode, all_evidence, connectivity_note),
        "",
        "## 本轮结论摘要",
        "",
    ]

    for summary in build_conclusion_summary(
        topics,
        high_evidence,
        edge_evidence,
        low_evidence,
        mode=mode,
    ):
        lines.append(f"- {summary}")

    lines.extend(
        [
            "",
            "## 本轮可信度",
            "",
            f"- 可信度：**{credibility_level}**",
            f"- 判断：{credibility_reason}",
            f"- 证据结构：高相关 {len(high_evidence)} 条，边缘相关 {len(edge_evidence)} 条，跑偏样本 {len(low_evidence)} 条。",
            "",
        ]
    )

    lines.extend(
        [
        "## 热门内容",
        "",
        ]
    )

    if all_evidence:
        for run in runs:
            best = next((item for item in run.evidence if item.relevance_level == "high"), None)
            prefix = "真实 Reddit 热点" if mode == "live" else "mock 热点"
            if best:
                subreddit = f"r/{best.subreddit}" if best.subreddit else "n/a"
                lines.append(
                    f"- **{run.topic}**：{prefix}为“{best.title}”（{subreddit}，{best.engagement}），"
                    f"相关性：高相关（{best.relevance_score} 分）。"
                )
            elif any(item.relevance_level in {"edge", "low"} for item in run.evidence):
                lines.append(
                    f"- **{run.topic}**：本轮仅发现低相关或跑偏结果，建议后续扩大数据源后再判断。"
                )
            else:
                lines.append(
                    f"- **{run.topic}**：本轮未获得高质量 Reddit 证据，暂不纳入趋势判断。"
                )
    else:
        lines.append("- 暂未获得可用 Reddit 证据。mock 模式仍可用于验证报告流程。")

    lines.extend(["", "## 用户痛点", ""])
    for topic in topics:
        for pain in infer_pain_points(topic):
            lines.append(f"- **{topic}**：{pain}")

    lines.extend(["", "## 趋势判断", ""])
    for insight in trend_insights(topics, high_evidence, mode=mode):
        lines.append(f"- {insight}")

    lines.extend(["", "## 内容选题", ""])
    lines.append("### 有 Reddit 高相关证据支撑的选题")
    supported_ideas = supported_content_ideas(high_evidence, mode=mode)
    if supported_ideas:
        for idea in supported_ideas:
            lines.append(f"- {idea}")
    elif mode == "mock":
        lines.append("- 当前为 mock 模式，暂无真实 Reddit 高相关证据支撑的选题。")
    else:
        lines.append("- 本轮暂无高相关 Reddit 证据支撑的选题。")
    lines.append("")
    lines.append("### 暂无充分证据但值得后续观察的选题")
    for idea in observation_content_ideas(topics, high_evidence, edge_evidence):
        lines.append(f"- {idea}")

    lines.extend(["", "## 小工具灵感", ""])
    lines.append("### 本轮证据直接支持的小工具")
    backed_tools = evidence_backed_tool_ideas(high_evidence, mode=mode)
    if backed_tools:
        for idea in backed_tools:
            lines.append(f"- {idea}")
    elif mode == "mock":
        lines.append("- 当前为 mock 模式，不把模拟数据写成本轮证据直接支持的小工具。")
    else:
        lines.append("- 本轮暂无足够高相关证据直接支撑具体小工具需求。")
    lines.append("")
    lines.append("### 长期产品方向")
    for idea in long_term_tool_ideas():
        lines.append(f"- {idea}")

    lines.extend(["", "## 下一轮搜索建议", ""])
    for suggestion in next_search_suggestions(
        topics,
        high_evidence,
        edge_evidence,
        low_evidence,
        mode=mode,
    ):
        lines.append(f"- {suggestion}")

    lines.extend(["", "## 高相关内容", ""])
    append_evidence_table(lines, high_evidence)

    lines.extend(["", "## 边缘相关内容", ""])
    append_evidence_table(lines, edge_evidence)

    lines.extend(["", "## 跑偏样本", ""])
    if low_evidence:
        lines.append("> 跑偏样本只用于过滤规则复盘，不计入趋势判断。")
        lines.append("")
        append_low_relevance_review(lines, low_evidence)
        lines.append("")
    append_evidence_table(lines, low_evidence)

    lines.extend(["", "## 原始证据/链接", ""])
    if all_evidence:
        append_evidence_table(lines, all_evidence, include_level=True)
    else:
        lines.append(f"- 暂无证据。{connectivity_note or 'live run returned no usable Reddit items.'}")
        for run in runs:
            if run.error:
                lines.append(f"- **{run.topic}**：{run.error}")

    lines.extend(
        [
            "",
            "## 后续升级接口",
            "",
            "- `--mode live` 当前只接入 Reddit；YouTube、Pinterest、GitHub Actions 留到后续阶段。",
            "- 报告结构来自 `prompts/ceramic_report_prompt.md`，后续可替换为 LLM 中文综合。",
            "- 自动化路线见 `docs/automation-roadmap.md`。",
            "",
            "## 当前报告模板",
            "",
            "```markdown",
            prompt_template.strip(),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def data_mode_label(mode: str) -> str:
    if mode == "live":
        return "last30days-skill `--quick --search=reddit`"
    return "last30days-skill `--mock --quick --search=reddit,youtube`"


def append_evidence_table(
    lines: list[str],
    evidence: list[Evidence],
    *,
    include_level: bool = False,
) -> None:
    if not evidence:
        lines.append("- 暂无。")
        return
    if include_level:
        lines.extend(
            [
                "| 相关性 | 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |",
                "|---|---|---|---|---|---|---|",
            ]
        )
    else:
        lines.extend(
            [
                "| 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |",
                "|---|---|---|---|---|---|---|",
            ]
        )
    for item in evidence:
        link = f"[打开]({item.url})" if item.url else "n/a"
        subreddit = f"r/{item.subreddit}" if item.subreddit else "n/a"
        row = [
            escape_cell(item.topic),
            escape_cell(subreddit),
            escape_cell(item.title),
            escape_cell(item.engagement),
            escape_cell(item.relevance_notes),
            link,
        ]
        if include_level:
            row.insert(0, relevance_label(item.relevance_level))
        lines.append("| " + " | ".join(row) + " |")


def append_low_relevance_review(lines: list[str], evidence: list[Evidence]) -> None:
    lines.append("### 过滤复盘")
    for item in evidence[:5]:
        lines.append(
            f"- **{short_title(item.title, 44)}**：{low_relevance_reason(item)} "
            f"下次可通过更具体关键词或排除词降低误伤。"
        )


def low_relevance_reason(item: Evidence) -> str:
    notes = item.relevance_notes
    if "跑偏词" in notes:
        return f"命中了跑偏信号（{notes}），主题不应进入陶瓷趋势判断。"
    if "未命中当前关键词意图" in notes:
        return "虽然可能碰到陶瓷词，但没有满足当前关键词意图。"
    if item.subreddit:
        return f"来自 r/{item.subreddit}，陶瓷语境不足或与本轮分类目标不一致。"
    return "陶瓷语境不足或主题偏离本轮分类目标。"


def relevance_label(level: str) -> str:
    return {
        "high": "高相关",
        "edge": "边缘相关",
        "low": "相关性较低",
    }.get(level, level)


def report_note(mode: str, evidence: list[Evidence], connectivity_note: str) -> str:
    if mode == "mock":
        return "> 说明：当前报告使用 mock 数据验证流程与版式，不代表真实社媒趋势。"
    if evidence:
        return "> 说明：当前报告使用 Reddit live 数据。YouTube、Pinterest、GitHub 等来源尚未接入。"
    return (
        "> 说明：当前 live 模式已调用 Reddit-only pipeline，但没有获得可用证据。"
        f"{connectivity_note or '请检查本机网络是否能访问 Reddit。'}"
    )


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def evidence_summary(runs: list[TopicRun]) -> dict[str, int]:
    all_evidence = [item for run in runs for item in run.evidence]
    high = [item for item in all_evidence if item.relevance_level == "high"]
    edge = [item for item in all_evidence if item.relevance_level == "edge"]
    low = [item for item in all_evidence if item.relevance_level == "low"]
    return {
        "evidence_count": len(all_evidence),
        "usable_evidence_count": len(high) + len(edge),
        "high_relevance_count": len(high),
        "edge_relevance_count": len(edge),
        "low_relevance_count": len(low),
    }


def collect_error_text(runs: list[TopicRun], connectivity_note: str = "") -> str:
    messages: list[str] = []
    for message in [run.error for run in runs] + [connectivity_note]:
        cleaned = str(message or "").strip()
        if cleaned and cleaned not in messages:
            messages.append(cleaned)
    return "\n".join(messages)


def live_status_and_error_type(
    runs: list[TopicRun],
    connectivity_note: str,
    usable_evidence_count: int,
) -> tuple[str, str, str]:
    error_text = collect_error_text(runs, connectivity_note)
    error_type = classify_error(error_text)
    if error_type == "rate_limited_429":
        status = "rate_limited"
    elif error_text or usable_evidence_count == 0:
        status = "failed"
    else:
        status = "success"
    if status != "success" and not error_type:
        error_type = "no_usable_reddit_evidence"
    return status, error_type, error_text


def live_error_guidance(error_type: str) -> str:
    guidance = {
        "forbidden_403": (
            "Reddit 已拒绝当前请求，通常是代理出口、IP、User-Agent 或 Reddit 访问策略导致。"
            "建议换代理节点，确认终端代理生效，稍后再试。代码和报告生成逻辑通常没有坏。"
        ),
        "rate_limited_429": (
            "Reddit 临时限流。请至少等待 30 分钟，不要连续使用 --force。"
            "可以先用 mock 模式调整报告结构。"
        ),
        "dns_error": (
            "当前运行环境无法解析 Reddit 域名。请检查网络、代理、DNS，或换到本地终端运行。"
        ),
        "timeout": (
            "网络连接不稳定或代理出口被重置。建议检查代理节点或稍后再试。"
        ),
        "network_error": (
            "当前网络无法稳定访问 Reddit。请检查代理、网络连通性，或稍后再试。"
        ),
        "no_usable_reddit_evidence": (
            "本次没有拿到可用 Reddit 证据。可以先用 mock 模式调整报告结构，再换更具体关键词重试 live。"
        ),
    }
    return guidance.get(
        error_type,
        "live 运行失败，但已保留上一份成功报告。请查看原始错误后再决定是否重试。",
    )


def cooldown_until_iso(now: datetime, control: RunControl) -> str:
    if control.cooldown_minutes <= 0:
        return ""
    return (now + timedelta(minutes=control.cooldown_minutes)).isoformat(timespec="seconds")


def build_run_state(
    *,
    mode: str,
    status: str,
    error_type: str,
    output_path: Path,
    error_path: Path | None,
    counts: dict[str, int],
    control: RunControl,
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    state = {
        "last_run_at": now.isoformat(timespec="seconds"),
        "mode": mode,
        "status": status,
        "error_type": error_type,
        "last_status": status,
        "last_error_type": error_type,
        "output_path": str(output_path),
        "cooldown_until": cooldown_until_iso(now, control) if mode == "live" else "",
        **counts,
    }
    if error_path is not None:
        state["error_path"] = str(error_path)
    return state


def render_live_error_report(
    *,
    runs: list[TopicRun],
    output_path: Path,
    error_type: str,
    error_text: str,
    connectivity_note: str,
    evidence_counts: dict[str, int],
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    guidance = live_error_guidance(error_type)
    lines = [
        "# Reddit live 运行失败记录",
        "",
        f"- 发生时间：{generated_at}",
        f"- 错误类型：{error_type or 'unknown'}",
        f"- 正式报告：{display_path(output_path)}",
        f"- 当前采取的保护动作：未覆盖 `reports/report.md`，已保留上一份成功报告",
        f"- 本次抓到证据总数：{evidence_counts['evidence_count']}",
        f"- 本次可用证据数：{evidence_counts['usable_evidence_count']}",
        "",
        "## 说明",
        "",
        "live 失败，未覆盖 `reports/report.md`。如果这是 Reddit 403 / 429 / DNS 问题，建议稍后再运行 live，mock 模式仍可继续用于测试报告流程。",
        "",
        "## 建议下一步操作",
        "",
        f"- {guidance}",
        "- 不要连续多次使用 `--force`，尤其是 429 限流后。",
        "- 需要继续改报告结构时，先运行 `bash scripts/run_mock.sh`。",
        "",
        "## 错误摘要",
        "",
    ]
    if error_text:
        lines.append("```text")
        lines.append(error_text.strip())
        lines.append("```")
    else:
        lines.append("- 本次没有拿到高相关或边缘相关 Reddit 证据，因此没有更新正式报告。")

    if connectivity_note:
        lines.extend(["", "## Reddit 预检", "", f"- {connectivity_note}"])

    topic_errors = [(run.topic, run.error) for run in runs if run.error]
    if topic_errors:
        lines.extend(["", "## 关键词错误", ""])
        for topic, error in topic_errors:
            lines.append(f"- **{topic}**：{error}")

    lines.extend(
        [
            "",
            "## NEXT STEPS",
            "",
            "- 如果是 `forbidden_403`：通常是 Reddit 阻挡当前网络或请求方式，稍后换网络或降低频率再试。",
            "- 如果是 `rate_limited_429`：不要立刻重复运行，等待冷却时间后再试。",
            "- 如果是 `dns_error`：先确认本机能解析并访问 `www.reddit.com`。",
            "- 如果是 `timeout`：检查代理出口稳定性，或稍后再试。",
            "- 如果是 `network_error`：先确认当前网络能打开 Reddit，再运行 `bash scripts/run_live.sh --force`。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def archive_filename(now: datetime) -> str:
    return f"{now.strftime('%Y-%m-%d_%H%M')}_report.md"


def write_successful_live_report(
    *,
    output_path: Path,
    latest_path: Path,
    archive_dir: Path,
    content: str,
) -> Path:
    now = datetime.now().astimezone()
    archive_path = archive_dir / archive_filename(now)
    write_text_file(output_path, content)
    write_text_file(latest_path, content)
    write_text_file(archive_path, content)
    return archive_path


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def normalize_subreddit(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned.startswith("r/"):
        cleaned = cleaned[2:]
    return cleaned


def main() -> int:
    args = parse_args()
    topics_path = Path(args.topics).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    latest_path = Path(args.latest).expanduser().resolve()
    archive_dir = Path(args.archive_dir).expanduser().resolve()
    script_path = Path(args.last30days_script).expanduser().resolve()
    prompt_path = DEFAULT_PROMPT_PATH
    state_path = Path(args.state_file).expanduser().resolve()
    error_path = Path(args.error_file).expanduser().resolve()
    control = RunControl(
        state_file=state_path,
        cooldown_minutes=args.cooldown_minutes,
        force=args.force,
    )

    config = load_config(topics_path)
    topics = load_topics(topics_path)
    relevance_config = load_relevance_config(config)
    prompt_template = prompt_path.read_text(encoding="utf-8")
    connectivity_note = ""
    state = load_run_state(state_path)
    if args.mode == "live":
        message = cooldown_message(state, control)
        if message:
            print(message)
            print(f"上次报告路径：{state.get('output_path', 'unknown')}")
            return 0

    skip_live_retrieval = False
    if args.mode == "live":
        ok, connectivity_note = check_reddit_connectivity()
        if not ok:
            print(connectivity_note, file=sys.stderr)
            skip_live_retrieval = True

    runs: list[TopicRun] = []
    for topic in topics:
        try:
            if args.mode == "live" and skip_live_retrieval:
                runs.append(TopicRun(topic=topic, report={"topic": topic}, evidence=[], error=connectivity_note))
                continue
            if args.mode == "live":
                report = run_last30days_live(
                    topic,
                    script_path,
                    recommended_subreddits=relevance_config.recommended_subreddits,
                )
            else:
                report = run_last30days_mock(topic, script_path)
            report = apply_relevance_ranking(report, relevance_config, topic)
            runs.append(
                TopicRun(
                    topic=topic,
                    report=report,
                    evidence=collect_evidence(topic, report),
                )
            )
        except Exception as exc:
            if args.mode != "live":
                raise
            runs.append(TopicRun(topic=topic, report={"topic": topic}, evidence=[], error=str(exc)))

    report_markdown = render_report(
        runs,
        prompt_template,
        mode=args.mode,
        connectivity_note=connectivity_note,
    )
    counts = evidence_summary(runs)
    if args.mode == "live":
        status, error_type, error_text = live_status_and_error_type(
            runs,
            connectivity_note,
            counts["usable_evidence_count"],
        )
        if status == "success":
            archive_path = write_successful_live_report(
                output_path=output_path,
                latest_path=latest_path,
                archive_dir=archive_dir,
                content=report_markdown,
            )
            run_state = build_run_state(
                mode=args.mode,
                status=status,
                error_type=error_type,
                output_path=output_path,
                error_path=error_path,
                counts=counts,
                control=control,
            )
            run_state["latest_path"] = str(latest_path)
            run_state["archive_path"] = str(archive_path)
            save_run_state(
                state_path,
                run_state,
            )
            print(f"已更新 {display_path(output_path)}")
            print(f"已更新 {display_path(latest_path)}")
            print(f"已归档 {display_path(archive_path)}")
            return 0

        write_text_file(
            error_path,
            render_live_error_report(
                runs=runs,
                output_path=output_path,
                error_type=error_type,
                error_text=error_text,
                connectivity_note=connectivity_note,
                evidence_counts=counts,
            ),
        )
        save_run_state(
            state_path,
            build_run_state(
                mode=args.mode,
                status=status,
                error_type=error_type,
                output_path=output_path,
                error_path=error_path,
                counts=counts,
                control=control,
            ),
        )
        print(f"live 失败，已保留上一份成功报告；错误详情见 {display_path(error_path)}")
        return 0

    write_text_file(output_path, report_markdown)
    save_run_state(
        state_path,
        build_run_state(
            mode=args.mode,
            status="success",
            error_type="",
            output_path=output_path,
            error_path=None,
            counts=counts,
            control=control,
        ),
    )
    print(f"已更新 {display_path(output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
