"""Scoring tests for score_reddit_item.

These pin the V0.4.2 scoring contract that V0.5.0 froze:

- exclude penalty: any跑偏词命中扣 ``5 + min(4, 命中数)`` 分（封顶 -9）；
- required gate: 命中 topic_rule 但缺 required_terms 时，若仍有陶瓷正向词则
  ``score = min(score, 4)``（最多压到边缘），否则再 ``score -= 2``；
- level thresholds: ``score >= 5`` → high，``score >= 1`` → edge，否则 low。

Configs are hand-built (not loaded from config/ceramic_topics.json) so each
assertion isolates exactly one rule and the arithmetic stays auditable.
"""

from __future__ import annotations

import unittest

from ceramic_report import RelevanceConfig, score_reddit_item


def make_config(*, recommended=None, positive=None, exclude=None, topic_rules=None):
    """Build a RelevanceConfig the same shape load_relevance_config produces."""
    return RelevanceConfig(
        recommended_subreddits=set(recommended or []),
        positive_terms=[term.lower() for term in (positive or [])],
        exclude_terms=[term.lower() for term in (exclude or [])],
        topic_rules=topic_rules or {},
    )


class ExcludePenaltyTests(unittest.TestCase):
    def test_single_exclude_term_costs_six(self):
        config = make_config(exclude=["anime"])
        score, level, _ = score_reddit_item({"title": "anime fan art"}, config)
        # 5 base penalty + min(4, 1) = 6
        self.assertEqual(score, -6)
        self.assertEqual(level, "low")

    def test_two_exclude_terms_cost_seven(self):
        config = make_config(exclude=["anime", "gaming"])
        score, _, _ = score_reddit_item({"title": "anime gaming crossover"}, config)
        # 5 + min(4, 2) = 7
        self.assertEqual(score, -7)

    def test_exclude_penalty_caps_at_nine(self):
        config = make_config(exclude=["anime", "gaming", "cats", "naruto", "fnaf"])
        score, _, _ = score_reddit_item(
            {"title": "anime gaming cats naruto fnaf"}, config
        )
        # 5 + min(4, 5) = 9 — the second term caps at four extra points
        self.assertEqual(score, -9)

    def test_exclude_overrides_positive_signal(self):
        config = make_config(positive=["ceramic"], exclude=["cats"])
        score, level, _ = score_reddit_item({"title": "ceramic and cats"}, config)
        # +1 positive, +2 title emphasis, then -6 exclude = -3
        self.assertEqual(score, -3)
        self.assertEqual(level, "low")

    def test_topic_rule_exclude_terms_merge_with_global(self):
        # A跑偏词 from the topic rule and one from the global list dedupe to two
        # distinct hits → 5 + min(4, 2) = 7 penalty.
        config = make_config(
            exclude=["anime"],
            topic_rules={"demo": {"exclude_terms": ["gaming"]}},
        )
        score, _, _ = score_reddit_item(
            {"title": "anime gaming post"}, config, topic="demo"
        )
        # base 0, no positive (so required-missing branch subtracts 2 as well):
        #   exclude -7, required-missing-no-positive -2 = -9
        self.assertEqual(score, -9)


class RequiredGateTests(unittest.TestCase):
    def test_missing_required_caps_high_item_to_four(self):
        config = make_config(
            recommended=["ceramics"],
            positive=["ceramic", "glaze"],
            topic_rules={
                "ai ceramic design": {
                    "required_terms": ["ai", "prompt"],
                    "boost_terms": [],
                    "exclude_terms": [],
                }
            },
        )
        item = {
            "title": "ceramic glaze tips",
            "body": "glaze",
            "container": "r/Ceramics",
        }
        score, level, _ = score_reddit_item(item, config, topic="AI ceramic design")
        # Without the gate this would be +4 +2 +2 = 8 (high); the missing
        # required terms pin it to min(8, 4) = 4 → edge.
        self.assertEqual(score, 4)
        self.assertEqual(level, "edge")

    def test_missing_required_and_no_positive_subtracts_two(self):
        config = make_config(
            positive=["ceramic"],
            topic_rules={
                "ai ceramic design": {
                    "required_terms": ["ai"],
                    "boost_terms": [],
                    "exclude_terms": [],
                }
            },
        )
        item = {"title": "random unrelated post"}
        score, level, _ = score_reddit_item(item, config, topic="AI ceramic design")
        self.assertEqual(score, -2)
        self.assertEqual(level, "low")

    def test_boost_applies_after_the_cap(self):
        config = make_config(
            recommended=["ceramics"],
            positive=["ceramic", "glaze"],
            topic_rules={
                "ai ceramic design": {
                    "required_terms": ["nonexistentreq"],
                    "boost_terms": ["parametric"],
                    "exclude_terms": [],
                }
            },
        )
        item = {
            "title": "ceramic glaze parametric study",
            "body": "glaze",
            "container": "r/Ceramics",
        }
        score, level, _ = score_reddit_item(item, config, topic="AI ceramic design")
        # Cap pins the running total to 4, then the boost term adds +1 → 5 → high.
        self.assertEqual(score, 5)
        self.assertEqual(level, "high")

    def test_present_required_terms_add_up(self):
        config = make_config(
            positive=["ceramic"],
            topic_rules={
                "ai ceramic design": {
                    "required_terms": ["ai", "prompt"],
                    "boost_terms": ["midjourney"],
                    "exclude_terms": [],
                }
            },
        )
        item = {"title": "ceramic ai prompt with midjourney"}
        score, level, _ = score_reddit_item(item, config, topic="AI ceramic design")
        # +1 positive, +2 title emphasis, +2 required (2 hits), +1 boost = 6
        self.assertEqual(score, 6)
        self.assertEqual(level, "high")


class LevelThresholdTests(unittest.TestCase):
    def test_score_five_is_high(self):
        # +4 recommended, +1 positive only in body (no title emphasis) = 5
        config = make_config(recommended=["ceramics"], positive=["clay"])
        item = {"title": "my post", "body": "clay work", "container": "r/Ceramics"}
        score, level, _ = score_reddit_item(item, config)
        self.assertEqual(score, 5)
        self.assertEqual(level, "high")

    def test_score_four_is_edge(self):
        # +4 recommended only — one below the high threshold
        config = make_config(recommended=["ceramics"], positive=["clay"])
        item = {"title": "my post", "body": "", "container": "r/Ceramics"}
        score, level, _ = score_reddit_item(item, config)
        self.assertEqual(score, 4)
        self.assertEqual(level, "edge")

    def test_score_one_is_edge(self):
        # +1 positive only in body — the lower boundary of edge
        config = make_config(positive=["clay"])
        item = {"title": "post", "body": "clay"}
        score, level, _ = score_reddit_item(item, config)
        self.assertEqual(score, 1)
        self.assertEqual(level, "edge")

    def test_score_zero_is_low(self):
        config = make_config(positive=["clay"])
        item = {"title": "post", "body": "nothing relevant here"}
        score, level, _ = score_reddit_item(item, config)
        self.assertEqual(score, 0)
        self.assertEqual(level, "low")


if __name__ == "__main__":
    unittest.main()
