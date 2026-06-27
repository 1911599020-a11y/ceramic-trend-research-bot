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
from urllib.error import HTTPError


def load_probe_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "probe_llm_scoring.py"
    spec = importlib.util.spec_from_file_location("probe_llm_scoring", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LLMScoringProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_probe_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.state_file = root / "state.json"
        self.output_file = root / "llm_scoring_probe.md"
        self.json_file = root / "llm_scoring_probe.json"
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
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, text = self.run_main(
                self.args(),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertIn("未发起网络请求", text)
        self.assertEqual(state["status"], "not_confirmed")
        self.assertFalse(state["network_request_attempted"])
        self.assertFalse(state["report_files_updated"])
        urlopen.assert_not_called()
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())

    def test_cli_rejects_output_paths_outside_local_outputs(self) -> None:
        output = io.StringIO()
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            with redirect_stdout(output):
                exit_code = self.module.main(
                    [
                        "--state-file",
                        str(self.state_file),
                        "--output",
                        str(self.output_file),
                        "--json-output",
                        str(self.json_file),
                        "--error-file",
                        str(self.error_file),
                    ],
                    env={"DEEPSEEK_API_KEY": "secret-token"},
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("输出路径不安全", output.getvalue())
        self.assertFalse(self.state_file.exists())
        urlopen.assert_not_called()

    def test_cli_rejects_non_probe_output_names(self) -> None:
        output = io.StringIO()
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            with redirect_stdout(output):
                exit_code = self.module.main(
                    [
                        "--state-file",
                        "local_outputs/other_state.json",
                        "--output",
                        "local_outputs/llm_scoring_probe.md",
                        "--json-output",
                        "local_outputs/llm_scoring_probe.json",
                        "--error-file",
                        "local_outputs/llm_scoring_probe_error.md",
                    ],
                    env={"DEEPSEEK_API_KEY": "secret-token"},
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("必须固定为 local_outputs/llm_scoring_probe_state.json", output.getvalue())
        urlopen.assert_not_called()

    def test_custom_base_url_is_rejected_without_network(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api", "--base-url", "https://example.com"),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 2)
        self.assertIn("base URL 不安全", text)
        self.assertEqual(state["status"], "invalid_base_url")
        self.assertFalse(state["network_request_attempted"])
        self.assertTrue(self.error_file.exists())
        urlopen.assert_not_called()

    def test_missing_key_with_confirm_does_not_call_network(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api"),
                env={},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "missing_key")
        self.assertEqual(state["error_type"], "missing_key")
        self.assertFalse(state["network_request_attempted"])
        self.assertTrue(self.error_file.exists())
        self.assertIn("未找到 API key", text)
        urlopen.assert_not_called()

    def test_sample_count_is_clamped_to_five(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, _text = self.run_main(
                self.args("--sample-count", "99"),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["sample_count"], 5)
        self.assertFalse(state["network_request_attempted"])
        urlopen.assert_not_called()

    def test_success_saves_sanitized_markdown_and_json(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "ceramic_relevance": "high",
                                "keyword_intent_match": "high",
                                "evidence_type": "pain_point",
                                "can_support_trend": True,
                                "is_noise": False,
                                "confidence": 88,
                                "reason": "真实陶瓷烧成问题。",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}

        with mock.patch.object(self.module.request, "urlopen", return_value=response) as urlopen:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api", "--sample-count", "1"),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = self.read_state()
        summary = json.loads(self.json_file.read_text(encoding="utf-8"))
        markdown = self.output_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "success")
        self.assertTrue(state["network_request_attempted"])
        self.assertFalse(state["report_files_updated"])
        self.assertEqual(summary["status"], "success")
        self.assertEqual(summary["results"][0]["result"]["confidence"], 88)
        self.assertIn("正式报告未更新", text)
        self.assertIn("真实陶瓷烧成问题", markdown)
        self.assertNotIn("secret-token", markdown)
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())
        urlopen.assert_called_once()

    def test_probe_reads_dotenv_file_without_printing_secret(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "ceramic_relevance": "low",
                                "keyword_intent_match": "low",
                                "evidence_type": "noise",
                                "can_support_trend": False,
                                "is_noise": True,
                                "confidence": 80,
                                "reason": "跑偏样本。",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}
        dotenv_path = Path(self.tmpdir.name) / ".env"
        dotenv_path.write_text("DEEPSEEK" + "_API_KEY=dotenv-secret\n", encoding="utf-8")

        with mock.patch.object(self.module.request, "urlopen", return_value=response):
            exit_code, text = self.run_main(
                self.args("--confirm-live-api", "--sample-count", "1", "--dotenv-file", str(dotenv_path)),
                env={},
            )

        self.assertEqual(exit_code, 0)
        self.assertNotIn("dotenv-secret", text)
        self.assertNotIn("dotenv-secret", self.output_file.read_text(encoding="utf-8"))
        self.assertNotIn("dotenv-secret", self.json_file.read_text(encoding="utf-8"))

    def test_http_errors_are_classified(self) -> None:
        cases = [
            (401, b"unauthorized", "unauthorized_401"),
            (403, b"blocked", "forbidden_403"),
            (429, b"too many requests", "rate_limited_429"),
            (402, b"insufficient balance", "quota_or_billing"),
        ]
        for status, body, expected in cases:
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    error = HTTPError(
                        url="https://api.deepseek.com/chat/completions",
                        code=status,
                        msg="error",
                        hdrs={},
                        fp=io.BytesIO(body),
                    )
                    args = [
                        "--state-file",
                        str(root / "state.json"),
                        "--output",
                        str(root / "llm_scoring_probe.md"),
                        "--json-output",
                        str(root / "llm_scoring_probe.json"),
                        "--error-file",
                        str(root / "error.md"),
                        "--confirm-live-api",
                    ]
                    with mock.patch.object(self.module.request, "urlopen", side_effect=error):
                        exit_code, _text = self.run_main(args, env={"DEEPSEEK_API_KEY": "secret-token"})

                    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                    self.assertEqual(exit_code, 1)
                    self.assertEqual(state["status"], "failure")
                    self.assertEqual(state["error_type"], expected)
                    self.assertTrue((root / "error.md").exists())

    def test_deepseek_response_parse_error_is_reported(self) -> None:
        payload = {"choices": [{"message": {"content": "not json"}}]}
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}

        with mock.patch.object(self.module.request, "urlopen", return_value=response):
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api", "--sample-count", "1"),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 1)
        self.assertEqual(state["status"], "failure")
        self.assertEqual(state["error_type"], "parse_error")
        self.assertTrue(self.error_file.exists())


if __name__ == "__main__":
    unittest.main()
