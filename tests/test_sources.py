"""Tests for the V0.5.0 data-source adapter layer.

Two contracts are pinned here:

1. MockSource output is digestible by the scoring/rendering pipeline — its
   reports flow through apply_relevance_ranking and collect_evidence exactly
   like the live last30days output did.
2. Last30DaysSource builds the subprocess command list item for item the same
   way the V0.4.2 run_last30days helper did. subprocess.run is mocked so no
   external skill or network is required.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ceramic_report import (
    DEFAULT_TOPICS_PATH,
    Evidence,
    apply_relevance_ranking,
    collect_evidence,
    load_config,
    load_relevance_config,
)
from sources.last30days_source import Last30DaysSource, build_query_plan
from sources.mock_source import MockSource


class MockSourceDigestionTests(unittest.TestCase):
    def setUp(self):
        self.source = MockSource()
        config = load_config(DEFAULT_TOPICS_PATH)
        self.relevance = load_relevance_config(config)

    def test_fetch_returns_last30days_shaped_report(self):
        report = self.source.fetch("pottery")
        self.assertIn("items_by_source", report)
        self.assertIn("reddit", report["items_by_source"])
        self.assertTrue(report["items_by_source"]["reddit"])
        # topic is filled in even if the sample entry omits it
        self.assertEqual(report["topic"], "pottery")

    def test_collect_evidence_consumes_raw_mock_output(self):
        report = self.source.fetch("pottery")
        evidence = collect_evidence("pottery", report)
        self.assertEqual(len(evidence), 2)
        self.assertTrue(all(isinstance(item, Evidence) for item in evidence))
        lead = evidence[0]
        self.assertEqual(lead.topic, "pottery")
        self.assertEqual(lead.subreddit, "pottery")
        self.assertEqual(lead.engagement, "286 upvotes, 41 comments")
        self.assertTrue(lead.url.startswith("https://"))
        # No ranking applied yet → collect_evidence uses its safe defaults.
        self.assertEqual(lead.relevance_level, "edge")
        self.assertEqual(lead.relevance_score, 0)

    def test_ranking_then_collect_produces_layers(self):
        report = self.source.fetch("pottery")
        report = apply_relevance_ranking(report, self.relevance, "pottery")
        evidence = collect_evidence("pottery", report)
        levels = {item.relevance_level for item in evidence}
        self.assertIn("high", levels)
        self.assertIn("low", levels)
        # The cat post is the intentional runoff sample for pottery.
        cat = next(item for item in evidence if "cat" in item.title.lower())
        self.assertEqual(cat.relevance_level, "low")
        self.assertLess(cat.relevance_score, 1)

    def test_unknown_topic_falls_back_to_single_item(self):
        report = self.source.fetch("totally unknown topic")
        evidence = collect_evidence("totally unknown topic", report)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].subreddit, "example")

    def test_recommended_subreddits_argument_is_ignored(self):
        without = self.source.fetch("pottery")
        with_arg = self.source.fetch("pottery", recommended_subreddits={"pottery"})
        self.assertEqual(without, with_arg)

    def test_fetch_returns_independent_copies(self):
        first = self.source.fetch("pottery")
        first["items_by_source"]["reddit"].clear()
        second = self.source.fetch("pottery")
        # Mutating one fetch must not corrupt the cached sample data.
        self.assertTrue(second["items_by_source"]["reddit"])


class Last30DaysCommandTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # assert_last30days_script only requires the path to exist.
        self.script = Path(self._tmp.name) / "last30days.py"
        self.script.write_text("# dummy last30days entry point\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    @staticmethod
    def _completed(payload, returncode=0, stderr=""):
        result = mock.Mock()
        result.returncode = returncode
        result.stdout = json.dumps(payload)
        result.stderr = stderr
        return result

    def test_live_command_is_item_for_item_identical(self):
        recommended = {"pottery", "ceramics"}
        with mock.patch("sources.last30days_source.subprocess.run") as run:
            run.return_value = self._completed({"items_by_source": {"reddit": []}})
            source = Last30DaysSource(self.script, mode="live")
            source.fetch("ceramic glaze", recommended_subreddits=recommended)

        command = run.call_args.args[0]
        expected = [
            sys.executable,
            str(self.script),
            "ceramic glaze",
            "--quick",
            "--emit=json",
            "--search=reddit",
            "--plan",
            json.dumps(build_query_plan("ceramic glaze", ["reddit"]), ensure_ascii=False),
            "--subreddits",
            "ceramics,pottery",  # sorted, comma-joined
        ]
        self.assertEqual(command, expected)
        # cwd / timeout / env handling moved verbatim from V0.4.2.
        self.assertEqual(run.call_args.kwargs["cwd"], str(self.script.parent))
        self.assertEqual(run.call_args.kwargs["timeout"], 60)
        env = run.call_args.kwargs["env"]
        self.assertIn("FROM_BROWSER", env)
        self.assertIn("LAST30DAYS_CONFIG_DIR", env)

    def test_live_command_without_recommended_omits_subreddits_flag(self):
        with mock.patch("sources.last30days_source.subprocess.run") as run:
            run.return_value = self._completed({"items_by_source": {"reddit": []}})
            Last30DaysSource(self.script, mode="live").fetch("pottery")

        command = run.call_args.args[0]
        self.assertNotIn("--subreddits", command)
        self.assertEqual(
            command,
            [
                sys.executable,
                str(self.script),
                "pottery",
                "--quick",
                "--emit=json",
                "--search=reddit",
                "--plan",
                json.dumps(build_query_plan("pottery", ["reddit"]), ensure_ascii=False),
            ],
        )

    def test_mock_command_inserts_mock_flag_and_youtube_source(self):
        with mock.patch("sources.last30days_source.subprocess.run") as run:
            run.return_value = self._completed({"items_by_source": {"reddit": []}})
            # recommended is supplied to prove mock mode ignores it.
            Last30DaysSource(self.script, mode="mock").fetch(
                "ceramic glaze", recommended_subreddits={"pottery"}
            )

        command = run.call_args.args[0]
        expected = [
            sys.executable,
            str(self.script),
            "ceramic glaze",
            "--mock",
            "--quick",
            "--emit=json",
            "--search=reddit,youtube",
            "--plan",
            json.dumps(
                build_query_plan("ceramic glaze", ["reddit", "youtube"]),
                ensure_ascii=False,
            ),
        ]
        self.assertEqual(command, expected)
        self.assertNotIn("--subreddits", command)

    def test_stdout_json_is_extracted_from_surrounding_noise(self):
        payload = {"items_by_source": {"reddit": [{"title": "hello"}]}}
        noisy = mock.Mock()
        noisy.returncode = 0
        noisy.stdout = "info log line\n" + json.dumps(payload) + "\ntrailing text"
        noisy.stderr = ""
        with mock.patch("sources.last30days_source.subprocess.run") as run:
            run.return_value = noisy
            result = Last30DaysSource(self.script, mode="live").fetch("pottery")
        self.assertEqual(result, payload)

    def test_nonzero_returncode_raises_runtimeerror(self):
        with mock.patch("sources.last30days_source.subprocess.run") as run:
            run.return_value = self._completed(
                {"items_by_source": {}}, returncode=1, stderr="boom"
            )
            with self.assertRaises(RuntimeError):
                Last30DaysSource(self.script, mode="live").fetch("pottery")


if __name__ == "__main__":
    unittest.main()
