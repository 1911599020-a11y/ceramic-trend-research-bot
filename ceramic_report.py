#!/usr/bin/env python3
"""V0.1 local wrapper for ceramic trend research reports.

This script intentionally runs last30days-skill in mock mode for now. The
function boundaries are kept small so live Reddit/YouTube search can replace
the mock call later without changing the report renderer.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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


@dataclass(frozen=True)
class Evidence:
    topic: str
    source: str
    title: str
    url: str
    snippet: str
    engagement: str


@dataclass(frozen=True)
class TopicRun:
    topic: str
    report: dict[str, Any]
    evidence: list[Evidence]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Chinese ceramic trend intelligence report."
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "live"],
        default="mock",
        help="Run mode. V0.1 implements mock only; live is reserved.",
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


def load_topics(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Topic config not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        topics = payload
    else:
        topics = payload.get("topics", [])
    cleaned = [str(topic).strip() for topic in topics if str(topic).strip()]
    if not cleaned:
        raise ValueError(f"No topics found in {path}")
    return cleaned


def build_mock_plan(topic: str) -> dict[str, Any]:
    return {
        "intent": "opinion",
        "freshness_mode": "balanced_recent",
        "cluster_mode": "debate",
        "source_weights": {"reddit": 1.0, "youtube": 0.9},
        "subqueries": [
            {
                "label": "community discussion",
                "search_query": topic,
                "ranking_query": (
                    "What are makers, collectors, and viewers saying about "
                    f"{topic}, including trends, pain points, workflows, and content ideas?"
                ),
                "sources": ["reddit", "youtube"],
                "weight": 1.0,
            }
        ],
        "notes": ["ceramic-trend-research-bot V0.1 mock plan"],
    }


def run_last30days_mock(topic: str, script_path: Path) -> dict[str, Any]:
    if not script_path.exists():
        raise FileNotFoundError(f"last30days.py not found: {script_path}")

    command = [
        sys.executable,
        str(script_path),
        topic,
        "--mock",
        "--quick",
        "--emit=json",
        "--search=reddit,youtube",
        "--plan",
        json.dumps(build_mock_plan(topic), ensure_ascii=False),
    ]
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
            "last30days mock run failed\n"
            f"topic: {topic}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return extract_json(result.stdout)


def extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON payload found in last30days output:\n{stdout}")
    return json.loads(stdout[start : end + 1])


def collect_evidence(topic: str, report: dict[str, Any]) -> list[Evidence]:
    evidence: list[Evidence] = []
    for source, items in (report.get("items_by_source") or {}).items():
        for item in items[:3]:
            evidence.append(
                Evidence(
                    topic=topic,
                    source=source,
                    title=item.get("title") or "(untitled)",
                    url=item.get("url") or "",
                    snippet=item.get("snippet") or item.get("body") or "",
                    engagement=format_engagement(item.get("engagement") or {}),
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


def render_report(runs: list[TopicRun], prompt_template: str) -> str:
    topics = [run.topic for run in runs]
    all_evidence = [item for run in runs for item in run.evidence]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# 陶瓷趋势情报报告",
        "",
        f"- 生成时间：{generated_at}",
        "- 版本：V0.1 mock 本地报告",
        "- 数据模式：last30days-skill `--mock --quick`",
        f"- 关键词数量：{len(topics)}",
        "",
        "> 说明：当前报告使用 mock 数据验证流程与版式，不代表真实社媒趋势。下一阶段接入 live 模式后，将替换为 Reddit、YouTube 等真实来源。",
        "",
        "## 热门内容",
        "",
    ]

    for run in runs:
        top_cluster = (run.report.get("clusters") or [{}])[0]
        title = top_cluster.get("title") or f"{run.topic} discussion"
        score = top_cluster.get("score", 0)
        lines.append(f"- **{run.topic}**：mock 热点为“{title}”，综合分约 {score:.0f}。")

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

    lines.extend(["", "## 原始证据/链接", ""])
    if all_evidence:
        lines.extend(["| 关键词 | 来源 | 标题 | 互动 | 链接 |", "|---|---|---|---|---|"])
        for item in all_evidence:
            source = item.source.capitalize()
            link = f"[打开]({item.url})" if item.url else "n/a"
            lines.append(
                f"| {escape_cell(item.topic)} | {escape_cell(source)} | "
                f"{escape_cell(item.title)} | {escape_cell(item.engagement)} | {link} |"
            )
    else:
        lines.append("- 暂无证据。")

    lines.extend(
        [
            "",
            "## 后续升级接口",
            "",
            "- `--mode live` 已预留，下一阶段会移除 `--mock` 并接入真实 Reddit / YouTube 数据源。",
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


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def main() -> int:
    args = parse_args()
    if args.mode == "live":
        raise SystemExit("live mode is reserved for the next phase; run with --mode mock for V0.1.")

    topics_path = Path(args.topics).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    script_path = Path(args.last30days_script).expanduser().resolve()
    prompt_path = DEFAULT_PROMPT_PATH

    topics = load_topics(topics_path)
    prompt_template = prompt_path.read_text(encoding="utf-8")

    runs: list[TopicRun] = []
    for topic in topics:
        report = run_last30days_mock(topic, script_path)
        runs.append(TopicRun(topic=topic, report=report, evidence=collect_evidence(topic, report)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(runs, prompt_template), encoding="utf-8")
    print(f"Generated {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
