"""Offline TrendSource backed by repository-local mock sample data.

MockSource replaces the V0.4.2 dependency on the external last30days-skill
for --mode mock. It reads data/mock_samples.json, so mock reports work on any
machine (Windows, macOS, CI) with zero configuration and zero network access.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MOCK_SAMPLES_PATH = PROJECT_ROOT / "data" / "mock_samples.json"


class MockSource:
    """TrendSource that serves canned last30days-shaped reports per topic."""

    def __init__(self, samples_path: Path | None = None) -> None:
        self.samples_path = (
            Path(samples_path) if samples_path is not None else DEFAULT_MOCK_SAMPLES_PATH
        )
        self._topics: dict[str, Any] | None = None

    def fetch(
        self,
        topic: str,
        *,
        recommended_subreddits: set[str] | None = None,
    ) -> dict[str, Any]:
        # recommended_subreddits is part of the TrendSource interface but the
        # mock data is static, so it is intentionally ignored here.
        entry = self._load_topics().get(topic)
        if entry is None:
            return self._fallback_report(topic)
        report = copy.deepcopy(entry)
        report.setdefault("topic", topic)
        return report

    def _load_topics(self) -> dict[str, Any]:
        if self._topics is None:
            if not self.samples_path.exists():
                raise FileNotFoundError(
                    "找不到 mock 样例数据文件。\n"
                    f"当前查找路径：{self.samples_path}\n"
                    "请确认仓库内的 data/mock_samples.json 存在；mock 模式不需要任何外部依赖。"
                )
            payload = json.loads(self.samples_path.read_text(encoding="utf-8"))
            topics = payload.get("topics")
            if not isinstance(topics, dict):
                raise ValueError(
                    f"mock 样例数据缺少顶层 \"topics\" 对象：{self.samples_path}"
                )
            self._topics = topics
        return self._topics

    @staticmethod
    def _fallback_report(topic: str) -> dict[str, Any]:
        # Topics added to config/ceramic_topics.json without sample data fall
        # back to the single placeholder item the external skill used to emit
        # in --mock mode, so the report still renders a V0.4.2-style row.
        return {
            "topic": topic,
            "items_by_source": {
                "reddit": [
                    {
                        "title": f"{topic} discussion thread",
                        "body": "",
                        "url": "https://reddit.com/r/example/comments/1",
                        "container": "example",
                        "engagement": {"score": 120, "num_comments": 48},
                        "local_rank_score": 1.0,
                    }
                ]
            },
        }
