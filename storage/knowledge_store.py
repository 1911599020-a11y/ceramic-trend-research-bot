"""Local knowledge store: remember scored evidence across runs.

V0.9.6 adds the "共同数据库" foundation: a SQLite file under data/ that
archives every successful run's scored items, so the bot stops forgetting
between runs. The store sits strictly AFTER report rendering:

- It never changes scoring, ranking, or report markdown output.
- Store failures must never break or overwrite the report flow; callers are
  expected to wrap :func:`save_run_to_store` in a guard.
- The report pipeline writes the ``reddit`` / ``youtube`` partitions;
  ``xiaohongshu`` and ``radar`` are reserved partitions for future manual
  importers and are not written by any current code.

The module is duck-typed on purpose: it reads ``topic`` / ``evidence``
attributes from the run objects and never imports ceramic_report, so a
broken import here can never take the report pipeline down with it.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "knowledge_store.json"

RESERVED_PLATFORMS = ("xiaohongshu", "radar")

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        mode TEXT NOT NULL,
        data_source TEXT NOT NULL,
        report_version TEXT NOT NULL,
        topics TEXT NOT NULL,
        high_count INTEGER NOT NULL DEFAULT 0,
        edge_count INTEGER NOT NULL DEFAULT 0,
        low_count INTEGER NOT NULL DEFAULT 0,
        item_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        topic TEXT NOT NULL,
        dedup_key TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL DEFAULT '',
        container TEXT NOT NULL DEFAULT '',
        snippet TEXT NOT NULL DEFAULT '',
        engagement TEXT NOT NULL DEFAULT '',
        latest_score INTEGER NOT NULL DEFAULT 0,
        latest_level TEXT NOT NULL DEFAULT '',
        latest_notes TEXT NOT NULL DEFAULT '',
        seen_count INTEGER NOT NULL DEFAULT 1,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        first_seen_run_id INTEGER NOT NULL,
        last_seen_run_id INTEGER NOT NULL,
        UNIQUE (platform, topic, dedup_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sightings (
        sighting_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        score INTEGER NOT NULL DEFAULT 0,
        level TEXT NOT NULL DEFAULT '',
        engagement TEXT NOT NULL DEFAULT '',
        seen_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_items_platform ON items (platform)",
    "CREATE INDEX IF NOT EXISTS idx_items_topic ON items (topic)",
    "CREATE INDEX IF NOT EXISTS idx_sightings_item ON sightings (item_id)",
    "CREATE INDEX IF NOT EXISTS idx_sightings_run ON sightings (run_id)",
)


@dataclass(frozen=True)
class KnowledgeStoreConfig:
    enabled: bool
    switch_env_var: str
    enabled_values: frozenset[str]
    disabled_values: frozenset[str]
    db_path: str
    allowed_db_root: str
    platforms: tuple[str, ...]


def load_knowledge_store_config(path: Path = DEFAULT_CONFIG_PATH) -> KnowledgeStoreConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return KnowledgeStoreConfig(
        enabled=bool(payload.get("enabled", True)),
        switch_env_var=str(payload.get("switch_env_var", "KNOWLEDGE_STORE_ENABLED")).strip()
        or "KNOWLEDGE_STORE_ENABLED",
        enabled_values=frozenset(
            str(value).strip().lower()
            for value in payload.get("enabled_values", ["on", "true", "1", "yes"])
            if str(value).strip()
        ),
        disabled_values=frozenset(
            str(value).strip().lower()
            for value in payload.get("disabled_values", ["off", "false", "0", "no"])
            if str(value).strip()
        ),
        db_path=str(payload.get("db_path", "data/ceramic_knowledge.db")),
        allowed_db_root=str(payload.get("allowed_db_root", "data")).strip() or "data",
        platforms=tuple(
            str(value).strip().lower()
            for value in payload.get("platforms", [])
            if str(value).strip()
        ),
    )


def store_enabled(
    config: KnowledgeStoreConfig,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Config decides the default; the env switch always wins when set."""
    environ = os.environ if env is None else env
    raw = str(environ.get(config.switch_env_var, "")).strip().lower()
    if raw:
        if raw in config.disabled_values:
            return False
        if raw in config.enabled_values:
            return True
    return config.enabled


