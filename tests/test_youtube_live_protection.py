from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ceramic_report


class FakeSource:
    def __init__(self, report: dict[str, object] | None = None, error: str = "") -> None:
        self.report = report or {}
        self.error = error

    def fetch(self, topic: str, *, recommended_subreddits=None) -> dict[str, object]:
        if self.error:
            raise RuntimeError(self.error)
        return self.report


def deepseek_response(payload: dict[str, object]) -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            }
        ]
    }


class YouTubeLiveProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)
        self.topics_path = self.root / "topics.json"
        self.output_path = self.root / "report.md"
        self.latest_path = self.root / "latest.md"
        self.archive_dir = self.root / "archive"
        self.state_path = self.root / "state.json"
        self.error_path = self.root / "youtube_live_error.md"
        self.topics_path.write_text(
            json.dumps(
                {
                    "topics": ["ceramic glaze"],
                    "recommended_subreddits": [],
                    "relevance": {
                        "positive_terms": ["ceramic", "glaze", "clay", "kiln"],
                        "exclude_terms": ["anime", "gaming", "cosplay"],
                    },
                    "topic_rules": {
                        "ceramic glaze": {
                            "required_terms": ["glaze"],
                            "boost_terms": ["cone", "kiln"],
                            "exclude_terms": [],
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def argv(self) -> list[str]:
        return [
            "ceramic_report.py",
            "--mode",
            "live",
            "--data-source",
            "scrapecreators_youtube_search",
            "--topics",
            str(self.topics_path),
            "--output",
            str(self.output_path),
            "--latest",
            str(self.latest_path),
            "--archive-dir",
            str(self.archive_dir),
            "--state-file",
            str(self.state_path),
            "--error-file",
            str(self.error_path),
            "--cooldown-minutes",
            "0",
            "--no-research-evidence",
        ]

    def run_main_with_source(
        self,
        source: FakeSource,
        *,
        env: dict[str, str] | None = None,
    ) -> int:
        # 知识库开关关闭：单测不得写入真实 data/ceramic_knowledge.db
        values = {"KNOWLEDGE_STORE_ENABLED": "off", "LLM_SCORING_ENABLED": "off"}
        if env:
            values.update(env)
        with mock.patch.dict("os.environ", values):
            with mock.patch.object(sys, "argv", self.argv()):
                with mock.patch("ceramic_report.build_trend_source", return_value=source):
                    return ceramic_report.main()

    def seed_previous_reports(self) -> None:
        self.output_path.write_text("previous report\n", encoding="utf-8")
        self.latest_path.write_text("previous latest\n", encoding="utf-8")

    def assert_previous_reports_preserved(self) -> None:
        self.assertEqual(self.output_path.read_text(encoding="utf-8"), "previous report\n")
        self.assertEqual(self.latest_path.read_text(encoding="utf-8"), "previous latest\n")
        self.assertFalse(self.archive_dir.exists())

    def youtube_report(self, items: list[dict[str, object]]) -> dict[str, object]:
        return {
            "topic": "ceramic glaze",
            "items_by_source": {"youtube": items},
            "metadata": {"source_id": "scrapecreators_youtube_search"},
        }

    def test_api_errors_do_not_overwrite_reports(self) -> None:
        for error_type in ["missing_key", "forbidden_403", "rate_limited_429", "parse_error"]:
            with self.subTest(error_type=error_type):
                self.seed_previous_reports()
                exit_code = self.run_main_with_source(FakeSource(error=f"{error_type}: simulated"))

                self.assertEqual(exit_code, 0)
                self.assert_previous_reports_preserved()
                self.assertTrue(self.error_path.exists())
                error_text = self.error_path.read_text(encoding="utf-8")
                self.assertIn(error_type, error_text)
                self.assertIn("未覆盖", error_text)
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
                self.assertEqual(state["status"], "failed" if error_type != "rate_limited_429" else "rate_limited")
                self.assertEqual(state["error_type"], error_type)
                self.error_path.unlink(missing_ok=True)
                self.state_path.unlink(missing_ok=True)
                self.output_path.unlink(missing_ok=True)
                self.latest_path.unlink(missing_ok=True)

    def test_live_failure_does_not_call_deepseek_review(self) -> None:
        self.seed_previous_reports()
        with mock.patch.dict(
            "os.environ",
            {"LLM_SCORING_ENABLED": "on", "DEEPSEEK_API_KEY": "secret-token"},
        ):
            with mock.patch("ceramic_report.request_deepseek_score") as request:
                exit_code = self.run_main_with_source(
                    FakeSource(error="network_error: simulated"),
                    env={"LLM_SCORING_ENABLED": "on", "DEEPSEEK_API_KEY": "secret-token"},
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(request.call_count, 0)
        self.assert_previous_reports_preserved()

    def test_empty_youtube_results_do_not_overwrite_reports(self) -> None:
        self.seed_previous_reports()
        exit_code = self.run_main_with_source(FakeSource(report=self.youtube_report([])))

        self.assertEqual(exit_code, 0)
        self.assert_previous_reports_preserved()
        error_text = self.error_path.read_text(encoding="utf-8")
        self.assertIn("no_usable_evidence", error_text)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["error_type"], "no_usable_evidence")

    def test_all_low_youtube_results_do_not_overwrite_reports(self) -> None:
        self.seed_previous_reports()
        low_item = {
            "title": "Naruto gaming cosplay compilation",
            "snippet": "not pottery",
            "container": "Anime Channel",
            "url": "https://www.youtube.com/watch?v=noise",
            "engagement": {"views": "10,000 views"},
            "metadata": {"platform": "youtube"},
        }
        exit_code = self.run_main_with_source(FakeSource(report=self.youtube_report([low_item])))

        self.assertEqual(exit_code, 0)
        self.assert_previous_reports_preserved()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["usable_evidence_count"], 0)
        self.assertEqual(state["low_relevance_count"], 1)
        self.assertEqual(state["error_type"], "no_usable_evidence")

    def test_high_youtube_result_updates_success_outputs(self) -> None:
        high_item = {
            "title": "Cone 6 ceramic glaze tests",
            "snippet": "ceramic glaze clay kiln results",
            "container": "Clay Studio",
            "url": "https://www.youtube.com/watch?v=abc123",
            "engagement": {"views": "2,000 views"},
            "metadata": {"platform": "youtube"},
        }
        exit_code = self.run_main_with_source(FakeSource(report=self.youtube_report([high_item])))

        self.assertEqual(exit_code, 0)
        self.assertTrue(self.output_path.exists())
        self.assertTrue(self.latest_path.exists())
        archives = sorted(self.archive_dir.glob("*_report.md"))
        self.assertEqual(len(archives), 1)
        text = self.output_path.read_text(encoding="utf-8")
        self.assertIn("Cone 6 ceramic glaze tests", text)
        self.assertIn("YouTube", text)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "success")
        self.assertEqual(state["usable_evidence_count"], 1)

    def test_successful_live_can_include_deepseek_review(self) -> None:
        high_item = {
            "title": "Cone 6 ceramic glaze tests",
            "snippet": "ceramic glaze clay kiln results",
            "container": "Clay Studio",
            "url": "https://www.youtube.com/watch?v=abc123",
            "engagement": {"views": "2,000 views"},
            "metadata": {"platform": "youtube"},
        }
        payload = deepseek_response(
            {
                "ceramic_relevance": "high",
                "keyword_intent_match": "high",
                "evidence_type": "trend_signal",
                "can_support_trend": True,
                "is_noise": False,
                "confidence": 88,
                "reason": "YouTube 标题和摘要都指向陶瓷釉料测试。",
            }
        )
        with mock.patch.dict(
            "os.environ",
            {"LLM_SCORING_ENABLED": "on", "DEEPSEEK_API_KEY": "secret-token"},
        ):
            with mock.patch("ceramic_report.request_deepseek_score", return_value=(payload, 200)) as request:
                exit_code = self.run_main_with_source(
                    FakeSource(report=self.youtube_report([high_item])),
                    env={"LLM_SCORING_ENABLED": "on", "DEEPSEEK_API_KEY": "secret-token"},
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(request.call_count, 1)
        text = self.output_path.read_text(encoding="utf-8")
        self.assertIn("## DeepSeek 语义质检", text)
        self.assertIn("YouTube 标题和摘要都指向陶瓷釉料测试", text)


if __name__ == "__main__":
    unittest.main()
