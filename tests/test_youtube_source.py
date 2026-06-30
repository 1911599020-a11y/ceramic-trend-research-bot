from __future__ import annotations

import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib import parse
from urllib.error import HTTPError, URLError

from ceramic_report import collect_evidence
from sources.youtube_source import ScrapeCreatorsYouTubeSearchSource


class ScrapeCreatorsYouTubeSearchSourceTests(unittest.TestCase):
    def test_source_missing_key_does_not_call_network(self) -> None:
        source = ScrapeCreatorsYouTubeSearchSource(env={})

        with mock.patch("sources.youtube_source.request.urlopen") as urlopen:
            with self.assertRaisesRegex(RuntimeError, "missing_key"):
                source.fetch("ceramic glaze")

        urlopen.assert_not_called()

    def test_source_fetch_converts_response_to_last30days_shape(self) -> None:
        payload = {
            "videos": [
                {
                    "title": "Understanding Ceramic Glazes",
                    "channelName": "Clay Studio",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "videoId": "abc123",
                    "publishedTimeText": "1 month ago",
                    "duration": "08:10",
                    "viewCountText": "2,000 views",
                    "description": "raw long description should not be copied",
                }
            ],
            "shorts": [],
        }
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}

        source = ScrapeCreatorsYouTubeSearchSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})
        with mock.patch(
            "sources.youtube_source.request.urlopen",
            return_value=response,
        ) as urlopen:
            report = source.fetch("ceramic glaze")

        self.assertEqual(report["topic"], "ceramic glaze")
        self.assertIn("youtube", report["items_by_source"])
        item = report["items_by_source"]["youtube"][0]
        self.assertEqual(item["title"], "Understanding Ceramic Glazes")
        self.assertEqual(item["url"], "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(item["container"], "Clay Studio")
        self.assertEqual(item["engagement"]["views"], "2,000 views")
        self.assertEqual(item["metadata"]["provider"], "scrapecreators")
        self.assertEqual(item["metadata"]["platform"], "youtube")
        self.assertEqual(item["metadata"]["video_id"], "abc123")
        self.assertNotIn("description", str(report))
        self.assertNotIn("secret-token", str(report))
        evidence = collect_evidence("ceramic glaze", report)
        self.assertEqual(evidence[0].source, "youtube")
        self.assertEqual(evidence[0].subreddit, "clay studio")
        self.assertEqual(evidence[0].engagement, "2,000 views")

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

    def test_source_reads_dotenv_without_printing_secret(self) -> None:
        payload = {"videos": [], "shorts": []}
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        response.status = 200
        response.headers = {}

        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(
                "SCRAPECREATORS" + "_API_KEY=dotenv-secret\n",
                encoding="utf-8",
            )
            source = ScrapeCreatorsYouTubeSearchSource(env={}, dotenv_path=dotenv_path)
            with mock.patch(
                "sources.youtube_source.request.urlopen",
                return_value=response,
            ):
                report = source.fetch("ceramic glaze")

        self.assertEqual(report["items_by_source"]["youtube"], [])
        self.assertNotIn("dotenv-secret", str(report))

    def test_source_http_error_is_classified_without_secret(self) -> None:
        cases = [
            (401, b"bad key secret-token Authorization: Bearer abc123", "unauthorized_401"),
            (403, b"blocked", "forbidden_403"),
            (403, b"quota credits billing required", "quota_or_billing"),
            (429, b"too many requests", "rate_limited_429"),
            (402, b"quota credits billing required", "quota_or_billing"),
        ]
        source = ScrapeCreatorsYouTubeSearchSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})

        for code, body, expected in cases:
            with self.subTest(code=code):
                error = HTTPError(
                    url="https://api.scrapecreators.com/v1/youtube/search",
                    code=code,
                    msg="error",
                    hdrs={},
                    fp=io.BytesIO(body),
                )
                with mock.patch("sources.youtube_source.request.urlopen", side_effect=error):
                    with self.assertRaisesRegex(RuntimeError, expected) as caught:
                        source.fetch("ceramic glaze")

                self.assertNotIn("secret-token", str(caught.exception))
                self.assertNotIn("abc123", str(caught.exception))

    def test_source_timeout_and_url_errors_are_classified(self) -> None:
        source = ScrapeCreatorsYouTubeSearchSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})

        with mock.patch(
            "sources.youtube_source.request.urlopen",
            side_effect=socket.timeout("timed out"),
        ):
            with self.assertRaisesRegex(RuntimeError, "timeout"):
                source.fetch("ceramic glaze")

        with mock.patch(
            "sources.youtube_source.request.urlopen",
            side_effect=URLError("nodename nor servname provided"),
        ):
            with self.assertRaisesRegex(RuntimeError, "dns_error"):
                source.fetch("ceramic glaze")

    def test_source_bad_videos_shape_is_parse_error(self) -> None:
        response = io.BytesIO(json.dumps({"success": True, "videos": {}}).encode("utf-8"))
        response.status = 200
        response.headers = {}
        source = ScrapeCreatorsYouTubeSearchSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})

        with mock.patch(
            "sources.youtube_source.request.urlopen",
            return_value=response,
        ):
            with self.assertRaisesRegex(RuntimeError, "parse_error"):
                source.fetch("ceramic glaze")

    def test_source_non_object_json_is_parse_error(self) -> None:
        response = io.BytesIO(json.dumps(["not", "an", "object"]).encode("utf-8"))
        response.status = 200
        response.headers = {}
        source = ScrapeCreatorsYouTubeSearchSource(env={"SCRAPECREATORS_API_KEY": "secret-token"})

        with mock.patch(
            "sources.youtube_source.request.urlopen",
            return_value=response,
        ):
            with self.assertRaisesRegex(RuntimeError, "parse_error"):
                source.fetch("ceramic glaze")


if __name__ == "__main__":
    unittest.main()
