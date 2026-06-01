#!/usr/bin/env python3
"""Compare recent archived ceramic trend reports."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_DIR = PROJECT_ROOT / "reports" / "archive"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "trend_diff.md"
DEFAULT_TOPICS_PATH = PROJECT_ROOT / "config" / "ceramic_topics.json"


@dataclass(frozen=True)
class ParsedReport:
    path: Path
    high_count: int
    edge_count: int
    low_count: int
    summary_keywords: set[str]
    high_keywords: set[str]
    suggested_keywords: set[str]
    noise_keywords: set[str]

    @property
    def all_keywords(self) -> set[str]:
        return self.summary_keywords | self.high_keywords | self.suggested_keywords


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare latest archived ceramic reports.")
    parser.add_argument(
        "--archive-dir",
        default=str(DEFAULT_ARCHIVE_DIR),
        help="Directory containing archived live reports.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Markdown output path for the comparison report.",
    )
    parser.add_argument(
        "--topics",
        default=str(DEFAULT_TOPICS_PATH),
        help="Topic config used to identify known ceramic keywords.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_dir = Path(args.archive_dir).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    topics = load_topics(Path(args.topics).expanduser().resolve())
    archives = sorted(archive_dir.glob("*_report.md"))

    if len(archives) < 2:
        write_report(
            output_path,
            render_insufficient_report(archive_dir, archives),
        )
        print(
            "archive 不足两份，已生成样本不足说明："
            f"{display_path(output_path)}"
        )
        return 0

    previous_path, latest_path = archives[-2], archives[-1]
    previous = parse_report(previous_path, topics)
    latest = parse_report(latest_path, topics)
    write_report(
        output_path,
        render_comparison(previous, latest, archive_count=len(archives)),
    )
    print(f"已生成 {display_path(output_path)}")
    return 0


def load_topics(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [str(item).strip() for item in payload if str(item).strip()]
    topics = payload.get("topics", []) if isinstance(payload, dict) else []
    return [str(item).strip() for item in topics if str(item).strip()]


def parse_report(path: Path, topics: list[str]) -> ParsedReport:
    text = path.read_text(encoding="utf-8")
    high_count, edge_count, low_count = parse_counts(text)
    summary_text = extract_section(text, "本轮结论摘要")
    high_section = extract_section(text, "高相关内容")
    suggestions_section = extract_section(text, "下一轮搜索建议")
    low_section = extract_section(text, "跑偏样本")
    return ParsedReport(
        path=path,
        high_count=high_count,
        edge_count=edge_count,
        low_count=low_count,
        summary_keywords=extract_known_keywords(summary_text, topics),
        high_keywords=extract_table_keywords(high_section),
        suggested_keywords=extract_suggestion_keywords(suggestions_section, topics),
        noise_keywords=extract_noise_keywords(low_section),
    )


def parse_counts(text: str) -> tuple[int, int, int]:
    match = re.search(
        r"相关性分层：高相关\s*(\d+)\s*条，边缘相关\s*(\d+)\s*条，跑偏样本\s*(\d+)\s*条",
        text,
    )
    if not match:
        return 0, 0, 0
    return tuple(int(value) for value in match.groups())


def extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def extract_known_keywords(text: str, topics: list[str]) -> set[str]:
    keywords = set()
    lowered = text.lower()
    for topic in topics:
        if topic.lower() in lowered:
            keywords.add(topic)
    fallback_terms = [
        "AI ceramic design",
        "ceramic business",
        "ceramic glaze",
        "kiln firing",
        "3D printed ceramics",
        "handmade pottery",
    ]
    for term in fallback_terms:
        if term.lower() in lowered:
            keywords.add(term)
    return keywords


def extract_table_keywords(section: str) -> set[str]:
    keywords = set()
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0] in {"关键词", "相关性"}:
            continue
        keyword_cell = cells[1] if cells[0] in {"高相关", "边缘相关", "相关性较低"} and len(cells) > 1 else cells[0]
        if keyword_cell and keyword_cell.lower() != "n/a":
            keywords.add(keyword_cell)
    return keywords


def extract_suggestion_keywords(section: str, topics: list[str]) -> set[str]:
    keywords = set()
    for match in re.findall(r"\*\*(.+?)\*\*", section):
        cleaned = match.strip()
        if cleaned:
            keywords.add(cleaned)
    for match in re.findall(r"`([^`]+)`", section):
        cleaned = match.strip()
        if cleaned:
            keywords.add(cleaned)
    keywords.update(extract_known_keywords(section, topics))
    return keywords


def extract_noise_keywords(section: str) -> set[str]:
    lowered = section.lower()
    noise_terms = [
        "anime",
        "cosplay",
        "cats",
        "cat",
        "gaming",
        "fivenightsatfreddys",
        "fnaf",
        "makati",
        "keyboards",
        "naruto",
        "outfit",
    ]
    return {term for term in noise_terms if term in lowered}


def render_insufficient_report(archive_dir: Path, archives: list[Path]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 陶瓷趋势报告对比",
        "",
        f"- 生成时间：{generated_at}",
        f"- archive 目录：{display_path(archive_dir)}",
        f"- 已发现历史成功 live 报告：{len(archives)} 份",
        "",
        "## 对比对象",
        "",
        "- 上一期报告文件：暂无",
        "- 最新一期报告文件：暂无" if not archives else f"- 最新一期报告文件：{display_path(archives[-1])}",
        "",
        "## 数量变化",
        "",
        "- 高相关数量变化：暂无可比数据",
        "- 边缘相关数量变化：暂无可比数据",
        "- 跑偏样本数量变化：暂无可比数据",
        "",
        "## 关键词变化",
        "",
        "- 新出现的关键词：暂无可比数据",
        "- 持续出现的关键词：暂无可比数据",
        "- 消失的关键词：暂无可比数据",
        "",
        "## 观察结论",
        "",
        "- 当前 archive 样本不足，不适合做强趋势判断。至少需要两份成功 live 归档报告后，才能做基础对比。",
        "- mock 报告不会进入 archive，因此不会污染历史真实数据。",
        "",
        "## 下一步建议",
        "",
        "- 先跑通一次真实 live，让系统生成 `reports/latest.md` 和一份 archive 报告。",
        "- 等有两份成功 live archive 后，再运行 `bash scripts/compare_reports.sh`。",
        "- 如果只是调整报告结构，继续使用 `bash scripts/run_mock.sh`。",
        "",
    ]
    return "\n".join(lines)


def render_comparison(previous: ParsedReport, latest: ParsedReport, *, archive_count: int) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_keywords = latest.all_keywords - previous.all_keywords
    continued_keywords = latest.all_keywords & previous.all_keywords
    disappeared_keywords = previous.all_keywords - latest.all_keywords
    strengthen = (latest.high_keywords | new_keywords | latest.suggested_keywords) - latest.noise_keywords
    reduce_noise = latest.noise_keywords | disappeared_keywords

    lines = [
        "# 陶瓷趋势报告对比",
        "",
        f"- 生成时间：{generated_at}",
        f"- archive 样本数：{archive_count}",
        "",
        "## 对比对象",
        "",
        f"- 上一期报告文件：{display_path(previous.path)}",
        f"- 最新一期报告文件：{display_path(latest.path)}",
        "",
        "## 数量变化",
        "",
        f"- 高相关数量变化：{previous.high_count} -> {latest.high_count}（{format_delta(latest.high_count - previous.high_count)}）",
        f"- 边缘相关数量变化：{previous.edge_count} -> {latest.edge_count}（{format_delta(latest.edge_count - previous.edge_count)}）",
        f"- 跑偏样本数量变化：{previous.low_count} -> {latest.low_count}（{format_delta(latest.low_count - previous.low_count)}）",
        "",
        "## 关键词变化",
        "",
        f"- 新出现的关键词：{format_keywords(new_keywords)}",
        f"- 持续出现的关键词：{format_keywords(continued_keywords)}",
        f"- 消失的关键词：{format_keywords(disappeared_keywords)}",
        "",
        "## 观察结论",
        "",
    ]
    lines.extend(render_observations(previous, latest, new_keywords, continued_keywords, disappeared_keywords, archive_count))
    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
            f"- 建议下轮加强这些关键词：{format_keywords(strengthen)}",
            f"- 建议下轮降低这些噪音关键词：{format_keywords(reduce_noise)}",
            "- 如果 Reddit live 继续失败，不要用失败报告做趋势对比；先修网络或代理，再积累成功 archive。",
            "",
        ]
    )
    return "\n".join(lines)


def render_observations(
    previous: ParsedReport,
    latest: ParsedReport,
    new_keywords: set[str],
    continued_keywords: set[str],
    disappeared_keywords: set[str],
    archive_count: int,
) -> list[str]:
    lines = []
    if archive_count < 3:
        lines.append("- 当前 archive 样本不足，不适合做强趋势判断；本报告只做最近两期的基础变化提示。")
    if latest.high_count > previous.high_count:
        lines.append("- 高相关证据数量上升，说明最新一期 Reddit 抓取结果更适合提炼内容和工具线索。")
    elif latest.high_count < previous.high_count:
        lines.append("- 高相关证据数量下降，下一轮应优先检查关键词是否过宽、网络是否稳定、subreddit 是否需要收窄。")
    else:
        lines.append("- 高相关证据数量持平，建议继续观察持续出现的关键词。")
    if continued_keywords:
        lines.append(f"- 持续出现的方向可能值得继续追踪：{format_keywords(continued_keywords)}。")
    if new_keywords:
        lines.append(f"- 新出现的方向可以进入下一轮观察清单：{format_keywords(new_keywords)}。")
    if latest.low_count > previous.low_count:
        lines.append("- 跑偏样本增加，说明下一轮需要强化排除词或收窄搜索语境。")
    if disappeared_keywords:
        lines.append(f"- 消失的关键词可能只是短期信号或本轮未抓到：{format_keywords(disappeared_keywords)}。")
    return lines


def format_delta(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def format_keywords(keywords: set[str]) -> str:
    if not keywords:
        return "暂无"
    return "、".join(sorted(keywords, key=str.lower))


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
