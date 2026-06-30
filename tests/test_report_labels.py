from __future__ import annotations

import unittest

from ceramic_report import DataSourceSelection, Evidence, TopicRun, render_report


class ReportLabelTests(unittest.TestCase):
    def test_youtube_evidence_uses_channel_labels_not_subreddit_labels(self) -> None:
        evidence = Evidence(
            topic="ceramic glaze",
            source="youtube",
            title="Cone 6 ceramic glaze tests",
            url="https://www.youtube.com/watch?v=abc123",
            snippet="ceramic glaze clay kiln",
            engagement="2,000 views",
            subreddit="clay studio",
            relevance_level="high",
            relevance_score=7,
            relevance_notes="YouTube 搜索结果已显式评分；命中陶瓷词：ceramic, glaze",
        )
        source = DataSourceSelection(
            requested="scrapecreators_youtube_search",
            source_id="scrapecreators_youtube_search",
            label="ScrapeCreators YouTube Search API",
            mode="live",
            status="available",
            kind="api_provider",
            description="explicit opt-in",
            fallback_sources=["mock"],
        )

        text = render_report(
            [TopicRun(topic="ceramic glaze", report={}, evidence=[evidence])],
            "",
            mode="live",
            model_provider="rules",
            data_source=source,
            research_evidence=[],
        )

        self.assertIn("YouTube", text)
        self.assertIn("YouTube 频道 clay studio", text)
        self.assertIn("有 YouTube 高相关证据支撑的选题", text)
        self.assertNotIn("r/clay studio", text)
        self.assertNotIn("真实 Reddit 热点", text)
        self.assertNotIn("有 Reddit 高相关证据支撑的选题", text)
        self.assertNotIn("YouTube、Pinterest、GitHub 等来源尚未接入", text)


if __name__ == "__main__":
    unittest.main()