def resolve_db_path(
    config: KnowledgeStoreConfig,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    """Keep the database inside the allowed root, mirroring the
    local_outputs-style guardrails used elsewhere in this project."""
    candidate = Path(config.db_path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    candidate = candidate.resolve()
    allowed_root = (project_root / config.allowed_db_root).resolve()
    if allowed_root != candidate and allowed_root not in candidate.parents:
        raise ValueError(
            f"知识库路径不安全：db_path 必须位于 {config.allowed_db_root}/ 下，当前为 {config.db_path}"
        )
    return candidate


def display_db_path(db_path: Path, project_root: Path = PROJECT_ROOT) -> str:
    try:
        return db_path.relative_to(project_root).as_posix()
    except ValueError:
        return str(db_path)


def normalize_platform(value: str) -> str:
    key = str(value or "").strip().lower()
    return key or "unknown"


def evidence_record(evidence: Any) -> dict[str, Any]:
    """Duck-typed Evidence -> plain dict. Never imports ceramic_report."""
    title = str(getattr(evidence, "title", "") or "")
    url = str(getattr(evidence, "url", "") or "")
    return {
        "platform": normalize_platform(getattr(evidence, "source", "")),
        "topic": str(getattr(evidence, "topic", "") or ""),
        "title": title,
        "url": url,
        "container": str(getattr(evidence, "subreddit", "") or ""),
        "snippet": str(getattr(evidence, "snippet", "") or ""),
        "engagement": str(getattr(evidence, "engagement", "") or ""),
        "score": int(getattr(evidence, "relevance_score", 0) or 0),
        "level": str(getattr(evidence, "relevance_level", "") or ""),
        "notes": str(getattr(evidence, "relevance_notes", "") or ""),
        "dedup_key": url or f"title::{title}",
    }


def save_run_to_store(
    runs: Iterable[Any],
    *,
    mode: str,
    data_source: str,
    report_version: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> str:
    """Archive one successful run. Returns a status line, or '' when disabled.

    Runs are appended as-is; items are deduplicated per (platform, topic,
    dedup_key) so an item seen again in a later run raises its seen_count
    instead of creating a duplicate row. Every occurrence is also recorded in
    sightings, which is what makes cross-period comparison possible.
    """
    config = load_knowledge_store_config(config_path)
    if not store_enabled(config, env):
        return ""

    timestamp = (now or datetime.now()).isoformat(timespec="seconds")
    topics: list[str] = []
    records: list[dict[str, Any]] = []
    for run in runs:
        topic = str(getattr(run, "topic", "") or "")
        if topic:
            topics.append(topic)
        for evidence in getattr(run, "evidence", None) or []:
            records.append(evidence_record(evidence))

    counts = {"high": 0, "edge": 0, "low": 0}
    for record in records:
        if record["level"] in counts:
            counts[record["level"]] += 1

    db_path = resolve_db_path(config, project_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    new_count = 0
    reseen_count = 0
    connection = sqlite3.connect(db_path)
    try:
        with connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            cursor = connection.execute(
                "INSERT INTO runs (started_at, mode, data_source, report_version,"
                " topics, high_count, edge_count, low_count, item_count)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    timestamp,
                    str(mode),
                    str(data_source),
                    str(report_version),
                    json.dumps(topics, ensure_ascii=False),
                    counts["high"],
                    counts["edge"],
                    counts["low"],
                    len(records),
                ),
            )
            run_id = cursor.lastrowid
            for record in records:
                row = connection.execute(
                    "SELECT item_id FROM items"
                    " WHERE platform = ? AND topic = ? AND dedup_key = ?",
                    (record["platform"], record["topic"], record["dedup_key"]),
                ).fetchone()
                if row is None:
                    cursor = connection.execute(
                        "INSERT INTO items (platform, topic, dedup_key, title, url,"
                        " container, snippet, engagement, latest_score, latest_level,"
                        " latest_notes, seen_count, first_seen_at, last_seen_at,"
                        " first_seen_run_id, last_seen_run_id)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)",
                        (
                            record["platform"],
                            record["topic"],
                            record["dedup_key"],
                            record["title"],
                            record["url"],
                            record["container"],
                            record["snippet"],
                            record["engagement"],
                            record["score"],
                            record["level"],
                            record["notes"],
                            timestamp,
                            timestamp,
                            run_id,
                            run_id,
                        ),
                    )
                    item_id = cursor.lastrowid
                    new_count += 1
                else:
                    item_id = row[0]
                    connection.execute(
                        "UPDATE items SET title = ?, snippet = ?, engagement = ?,"
                        " latest_score = ?, latest_level = ?, latest_notes = ?,"
                        " seen_count = seen_count + 1, last_seen_at = ?,"
                        " last_seen_run_id = ? WHERE item_id = ?",
                        (
                            record["title"],
                            record["snippet"],
                            record["engagement"],
                            record["score"],
                            record["level"],
                            record["notes"],
                            timestamp,
                            run_id,
                            item_id,
                        ),
                    )
                    reseen_count += 1
                connection.execute(
                    "INSERT INTO sightings (run_id, item_id, score, level,"
                    " engagement, seen_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        item_id,
                        record["score"],
                        record["level"],
                        record["engagement"],
                        timestamp,
                    ),
                )
    finally:
        connection.close()

    location = display_db_path(db_path, project_root)
    if not records:
        return f"知识库已记录本轮运行档案（本轮无可入库证据），数据库：{location}"
    return (
        f"知识库已记录本轮：新增 {new_count} 条、重逢 {reseen_count} 条，"
        f"数据库：{location}"
    )


def open_store(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def store_overview(db_path: Path) -> dict[str, Any]:
    connection = open_store(db_path)
    try:
        run_row = connection.execute(
            "SELECT COUNT(*) AS run_count, MIN(started_at) AS first_run,"
            " MAX(started_at) AS last_run FROM runs"
        ).fetchone()
        platform_rows = connection.execute(
            "SELECT platform, COUNT(*) AS item_count FROM items GROUP BY platform"
        ).fetchall()
        level_rows = connection.execute(
            "SELECT latest_level, COUNT(*) AS item_count FROM items GROUP BY latest_level"
        ).fetchall()
        item_count = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        repeat_count = connection.execute(
            "SELECT COUNT(*) FROM items WHERE seen_count > 1"
        ).fetchone()[0]
    finally:
        connection.close()
    return {
        "run_count": run_row["run_count"],
        "first_run": run_row["first_run"],
        "last_run": run_row["last_run"],
        "item_count": item_count,
        "repeat_count": repeat_count,
        "platforms": {row["platform"]: row["item_count"] for row in platform_rows},
        "levels": {row["latest_level"]: row["item_count"] for row in level_rows},
    }


def repeat_items(db_path: Path, limit: int = 10) -> list[dict[str, Any]]:
    connection = open_store(db_path)
    try:
        rows = connection.execute(
            "SELECT platform, topic, title, url, seen_count, latest_level,"
            " latest_score, first_seen_at, last_seen_at FROM items"
            " WHERE seen_count > 1"
            " ORDER BY seen_count DESC, latest_score DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def topic_items(db_path: Path, topic: str, limit: int = 20) -> list[dict[str, Any]]:
    connection = open_store(db_path)
    try:
        rows = connection.execute(
            "SELECT platform, topic, title, url, seen_count, latest_level,"
            " latest_score, latest_notes, first_seen_at, last_seen_at FROM items"
            " WHERE topic = ?"
            " ORDER BY latest_score DESC, seen_count DESC LIMIT ?",
            (str(topic), int(limit)),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def list_runs(db_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    connection = open_store(db_path)
    try:
        rows = connection.execute(
            "SELECT run_id, started_at, mode, data_source, report_version, topics,"
            " high_count, edge_count, low_count, item_count FROM runs"
            " ORDER BY run_id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]
