from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scoring.llm_scorer import (
    LLMScoringInput,
    MockLLMScorer,
    build_llm_scoring_prompt,
    combine_rule_and_llm,
    load_llm_scoring_config,
    parse_llm_score_payload,
)


class LLMScoringContractTests(unittest.TestCase):
    def test_config_is_design_only_and_disabled_by_default(self) -> None:
        config = load_llm_scoring_config(Path("config/llm_scoring.json"))

        self.assertFalse(config.enabled)
        self.assertEqual(config.provider, "deepseek")
        self.assertEqual(config.mode, "design_only")
        self.assertEqual(config.model, "deepseek-chat")
        self.assertEqual(config.switch_env_var, "LLM_SCORING_ENABLED")
        self.assertIn("on", config.enabled_values)
        self.assertEqual(config.output_path, "local_outputs/llm_scoring_probe.md")

    def test_prompt_includes_evidence_context(self) -> None:
        template = Path("prompts/llm_scoring_prompt.md").read_text(encoding="utf-8")
        prompt = build_llm_scoring_prompt(
            template,
            LLMScoringInput(
                topic="kiln firing",
                title="Cone 6 glaze defect after firing",
                subreddit="r/Pottery",
                rule_level="high",
                rule_score=8,
                rule_notes="命中 kiln 与 glaze",
            ),
        )

        self.assertIn("kiln firing", prompt)
        self.assertIn("Cone 6 glaze defect after firing", prompt)
        self.assertIn("只返回 JSON", prompt)
        self.assertIn("0 到 100 的整数百分制", prompt)

    def test_parse_llm_score_payload_validates_schema(self) -> None:
        result = parse_llm_score_payload(
            {
                "ceramic_relevance": "high",
                "keyword_intent_match": "medium",
                "evidence_type": "pain_point",
                "can_support_trend": True,
                "is_noise": False,
                "confidence": 120,
                "reason": "真实陶瓷烧成问题。",
            }
        )

        self.assertEqual(result.ceramic_relevance, "high")
        self.assertEqual(result.confidence, 100)
        self.assertTrue(result.can_support_trend)

    def test_parse_llm_score_payload_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            parse_llm_score_payload(
                {
                    "ceramic_relevance": "great",
                    "keyword_intent_match": "medium",
                    "evidence_type": "pain_point",
                    "reason": "bad enum",
                }
            )

    def test_mock_scorer_flags_noise(self) -> None:
        result = MockLLMScorer().score(
            LLMScoringInput(
                topic="AI ceramic design",
                title="Naruto gaming AI video with ceramic skin",
                subreddit="r/gaming",
            )
        )

        self.assertTrue(result.is_noise)
        self.assertEqual(result.ceramic_relevance, "low")
        self.assertFalse(result.can_support_trend)

    def test_mock_scorer_detects_intent_match(self) -> None:
        result = MockLLMScorer().score(
            LLMScoringInput(
                topic="kiln firing",
                title="Cone 6 kiln firing glaze defect help",
                subreddit="r/Pottery",
            )
        )

        self.assertEqual(result.ceramic_relevance, "high")
        self.assertEqual(result.keyword_intent_match, "high")
        self.assertTrue(result.can_support_trend)

    def test_combined_scoring_demotes_llm_noise(self) -> None:
        llm_result = MockLLMScorer().score(
            LLMScoringInput(
                topic="AI ceramic design",
                title="Naruto gaming AI video with ceramic skin",
                subreddit="r/gaming",
            )
        )
        combined = combine_rule_and_llm(
            rule_level="high",
            rule_score=8,
            llm_result=llm_result,
        )

        self.assertEqual(combined.level, "low")
        self.assertIn("噪音", combined.reason)

    def test_prompt_builder_can_use_external_template_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt.md"
            path.write_text("Topic=$topic Title=$title Score=$rule_score", encoding="utf-8")
            prompt = build_llm_scoring_prompt(
                path.read_text(encoding="utf-8"),
                LLMScoringInput(topic="ceramic business", title="Etsy pottery pricing", rule_score=4),
            )

        self.assertEqual(prompt, "Topic=ceramic business Title=Etsy pottery pricing Score=4")


if __name__ == "__main__":
    unittest.main()
