#!/usr/bin/env python3
"""Read-only CLI for the local knowledge store (共同数据库).

This script never writes anything. It opens data/ceramic_knowledge.db and
prints what the bot has remembered so far: runs, partitions, repeat items,
and per-topic history.

Usage:
    python scripts/query_knowledge.py             # 总览
    python scripts/query_knowledge.py --runs      # 各轮运行档案
    python scripts/query_knowledge.py --repeats   # 出现超过一次的“重逢”条目
    python scripts/query_knowledge.py --topic "ceramic glaze"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.knowledge_store import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    RESERVED_PLATFORMS,
    display_db_path,
    list_runs,
    load_knowledge_store_config,
    repeat_items,
    resolve_db_path,
    store_overview,
    topic_items,
)

LEVEL_LABELS = {"high": "高相关", "edge": "边缘相关", "low": "跑偏"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="查询本地知识库（只读，不写任何文件）。")
    parser.add_argument("--topic", default="", help="查看某个关键词下已归档的条目。")
    parser.add_argument("--repeats", action="store_true", help="查看出现超过一次的条目。")
    parser.add_argument("--runs", action="store_true", help="查看各轮运行档案。")
    parser.add_argument("--limit", type=int, default=10, help="列表条数上限（默认 10）。")
    return parser.parse_args()


def level_label(value: str) -> str:
    return LEVEL_LABELS.get(str(value), str(value) or "未知")


def print_overview(db_path: Path) -> None:
    overview = store_overview(db_path)
    config = load_knowledge_store_config(DEFAULT_CONFIG_PATH)
    print("# 知识库总览")
    print(f"- 数据库：{display_db_path(db_path)}")
    print(f"- 已归档运行：{overview['run_count']} 轮（{overview['first_run']} ～ {overview['last_run']}）")
    print(f"- 条目总数：{overview['item_count']}（其中出现超过一次的：{overview['repeat_count']} 条）")
    print("- 分区（抽屉）：")
    platforms = dict(overview["platforms"])
    known = list(config.platforms) or sorted(platforms)
    for platform in known:
        count = platforms.pop(platform, 0)
        suffix = "（预留，暂无写入）" if platform in RESERVED_PLATFORMS and count == 0 else ""
        print(f"  - {platform}: {count} 条{suffix}")
    for platform, count in sorted(platforms.items()):
        print(f"  - {platform}: {count} 条")
    if overview["levels"]:
        levels = "、".join(
            f"{level_label(level)} {count} 条"
            for level, count in sorted(overview["levels"].items())
        )
        print(f"- 相关性分布：{levels}")


def print_runs(db_path: Path, limit: int) -> None:
    print("# 运行档案（新→旧）")
    for run in list_runs(db_path, limit=limit):
        print(
            f"- 第 {run['run_id']} 轮 {run['started_at']}"
            f"｜mode={run['mode']}｜source={run['data_source']}"
            f"｜高 {run['high_count']} / 边缘 {run['edge_count']} / 跑偏 {run['low_count']}"
            f"｜共 {run['item_count']} 条"
        )


def print_repeats(db_path: Path, limit: int) -> None:
    rows = repeat_items(db_path, limit=limit)
    print("# 重逢条目（出现超过一次 = 机器人“记住了”）")
    if not rows:
        print("- 暂无：还没有条目在两轮运行中重复出现。")
        return
    for row in rows:
        print(
            f"- [{row['platform']}] {row['title'][:60]}"
            f"｜出现 {row['seen_count']} 次｜{level_label(row['latest_level'])}（{row['latest_score']} 分）"
            f"｜首次 {row['first_seen_at']} → 最近 {row['last_seen_at']}"
        )


def print_topic(db_path: Path, topic: str, limit: int) -> None:
    rows = topic_items(db_path, topic, limit=limit)
    print(f"# 关键词「{topic}」的归档条目")
    if not rows:
        print("- 暂无该关键词的归档条目。")
        return
    for row in rows:
        print(
            f"- [{row['platform']}] {row['title'][:60]}"
            f"｜{level_label(row['latest_level'])}（{row['latest_score']} 分）"
            f"｜出现 {row['seen_count']} 次"
        )


def main() -> int:
    args = parse_args()
    config = load_knowledge_store_config(DEFAULT_CONFIG_PATH)
    db_path = resolve_db_path(config)
    if not db_path.exists():
        print("知识库还没建立：先跑一次报告（mock 或 live 均可），成功后会自动创建。")
        print(f"预期位置：{display_db_path(db_path)}")
        return 0
    if args.topic:
        print_topic(db_path, args.topic, args.limit)
        return 0
    if args.repeats:
        print_repeats(db_path, args.limit)
        return 0
    if args.runs:
        print_runs(db_path, args.limit)
        return 0
    print_overview(db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
