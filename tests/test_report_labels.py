from __future__ import annotations

import unittest

from ceramic_report import (
    DataSourceSelection,
    Evidence,
    TopicRun,
    evidence_backed_tool_ideas,
    infer_pain_points,
    long_term_tool_ideas,
    trend_insights,
    suggested_keywords_for_topic,
    render_report,
)


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

    def test_youtube_channel_studio_does_not_create_business_tool_idea(self) -> None:
        evidence = Evidence(
            topic="ceramic glaze",
            source="youtube",
            title="Understanding Pottery Chapter 8 Glaze Chemistry Part 1",
            url="https://www.youtube.com/watch?v=fKJL4mRKfa8",
            snippet="channel: washington street studios. ceramic glaze chemistry.",
            engagement="77,111 views",
            subreddit="washington street studios",
            relevance_level="high",
            relevance_score=6,
            relevance_notes="YouTube 搜索结果已显式评分；命中陶瓷词：glaze, pottery；命中分类意图：glaze",
        )

        tool_ideas = evidence_backed_tool_ideas([evidence], mode="live")
        insights = trend_insights(
            ["ceramic glaze"],
            [evidence],
            mode="live",
            platform_label="YouTube",
        )

        self.assertTrue(any("釉色实验记录器" in idea for idea in tool_ideas))
        self.assertFalse(any("工作室定价与客户沟通表" in idea for idea in tool_ideas))
        self.assertFalse(any("经营类问题" in insight for insight in insights))

    def test_strong_business_signal_can_override_glaze_tool_idea(self) -> None:
        evidence = Evidence(
            topic="ceramic business",
            source="youtube",
            title="Pricing handmade pottery glaze tests for studio sales",
            url="https://www.youtube.com/watch?v=pricing123",
            snippet="customer orders, pricing, inventory, and ceramic glaze samples",
            engagement="1,500 views",
            subreddit="pottery business channel",
            relevance_level="high",
            relevance_score=7,
            relevance_notes="YouTube 搜索结果已显式评分；命中陶瓷词：pottery, glaze；命中经营意图：pricing, customer, order",
        )

        tool_ideas = evidence_backed_tool_ideas([evidence], mode="live")

        self.assertTrue(any("工作室定价与客户沟通表" in idea for idea in tool_ideas))
        self.assertFalse(any("釉色实验记录器" in idea for idea in tool_ideas))

    def test_handmade_pottery_pain_points_do_not_assume_sales_decision_tools(self) -> None:
        pain_points = infer_pain_points("handmade pottery")
        text = "\n".join(pain_points)

        self.assertIn("制作步骤", text)
        self.assertIn("器型", text)
        self.assertNotIn("销售", text)
        self.assertNotIn("决策工具", text)

    def test_youtube_making_video_uses_process_case_framing(self) -> None:
        evidence = Evidence(
            topic="handmade pottery",
            source="youtube",
            title="How to Make a Handmade Pottery Teapot — ASMR Version",
            url="https://www.youtube.com/watch?v=gAzaeA-ifNE",
            snippet="handmade pottery teapot clay throwing trimming process",
            engagement="3,541,587 views",
            subreddit="florian gadsby",
            relevance_level="high",
            relevance_score=6,
            relevance_notes="YouTube 搜索结果已显式评分；命中陶瓷词：handmade, pottery；命中分类意图：handmade, pottery",
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
            [TopicRun(topic="handmade pottery", report={}, evidence=[evidence])],
            "",
            mode="live",
            model_provider="rules",
            data_source=source,
            research_evidence=[],
        )

        self.assertIn("handmade pottery：制作过程拆解", text)
        self.assertIn("工艺复盘", text)
        self.assertNotIn("handmade pottery：把一个 YouTube 真实问题讲透", text)
        self.assertNotIn("销售之间缺少连续的决策工具", text)

    def test_strong_business_signal_is_not_overridden_by_handmade_terms(self) -> None:
        evidence = Evidence(
            topic="handmade pottery",
            source="youtube",
            title="Pricing handmade pottery for studio sales",
            url="https://www.youtube.com/watch?v=pricing456",
            snippet="customer orders, pricing, inventory, and handmade pottery sales",
            engagement="2,400 views",
            subreddit="pottery business channel",
            relevance_level="high",
            relevance_score=7,
            relevance_notes="YouTube 搜索结果已显式评分；命中陶瓷词：handmade, pottery；命中经营意图：pricing, customer, order",
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
            [TopicRun(topic="handmade pottery", report={}, evidence=[evidence])],
            "",
            mode="live",
            model_provider="rules",
            data_source=source,
            research_evidence=[],
        )

        self.assertIn("handmade pottery：把一个 YouTube 真实问题讲透", text)
        self.assertIn("定价、客户沟通或销售复盘", text)
        self.assertNotIn("handmade pottery：制作过程拆解", text)

    def test_long_term_business_tool_idea_uses_strong_business_signals(self) -> None:
        text = "\n".join(long_term_tool_ideas([]))

        self.assertIn("pricing / customer / order / sell", text)
        self.assertNotIn("business / studio 证据", text)

    def test_studio_keyword_suggestions_are_not_pricing_by_default(self) -> None:
        studio_terms = suggested_keywords_for_topic("ceramic studio")
        business_terms = suggested_keywords_for_topic("ceramic business")

        self.assertIn("ceramic studio workflow", studio_terms)
        self.assertNotIn("Etsy pottery pricing", studio_terms)
        self.assertIn("Etsy pottery pricing", business_terms)


if __name__ == "__main__":
    unittest.main()
