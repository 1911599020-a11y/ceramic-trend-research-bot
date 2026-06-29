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
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "review_youtube_video_probe.py"
    spec = importlib.util.spec_from_file_location("review_youtube_video_probe", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def video_probe_payload() -> dict[str, object]:
    return {
        "status": "success",
        "video_url": "https://www.youtube.com/watch?v=abc123",
        "requested_at": "2026-06-29T09:50:00+00:00",
        "details": {
            "id": "abc123",
            "url": "https://www.youtube.com/watch?v=abc123",
            "title": "Understanding Ceramic Glazes",
            "description_excerpt": "A ceramic glaze tutorial about food-safe low-fire and high-fire glazes.",
            "channel": {"title": "Clay Studio"},
            "view_count_text": "2,000 views",
            "view_count_int": 2000,
            "like_count_int": 100,
            "comment_count_int": 12,
            "duration_formatted": "8:10",
            "publish_date_text": "1 month ago",
            "keywords": ["ceramic", "glaze", "pottery"],
            "caption_tracks": {"count": 1, "languages": ["en"]},
        },
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


class YouTubeVideoReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_review_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.input_file = root / "youtube_video_probe.json"
        self.state_file = root / "state.json"
        self.output_file = root / "review.md"
        self.json_file = root / "review.json"
        self.error_file = root / "error.md"
        self.report_file = root / "report.md"
        self.latest_file = root / "latest.md"
        self.archive_dir = root / "archive"
        self.input_file.write_text(json.dumps(video_probe_payload()), encoding="utf-8")

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
        self.assertEqual(summary["analysis"]["sample"]["rule_level"], "high")
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

    def test_validate_rejects_output_path_even_with_default_input(self) -> None:
        outside_output = Path(self.tmpdir.name) / "outside.md"
        paths = self.module.ReviewPaths(
            input_file=self.module.DEFAULT_INPUT_FILE,
            state_file=self.module.EXPECTED_OUTPUTS["state-file"],
            output_file=outside_output,
            json_file=self.module.EXPECTED_OUTPUTS["json-output"],
            error_file=self.module.EXPECTED_OUTPUTS["error-file"],
            report_file=self.report_file,
            latest_file=self.latest_file,
            archive_dir=self.archive_dir,
        )

        error = self.module.validate_local_output_paths(paths)

        self.assertIn("output 必须位于 local_outputs/", error)

    def test_confirm_with_switch_off_does_not_call_network(self) -> None:
        with mock.patch.object(self.module, "request_deepseek_score") as request_deepseek:
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"DEEPSEEK_API_KEY": "secret-token"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        summary = self.read_json()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "switch_off")
        self.assertEqual(summary["llm_status"], "switch_off")
        self.assertFalse(state["network_request_attempted"])
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

    def test_confirm_success_reviews_video_details_with_deepseek(self) -> None:
        response = deepseek_response(
            {
                "ceramic_relevance": "high",
                "keyword_intent_match": "high",
                "evidence_type": "trend_signal",
                "can_support_trend": True,
                "is_noise": False,
                "confidence": 88,
                "reason": "详情简介和关键词都说明这是陶瓷釉料教学。",
            }
        )

        with mock.patch.object(
            self.module,
            "request_deepseek_score",
            return_value=(json.loads(response.getvalue().decode("utf-8")), 200),
        ) as request_deepseek:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api"),
                env={"DEEPSEEK_API_KEY": "secret-token", "LLM_SCORING_ENABLED": "on"},
            )

        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        summary = self.read_json()
        self.assertEqual(exit_code, 0)
        self.assertIn("DeepSeek YouTube video details 旁路审核完成", text)
        self.assertTrue(state["network_request_attempted"])
        self.assertEqual(summary["llm_status"], "success")
        self.assertEqual(summary["llm_counts"]["trend_candidates"], 1)
        self.assertNotIn("secret-token", self.output_file.read_text(encoding="utf-8"))
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())
        request_deepseek.assert_called_once()

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

    def test_http_402_is_quota_or_billing(self) -> None:
        error = HTTPError(
            url="https://api.deepseek.com/chat/completions",
            code=402,
            msg="payment required",
            hdrs={},
            fp=io.BytesIO(b""),
        )

        self.assertEqual(self.module.classify_http_error(error, ""), "quota_or_billing")


if __name__ == "__main__":
    unittest.main()
