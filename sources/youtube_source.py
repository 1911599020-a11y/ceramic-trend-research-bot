"""ScrapeCreators YouTube Search TrendSource adapter.

V0.9 keeps YouTube explicit opt-in. This source only converts YouTube Search
results into the existing last30days-shaped contract. It does not request
transcripts, comments, video details, or keyframes.
"""

from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError

from sources.scrapecreators_source import (
    classify_http_error,
    configured_scrapecreators_env_var,
    effective_env,
    redact_secret,
)


SCRAPECREATORS_YOUTUBE_SEARCH_URL = "https://api.scrapecreators.com/v1/youtube/search"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_SUMMARY_LIMIT = 3
MAX_SUMMARY_LIMIT = 3
USER_AGENT = "ceramic-trend-research-bot/0.9.0"


def clamp_summary_limit(value: int) -> int:
    if value < 1:
        return 1
    return min(value, MAX_SUMMARY_LIMIT)


def safe_text(value: Any, max_length: int = 200) -> str:
    if isinstance(value, Mapping):
        for key in ("text", "simpleText", "title", "name"):
            if key in value:
                return safe_text(value.get(key), max_length=max_length)
        runs = value.get("runs")
        if isinstance(runs, list):
            return " ".join(
                safe_text(item, max_length=max_length)
                for item in runs
                if item
            ).strip()[:max_length]
    if isinstance(value, list):
        return " ".join(
            safe_text(item, max_length=max_length)
            for item in value
            if item
        ).strip()[:max_length]
    return str(value or "").strip()[:max_length]


def first_present(raw: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return ""


def channel_name(raw: Mapping[str, Any]) -> str:
    channel = raw.get("channel")
    if isinstance(channel, Mapping):
        value = first_present(channel, ("name", "title", "channelName", "channelTitle"))
        if value:
            return safe_text(value, max_length=120)
    return safe_text(
        first_present(raw, ("channelName", "channelTitle", "channel", "author")),
        max_length=120,
    )


def video_id(raw: Mapping[str, Any]) -> str:
    return safe_text(first_present(raw, ("videoId", "video_id", "id")), max_length=120)


def video_url(raw: Mapping[str, Any]) -> str:
    for key in ("url", "videoUrl", "link"):
        value = safe_text(raw.get(key), max_length=500)
        if value:
            return value
    vid = video_id(raw)
    if vid:
        return f"https://www.youtube.com/watch?v={vid}"
    return ""


def build_youtube_search_url(
    topic: str,
    *,
    upload_date: str,
    sort_by: str,
    item_type: str,
) -> str:
    params = parse.urlencode(
        {
            "query": topic,
            "uploadDate": upload_date,
            "sortBy": sort_by,
            "type": item_type,
        }
    )
    return f"{SCRAPECREATORS_YOUTUBE_SEARCH_URL}?{params}"


def classify_url_error(error: URLError) -> str:
    reason = str(error.reason).lower()
    if "timed out" in reason or "timeout" in reason:
        return "timeout"
    if (
        "name or service not known" in reason
        or "nodename nor servname" in reason
        or "name resolution" in reason
    ):
        return "dns_error"
    return "network_error"


def video_rank_score(raw: Mapping[str, Any], index: int) -> float:
    views = safe_text(first_present(raw, ("viewCountText", "views", "viewCount")), max_length=80)
    digits = "".join(ch for ch in views if ch.isdigit())
    try:
        view_score = min(float(digits or 0) / 1000, 1000)
    except (TypeError, ValueError):
        view_score = 0.0
    return max(0, 100 - index) + view_score


def video_snippet(
    *,
    channel: str,
    published: str,
    duration: str,
    views: str,
) -> str:
    parts = []
    if channel:
        parts.append(f"channel: {channel}")
    if published:
        parts.append(f"published: {published}")
    if duration:
        parts.append(f"duration: {duration}")
    if views:
        parts.append(f"views: {views}")
    return "; ".join(parts)


def convert_video(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    title = safe_text(first_present(raw, ("title", "headline")), max_length=200) or "(untitled)"
    channel = channel_name(raw)
    published = safe_text(
        first_present(raw, ("publishedTimeText", "published", "publishedAt", "date")),
        max_length=120,
    )
    duration = safe_text(first_present(raw, ("duration", "lengthText")), max_length=80)
    views = safe_text(first_present(raw, ("viewCountText", "views", "viewCount")), max_length=80)
    vid = video_id(raw)
    snippet = video_snippet(
        channel=channel,
        published=published,
        duration=duration,
        views=views,
    )
    return {
        "title": title,
        "body": snippet,
        "snippet": snippet,
        "url": video_url(raw),
        "container": channel,
        "subreddit": channel,
        "engagement": {"views": views},
        "local_rank_score": video_rank_score(raw, index),
        "metadata": {
            "provider": "scrapecreators",
            "platform": "youtube",
            "video_id": vid,
            "channel": channel,
            "published": published,
            "duration": duration,
        },
    }


def convert_payload_to_last30days(topic: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    videos = payload.get("videos", [])
    if not isinstance(videos, list):
        raise ValueError("ScrapeCreators YouTube response missing list field: videos")
    converted = [
        convert_video(raw, index)
        for index, raw in enumerate(videos[:MAX_SUMMARY_LIMIT])
        if isinstance(raw, Mapping)
    ]
    return {
        "topic": topic,
        "items_by_source": {"youtube": converted},
        "metadata": {
            "source_id": "scrapecreators_youtube_search",
            "provider": "scrapecreators",
            "platform": "youtube",
            "video_count_in_response": len(videos),
            "continuation_followed": False,
            "video_details_requested": False,
            "transcripts_requested": False,
            "comments_requested": False,
            "raw_response_saved": False,
        },
    }


class ScrapeCreatorsYouTubeSearchSource:
    """TrendSource backed by ScrapeCreators YouTube Search.

    The source is explicit opt-in only. It intentionally fetches only search
    result metadata and returns the same shape as other TrendSource adapters.
    """

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        dotenv_path: Path | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        upload_date: str = "this_month",
        sort_by: str = "relevance",
        item_type: str = "videos",
        summary_limit: int = DEFAULT_SUMMARY_LIMIT,
    ) -> None:
        self.env = effective_env(env, dotenv_path)
        self.timeout = timeout
        self.upload_date = upload_date
        self.sort_by = sort_by
        self.item_type = item_type
        self.summary_limit = clamp_summary_limit(summary_limit)

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
            report = convert_payload_to_last30days(topic, payload)
        except ValueError as error:
            raise RuntimeError(f"parse_error: {error}") from error
        items = report.get("items_by_source", {}).get("youtube", [])
        if isinstance(items, list):
            report["items_by_source"]["youtube"] = items[: self.summary_limit]
        return report

    def _request(self, topic: str, api_key: str) -> dict[str, Any]:
        req = request.Request(
            build_youtube_search_url(
                topic,
                upload_date=self.upload_date,
                sort_by=self.sort_by,
                item_type=self.item_type,
            ),
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
                raise ValueError("ScrapeCreators YouTube response JSON is not an object")
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
