"""Data-source adapter layer for ceramic-trend-research-bot.

V0.5.0 separates "where the evidence comes from" (this package) from "how it
is scored and rendered" (ceramic_report.py). Every source returns the same
last30days-shaped report dict, so the scoring and rendering layers never need
to know which backend produced it.

Available sources:

- MockSource          reads repository-local data/mock_samples.json; no
                      network, no external skill, works on Windows / CI.
- Last30DaysSource    shells out to the external last30days-skill exactly the
                      way ceramic_report.py V0.4.2 did; used by --mode live.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TrendSource(Protocol):
    """One topic in, one last30days-shaped report dict out.

    The returned dict must be parseable the same way extract_json output is:
    an "items_by_source" mapping of source name -> list of items, where each
    item may carry title, body/snippet, url, container/subreddit,
    engagement{score, num_comments, views, likes}, and local_rank_score.
    """

    def fetch(
        self,
        topic: str,
        *,
        recommended_subreddits: set[str] | None = None,
    ) -> dict[str, Any]: ...


from sources.last30days_source import Last30DaysSource  # noqa: E402
from sources.mock_source import MockSource  # noqa: E402

__all__ = ["TrendSource", "MockSource", "Last30DaysSource"]
