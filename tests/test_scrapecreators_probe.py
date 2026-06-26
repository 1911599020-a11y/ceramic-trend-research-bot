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
from urllib.error import HTTPError, URLError


def load_probe_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "probe_scrapecreators_reddit.py"
    spec = importlib.util.spec_from_file_location("probe_scrapecreators_reddit", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ScrapeCreatorsProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_probe_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.state_file = root / "state.json"
        self.output_file = root / "probe.json"
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
            exit_code, _text = self.run_main(
                self.args(),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
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
                        "--error-file",
                        str(self.error_file),
                    ],
                    env={"SCRAPECREATORS_API_KEY": "secret-token"},
                )

        text = output.getvalue()
        self.assertEqual(exit_code, 2)
        self.assertIn("输出路径不安全", text)
        self.assertFalse(self.state_file.exists())
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
        self.assertNotIn("secret-token", text)
        urlopen.assert_not_called()

    def test_limit_is_clamped_to_three(self) -> None:
        with mock.patch.object(self.module.request, "urlopen") as urlopen:
            exit_code, _text = self.run_main(
                self.args("--limit", "99"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["limit"], 3)
        self.assertFalse(state["network_request_attempted"])
        urlopen.assert_not_called()

    def test_success_saves_sanitized_summary(self) -> None:
        payload = {
            "success": True,
            "posts": [
                {
                    "title": "Cone 6 glaze test results",
                    "subreddit": "Pottery",
                    "url": "https://reddit.com/r/Pottery/example",
                    "score": 42,
                    "num_comments": 7,
                    "created_utc": 123456,
                    "selftext": "long body should not be saved",
                }
            ],
            "after": "next-page-token",
        }
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}

        with mock.patch.object(self.module.request, "urlopen", return_value=response) as urlopen:
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        summary = json.loads(self.output_file.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "success")
        self.assertTrue(state["network_request_attempted"])
        self.assertFalse(state["report_files_updated"])
        self.assertEqual(summary["post_count_in_response"], 1)
        self.assertEqual(summary["posts"][0]["title"], "Cone 6 glaze test results")
        self.assertNotIn("secret-token", self.output_file.read_text(encoding="utf-8"))
        self.assertNotIn("selftext", self.output_file.read_text(encoding="utf-8"))
        urlopen.assert_called_once()

    def test_probe_reads_dotenv_file_without_printing_secret(self) -> None:
        payload = {"success": True, "posts": [], "after": None}
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

        state = self.read_state()
        output_text = self.output_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertEqual(state["status"], "success")
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
        self.assertEqual(exit_code, 1)
        self.assertEqual(state["status"], "failure")
        self.assertEqual(state["error_type"], "parse_error")
        summary = json.loads(self.output_file.read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "failure")
        self.assertEqual(summary["error_type"], "parse_error")

    def test_http_errors_are_classified(self) -> None:
        cases = [
            (401, b"unauthorized", "unauthorized_401"),
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
                        url="https://api.scrapecreators.com/v1/reddit/search",
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
                    self.assertEqual(exit_code, 1)
                    self.assertEqual(state["status"], "failure")
                    self.assertEqual(state["error_type"], expected)
                    self.assertTrue((root / "error.md").exists())

    def test_timeout_is_classified(self) -> None:
        with mock.patch.object(self.module.request, "urlopen", side_effect=socket.timeout("timed out")):
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 1)
        self.assertEqual(state["error_type"], "timeout")

    def test_url_error_timeout_is_classified(self) -> None:
        with mock.patch.object(self.module.request, "urlopen", side_effect=URLError("timed out")):
            exit_code, _text = self.run_main(
                self.args("--confirm-live-api"),
                env={"SCRAPECREATORS_API_KEY": "secret-token"},
            )

        state = self.read_state()
        self.assertEqual(exit_code, 1)
        self.assertEqual(state["error_type"], "timeout")


if __name__ == "__main__":
    unittest.main()
