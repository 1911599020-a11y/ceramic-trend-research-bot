from __future__ import annotations

import os
import subprocess
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

    def test_parse_args_does_not_allow_env_to_select_paid_source(self) -> None:
        with mock.patch.dict("os.environ", {"CERAMIC_DATA_SOURCE": "scrapecreators_reddit"}):
            with mock.patch("sys.argv", ["ceramic_report.py", "--mode", "live"]):
                args = ceramic_report.parse_args()

        self.assertEqual(args.data_source, "auto")

    def test_scrapecreators_is_explicit_available_source_not_default(self) -> None:
        auto_selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="live",
            requested="auto",
        )
        scrape_selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="live",
            requested="scrapecreators_reddit",
        )

        self.assertEqual(auto_selection.source_id, "reddit_last30days")
        self.assertEqual(scrape_selection.source_id, "scrapecreators_reddit")
        self.assertEqual(scrape_selection.status, "available")
        self.assertEqual(scrape_selection.kind, "api_provider")

    def test_scrapecreators_probe_topics_keep_relevance_rules(self) -> None:
        path = ceramic_report.PROJECT_ROOT / "config" / "scrapecreators_probe_topics.json"
        config = ceramic_report.load_config(path)
        relevance = ceramic_report.load_relevance_config(config)

        self.assertEqual(ceramic_report.load_topics(path), ["ceramic glaze"])
        self.assertIn("pottery", relevance.recommended_subreddits)
        self.assertIn("glaze", relevance.positive_terms)
        self.assertIn("ceramic glaze", {key.lower() for key in relevance.topic_rules})

    def test_run_live_script_forces_auto_data_source(self) -> None:
        script = (ceramic_report.PROJECT_ROOT / "scripts" / "run_live.sh").read_text(encoding="utf-8")

        self.assertIn("--data-source auto", script)

    def test_scrapecreators_live_script_defaults_to_single_topic_dry_run(self) -> None:
        result = subprocess.run(
            ["bash", "scripts/run_scrapecreators_live.sh", "--dry-run"],
            cwd=ceramic_report.PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout
        self.assertIn("Dry run", output)
        self.assertIn("--data-source scrapecreators_reddit", output)
        self.assertIn("config/scrapecreators_probe_topics.json", output)
        self.assertNotIn("config/ceramic_topics.json", output)

    def test_scrapecreators_live_script_requires_explicit_full_confirmation(self) -> None:
        result = subprocess.run(
            ["bash", "scripts/run_scrapecreators_live.sh", "--dry-run", "--confirm-full-api"],
            cwd=ceramic_report.PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout
        self.assertIn("已显式确认全量关键词运行", output)
        self.assertIn("--confirm-full-api", output)
        self.assertIn("config/ceramic_topics.json", output)
        self.assertNotIn("config/scrapecreators_probe_topics.json", output)

    def test_scrapecreators_default_python_full_topics_requires_confirmation(self) -> None:
        selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="live",
            requested="scrapecreators_reddit",
        )

        with self.assertRaisesRegex(ValueError, "confirm-full-api"):
            ceramic_report.validate_api_topic_scope(
                mode="live",
                data_source=selection,
                topics_path=ceramic_report.DEFAULT_TOPICS_PATH,
                confirm_full_api=False,
            )

    def test_scrapecreators_python_single_topic_does_not_require_full_confirmation(self) -> None:
        selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="live",
            requested="scrapecreators_reddit",
        )

        ceramic_report.validate_api_topic_scope(
            mode="live",
            data_source=selection,
            topics_path=ceramic_report.PROJECT_ROOT / "config" / "scrapecreators_probe_topics.json",
            confirm_full_api=False,
        )

    def test_scrapecreators_python_full_topics_allows_explicit_confirmation(self) -> None:
        selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="live",
            requested="scrapecreators_reddit",
        )

        ceramic_report.validate_api_topic_scope(
            mode="live",
            data_source=selection,
            topics_path=ceramic_report.DEFAULT_TOPICS_PATH,
            confirm_full_api=True,
        )

    def test_build_trend_source_supports_scrapecreators(self) -> None:
        selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="live",
            requested="scrapecreators_reddit",
        )

        source = ceramic_report.build_trend_source(
            selection,
            ceramic_report.DEFAULT_LAST30DAYS_SCRIPT,
        )

        self.assertEqual(source.__class__.__name__, "ScrapeCreatorsSource")

    def test_planned_sources_are_reserved_not_silent_network(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            for source_id in [
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

    def test_mock_run_state_does_not_check_scrapecreators_env(self) -> None:
        selection = ceramic_report.resolve_data_source(
            self.catalog,
            mode="mock",
            requested="auto",
        )
        control = ceramic_report.RunControl(
            state_file=Path("local_outputs/run_state.json"),
            cooldown_minutes=30,
            force=False,
        )

        with mock.patch("ceramic_report.local_scrapecreators_status_label") as status_label:
            state = ceramic_report.build_run_state(
                mode="mock",
                status="success",
                error_type="",
                output_path=Path("reports/report.md"),
                error_path=None,
                counts={
                    "evidence_count": 1,
                    "usable_evidence_count": 1,
                    "high_relevance_count": 1,
                    "edge_relevance_count": 0,
                    "low_relevance_count": 0,
                },
                control=control,
                data_source=selection,
            )

        status_label.assert_not_called()
        self.assertEqual(state["scrapecreators_fallback"], "not_checked_in_mock")


if __name__ == "__main__":
    unittest.main()
