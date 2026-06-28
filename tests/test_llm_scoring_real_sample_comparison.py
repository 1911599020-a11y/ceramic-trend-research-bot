from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scoring.llm_scorer import LLMScoringInput, LLMScoringResult


def load_real_comparison_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "compare_real_llm_scoring.py"
    spec = importlib.util.spec_from_file_location("compare_real_llm_scoring", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LLMScoringRealSampleComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_real_comparison_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.state_file = root / "state.json"
        self.output_file = root / "real_comparison.md"
        self.json_file = root / "real_comparison.json"
        self.error_file = root / "error.md"
        self.report_file = root / "report.md"
        self.latest_file = root / "latest.md"
        self.archive_dir = root / "archive"

    def args(self, *extra: str) -> list[str]:
        return [
            "--state-file",
            str(self.state_file),
            "--output",
            str(self.output_file),
            "--json-output",
            str(self.json_file),
            "--error-file",
            str(self.error_file),
            "--report-file",
            str(self.report_file),
            "--latest-file",
            str(self.latest_file),
            "--archive-dir",
            str(self.archive_dir),
            *extra,
        ]

    def run_main(self, argv: list[str], env: dict[str, str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = self.module.main(argv, env=env, allow_outside_local_outputs=True)
        return exit_code, output.getvalue()

    def read_state(self) -> dict[str, object]:
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def test_default_does_not_fetch_or_call_deepseek(self) -> None:
        with mock.patch.object(self.module, "fetch_real_samples") as fetch_real_samples:
            with mock.patch.object(self.module, "request_deepseek_score") as request_score:
                exit_code, text = self.run_main(
                    self.args(),
                    env={
                        "DEEPSEEK_API_KEY": "deepseek-secret",
                        "SCRAPECREATORS_API_KEY": "scrape-secret",
                    },
                )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertIn("未发起网络请求", text)
        self.assertEqual(state["status"], "not_confirmed")
        self.assertFalse(state["network_request_attempted"])
        fetch_real_samples.assert_not_called()
        request_score.assert_not_called()
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())

    def test_confirm_with_switch_off_does_not_fetch_or_call_deepseek(self) -> None:
        with mock.patch.object(self.module, "fetch_real_samples") as fetch_real_samples:
            with mock.patch.object(self.module, "request_deepseek_score") as request_score:
                exit_code, text = self.run_main(
                    self.args("--confirm-live-api"),
                    env={
                        "DEEPSEEK_API_KEY": "deepseek-secret",
                        "SCRAPECREATORS_API_KEY": "scrape-secret",
                    },
                )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "switch_off")
        self.assertFalse(state["network_request_attempted"])
        self.assertIn("保护机制已拦截", text)
        fetch_real_samples.assert_not_called()
        request_score.assert_not_called()

    def test_missing_scrapecreators_key_does_not_fetch(self) -> None:
        with mock.patch.object(self.module, "fetch_real_samples") as fetch_real_samples:
            with mock.patch.object(self.module, "request_deepseek_score") as request_score:
                exit_code, text = self.run_main(
                    self.args("--confirm-live-api"),
                    env={
                        "DEEPSEEK_API_KEY": "deepseek-secret",
                        "LLM_SCORING_ENABLED": "on",
                    },
                )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "missing_scrapecreators_key")
        self.assertFalse(state["network_request_attempted"])
        self.assertIn("missing_scrapecreators_key", text)
        fetch_real_samples.assert_not_called()
        request_score.assert_not_called()

    def test_success_writes_real_comparison_without_reports(self) -> None:
        samples = [
            LLMScoringInput(
                topic="kiln firing",
                title="Cone 6 glaze defects after firing",
                subreddit="r/Pottery",
                body="Electric kiln pinholes on stoneware.",
                url="https://example.com/1",
                rule_level="high",
                rule_score=8,
                rule_notes="命中 kiln、firing、glaze。",
            ),
            LLMScoringInput(
                topic="AI ceramic design",
                title="AI anime video with ceramic skin",
                subreddit="r/gaming",
                body="Not a pottery workflow.",
                url="https://example.com/2",
                rule_level="high",
                rule_score=6,
                rule_notes="规则命中 AI 和 ceramic。",
            ),
        ]
        results = [
            LLMScoringResult(
                ceramic_relevance="high",
                keyword_intent_match="high",
                evidence_type="pain_point",
                can_support_trend=True,
                is_noise=False,
                confidence=90,
                reason="真实陶瓷烧成问题。",
                provider="deepseek",
            ),
            LLMScoringResult(
                ceramic_relevance="low",
                keyword_intent_match="low",
                evidence_type="noise",
                can_support_trend=False,
                is_noise=True,
                confidence=88,
                reason="跑偏视频样本。",
                provider="deepseek",
            ),
        ]

        def fake_parse(_payload: object) -> LLMScoringResult:
            return results.pop(0)

        with mock.patch.object(self.module, "fetch_real_samples", return_value=(["kiln firing"], samples)) as fetch_real:
            with mock.patch.object(self.module, "request_deepseek_score", return_value=({}, 200)) as request_score:
                with mock.patch.object(self.module, "parse_deepseek_score_response", side_effect=fake_parse):
                    exit_code, text = self.run_main(
                        self.args("--confirm-live-api", "--sample-count", "2"),
                        env={
                            "DEEPSEEK_API_KEY": "deepseek-secret",
                            "SCRAPECREATORS_API_KEY": "scrape-secret",
                            "LLM_SCORING_ENABLED": "on",
                        },
                    )

        state = self.read_state()
        summary = json.loads(self.json_file.read_text(encoding="utf-8"))
        markdown = self.output_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "success")
        self.assertTrue(state["network_request_attempted"])
        self.assertFalse(state["report_files_updated"])
        self.assertEqual(summary["source_id"], "deepseek_real_sample_scoring_comparison")
        self.assertEqual(summary["counts"]["agree_high"], 1)
        self.assertEqual(summary["counts"]["llm_demoted"], 1)
        self.assertIn("真实 Reddit 小样本", markdown)
        self.assertIn("正式报告未更新", text)
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())
        fetch_real.assert_called_once()
        self.assertEqual(request_score.call_count, 2)

    def test_sample_selection_round_robins_topics_and_deduplicates(self) -> None:
        evidence = self.module.Evidence
        runs = [
            (
                "kiln firing",
                [
                    evidence("kiln firing", "reddit", "Kiln A", "https://example.com/a", "", "", "Pottery", "high", 9, ""),
                    evidence("kiln firing", "reddit", "Kiln B", "https://example.com/b", "", "", "Pottery", "high", 8, ""),
                ],
            ),
            (
                "ceramic business",
                [
                    evidence("ceramic business", "reddit", "Business A", "https://example.com/c", "", "", "Ceramics", "high", 8, ""),
                    evidence("ceramic business", "reddit", "Business A", "https://example.com/duplicate", "", "", "Ceramics", "high", 8, ""),
                    evidence("ceramic business", "reddit", "Business-A", "https://example.com/punct", "", "", "Ceramics", "high", 8, ""),
                    evidence("ceramic business", "reddit", "Business B", "https://example.com/d", "", "", "Ceramics", "high", 7, ""),
                ],
            ),
            (
                "AI ceramic design",
                [
                    evidence("AI ceramic design", "reddit", "AI A", "https://example.com/e", "", "", "Ceramics", "high", 8, ""),
                ],
            ),
        ]

        selected = self.module.select_evidence_samples(runs, sample_count=5, per_topic_limit=4)

        self.assertEqual(
            [(item.topic, item.title) for item in selected],
            [
                ("kiln firing", "Kiln A"),
                ("ceramic business", "Business A"),
                ("AI ceramic design", "AI A"),
                ("kiln firing", "Kiln B"),
                ("ceramic business", "Business B"),
            ],
        )

    def test_default_main_rejects_report_output_before_network(self) -> None:
        output = io.StringIO()
        with mock.patch.object(self.module, "fetch_real_samples") as fetch_real_samples:
            with mock.patch.object(self.module, "request_deepseek_score") as request_score:
                with redirect_stdout(output):
                    exit_code = self.module.main(
                        ["--output", "reports/report.md", "--confirm-live-api"],
                        env={
                            "DEEPSEEK_API_KEY": "deepseek-secret",
                            "SCRAPECREATORS_API_KEY": "scrape-secret",
                            "LLM_SCORING_ENABLED": "on",
                        },
                    )

        self.assertEqual(exit_code, 2)
        self.assertIn("输出路径不安全", output.getvalue())
        fetch_real_samples.assert_not_called()
        request_score.assert_not_called()


if __name__ == "__main__":
    unittest.main()
