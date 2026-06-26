from __future__ import annotations

import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from ceramic_report import collect_evidence
from sources.scrapecreators_source import (
    ScrapeCreatorsSource,
    check_scrapecreators_readiness,
    configured_scrapecreators_env_var,
    scrapecreators_status_label,
)


def load_ready_script_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_scrapecreators_ready.py"
    spec = importlib.util.spec_from_file_location("check_scrapecreators_ready", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ScrapeCreatorsSourceTests(unittest.TestCase):
    def test_readiness_reports_missing_without_network(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            readiness = check_scrapecreators_readiness()

        self.assertEqual(readiness.status, "missing")
        self.assertFalse(readiness.can_attempt_api)
        self.assertIn("missing", readiness.detail)

    def test_readiness_reports_configured_without_printing_secret(self) -> None:
        with mock.patch.dict(os.environ, {"SCRAPECREATORS_API_KEY": "secret-token"}, clear=True):
            readiness = check_scrapecreators_readiness()

        self.assertEqual(readiness.status, "configured")
        self.assertTrue(readiness.can_attempt_api)
        self.assertEqual(readiness.configured_env_var, "SCRAPECREATORS_API_KEY")
        self.assertNotIn("secret-token", str(readiness))

    def test_legacy_env_name_is_accepted_without_printing_secret(self) -> None:
        env = {"SCRAPE_CREATORS_API_KEY": "legacy-secret"}

        self.assertEqual(configured_scrapecreators_env_var(env), "SCRAPE_CREATORS_API_KEY")
        self.assertEqual(scrapecreators_status_label(env), "configured")
        self.assertNotIn("legacy-secret", str(check_scrapecreators_readiness(env)))

    def test_source_missing_key_does_not_call_network(self) -> None:
        source = ScrapeCreatorsSource(env={})

        with mock.patch("sources.scrapecreators_source.request.urlopen") as urlopen:
            with self.assertRaisesRegex(RuntimeError, "missing_key"):
                source.fetch("ceramic glaze")

        urlopen.assert_not_called()

    def test_source_fetch_converts_response_to_last30days_shape(self) -> None:
        payload = {
            "success": True,
            "posts": [
                {
                    "title": "Glaze Combo?",
                    "subreddit": "Pottery",
                    "url": "https://www.reddit.com/r/Pottery/comments/1/example",
                    "score": 2544,
                    "num_comments": 73,
                    "created_utc": 1780793417,
                }
            ],
            "after": "next-page",
        }
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}

        source = ScrapeCreatorsSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})
        with mock.patch(
            "sources.scrapecreators_source.request.urlopen",
            return_value=response,
        ) as urlopen:
            report = source.fetch("ceramic glaze")

        self.assertEqual(report["topic"], "ceramic glaze")
        self.assertIn("reddit", report["items_by_source"])
        item = report["items_by_source"]["reddit"][0]
        self.assertEqual(item["title"], "Glaze Combo?")
        self.assertEqual(item["container"], "Pottery")
        self.assertEqual(item["engagement"]["score"], 2544)
        self.assertEqual(item["engagement"]["num_comments"], 73)
        evidence = collect_evidence("ceramic glaze", report)
        self.assertEqual(evidence[0].subreddit, "pottery")
        self.assertEqual(evidence[0].engagement, "2544 upvotes, 73 comments")
        request_arg = urlopen.call_args.args[0]
        self.assertIn("query=ceramic+glaze", request_arg.full_url)
        self.assertNotIn("secret-token", str(report))

    def test_source_reads_dotenv_without_printing_secret(self) -> None:
        payload = {"success": True, "posts": [], "after": None}
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}

        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(
                "SCRAPECREATORS" + "_API_KEY=dotenv-secret\n",
                encoding="utf-8",
            )
            source = ScrapeCreatorsSource(env={}, dotenv_path=dotenv_path)
            with mock.patch(
                "sources.scrapecreators_source.request.urlopen",
                return_value=response,
            ):
                report = source.fetch("ceramic glaze")

        self.assertEqual(report["items_by_source"]["reddit"], [])
        self.assertNotIn("dotenv-secret", str(report))

    def test_source_http_error_is_classified_without_secret(self) -> None:
        cases = [
            (401, b"bad key secret-token Authorization: Bearer abc123", "unauthorized_401"),
            (403, b"blocked", "forbidden_403"),
            (403, b"quota credits billing required", "quota_or_billing"),
            (429, b"too many requests", "rate_limited_429"),
            (402, b"quota credits billing required", "quota_or_billing"),
        ]
        source = ScrapeCreatorsSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})

        for code, body, expected in cases:
            with self.subTest(code=code):
                error = HTTPError(
                    url="https://api.scrapecreators.com/v1/reddit/search",
                    code=code,
                    msg="error",
                    hdrs={},
                    fp=io.BytesIO(body),
                )
                with mock.patch("sources.scrapecreators_source.request.urlopen", side_effect=error):
                    with self.assertRaisesRegex(RuntimeError, expected) as caught:
                        source.fetch("ceramic glaze")

                self.assertNotIn("secret-token", str(caught.exception))
                self.assertNotIn("abc123", str(caught.exception))

    def test_source_timeout_is_classified(self) -> None:
        source = ScrapeCreatorsSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})

        with mock.patch(
            "sources.scrapecreators_source.request.urlopen",
            side_effect=socket.timeout("timed out"),
        ):
            with self.assertRaisesRegex(RuntimeError, "timeout"):
                source.fetch("ceramic glaze")

    def test_source_bad_posts_shape_is_parse_error(self) -> None:
        response = io.BytesIO(json.dumps({"success": True, "posts": {}}).encode("utf-8"))
        response.status = 200
        response.headers = {}
        source = ScrapeCreatorsSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})

        with mock.patch(
            "sources.scrapecreators_source.request.urlopen",
            return_value=response,
        ):
            with self.assertRaisesRegex(RuntimeError, "parse_error"):
                source.fetch("ceramic glaze")

    def test_ready_script_does_not_print_secret(self) -> None:
        module = load_ready_script_module()
        output = io.StringIO()

        with mock.patch.dict(os.environ, {"SCRAPECREATORS_API_KEY": "script-secret"}, clear=True):
            with redirect_stdout(output):
                exit_code = module.main()

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("key status: configured", text)
        self.assertIn("network request: not attempted", text)
        self.assertNotIn("script-secret", text)

    def test_ready_script_reads_dotenv_without_printing_secret(self) -> None:
        module = load_ready_script_module()
        output = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(
                "SCRAPECREATORS" + "_API_KEY=" + "dotenv-secret\n",
                encoding="utf-8",
            )
            with redirect_stdout(output):
                exit_code = module.main(env={}, dotenv_path=dotenv_path)

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("key status: configured", text)
        self.assertNotIn("dotenv-secret", text)


if __name__ == "__main__":
    unittest.main()
