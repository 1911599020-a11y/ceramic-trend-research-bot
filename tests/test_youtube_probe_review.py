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


def load_review_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "review_youtube_probe.py"
    spec = importlib.util.spec_from_file_location("review_youtube_probe", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def youtube_probe_payload() -> dict[str, object]:
    return {
        "status": "success",
        "query": "ceramic glaze",
        "requested_at": "2026-06-29T09:33:21+00:00",
        "counts_in_response": {"videos": 19, "shorts": 25},
        "summarized_count": 3,
        "videos": [
            {
                "title": "Understanding Ceramic Glazes",
                "channel": "Clay Studio",
                "url": "https://www.youtube.com/watch?v=abc",
                "video_id": "abc",
                "published": "1 month ago",
                "duration": "8:10",
                "views": "2,000 views",
            },
            {
                "title": "Automotive ceramic coating mistakes",
                "channel": "Car Detailer",
                "url": "https://www.youtube.com/watch?v=def",
                "video_id": "def",
                "published": "2 weeks ago",
                "duration": "4:00",
                "views": "9,000 views",
            },
        ],
    }


def deepseek_response(payload: dict[str, object]) -> io.BytesIO:
    body = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            }
        ]
    }
    response = io.BytesIO(json.dumps(body).encode("utf-8"))
    response.status = 200
    return response


class YouTubeProbeReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_review_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.input_file = root / "youtube_probe.json"
        self.state_file = root / "state.json"
        self.output_file = root / "review.md"
        self.json_file = root / "review.json"
        self.error_file = root / "error.md"
        self.report_file = root / "report.md"
        self.latest_file = root / "latest.md"
        self.archive_dir = root / "archive"
        self.input_file.write_text(json.dumps(youtube_probe_payload()), encoding="utf-8")

    def args(self, *extra: str) -> list[str]:
        return [
            "--input-file",
            str(self.input_file),
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

    def read_json(self) -> dict[str, object]:
        return json.loads(self.json_file.read_text(encoding="utf-8"))

    def test_default_analyzes_fields_without_network_or_reports(self) -> None:
        with mock.patch.object(self.module, "request_deepseek_score") as request_deepseek:
            exit_code, text = self.run_main(
                self.args(),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        summary = self.read_json()
        self.assertEqual(exit_code, 0)
        self.assertIn("未发起 DeepSeek 请求", text)
        self.assertEqual(state["status"], "success")
        self.assertEqual(state["llm_status"], "not_confirmed")
        self.assertFalse(state["network_request_attempted"])
        self.assertEqual(summary["analysis"]["field_presence"]["title"]["status"], "stable")
        self.assertEqual(summary["analysis"]["samples"][0]["rule_level"], "high")
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())
        request_deepseek.assert_not_called()

    def test_cli_rejects_output_paths_outside_local_outputs(self) -> None:
        output = io.StringIO()
        with mock.patch.object(self.module, "request_deepseek_score") as request_deepseek:
            with redirect_stdout(output):
                exit_code = self.module.main(
                    [
                        "--input-file",
                        str(self.input_file),
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
        request_deepseek.assert_not_called()

    def test_missing_input_does_not_call_network(self) -> None:
        self.input_file.unlink()
        with mock.patch.object(self.module, "request_deepseek_score") as request_deepseek:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api"),
                env={"DEEPSEEK_API_KEY": "secret-token", "LLM_SCORING_ENABLED": "on"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "missing_input")
        self.assertFalse(state["network_request_attempted"])
        self.assertIn("未找到 YouTube probe 输入", text)
        request_deepseek.assert_not_called()

    def test_confirm_with_switch_off_does_not_call_network(self) -> None:
        with mock.patch.object(self.module, "request_deepseek_score") as request_deepseek:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api"),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        summary = self.read_json()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "switch_off")
        self.assertEqual(summary["llm_status"], "switch_off")
        self.assertFalse(state["network_request_attempted"])
        self.assertIn("DeepSeek 未执行", text)
        request_deepseek.assert_not_called()

    def test_confirm_missing_key_does_not_call_network(self) -> None:
        with mock.patch.object(self.module, "request_deepseek_score") as request_deepseek:
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"LLM_SCORING_ENABLED": "on"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "missing_key")
        self.assertFalse(state["network_request_attempted"])
        request_deepseek.assert_not_called()

    def test_invalid_base_url_writes_json_failure_without_network(self) -> None:
        with mock.patch.object(self.module, "request_deepseek_score") as request_deepseek:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api", "--base-url", "https://example.com"),
                env={"DEEPSEEK_API_KEY": "secret-token", "LLM_SCORING_ENABLED": "on"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        summary = self.read_json()
        self.assertEqual(exit_code, 2)
        self.assertIn("base URL 不安全", text)
        self.assertEqual(state["status"], "invalid_base_url")
        self.assertEqual(summary["status"], "failure")
        self.assertEqual(summary["error_type"], "invalid_base_url")
        self.assertFalse(state["network_request_attempted"])
        request_deepseek.assert_not_called()

    def test_confirm_success_reviews_samples_with_deepseek(self) -> None:
        responses = [
            deepseek_response(
                {
                    "ceramic_relevance": "high",
                    "keyword_intent_match": "high",
                    "evidence_type": "trend_signal",
                    "can_support_trend": True,
                    "is_noise": False,
                    "confidence": 86,
                    "reason": "标题和频道都指向陶瓷釉料。",
                }
            ),
            deepseek_response(
                {
                    "ceramic_relevance": "low",
                    "keyword_intent_match": "low",
                    "evidence_type": "noise",
                    "can_support_trend": False,
                    "is_noise": True,
                    "confidence": 91,
                    "reason": "这是汽车陶瓷镀膜，不是陶艺釉料。",
                }
            ),
        ]

        with mock.patch.object(
            self.module,
            "request_deepseek_score",
            side_effect=[
                (json.loads(responses[0].getvalue().decode("utf-8")), 200),
                (json.loads(responses[1].getvalue().decode("utf-8")), 200),
            ],
        ) as request_deepseek:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api", "--sample-count", "2"),
                env={"DEEPSEEK_API_KEY": "secret-token", "LLM_SCORING_ENABLED": "on"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        summary = self.read_json()
        self.assertEqual(exit_code, 0)
        self.assertIn("DeepSeek YouTube 旁路审核完成", text)
        self.assertTrue(state["network_request_attempted"])
        self.assertEqual(summary["llm_status"], "success")
        self.assertEqual(summary["llm_counts"]["trend_candidates"], 1)
        self.assertEqual(summary["llm_counts"]["noise_or_low"], 1)
        self.assertNotIn("secret-token", self.output_file.read_text(encoding="utf-8"))
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())
        self.assertEqual(request_deepseek.call_count, 2)

    def test_http_error_is_classified_and_redacted(self) -> None:
        error = HTTPError(
            url="https://api.deepseek.com/chat/completions",
            code=429,
            msg="error",
            hdrs={},
            fp=io.BytesIO(b"too many requests secret-token"),
        )
        with mock.patch.object(self.module, "request_deepseek_score", side_effect=error):
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"DEEPSEEK_API_KEY": "secret-token", "LLM_SCORING_ENABLED": "on"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        error_text = self.error_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 1)
        self.assertEqual(state["status"], "failure")
        self.assertEqual(state["error_type"], "rate_limited_429")
        self.assertNotIn("secret-token", error_text)


if __name__ == "__main__":
    unittest.main()
