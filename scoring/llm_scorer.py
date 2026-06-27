"""Design-only LLM scoring contracts.

V0.6.7 does not call any external model API. This module defines the data
contract and a deterministic mock scorer so V0.6.8 can add a tiny live probe
without touching the existing rule-based report flow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any


VALID_RELEVANCE = {"high", "edge", "low"}
VALID_INTENT_MATCH = {"high", "medium", "low"}
VALID_EVIDENCE_TYPES = {
    "trend_signal",
    "pain_point",
    "content_idea",
    "tool_idea",
    "noise",
    "background",
}


@dataclass(frozen=True)
class LLMScoringConfig:
    enabled: bool
    switch_env_var: str
    enabled_values: frozenset[str]
    provider: str
    mode: str
    model: str
    max_items_per_run: int
    output_path: str
    allowed_output_root: str


@dataclass(frozen=True)
class LLMScoringInput:
    topic: str
    title: str
    subreddit: str = ""
    body: str = ""
    url: str = ""
    source: str = "reddit"
    rule_level: str = ""
    rule_score: int = 0
    rule_notes: str = ""


@dataclass(frozen=True)
class LLMScoringResult:
    ceramic_relevance: str
    keyword_intent_match: str
    evidence_type: str
    can_support_trend: bool
    is_noise: bool
    confidence: int
    reason: str
    provider: str = "mock"


@dataclass(frozen=True)
class CombinedScoringResult:
    level: str
    confidence: int
    reason: str


def load_llm_scoring_config(path: Path) -> LLMScoringConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return LLMScoringConfig(
        enabled=bool(payload.get("enabled", False)),
        switch_env_var=str(payload.get("switch_env_var", "LLM_SCORING_ENABLED")).strip()
        or "LLM_SCORING_ENABLED",
        enabled_values=frozenset(
            str(value).strip().lower()
            for value in payload.get("enabled_values", ["on", "true", "1", "yes"])
            if str(value).strip()
        ),
        provider=str(payload.get("provider", "none")).strip() or "none",
        mode=str(payload.get("mode", "design_only")).strip() or "design_only",
        model=str(payload.get("model", "")).strip(),
        max_items_per_run=int(payload.get("max_items_per_run", 5)),
        output_path=str(payload.get("output_path", "local_outputs/llm_scoring_probe.md")),
        allowed_output_root=str(payload.get("allowed_output_root", "local_outputs")),
    )


def build_llm_scoring_prompt(template_text: str, item: LLMScoringInput) -> str:
    context = {
        "topic": item.topic,
        "title": item.title,
        "subreddit": item.subreddit or "n/a",
        "body": item.body or "n/a",
        "url": item.url or "n/a",
        "source": item.source,
        "rule_level": item.rule_level or "n/a",
        "rule_score": str(item.rule_score),
        "rule_notes": item.rule_notes or "n/a",
    }
    return Template(template_text).safe_substitute(context)


def parse_llm_score_payload(payload: dict[str, Any]) -> LLMScoringResult:
    relevance = require_choice(payload, "ceramic_relevance", VALID_RELEVANCE)
    intent = require_choice(payload, "keyword_intent_match", VALID_INTENT_MATCH)
    evidence_type = require_choice(payload, "evidence_type", VALID_EVIDENCE_TYPES)
    reason = str(payload.get("reason", "")).strip()
    if not reason:
        raise ValueError("LLM scoring result requires a non-empty reason.")
    return LLMScoringResult(
        ceramic_relevance=relevance,
        keyword_intent_match=intent,
        evidence_type=evidence_type,
        can_support_trend=bool(payload.get("can_support_trend", False)),
        is_noise=bool(payload.get("is_noise", False)),
        confidence=clamp_int(payload.get("confidence", 0), 0, 100),
        reason=reason,
        provider=str(payload.get("provider", "unknown")).strip() or "unknown",
    )


def require_choice(payload: dict[str, Any], key: str, valid: set[str]) -> str:
    value = str(payload.get(key, "")).strip().lower()
    if value not in valid:
        raise ValueError(f"{key} must be one of {sorted(valid)}.")
    return value


def clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


class MockLLMScorer:
    """Deterministic stand-in for the future API-backed scorer."""

    ceramic_terms = {
        "ceramic",
        "ceramics",
        "pottery",
        "clay",
        "glaze",
        "kiln",
        "firing",
        "porcelain",
        "stoneware",
        "bisque",
        "studio",
    }
    noise_terms = {
        "anime",
        "cosplay",
        "gaming",
        "fnaf",
        "naruto",
        "makati",
        "keyboard",
        "outfit",
    }
    pain_terms = {
        "problem",
        "issue",
        "help",
        "crack",
        "defect",
        "warp",
        "pricing",
        "sell",
        "customer",
    }
    topic_intent_terms = {
        "ai ceramic design": {"ai", "generative", "computational", "prompt", "pattern", "digital"},
        "ceramic business": {"business", "sell", "pricing", "etsy", "customer", "studio", "marketing"},
        "kiln firing": {"kiln", "firing", "cone", "temperature", "bisque", "glaze", "defect"},
    }

    def score(self, item: LLMScoringInput) -> LLMScoringResult:
        text = " ".join([item.topic, item.title, item.subreddit, item.body]).lower()
        ceramic_hits = sorted(term for term in self.ceramic_terms if term in text)
        noise_hits = sorted(term for term in self.noise_terms if term in text)
        intent_terms = self.topic_intent_terms.get(item.topic.lower(), set())
        intent_hits = sorted(term for term in intent_terms if term in text)
        pain_hits = sorted(term for term in self.pain_terms if term in text)

        is_noise = bool(noise_hits and len(ceramic_hits) <= 1)
        if is_noise:
            return LLMScoringResult(
                ceramic_relevance="low",
                keyword_intent_match="low",
                evidence_type="noise",
                can_support_trend=False,
                is_noise=True,
                confidence=82,
                reason=f"疑似跑偏样本，命中噪音词：{', '.join(noise_hits)}。",
                provider="mock",
            )

        if ceramic_hits and intent_hits:
            evidence_type = "pain_point" if pain_hits else "trend_signal"
            return LLMScoringResult(
                ceramic_relevance="high",
                keyword_intent_match="high",
                evidence_type=evidence_type,
                can_support_trend=True,
                is_noise=False,
                confidence=78,
                reason=(
                    f"同时命中陶瓷信号（{', '.join(ceramic_hits[:3])}）"
                    f"和关键词意图（{', '.join(intent_hits[:3])}）。"
                ),
                provider="mock",
            )

        if ceramic_hits:
            return LLMScoringResult(
                ceramic_relevance="high",
                keyword_intent_match="low" if intent_terms else "medium",
                evidence_type="background",
                can_support_trend=False,
                is_noise=False,
                confidence=61,
                reason="内容与陶瓷有关，但暂未匹配当前关键词的具体意图。",
                provider="mock",
            )

        return LLMScoringResult(
            ceramic_relevance="low",
            keyword_intent_match="low",
            evidence_type="background",
            can_support_trend=False,
            is_noise=False,
            confidence=55,
            reason="未发现足够陶瓷领域信号。",
            provider="mock",
        )


def combine_rule_and_llm(
    *,
    rule_level: str,
    rule_score: int,
    llm_result: LLMScoringResult,
) -> CombinedScoringResult:
    if llm_result.is_noise or llm_result.ceramic_relevance == "low":
        return CombinedScoringResult(
            level="low",
            confidence=max(40, llm_result.confidence),
            reason=f"LLM 将样本判为噪音或低相关：{llm_result.reason}",
        )

    if (
        rule_level == "high"
        and llm_result.ceramic_relevance == "high"
        and llm_result.keyword_intent_match in {"high", "medium"}
        and llm_result.can_support_trend
    ):
        return CombinedScoringResult(
            level="high",
            confidence=min(95, max(70, llm_result.confidence + min(rule_score, 10))),
            reason=f"规则分和语义判断一致，可作为趋势证据：{llm_result.reason}",
        )

    if llm_result.ceramic_relevance == "high":
        return CombinedScoringResult(
            level="edge",
            confidence=max(50, llm_result.confidence),
            reason=f"陶瓷相关但证据强度不足，作为补充观察：{llm_result.reason}",
        )

    return CombinedScoringResult(
        level="low",
        confidence=llm_result.confidence,
        reason=f"证据不足：{llm_result.reason}",
    )
