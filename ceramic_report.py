#!/usr/bin/env python3
"""Local wrapper for ceramic trend research reports.

V0.2 supports mock reports and a minimal Reddit-only live mode. YouTube,
Pinterest, GitHub Actions, and API-key-backed sources are intentionally left
for later phases.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TOPICS_PATH = PROJECT_ROOT / "config" / "ceramic_topics.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "report.md"
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "prompts" / "ceramic_report_prompt.md"
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
        "--topics",
        default=str(DEFAULT_TOPICS_PATH),
        help="Path to ceramic topic config JSON.",
    )
    parser.add_argument(
        "--last30days-script",
        default=os.environ.get("LAST30DAYS_SCRIPT", str(DEFAULT_LAST30DAYS_SCRIPT)),
        help="Path to last30days.py.",
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


def extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON payload found in last30days output:\n{stdout}")
    return json.loads(stdout[start : end + 1])


def apply_relevance_ranking(report: dict[str, Any], rules: RelevanceConfig) -> dict[str, Any]:
    for source, items in (report.get("items_by_source") or {}).items():
        if source != "reddit" or not isinstance(items, list):
            continue
        for item in items:
            score, level, notes = score_reddit_item(item, rules)
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


def score_reddit_item(item: dict[str, Any], rules: RelevanceConfig) -> tuple[int, str, str]:
    title = str(item.get("title") or "")
    body = str(item.get("body") or item.get("snippet") or "")
    subreddit = normalize_subreddit(str(item.get("container") or item.get("subreddit") or ""))
    haystack = " ".join([title, body, subreddit]).lower()

    score = 0
    notes = []
    if subreddit and subreddit in rules.recommended_subreddits:
        score += 4
        notes.append(f"来自推荐 subreddit r/{subreddit}")

    positive_hits = [term for term in rules.positive_terms if term in haystack]
    if positive_hits:
        score += min(5, len(set(positive_hits)))
        notes.append("命中陶瓷词：" + ", ".join(sorted(set(positive_hits))[:5]))

    title_or_sub = f"{title} {subreddit}".lower()
    strong_hits = [term for term in rules.positive_terms if term in title_or_sub]
    if strong_hits:
        score += 2
        notes.append("标题或 subreddit 直接相关")

    exclude_hits = [term for term in rules.exclude_terms if term in haystack]
    if exclude_hits:
        score -= 5 + min(4, len(set(exclude_hits)))
        notes.append("跑偏词：" + ", ".join(sorted(set(exclude_hits))[:5]))

    if score >= 5:
        level = "high"
    elif score >= 1:
        level = "edge"
    else:
        level = "low"
    return score, level, "；".join(notes) if notes else "未命中明确陶瓷相关信号"


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


def trend_insights(topics: list[str]) -> list[str]:
    joined = " ".join(topics).lower()
    insights = [
        "手作陶瓷仍然适合用“过程感”表达价值，用户更容易被制作细节、失败修正和前后对比吸引。",
        "釉色、肌理、窑变这类视觉信号适合做短视频和图文系列，因为它们天然具备收藏、评论和二次提问空间。",
    ]
    if "ai" in joined or "3d" in joined:
        insights.append("AI 与 3D 打印更适合作为灵感生成和打样辅助，而不是直接替代手作叙事。")
    if "business" in joined or "studio" in joined:
        insights.append("陶瓷工作室的内容不应只展示成品，也可以展示定价、排课、工具选择和经营复盘。")
    if "kiln" in joined or "firing" in joined:
        insights.append("烧成知识是高信任内容入口，适合沉淀成检查清单、记录表和案例库。")
    return insights


def content_ideas(topics: list[str]) -> list[str]:
    return [
        f"《{topic} 最近 30 天大家在讨论什么？》"
        for topic in topics[:5]
    ] + [
        "《一个陶瓷作品从灵感到烧成失败复盘》",
        "《釉色测试片如何变成可售卖系列》",
        "《AI 生成纹样到真实陶瓷表面的完整流程》",
    ]


def tool_ideas() -> list[str]:
    return [
        "釉色实验记录器：记录配方、厚度、窑温、位置和成品照片。",
        "陶瓷内容选题雷达：按 Reddit/YouTube/Pinterest 热点聚合中文选题。",
        "AI 陶瓷纹样 Prompt 生成器：把风格、器型、釉色和工艺限制组合成提示词。",
        "烧成失败诊断卡：根据针孔、流釉、变形、开裂等现象给出排查路径。",
        "工作室定价小工具：把泥料、釉料、烧成、工时、损耗和平台费用折算进价格。",
    ]


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

    lines = [
        "# 陶瓷趋势情报报告",
        "",
        f"- 生成时间：{generated_at}",
        f"- 版本：V0.3.1 {'Reddit live' if mode == 'live' else 'mock'} 本地报告",
        f"- 数据模式：{data_mode_label(mode)}",
        f"- 关键词数量：{len(topics)}",
        f"- 相关性分层：高相关 {len(high_evidence)} 条，边缘相关 {len(edge_evidence)} 条，跑偏样本 {len(low_evidence)} 条",
        "",
        report_note(mode, all_evidence, connectivity_note),
        "",
        "## 热门内容",
        "",
    ]

    if all_evidence:
        for run in runs:
            best = next((item for item in run.evidence if item.relevance_level == "high"), None)
            if best is None and run.evidence:
                best = run.evidence[0]
            title = best.title if best else f"{run.topic} discussion"
            score = best.relevance_score if best else 0
            prefix = "真实 Reddit 热点" if mode == "live" else "mock 热点"
            level = relevance_label(best.relevance_level) if best else "暂无证据"
            lines.append(f"- **{run.topic}**：{prefix}为“{title}”，相关性：{level}（{score} 分）。")
    else:
        lines.append("- 暂未获得可用 Reddit 证据。mock 模式仍可用于验证报告流程。")

    lines.extend(["", "## 用户痛点", ""])
    for topic in topics:
        for pain in infer_pain_points(topic):
            lines.append(f"- **{topic}**：{pain}")

    lines.extend(["", "## 趋势判断", ""])
    for insight in trend_insights(topics):
        lines.append(f"- {insight}")

    lines.extend(["", "## 内容选题", ""])
    for idea in content_ideas(topics):
        lines.append(f"- {idea}")

    lines.extend(["", "## 小工具灵感", ""])
    for idea in tool_ideas():
        lines.append(f"- {idea}")

    lines.extend(["", "## 高相关内容", ""])
    append_evidence_table(lines, high_evidence)

    lines.extend(["", "## 边缘相关内容", ""])
    append_evidence_table(lines, edge_evidence)

    lines.extend(["", "## 跑偏样本", ""])
    if low_evidence:
        lines.append("> 这些内容不应直接作为陶瓷趋势结论，只用于观察关键词误伤和后续过滤优化。")
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
    script_path = Path(args.last30days_script).expanduser().resolve()
    prompt_path = DEFAULT_PROMPT_PATH

    config = load_config(topics_path)
    topics = load_topics(topics_path)
    relevance_config = load_relevance_config(config)
    prompt_template = prompt_path.read_text(encoding="utf-8")
    connectivity_note = ""
    if args.mode == "live":
        ok, connectivity_note = check_reddit_connectivity()
        if not ok:
            print(connectivity_note, file=sys.stderr)

    runs: list[TopicRun] = []
    for topic in topics:
        try:
            if args.mode == "live":
                report = run_last30days_live(
                    topic,
                    script_path,
                    recommended_subreddits=relevance_config.recommended_subreddits,
                )
            else:
                report = run_last30days_mock(topic, script_path)
            report = apply_relevance_ranking(report, relevance_config)
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_report(
            runs,
            prompt_template,
            mode=args.mode,
            connectivity_note=connectivity_note,
        ),
        encoding="utf-8",
    )
    print(f"Generated {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
