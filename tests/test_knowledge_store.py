from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from ceramic_report import Evidence, TopicRun
from storage.knowledge_store import (
    RESERVED_PLATFORMS,
    load_knowledge_store_config,
    resolve_db_path,
    save_run_to_store,
    store_enabled,
    store_overview,
)


def make_evidence(
    *,
    topic: str = "ceramic glaze",
    source: str = "reddit",
    title: str = "Glaze crawling on cone 6 mugs",
    url: str = "https://example.com/post/1",
    level: str = "high",
    score: int = 6,
) -> Evidence:
    return Evidence(
        topic=topic,
        source=source,
        title=title,
        url=url,
        snippet="channel: example",
        engagement="12 comments",
        subreddit="pottery",
        relevance_level=level,
        relevance_score=score,
        relevance_notes="命中陶瓷词",
    )


def make_config_file(tmp_root: Path, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "version": "V0.9.6",
        "enabled": True,
        "switch_env_var": "KNOWLEDGE_STORE_ENABLED",
        "enabled_values": ["on", "true", "1", "yes"],
        "disabled_values": ["off", "false", "0", "no"],
        "db_path": "data/test_knowledge.db",
        "allowed_db_root": "data",
        "platforms": ["reddit", "youtube", "xiaohongshu", "radar"],
    }
    payload.update(overrides)
    path = tmp_root / "knowledge_store.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class KnowledgeStoreConfigTests(unittest.TestCase):
    def test_repo_config_defaults_enabled_inside_data_dir(self) -> None:
        config = load_knowledge_store_config(Path("config/knowledge_store.json"))

        self.assertTrue(config.enabled)
        self.assertEqual(config.switch_env_var, "KNOWLEDGE_STORE_ENABLED")
        self.assertEqual(config.db_path, "data/ceramic_knowledge.db")
        self.assertEqual(config.allowed_db_root, "data")
        for reserved in RESERVED_PLATFORMS:
            self.assertIn(reserved, config.platforms)

    def test_env_switch_overrides_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            enabled_config = load_knowledge_store_config(make_config_file(tmp_root))
            disabled_config = load_knowledge_store_config(
                make_config_file(tmp_root, enabled=False)
            )

        self.assertFalse(store_enabled(enabled_config, {"KNOWLEDGE_STORE_ENABLED": "off"}))
        self.assertTrue(store_enabled(disabled_config, {"KNOWLEDGE_STORE_ENABLED": "on"}))
        self.assertTrue(store_enabled(enabled_config, {}))
        self.assertFalse(store_enabled(disabled_config, {}))

    def test_unsafe_db_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            config = load_knowledge_store_config(
                make_config_file(tmp_root, db_path="../outside.db")
            )
            with self.assertRaisesRegex(ValueError, "知识库路径不安全"):
                resolve_db_path(config, project_root=tmp_root)


class KnowledgeStoreSaveTests(unittest.TestCase):
    def save(
        self,
        runs: list[TopicRun],
        tmp_root: Path,
        config_path: Path,
        *,
        env: dict[str, str] | None = None,
        now: datetime | None = None,
    ) -> str:
        return save_run_to_store(
            runs,
            mode="mock",
            data_source="mock",
            report_version="V0.6.6",
            config_path=config_path,
            project_root=tmp_root,
            env={} if env is None else env,
            now=now or datetime(2026, 7, 2, 10, 0, 0),
        )

    def test_save_creates_schema_run_items_and_sightings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            config_path = make_config_file(tmp_root)
            runs = [
                TopicRun(
                    topic="ceramic glaze",
                    report={},
                    evidence=[
                        make_evidence(),
                        make_evidence(
                            source="youtube",
                            title="Kiln firing basics",
                            url="https://example.com/video/2",
                            level="edge",
                            score=3,
                        ),
                    ],
                )
            ]

            note = self.save(runs, tmp_root, config_path)
            db_path = tmp_root / "data" / "test_knowledge.db"
            self.assertTrue(db_path.exists())
            self.assertIn("新增 2 条", note)
            self.assertIn("重逢 0 条", note)

            connection = sqlite3.connect(db_path)
            try:
                run_row = connection.execute(
                    "SELECT mode, data_source, report_version, high_count,"
                    " edge_count, low_count, item_count FROM runs"
                ).fetchone()
                item_count = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
                sighting_count = connection.execute(
                    "SELECT COUNT(*) FROM sightings"
                ).fetchone()[0]
                platforms = {
                    row[0]
                    for row in connection.execute("SELECT platform FROM items").fetchall()
                }
            finally:
                connection.close()

        self.assertEqual(run_row, ("mock", "mock", "V0.6.6", 1, 1, 0, 2))
        self.assertEqual(item_count, 2)
        self.assertEqual(sighting_count, 2)
        self.assertEqual(platforms, {"reddit", "youtube"})

    def test_second_run_marks_items_as_reseen_instead_of_duplicating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            config_path = make_config_file(tmp_root)
            first = [TopicRun(topic="ceramic glaze", report={}, evidence=[make_evidence()])]
            second = [
                TopicRun(
                    topic="ceramic glaze",
                    report={},
                    evidence=[
                        make_evidence(score=7),
                        make_evidence(
                            title="Brand new pottery wheel question",
                            url="https://example.com/post/9",
                            level="edge",
                            score=2,
                        ),
                    ],
                )
            ]

            self.save(first, tmp_root, config_path, now=datetime(2026, 7, 1, 9, 0, 0))
            note = self.save(second, tmp_root, config_path, now=datetime(2026, 7, 2, 9, 0, 0))
            self.assertIn("新增 1 条", note)
            self.assertIn("重逢 1 条", note)

            db_path = tmp_root / "data" / "test_knowledge.db"
            connection = sqlite3.connect(db_path)
            try:
                seen_count, latest_score, first_seen, last_seen = connection.execute(
                    "SELECT seen_count, latest_score, first_seen_at, last_seen_at"
                    " FROM items WHERE url = ?",
                    ("https://example.com/post/1",),
                ).fetchone()
                item_count = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
                run_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            finally:
                connection.close()

            overview = store_overview(db_path)

        self.assertEqual(seen_count, 2)
        self.assertEqual(latest_score, 7)
        self.assertEqual(first_seen, "2026-07-01T09:00:00")
        self.assertEqual(last_seen, "2026-07-02T09:00:00")
        self.assertEqual(item_count, 2)
        self.assertEqual(run_count, 2)
        self.assertEqual(overview["run_count"], 2)
        self.assertEqual(overview["repeat_count"], 1)

    def test_disabled_store_writes_nothing_and_returns_empty_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            config_path = make_config_file(tmp_root)
            runs = [TopicRun(topic="ceramic glaze", report={}, evidence=[make_evidence()])]

            note = self.save(
                runs,
                tmp_root,
                config_path,
                env={"KNOWLEDGE_STORE_ENABLED": "off"},
            )

            self.assertEqual(note, "")
            self.assertFalse((tmp_root / "data" / "test_knowledge.db").exists())

    def test_run_without_evidence_is_still_archived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            config_path = make_config_file(tmp_root)
            runs = [TopicRun(topic="ceramic glaze", report={}, evidence=[])]

            note = self.save(runs, tmp_root, config_path)
            db_path = tmp_root / "data" / "test_knowledge.db"
            connection = sqlite3.connect(db_path)
            try:
                run_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                item_count = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            finally:
                connection.close()

        self.assertIn("无可入库证据", note)
        self.assertEqual(run_count, 1)
        self.assertEqual(item_count, 0)


if __name__ == "__main__":
    unittest.main()
