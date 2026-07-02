from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from ceramic_report import (
    Evidence,
    LLMReviewStatus,
    MAX_LLM_REVIEW_ITEMS_PER_RUN,
    ReportLLMReview,
    TopicRun,
    build_llm_reviews_with_mock,
    evidence_to_llm_input,
    main,
    maybe_build_llm_reviews,
    render_report,
    select_llm_review_candidates,
)


def make_evidence(
    *,
    topic: str = "kiln firing",
    source: str = "reddit",
    title: str = "Cone 6 kiln firing glaze defect help",
    url: str = "https://example.com/post/1",
    snippet: str = "Electric kiln pinholes on stoneware test tile.",
    engagement: str = "12 comments",
    subreddit: str = "Pottery",
    level: str = "high",
    score: int = 8,
    notes: str = "命中 kiln、firing、glaze。",
) -> Evidence:
    return Evidence(
        topic=topic,
        source=source,
        title=title,
        url=url,
        snippet=snippet,
        engagement=engagement,
        subreddit=subreddit,
        relevance_level=level,
        relevance_score=score,
        relevance_notes=notes,
    )


def make_run(evidence: list[Evidence] | None = None) -> TopicRun:
    return TopicRun(
        topic="kiln firing",
        report={},
        evidence=evidence if evidence is not None else [make_evidence()],
    )


def make_review() -> ReportLLMReview:
    return ReportLLMReview(
        topic="kiln firing",
        source="reddit",
        container="Pottery",
        title="Cone 6 kiln firing glaze defect help",
        url="https://example.com/post/1",
        rule_level="high",
        rule_score=8,
        rule_notes="命中 kiln、firing、glaze。",
        llm_relevance="high",
        llm_intent_match="high",
        llm_evidence_type="pain_point",
        llm_can_support_trend=True,
        llm_is_noise=False,
        llm_confidence=86,
        llm_reason="真实陶瓷烧成问题，可作为趋势证据。",
        combined_level="high",
        combined_confidence=94,
        combined_reason="规则分和语义判断一致。",
    )


def deepseek_response(payload: dict[str, object]) -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            }
        ]
    }


