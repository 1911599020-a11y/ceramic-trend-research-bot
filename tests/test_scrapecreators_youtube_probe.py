from __future__ import annotations

import importlib.util
import io
import json
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from urllib import parse
from urllib.error import HTTPError, URLError


def load_probe_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "probe_scrapecreators_youtube.py"
    spec = importlib.util.spec_from_file_location("probe_scrapecreators_youtube", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ScrapeCreatorsYouTubeProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_probe_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.state_file = root / "youtube_probe_state.json"
        self.output_file = root / "youtube_probe.json"
        self.error_file = root / "youtube_probe_error.md"
        self.report_file = root / "report.md"
        self.latest_file = root / "latest.md"
        self.archive_dir = root / "archive"

    def args(self, *extra: str) -> list[str]:
        return [
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

    def read_state(self) -> dict[str, object]:
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def run_main(self, argv: list[str], env: dict[str, str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = self.module.main(argv, env=env, allow_outside_local_outputs=True)
        return exit_code, output.getvalue()

    def test_no_confirm_default_does_not_call_network_or_reports(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, text = self.run_main(
                self.args(),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertIn("未发起网络请求", text)
        self.assertEqual(state["status"], "not_confirmed")
        self.assertFalse(state["network_request_attempted"])
        self.assertFalse(state["report_files_updated"])
        self.assertFalse(state["raw_response_saved"])
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
                        "--error-file",
                        str(self.error_file),
                    ],
                    env={"SCRAPECREATORS_API_KEY": "secret-token"},
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
                        "local_outputs/other_youtube_state.json",
                        "--output",
                        "local_outputs/youtube_probe.json",
                        "--error-file",
                        "local_outputs/youtube_probe_error.md",
                    ],
                    env={"SCRAPECREATORS_API_KEY": "secret-token"},
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("必须固定为 local_outputs/youtube_probe_state.json", output.getvalue())
        urlopen.assert_not_called()

    def test_missing_key_with_confirm_does_not_call_network(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api"),
                env={},
            )

        state = self.read_state()
        summary = json.loads(self.output_file.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "missing_key")
        self.assertEqual(state["error_type"], "missing_key")
        self.assertFalse(state["network_request_attempted"])
        self.assertEqual(summary["status"], "failure")
        self.assertTrue(self.error_file.exists())
        self.assertNotIn("secret-token", text)
        urlopen.assert_not_called()

    def test_summary_limit_is_clamped_to_three(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, _text = self.run_main(
                self.args("--summary-limit", "99"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["summary_limit"], 3)
        self.assertFalse(state["network_request_attempted"])
        urlopen.assert_not_called()

    def test_success_saves_sanitized_summary_and_only_one_search_request(self) -> None:
        payload = {
            "videos": [
                {
                    "title": "Cone 6 ceramic glaze tests",
                    "channel": {"name": "Studio Tests"},
                    "videoId": "abc123",
                    "publishedTimeText": "2 weeks ago",
                    "duration": "8:10",
                    "views": 1200,
                    "description": "long description should not be saved",
                },
                {
                    "title": "Pottery studio vlog",
                    "channelName": "Clay Channel",
                    "url": "https://youtube.com/watch?v=def456",
                    "viewCountText": "4K views",
                    "description": "also not saved",
                },
                {"title": "Third video", "videoId": "ghi789"},
                {"title": "Fourth video should not be summarized", "videoId": "jkl000"},
            ],
            "shorts": [{"title": "short"}],
            "continuationToken": "token-that-must-not-be-saved",
        }
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}

        with mock.patch.object(self.module.request, "urlopen", return_value=response) as urlopen:
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api", "--query", "ceramic glaze"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        summary_text = self.output_file.read_text(encoding="utf-8")
        summary = json.loads(summary_text)
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "success")
        self.assertTrue(state["network_request_attempted"])
        self.assertFalse(state["report_files_updated"])
        self.assertFalse(summary["raw_response_saved"])
        self.assertFalse(summary["continuation_followed"])
        self.assertFalse(summary["video_details_requested"])
        self.assertFalse(summary["transcripts_requested"])
        self.assertFalse(summary["comments_requested"])
        self.assertEqual(summary["summarized_count"], 3)
        self.assertEqual(summary["counts_in_response"]["videos"], 4)
        self.assertEqual(summary["videos"][0]["title"], "Cone 6 ceramic glaze tests")
        self.assertEqual(summary["videos"][0]["views"], "1200")
        self.assertEqual(summary["videos"][0]["url"], "https://www.youtube.com/watch?v=abc123")
        self.assertNotIn("description", summary_text)
        self.assertNotIn("token-that-must-not-be-saved", summary_text)
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
        self.assertEqual(parsed.path, "/v1/youtube/search")
        self.assertEqual(set(params), {"query", "uploadDate", "sortBy", "type"})
        self.assertEqual(params["query"], ["ceramic glaze"])
        self.assertEqual(params["uploadDate"], ["this_month"])
        self.assertEqual(params["sortBy"], ["relevance"])
        self.assertEqual(params["type"], ["videos"])

    def test_probe_reads_dotenv_file_without_printing_secret(self) -> None:
        payload = {"videos": [], "shorts": []}
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}
        dotenv_path = Path(self.tmpdir.name) / ".env"
        dotenv_path.write_text(
            "SCRAPECREATORS" + "_API_KEY=dotenv-secret\n",
            encoding="utf-8",
        )

        with mock.patch.object(self.module.request, "urlopen", return_value=response) as urlopen:
            exit_code, text = self.run_main(
                self.args("--confirm-live-api", "--dotenv-file", str(dotenv_path)),
                env={},
            )

        output_text = self.output_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertNotIn("dotenv-secret", text)
        self.assertNotIn("dotenv-secret", output_text)
        urlopen.assert_called_once()

    def test_non_object_json_is_parse_error(self) -> None:
        response = io.BytesIO(json.dumps(["not", "an", "object"]).encode("utf-8"))
        response.status = 200
        response.headers = {}

        with mock.patch.object(self.module.request, "urlopen", return_value=response):
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        summary = json.loads(self.output_file.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(state["status"], "failure")
        self.assertEqual(state["error_type"], "parse_error")
        self.assertEqual(summary["error_type"], "parse_error")
        self.assertFalse(self.report_file.exists())
        self.assertFalse(self.latest_file.exists())
        self.assertFalse(self.archive_dir.exists())

    def test_http_errors_are_classified_and_secret_is_redacted(self) -> None:
        cases = [
            (401, b"unauthorized secret-token", "unauthorized_401"),
            (403, b"blocked", "forbidden_403"),
            (403, b"quota credits billing required", "quota_or_billing"),
            (429, b"too many requests", "rate_limited_429"),
            (402, b"quota credits billing required", "quota_or_billing"),
        ]

        for status, body, expected in cases:
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    error = HTTPError(
                        url="https://api.scrapecreators.com/v1/youtube/search",
                        code=status,
                        msg="error",
                        hdrs={},
                        fp=io.BytesIO(body),
                    )
                    args = [
                        "--state-file",
                        str(root / "state.json"),
                        "--output",
                        str(root / "probe.json"),
                        "--error-file",
                        str(root / "error.md"),
                        "--confirm-live-api",
                    ]
                    with mock.patch.object(self.module.request, "urlopen", side_effect=error):
                        exit_code, _text = self.run_main(args, env={"SCRAPECREATORS_API_KEY": "secret-token"})

                    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                    error_text = (root / "error.md").read_text(encoding="utf-8")
                    self.assertEqual(exit_code, 1)
                    self.assertEqual(state["status"], "failure")
                    self.assertEqual(state["error_type"], expected)
                    self.assertNotIn("secret-token", error_text)

    def test_timeout_and_dns_errors_are_classified(self) -> None:
        with mock.patch.object(self.module.request, "urlopen", side_effect=socket.timeout("timed out")):
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(self.read_state()["error_type"], "timeout")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = [
                "--state-file",
                str(root / "state.json"),
                "--output",
                str(root / "probe.json"),
                "--error-file",
                str(root / "error.md"),
                "--confirm-live-api",
            ]
            with mock.patch.object(self.module.request, "urlopen", side_effect=URLError("nodename nor servname")):
                exit_code, _text = self.run_main(args, env={"SCRAPECREATORS_API_KEY": "secret-token"})
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(state["error_type"], "dns_error")


if __name__ == "__main__":
    unittest.main()
