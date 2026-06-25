from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

import ceramic_report


class DataSourceSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ceramic_report.load_data_source_catalog(
            ceramic_report.DEFAULT_DATA_SOURCE_CATALOG_PATH
        )

    def test_auto_selects_mock_for_mock_mode(self) -> None:
        selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="mock",
            requested="auto",
        )

        self.assertEqual(selection.source_id, "mock")
        self.assertEqual(selection.status, "available")

    def test_auto_selects_reddit_last30days_for_live_mode(self) -> None:
        selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="live",
            requested="auto",
        )

        self.assertEqual(selection.source_id, "reddit_last30days")
        self.assertIn("scrapecreators_reddit", selection.fallback_sources)

    def test_planned_sources_are_reserved_not_silent_network(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            for source_id in [
                "scrapecreators_reddit",
                "youtube_future",
                "pinterest_future",
            ]:
                with self.subTest(source_id=source_id):
                    with self.assertRaisesRegex(ValueError, "已预留但尚未实现"):
                        ceramic_report.resolve_data_source(
                            self.catalog,
                            mode="live",
                            requested=source_id,
                        )

    def test_wrong_mode_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "不能用于 `--mode mock`"):
            ceramic_report.resolve_data_source(
                self.catalog,
                mode="mock",
                requested="reddit_last30days",
            )

    def test_run_state_records_selected_source_without_secret(self) -> None:
        selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="live",
            requested="auto",
        )
        control = ceramic_report.RunControl(
            state_file=Path("local_outputs/run_state.json"),
            cooldown_minutes=30,
            force=False,
        )

        with mock.patch.dict(os.environ, {"SCRAPECREATORS_API_KEY": "secret-token"}, clear=True):
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
                data_source=selection,
            )

        self.assertEqual(state["data_source"], "reddit_last30days")
        self.assertEqual(state["fallback_action"], "preserved_previous_report")
        self.assertIn("scrapecreators_reddit", state["fallback_sources"])
        self.assertNotIn("secret-token", str(state))


if __name__ == "__main__":
    unittest.main()
