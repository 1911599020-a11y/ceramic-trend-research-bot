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
from urllib import parse
from urllib.error import HTTPError


def load_probe_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "probe_scrapecreators_youtube_video.py"
    spec = importlib.util.spec_from_file_location("probe_scrapecreators_youtube_video", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def review_payload() -> dict[str, object]:
    return {
        "status": "success",
        "llm_results": [
            {
                "review_label": "可作为 YouTube 趋势候选",
                "sample": {
                    "title": "Understanding Ceramic Glazes",
                    "url": "https://www.youtube.com/watch?v=abc123",
                },
            }
        ],
        "analysis": {
            "samples": [
                {
                    "title": "Fallback video",
                    "url": "https://www.youtube.com/watch?v=fallback",
                }
            ]
        },
    }


def video_details_payload() -> dict[str, object]:
    return {
        "id": "abc123",
        "url": "https://www.youtube.com/watch?v=abc123",
        "type": "video",
        "title": "Understanding Ceramic Glazes",
        "thumbnail": "https://i.ytimg.com/example.jpg",
        "description": "Short ceramic glaze description with private link https://example.com/private",
        "descriptionLinks": [{"url": "https://example.com"}],
        "channel": {
            "id": "channel-1",
            "title": "Clay Studio",
            "handle": "@claystudio",
            "url": "https://www.youtube.com/@claystudio",
        },
        "viewCountText": "2,000 views",
        "viewCountInt": 2000,
        "likeCountText": "100 likes",
        "likeCountInt": 100,
        "commentCountText": "12 comments",
        "commentCountInt": 12,
        "durationMs": 490000,
        "durationFormatted": "8:10",
        "publishDateText": "1 month ago",
        "genre": "Education",
        "keywords": ["ceramic", "glaze", "pottery"],
        "captionTracks": [
            {"languageCode": "en", "baseUrl": "https://caption.example/secret"}
        ],
        "watchNextVideos": [{"title": "do not save"}],
    }


class YouTubeVideoProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_probe_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.input_file = root / "youtube_probe_review.json"
        self.state_file = root / "state.json"
        self.output_file = root / "youtube_video_probe.json"
        self.error_file = root / "error.md"
        self.report_file = root / "report.md"
        self.latest_file = root / "latest.md"
        self.archive_dir = root / "archive"
        self.input_file.write_text(json.dumps(review_payload()), encoding="utf-8")

    def args(self, *extra: str) -> list[str]:
        return [
            "--input-file",
            str(self.input_file),
            "--state-file",
            str(self.state_file),
            "--output",
            str(self.output_file),
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

    def test_default_selects_candidate_without_network_or_reports(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, text = self.run_main(
                self.args(),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertIn("未发起网络请求", text)
        self.assertEqual(state["status"], "not_confirmed")
        self.assertEqual(state["video_url"], "https://www.youtube.com/watch?v=abc123")
        self.assertFalse(state["network_request_attempted"])
        self.assertFalse(state["report_files_updated"])
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())
        urlopen.assert_not_called()

    def test_cli_rejects_output_paths_outside_local_outputs(self) -> None:
        output = io.StringIO()
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            with redirect_stdout(output):
                exit_code = self.module.main(
                    [
                        "--input-file",
                        str(self.input_file),
                        "--state-file",
                        str(self.state_file),
                        "--output",
                        str(self.output_file),
                        "--error-file",
                        str(self.error_file),
                    ],
                    env={"SCRAPECREATORS_API_KEY": "secret-token"},
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("输出路径不安全", output.getvalue())
        urlopen.assert_not_called()

    def test_validate_rejects_output_path_even_with_default_input(self) -> None:
        outside_output = Path(self.tmpdir.name) / "outside.json"
        paths = self.module.ProbePaths(
            input_file=self.module.DEFAULT_INPUT_FILE,
            state_file=self.module.EXPECTED_OUTPUTS["state-file"],
            output_file=outside_output,
            error_file=self.module.EXPECTED_OUTPUTS["error-file"],
            report_file=self.report_file,
            latest_file=self.latest_file,
            archive_dir=self.archive_dir,
        )

        error = self.module.validate_local_output_paths(paths)

        self.assertIn("output 必须位于 local_outputs/", error)

    def test_missing_key_with_confirm_does_not_call_network(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api"),
                env={},
            )

        state = self.read_state()
        summary = json.loads(self.output_file.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertIn("未找到 API key", text)
        self.assertEqual(state["status"], "missing_key")
        self.assertFalse(state["network_request_attempted"])
        self.assertEqual(summary["status"], "failure")
        urlopen.assert_not_called()

    def test_success_saves_sanitized_details_and_only_one_request(self) -> None:
        response = io.BytesIO(json.dumps(video_details_payload()).encode("utf-8"))
        response.status = 200
        response.headers = {}

        with mock.patch.object(self.module.request, "urlopen", return_value=response) as urlopen:
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        summary_text = self.output_file.read_text(encoding="utf-8")
        summary = json.loads(summary_text)
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "success")
        self.assertTrue(state["network_request_attempted"])
        self.assertFalse(summary["raw_response_saved"])
        self.assertFalse(summary["transcripts_requested"])
        self.assertFalse(summary["comments_requested"])
        self.assertEqual(summary["details"]["id"], "abc123")
        self.assertEqual(summary["details"]["channel"]["title"], "Clay Studio")
        self.assertEqual(summary["details"]["view_count_int"], 2000)
        self.assertEqual(summary["details"]["caption_tracks"]["count"], 1)
        self.assertGreater(summary["details"]["description_char_count"], 0)
        self.assertEqual(summary["details"]["description_excerpt"], "")
        self.assertNotIn("Short ceramic glaze description", summary_text)
        self.assertNotIn("https://example.com/private", summary_text)
        self.assertNotIn("baseUrl", summary_text)
        self.assertNotIn("caption.example", summary_text)
        self.assertNotIn("do not save", summary_text)
        self.assertNotIn("secret-token", summary_text)
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())
        urlopen.assert_called_once()

        request_arg = urlopen.call_args.args[0]
        parsed = parse.urlparse(request_arg.full_url)
        params = parse.parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "api.scrapecreators.com")
        self.assertEqual(parsed.path, "/v1/youtube/video")
        self.assertEqual(set(params), {"url", "language"})
        self.assertEqual(params["url"], ["https://www.youtube.com/watch?v=abc123"])
        self.assertEqual(params["language"], ["en"])

    def test_long_description_excerpt_is_truncated_and_url_redacted(self) -> None:
        raw_description = (
            "Ceramic glaze chemistry https://private.example/secret "
            + "kiln firing cone 6 glaze defect troubleshooting " * 20
        )

        details = self.module.sanitize_details(
            {"description": raw_description, "title": "Long glaze tutorial"},
            "https://www.youtube.com/watch?v=abc123",
        )

        excerpt = details["description_excerpt"]
        self.assertIn("[truncated]", excerpt)
        self.assertLess(len(excerpt), len(raw_description))
        self.assertNotIn("https://", excerpt)
        self.assertNotIn("private.example", excerpt)

    def test_http_error_is_classified_and_redacted(self) -> None:
        error = HTTPError(
            url="https://api.scrapecreators.com/v1/youtube/video",
            code=429,
            msg="error",
            hdrs={},
            fp=io.BytesIO(b"too many requests secret-token"),
        )
        with mock.patch.object(self.module.request, "urlopen", side_effect=error):
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        error_text = self.error_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 1)
        self.assertEqual(state["error_type"], "rate_limited_429")
        self.assertNotIn("secret-token", error_text)

    def test_http_402_is_quota_or_billing(self) -> None:
        error = HTTPError(
            url="https://api.scrapecreators.com/v1/youtube/video",
            code=402,
            msg="payment required",
            hdrs={},
            fp=io.BytesIO(b""),
        )

        self.assertEqual(self.module.classify_http_error(error, ""), "quota_or_billing")


if __name__ == "__main__":
    unittest.main()
