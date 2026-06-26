"""ScrapeCreators readiness helpers.

This module is intentionally readiness-only for the formal source layer. It centralizes the
API-key checks and the future TrendSource placeholder without making any HTTP
requests. V0.6.3's independent tiny probe lives under scripts/ and remains
outside the formal report pipeline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


SCRAPECREATORS_ENV_KEYS = ("SCRAPECREATORS_API_KEY", "SCRAPE_CREATORS_API_KEY")


@dataclass(frozen=True)
class ScrapeCreatorsReadiness:
    status: str
    configured_env_var: str
    detail: str
    can_attempt_api: bool


def configured_scrapecreators_env_var(
    env: Mapping[str, str] | None = None,
) -> str:
    values = os.environ if env is None else env
    for key in SCRAPECREATORS_ENV_KEYS:
        if values.get(key):
            return key
    return ""


def is_scrapecreators_configured(env: Mapping[str, str] | None = None) -> bool:
    return bool(configured_scrapecreators_env_var(env))


def scrapecreators_status_label(env: Mapping[str, str] | None = None) -> str:
    return "configured" if is_scrapecreators_configured(env) else "missing"


def check_scrapecreators_readiness(
    env: Mapping[str, str] | None = None,
) -> ScrapeCreatorsReadiness:
    configured_env_var = configured_scrapecreators_env_var(env)
    if configured_env_var:
        return ScrapeCreatorsReadiness(
            status="configured",
            configured_env_var=configured_env_var,
            detail=(
                f"{configured_env_var}=configured; key value is hidden. "
                "Readiness check does not validate quota or make ScrapeCreators requests. "
                "Use the tiny probe only with explicit confirmation."
            ),
            can_attempt_api=True,
        )
    return ScrapeCreatorsReadiness(
        status="missing",
        configured_env_var="",
        detail=(
            "missing; set SCRAPECREATORS_API_KEY later when you are ready for "
            "a key-backed Reddit fallback test."
        ),
        can_attempt_api=False,
    )


class ScrapeCreatorsSource:
    """Future TrendSource placeholder for ScrapeCreators Reddit.

    Keeping this class in the source layer makes the future integration point
    explicit, but fetch() is deliberately disabled so the formal report flow
    cannot silently consume API quota or send network requests.
    """

    def fetch(
        self,
        topic: str,
        *,
        recommended_subreddits: set[str] | None = None,
    ) -> dict[str, Any]:
        raise RuntimeError(
            "ScrapeCreatorsSource 目前仍是正式数据源预留接口，不会发起真实 API 请求。"
            "请继续使用 `--data-source auto`；如需验证 key，请使用独立 tiny probe。"
        )
