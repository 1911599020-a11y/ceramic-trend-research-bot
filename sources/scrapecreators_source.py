"""ScrapeCreators readiness helpers and Reddit TrendSource adapter.

V0.6.4 keeps ScrapeCreators opt-in: the formal report flow can use it only
when the user explicitly selects --data-source scrapecreators_reddit. The
default live source remains reddit_last30days.
"""

from __future__ import annotations

import json
import os
import re
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError


SCRAPECREATORS_ENV_KEYS = ("SCRAPECREATORS_API_KEY", "SCRAPE_CREATORS_API_KEY")
SCRAPECREATORS_REDDIT_SEARCH_URL = "https://api.scrapecreators.com/v1/reddit/search"
DEFAULT_TIMEOUT_SECONDS = 30
USER_AGENT = "ceramic-trend-research-bot/0.6.4"


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


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def effective_env(
    env: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> dict[str, str]:
    values = dict(os.environ if env is None else env)
    if dotenv_path is not None:
        for key, value in parse_dotenv(dotenv_path).items():
            values.setdefault(key, value)
    return values


def redact_secret(text: str, secret: str) -> str:
    redacted = text.replace(secret, "[hidden]") if secret else text
    redacted = re.sub(r"(?i)(bearer)\s+[A-Za-z0-9._~+/=-]+", r"\1 [hidden]", redacted)
    redacted = re.sub(
        r"(?i)(x-api-key|api[_-]?key|authorization)(\s*[:=]\s*)[^\s,&]+",
        r"\1\2[hidden]",
        redacted,
    )
    return redacted


def classify_http_error(error: HTTPError, body: str) -> str:
    lowered = body.lower()
    if error.code == 401:
        return "unauthorized_401"
    if error.code == 429:
        return "rate_limited_429"
    if any(term in lowered for term in ("quota", "billing", "credit", "payment", "insufficient")):
        return "quota_or_billing"
    if error.code == 403:
        return "forbidden_403"
    return "network_error"


def classify_url_error(error: URLError) -> str:
    reason = str(error.reason).lower()
    if "timed out" in reason or "timeout" in reason:
        return "timeout"
    return "network_error"


def build_reddit_search_url(topic: str, *, sort: str, timeframe: str) -> str:
    params = parse.urlencode(
        {
            "query": topic,
            "sort": sort,
            "timeframe": timeframe,
            "trim": "true",
        }
    )
    return f"{SCRAPECREATORS_REDDIT_SEARCH_URL}?{params}"


def normalize_subreddit(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("r/"):
        text = text[2:]
    return text


def post_url(raw: Mapping[str, Any]) -> str:
    for key in ("url", "permalink", "link"):
        value = str(raw.get(key) or "").strip()
        if not value:
            continue
        if value.startswith("/"):
            return f"https://www.reddit.com{value}"
        return value
    return ""


def post_subreddit(raw: Mapping[str, Any]) -> str:
    return normalize_subreddit(raw.get("subreddit") or raw.get("subreddit_name_prefixed"))


def post_score(raw: Mapping[str, Any]) -> Any:
    return raw.get("score") if raw.get("score") is not None else raw.get("ups")


def post_comments(raw: Mapping[str, Any]) -> Any:
    for key in ("num_comments", "comments", "comment_count"):
        if raw.get(key) is not None:
            return raw.get(key)
    return None


def local_rank_score(raw: Mapping[str, Any], index: int) -> float:
    score = post_score(raw)
    comments = post_comments(raw)
    try:
        score_value = float(score or 0)
    except (TypeError, ValueError):
        score_value = 0.0
    try:
        comment_value = float(comments or 0)
    except (TypeError, ValueError):
        comment_value = 0.0
    return score_value + comment_value * 2 + max(0, 100 - index)


def convert_post(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    title = str(raw.get("title") or "(untitled)").strip()
    snippet = str(
        raw.get("selftext")
        or raw.get("body")
        or raw.get("snippet")
        or raw.get("description")
        or ""
    ).strip()
    return {
        "title": title,
        "body": snippet,
        "snippet": snippet,
        "url": post_url(raw),
        "container": post_subreddit(raw),
        "subreddit": post_subreddit(raw),
        "engagement": {
            "score": post_score(raw),
            "num_comments": post_comments(raw),
        },
        "local_rank_score": local_rank_score(raw, index),
        "metadata": {
            "provider": "scrapecreators",
            "created_utc": raw.get("created_utc") or raw.get("created"),
        },
    }


def convert_payload_to_last30days(topic: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    posts = payload.get("posts", [])
    if not isinstance(posts, list):
        raise ValueError("ScrapeCreators response missing list field: posts")
    converted = [
        convert_post(raw, index)
        for index, raw in enumerate(posts)
        if isinstance(raw, Mapping)
    ]
    return {
        "topic": topic,
        "items_by_source": {"reddit": converted},
        "metadata": {
            "source_id": "scrapecreators_reddit",
            "provider": "scrapecreators",
            "after": payload.get("after"),
            "post_count_in_response": len(posts),
        },
    }


class ScrapeCreatorsSource:
    """TrendSource backed by ScrapeCreators Reddit search.

    The source is not selected by auto mode. It is only used when the caller
    explicitly chooses scrapecreators_reddit.
    """

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        dotenv_path: Path | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        sort: str = "relevance",
        timeframe: str = "month",
    ) -> None:
        self.env = effective_env(env, dotenv_path)
        self.timeout = timeout
        self.sort = sort
        self.timeframe = timeframe

    def fetch(
        self,
        topic: str,
        *,
        recommended_subreddits: set[str] | None = None,
    ) -> dict[str, Any]:
        env_var = configured_scrapecreators_env_var(self.env)
        api_key = self.env.get(env_var, "") if env_var else ""
        if not api_key:
            raise RuntimeError(
                "missing_key: 未找到 SCRAPECREATORS_API_KEY。"
                "请确认本地 .env 或环境变量已配置；正式报告未更新。"
            )
        payload = self._request(topic, api_key)
        try:
            return convert_payload_to_last30days(topic, payload)
        except ValueError as error:
            raise RuntimeError(f"parse_error: {error}") from error

    def _request(self, topic: str, api_key: str) -> dict[str, Any]:
        req = request.Request(
            build_reddit_search_url(topic, sort=self.sort, timeframe=self.timeframe),
            headers={
                "x-api-key": api_key,
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            response = request.urlopen(req, timeout=self.timeout)
            body = response.read().decode("utf-8")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("ScrapeCreators response JSON is not an object")
            return payload
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            error_type = classify_http_error(error, body)
            safe_body = redact_secret(body[:500], api_key)
            raise RuntimeError(f"{error_type}: HTTP {error.code}: {safe_body}") from error
        except (socket.timeout, TimeoutError) as error:
            raise RuntimeError(f"timeout: {error}") from error
        except URLError as error:
            raise RuntimeError(f"{classify_url_error(error)}: {error}") from error
        except (json.JSONDecodeError, ValueError) as error:
            raise RuntimeError(f"parse_error: {error}") from error
