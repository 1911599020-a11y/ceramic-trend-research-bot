from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

import ceramic_report


class LiveFailureGuidanceTests(unittest.TestCase):
    def test_forbidden_guidance_mentions_missing_scrapecreators_without_secret(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            guidance = ceramic_report.live_error_guidance("forbidden_403")

        self.assertIn("没有检测到 `SCRAPECREATORS_API_KEY`", guidance)
        self.assertIn("ScrapeCreators Reddit API", guidance)

    def test_forbidden_guidance_mentions_configured_without_printing_secret(self) -> None:
        with mock.patch.dict(os.environ, {"SCRAPECREATORS_API_KEY": "dummy-token-for-test"}, clear=True):
            guidance = ceramic_report.live_error_guidance("forbidden_403")

        self.assertIn("已检测到 `SCRAPECREATORS_API_KEY`", guidance)
        self.assertNotIn("dummy-token-for-test", guidance)

    def test_run_state_records_scrapecreators_status_only(self) -> None:
        control = ceramic_report.RunControl(
            state_file=Path("local_outputs/run_state.json"),
            cooldown_minutes=30,
            force=False,
        )
        with mock.patch.dict(os.environ, {"SCRAPECREATORS_API_KEY": "dummy-token-for-test"}, clear=True):
            state = ceramic_report.build_run_state(
                mode="live",
                status="failed",
                error_type="forbidden_403",
                output_path=Path("reports/report.md"),
                error_path=Path("local_outputs/last_error.md"),
                counts={
                    "evidence_count": 0,
                    "usable_evidence_count": 0,
                    "high_relevance_count": 0,
                    "edge_relevance_count": 0,
                    "low_relevance_count": 0,
                },
                control=control,
            )

        self.assertEqual(state["scrapecreators_fallback"], "configured")
        self.assertNotIn("dummy-token-for-test", str(state))


if __name__ == "__main__":
    unittest.main()
