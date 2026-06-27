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

from scoring.llm_scorer import LLMScoringResult


def load_comparison_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "compare_llm_scoring.py"
    spec = importlib.util.spec_from_file_location("compare_llm_scoring", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LLMScoringComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_comparison_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.state_file = root / "state.json"
        self.output_file = root / "comparison.md"
        self.json_file = root / "comparison.json"
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

    def test_default_does_not_call_network_or_reports(self) -> None:
        with mock.patch.object(self.module, "request_deepseek_score") as request_score:
            exit_code, text = self.run_main(
                self.args(),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertIn("未发起网络请求", text)
        self.assertEqual(state["status"], "not_confirmed")
        self.assertFalse(state["network_request_attempted"])
        request_score.assert_not_called()
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())

    def test_confirm_with_switch_off_does_not_call_network(self) -> None:
        with mock.patch.object(self.module, "request_deepseek_score") as request_score:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api"),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "switch_off")
        self.assertFalse(state["network_request_attempted"])
        self.assertIn("开关未开启", text)
        request_score.assert_not_called()

    def test_cli_rejects_output_paths_outside_local_outputs(self) -> None:
        defaults = {
            "--state-file": "local_outputs/llm_scoring_comparison_state.json",
            "--output": "local_outputs/llm_scoring_comparison.md",
            "--json-output": "local_outputs/llm_scoring_comparison.json",
            "--error-file": "local_outputs/llm_scoring_comparison_error.md",
        }
        outside_paths = {
            "--state-file": str(self.state_file),
            "--output": str(self.output_file),
            "--json-output": str(self.json_file),
            "--error-file": str(self.error_file),
        }
        for flag, outside_path in outside_paths.items():
            with self.subTest(flag=flag):
                output = io.StringIO()
                argv: list[str] = []
                for default_flag, default_value in defaults.items():
                    argv.extend([default_flag, outside_path if default_flag == flag else default_value])
                with mock.patch.object(self.module, "request_deepseek_score") as request_score:
                    with redirect_stdout(output):
                        exit_code = self.module.main(
                            argv,
                            env={"DEEPSEEK_API_KEY": "secret-token"},
                        )

                self.assertEqual(exit_code, 2)
                self.assertIn("输出路径不安全", output.getvalue())
                request_score.assert_not_called()

    def test_cli_rejects_non_comparison_output_names(self) -> None:
        defaults = {
            "--state-file": "local_outputs/llm_scoring_comparison_state.json",
            "--output": "local_outputs/llm_scoring_comparison.md",
            "--json-output": "local_outputs/llm_scoring_comparison.json",
            "--error-file": "local_outputs/llm_scoring_comparison_error.md",
        }
        renamed_paths = {
            "--state-file": "local_outputs/other_state.json",
            "--output": "local_outputs/other.md",
            "--json-output": "local_outputs/other.json",
            "--error-file": "local_outputs/other_error.md",
        }
        for flag, renamed_path in renamed_paths.items():
            with self.subTest(flag=flag):
                output = io.StringIO()
                argv: list[str] = []
                for default_flag, default_value in defaults.items():
                    argv.extend([default_flag, renamed_path if default_flag == flag else default_value])
                with mock.patch.object(self.module, "request_deepseek_score") as request_score:
                    with redirect_stdout(output):
                        exit_code = self.module.main(
                            argv,
                            env={"DEEPSEEK_API_KEY": "secret-token"},
                        )

                self.assertEqual(exit_code, 2)
                self.assertIn("必须固定为", output.getvalue())
                request_score.assert_not_called()

    def test_success_writes_comparison_without_reports(self) -> None:
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
                confidence=90,
                reason="跑偏动漫游戏样本。",
                provider="deepseek",
            ),
        ]

        def fake_parse(_payload: object) -> LLMScoringResult:
            return results.pop(0)

        with mock.patch.object(self.module, "request_deepseek_score", return_value=({}, 200)) as request_score:
            with mock.patch.object(self.module, "parse_deepseek_score_response", side_effect=fake_parse):
                exit_code, text = self.run_main(
                    self.args("--confirm-live-api", "--sample-count", "2"),
                    env={"DEEPSEEK_API_KEY": "secret-token", "LLM_SCORING_ENABLED": "on"},
                )

        state = self.read_state()
        summary = json.loads(self.json_file.read_text(encoding="utf-8"))
        markdown = self.output_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "success")
        self.assertTrue(state["network_request_attempted"])
        self.assertFalse(state["report_files_updated"])
        self.assertEqual(summary["counts"]["agree_high"], 1)
        self.assertEqual(summary["counts"]["llm_demoted"], 1)
        self.assertIn("DeepSeek 降级：规则疑似误判", markdown)
        self.assertIn("正式报告未更新", text)
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())
        self.assertEqual(request_score.call_count, 2)

    def test_base_url_with_path_is_rejected_without_network(self) -> None:
        with mock.patch.object(self.module, "request_deepseek_score") as request_score:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api", "--base-url", "https://api.deepseek.com/v1"),
                env={"DEEPSEEK_API_KEY": "secret-token", "LLM_SCORING_ENABLED": "on"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 2)
        self.assertEqual(state["status"], "invalid_base_url")
        self.assertFalse(state["network_request_attempted"])
        self.assertIn("base URL 不安全", text)
        request_score.assert_not_called()

    def test_edge_result_is_not_counted_as_agree_high(self) -> None:
        result = LLMScoringResult(
            ceramic_relevance="edge",
            keyword_intent_match="medium",
            evidence_type="background",
            can_support_trend=True,
            is_noise=False,
            confidence=67,
            reason="陶瓷相关但证据偏弱。",
            provider="deepseek",
        )

        row = self.module.build_row(self.module.SAMPLE_ITEMS[0], result)
        counts = self.module.aggregate_counts([row])

        self.assertEqual(row["alignment"], "边缘相关，建议人工复核")
        self.assertEqual(row["combined"]["level"], "low")
        self.assertEqual(counts["agree_high"], 0)
        self.assertEqual(counts["edge_review"], 1)

    def test_default_main_rejects_report_output_before_network(self) -> None:
        output = io.StringIO()
        with mock.patch.object(self.module, "request_deepseek_score") as request_score:
            with redirect_stdout(output):
                exit_code = self.module.main(
                    ["--output", "reports/report.md", "--confirm-live-api"],
                    env={"DEEPSEEK_API_KEY": "secret-token", "LLM_SCORING_ENABLED": "on"},
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("输出路径不安全", output.getvalue())
        request_score.assert_not_called()


if __name__ == "__main__":
    unittest.main()