class LLMReportIntegrationTests(unittest.TestCase):
    def test_render_report_without_llm_review_has_no_fake_deepseek_result(self) -> None:
        report = render_report(
            [make_run()],
            "# template",
            mode="mock",
            model_provider="rules",
        )

        self.assertNotIn("## DeepSeek 语义质检", report)
        self.assertIn("## 用户痛点假设", report)
        self.assertIn("尚未基于评论、字幕或长文本证据抽取", report)

    def test_render_report_includes_deepseek_review_section(self) -> None:
        report = render_report(
            [make_run()],
            "# template",
            mode="mock",
            model_provider="rules",
            llm_reviews=[make_review()],
            llm_review_status=LLMReviewStatus(
                status="success",
                message="DeepSeek 语义质检已完成：本轮复核 1 条证据。",
                reviewed_count=1,
                max_items=5,
            ),
        )

        self.assertIn("## DeepSeek 语义质检", report)
        self.assertIn("规则判断", report)
        self.assertIn("DeepSeek 判断", report)
        self.assertIn("真实陶瓷烧成问题", report)
        self.assertIn("r/Pottery", report)

    def test_render_report_includes_disabled_status_without_reviews(self) -> None:
        report = render_report(
            [make_run()],
            "# template",
            mode="mock",
            model_provider="rules",
            llm_review_status=LLMReviewStatus(
                status="disabled",
                message="DeepSeek 语义质检未开启；本报告仅使用规则评分。",
                max_items=5,
            ),
        )

        self.assertIn("## DeepSeek 语义质检", report)
        self.assertIn("本报告仅使用规则评分", report)
        self.assertNotIn("| 关键词 | 来源 | 标题 | 规则判断 |", report)

    def test_evidence_to_llm_input_preserves_context(self) -> None:
        youtube = make_evidence(
            source="youtube",
            title="Handmade ceramic mug process",
            snippet="channel snippet",
            subreddit="Studio Channel",
            level="edge",
            score=3,
            notes="YouTube 搜索结果已显式评分",
        )

        item = evidence_to_llm_input(youtube)

        self.assertEqual(item.source, "youtube")
        self.assertEqual(item.subreddit, "Studio Channel")
        self.assertEqual(item.body, "channel snippet")
        self.assertEqual(item.rule_level, "edge")
        self.assertEqual(item.rule_score, 3)
        self.assertEqual(item.rule_notes, "YouTube 搜索结果已显式评分")

    def test_select_llm_review_candidates_prioritizes_high_and_caps(self) -> None:
        high_items = [
            make_evidence(title=f"high {index}", level="high", score=8)
            for index in range(4)
        ]
        edge_items = [
            make_evidence(title=f"edge {index}", level="edge", score=3)
            for index in range(4)
        ]
        low_item = make_evidence(title="low", level="low", score=-3)

        selected = select_llm_review_candidates(
            [make_run(high_items + edge_items + [low_item])],
            max_items=5,
        )

        self.assertEqual(len(selected), 5)
        self.assertEqual([item.relevance_level for item in selected], ["high"] * 4 + ["edge"])
        self.assertNotIn(low_item, selected)

    def test_select_llm_review_candidates_handles_empty_runs(self) -> None:
        self.assertEqual(select_llm_review_candidates([make_run([])], max_items=5), [])

    def test_mock_reviews_combine_noise_to_low(self) -> None:
        noise = make_evidence(
            topic="AI ceramic design",
            title="Naruto gaming AI video with ceramic skin",
            snippet="anime gaming clip, not craft work",
            subreddit="gaming",
            level="high",
            score=8,
        )

        review = build_llm_reviews_with_mock([noise])[0]

        self.assertEqual(review.llm_relevance, "low")
        self.assertEqual(review.combined_level, "low")
        self.assertIn("噪音", review.combined_reason)

    def test_maybe_build_llm_reviews_disabled_returns_status(self) -> None:
        reviews, status = maybe_build_llm_reviews(
            [make_run()],
            env={"LLM_SCORING_ENABLED": "off"},
        )

        self.assertEqual(reviews, [])
        self.assertEqual(status.status, "disabled")
        self.assertIn("未开启", status.message)

    def test_maybe_build_llm_reviews_missing_key_returns_status(self) -> None:
        reviews, status = maybe_build_llm_reviews(
            [make_run()],
            env={"LLM_SCORING_ENABLED": "on"},
        )

        self.assertEqual(reviews, [])
        self.assertEqual(status.status, "missing_key")
        self.assertIn("未找到 API key", status.message)

    def test_maybe_build_llm_reviews_calls_deepseek_when_enabled(self) -> None:
        payload = deepseek_response(
            {
                "ceramic_relevance": "high",
                "keyword_intent_match": "high",
                "evidence_type": "pain_point",
                "can_support_trend": True,
                "is_noise": False,
                "confidence": 86,
                "reason": "真实陶瓷烧成问题。",
            }
        )
        with mock.patch("ceramic_report.request_deepseek_score", return_value=(payload, 200)) as request:
            reviews, status = maybe_build_llm_reviews(
                [make_run()],
                env={
                    "LLM_SCORING_ENABLED": "on",
                    "DEEPSEEK_API_KEY": "secret-token",
                },
            )

        self.assertEqual(status.status, "success")
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].llm_confidence, 86)
        self.assertEqual(request.call_count, 1)

    def test_maybe_build_llm_reviews_invalid_timeout_falls_back(self) -> None:
        payload = deepseek_response(
            {
                "ceramic_relevance": "high",
                "keyword_intent_match": "high",
                "evidence_type": "trend_signal",
                "can_support_trend": True,
                "is_noise": False,
                "confidence": 80,
                "reason": "真实陶瓷证据。",
            }
        )
        with mock.patch("ceramic_report.request_deepseek_score", return_value=(payload, 200)) as request:
            reviews, status = maybe_build_llm_reviews(
                [make_run()],
                env={
                    "LLM_SCORING_ENABLED": "on",
                    "DEEPSEEK_API_KEY": "secret-token",
                    "DEEPSEEK_TIMEOUT_SECONDS": "not-a-number",
                },
            )

        self.assertEqual(status.status, "success")
        self.assertEqual(len(reviews), 1)
        self.assertGreater(request.call_args.kwargs["timeout"], 0)

    def test_maybe_build_llm_reviews_bad_config_fails_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "bad_llm_config.json"
            config_path.write_text("{bad json", encoding="utf-8")

            reviews, status = maybe_build_llm_reviews(
                [make_run()],
                env={"LLM_SCORING_ENABLED": "on", "DEEPSEEK_API_KEY": "secret-token"},
                config_path=config_path,
            )

        self.assertEqual(reviews, [])
        self.assertEqual(status.status, "failure")
        self.assertEqual(status.error_type, "config_error")
        self.assertIn("配置读取失败", status.message)

    def test_maybe_build_llm_reviews_missing_prompt_fails_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_prompt = Path(tmp) / "missing_prompt.md"

            reviews, status = maybe_build_llm_reviews(
                [make_run()],
                env={"LLM_SCORING_ENABLED": "on", "DEEPSEEK_API_KEY": "secret-token"},
                prompt_path=missing_prompt,
            )

        self.assertEqual(reviews, [])
        self.assertEqual(status.status, "failure")
        self.assertEqual(status.error_type, "unknown_error")
        self.assertIn("本报告仅使用规则评分", status.message)

    def test_maybe_build_llm_reviews_has_code_level_cap(self) -> None:
        payload = deepseek_response(
            {
                "ceramic_relevance": "high",
                "keyword_intent_match": "high",
                "evidence_type": "trend_signal",
                "can_support_trend": True,
                "is_noise": False,
                "confidence": 80,
                "reason": "真实陶瓷证据。",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "switch_env_var": "LLM_SCORING_ENABLED",
                        "enabled_values": ["on", "true", "1", "yes"],
                        "provider": "deepseek",
                        "mode": "formal_report_review",
                        "model": "deepseek-chat",
                        "max_items_per_run": 500,
                        "output_path": "local_outputs/llm_scoring_probe.md",
                        "allowed_output_root": "local_outputs",
                    }
                ),
                encoding="utf-8",
            )
            evidence = [
                make_evidence(title=f"candidate {index}", url=f"https://example.com/{index}")
                for index in range(MAX_LLM_REVIEW_ITEMS_PER_RUN + 5)
            ]
            with mock.patch("ceramic_report.request_deepseek_score", return_value=(payload, 200)) as request:
                reviews, status = maybe_build_llm_reviews(
                    [make_run(evidence)],
                    env={"LLM_SCORING_ENABLED": "on", "DEEPSEEK_API_KEY": "secret-token"},
                    config_path=config_path,
                )

        self.assertEqual(status.status, "success")
        self.assertEqual(len(reviews), MAX_LLM_REVIEW_ITEMS_PER_RUN)
        self.assertEqual(request.call_count, MAX_LLM_REVIEW_ITEMS_PER_RUN)

    def test_maybe_build_llm_reviews_http_error_survives(self) -> None:
        error = HTTPError(
            url="https://api.deepseek.com/chat/completions",
            code=429,
            msg="error",
            hdrs={},
            fp=io.BytesIO(b"too many requests secret-token"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            error_path = Path(tmp) / "llm_error.md"
            with mock.patch("ceramic_report.DEFAULT_LLM_REVIEW_ERROR_FILE", error_path):
                with mock.patch("ceramic_report.request_deepseek_score", side_effect=error):
                    reviews, status = maybe_build_llm_reviews(
                        [make_run()],
                        env={
                            "LLM_SCORING_ENABLED": "on",
                            "DEEPSEEK_API_KEY": "secret-token",
                        },
                    )
            error_text = error_path.read_text(encoding="utf-8")

        self.assertEqual(reviews, [])
        self.assertEqual(status.status, "failure")
        self.assertEqual(status.error_type, "rate_limited_429")
        self.assertNotIn("secret-token", error_text)

    def test_main_writes_deepseek_section_when_enabled(self) -> None:
        payload = deepseek_response(
            {
                "ceramic_relevance": "high",
                "keyword_intent_match": "medium",
                "evidence_type": "trend_signal",
                "can_support_trend": True,
                "is_noise": False,
                "confidence": 78,
                "reason": "mock 样本中有真实陶瓷信号。",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.md"
            state = Path(tmp) / "state.json"
            argv = [
                "ceramic_report.py",
                "--mode",
                "mock",
                "--output",
                str(output),
                "--state-file",
                str(state),
                "--no-research-evidence",
            ]
            with mock.patch.dict(
                "os.environ",
                {
                    "KNOWLEDGE_STORE_ENABLED": "off",
                    "LLM_SCORING_ENABLED": "on",
                    "DEEPSEEK_API_KEY": "secret-token",
                },
            ):
                with mock.patch("ceramic_report.request_deepseek_score", return_value=(payload, 200)):
                    with mock.patch("sys.argv", argv):
                        exit_code = main()
            report = output.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("## DeepSeek 语义质检", report)
        self.assertIn("mock 样本中有真实陶瓷信号", report)


if __name__ == "__main__":
    unittest.main()
