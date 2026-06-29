#!/usr/bin/env python3
"""Tiny opt-in ScrapeCreators YouTube Video Details probe.

This script stays outside the formal report pipeline. It picks one high-quality
YouTube URL from the existing local probe review, optionally calls the
ScrapeCreators Video/Short Details endpoint, and writes only sanitized output
under local_outputs/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib import parse, request
from urllib.error import HTTPError, URLError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sources.scrapecreators_source import (  # noqa: E402
    check_scrapecreators_readiness,
    configured_scrapecreators_env_var,
)


SOURCE_ID = "scrapecreators_youtube_video_details"
ENDPOINT = "https://api.scrapecreators.com/v1/youtube/video"
LOCAL_OUTPUTS_DIR = PROJECT_ROOT / "local_outputs"
DEFAULT_INPUT_FILE = LOCAL_OUTPUTS_DIR / "youtube_probe_review.json"
FALLBACK_INPUT_FILE = LOCAL_OUTPUTS_DIR / "youtube_probe.json"
DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_LANGUAGE = "en"
USER_AGENT = "ceramic-trend-research-bot/0.8.4"
DESCRIPTION_EXCERPT_MAX_CHARS = 320
EXPECTED_OUTPUTS = {
    "state-file": LOCAL_OUTPUTS_DIR / "youtube_video_probe_state.json",
    "output": LOCAL_OUTPUTS_DIR / "youtube_video_probe.json",
    "error-file": LOCAL_OUTPUTS_DIR / "youtube_video_probe_error.md",
}


@dataclass(frozen=True)
class ProbePaths:
    input_file: Path
    state_file: Path
    output_file: Path
    error_file: Path
    report_file: Path
    latest_file: Path
    archive_dir: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a tiny opt-in ScrapeCreators YouTube Video Details probe. "
            "Without --confirm-live-api this command does not call the network."
        )
    )
    parser.add_argument("--confirm-live-api", action="store_true")
    parser.add_argument("--input-file", default="local_outputs/youtube_probe_review.json")
    parser.add_argument("--url", default="")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--state-file", default="local_outputs/youtube_video_probe_state.json")
    parser.add_argument("--output", default="local_outputs/youtube_video_probe.json")
    parser.add_argument("--error-file", default="local_outputs/youtube_video_probe_error.md")
    parser.add_argument("--dotenv-file", default=None)

    # Test-only guard paths. The probe never writes these files.
    parser.add_argument("--report-file", default="reports/report.md", help=argparse.SUPPRESS)
    parser.add_argument("--latest-file", default="reports/latest.md", help=argparse.SUPPRESS)
    parser.add_argument("--archive-dir", default="reports/archive", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def project_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def validate_local_output_paths(paths: ProbePaths) -> str:
    allowed_inputs = {DEFAULT_INPUT_FILE.resolve(), FALLBACK_INPUT_FILE.resolve()}
    if paths.input_file.resolve() not in allowed_inputs:
        return "input-file 必须固定为 local_outputs/youtube_probe_review.json 或 local_outputs/youtube_probe.json"
    for label, path in (
        ("state-file", paths.state_file),
        ("output", paths.output_file),
        ("error-file", paths.error_file),
    ):
        if not is_within_directory(path, LOCAL_OUTPUTS_DIR):
            return f"{label} 必须位于 local_outputs/ 目录内：{path}"
        expected = EXPECTED_OUTPUTS[label]
        if path.resolve() != expected.resolve():
            return f"{label} 必须固定为 {expected.relative_to(PROJECT_ROOT)}"
    return ""


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


def effective_env(env: Mapping[str, str] | None, dotenv_file: str | None) -> dict[str, str]:
    values = dict(os.environ if env is None else env)
    dotenv_path: Path | None = None
    if dotenv_file:
        dotenv_path = project_path(dotenv_file)
    elif env is None:
        dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path:
        for key, value in parse_dotenv(dotenv_path).items():
            values.setdefault(key, value)
    return values


def configured_api_key(env: Mapping[str, str]) -> tuple[str, str]:
    env_var = configured_scrapecreators_env_var(env)
    return env_var, env.get(env_var, "") if env_var else ""


def redact_secret(text: str, secret: str) -> str:
    redacted = text.replace(secret, "[hidden]") if secret else text
    redacted = re.sub(r"(?i)(x-api-key|api[_-]?key|authorization)(\s*[:=]\s*)[^\s,&]+", r"\1\2[hidden]", redacted)
    redacted = re.sub(r"(?i)(bearer)\s+[A-Za-z0-9._~+/=-]+", r"\1 [hidden]", redacted)
    return redacted


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_error_markdown(
    path: Path,
    *,
    state: Mapping[str, Any],
    message: str,
    next_step: str,
    secret: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "# ScrapeCreators YouTube Video Details Probe Error",
            "",
            f"- 错误类型：{state.get('error_type', 'unknown_error')}",
            f"- 发生时间：{state.get('requested_at', '')}",
            f"- 视频链接：{state.get('video_url', '')}",
            f"- 是否已发起网络请求：{state.get('network_request_attempted', False)}",
            "- 保护动作：未覆盖 reports/report.md、reports/latest.md 或 reports/archive/",
            f"- 错误说明：{redact_secret(message, secret)}",
            f"- 建议下一步：{redact_secret(next_step, secret)}",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def base_state(
    *,
    status: str,
    error_type: str,
    video_url: str,
    network_request_attempted: bool,
    requested_at: str,
    key_status: str,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": status,
        "error_type": error_type,
        "video_url": video_url,
        "requested_at": requested_at,
        "network_request_attempted": network_request_attempted,
        "report_files_updated": False,
        "raw_response_saved": False,
        "details_requested": network_request_attempted,
        "transcripts_requested": False,
        "comments_requested": False,
        "report_paths": {
            "report": "reports/report.md",
            "latest": "reports/latest.md",
            "archive": "reports/archive/",
        },
        "key_status": key_status,
    }


def classify_http_error(error: HTTPError, body: str) -> str:
    body_lower = body.lower()
    if error.code == 401:
        return "unauthorized_401"
    if error.code == 402:
        return "quota_or_billing"
    if error.code == 404:
        return "not_found_404"
    if error.code == 429:
        return "rate_limited_429"
    if any(term in body_lower for term in ("quota", "billing", "credit", "payment", "insufficient")):
        return "quota_or_billing"
    if error.code == 403:
        return "forbidden_403"
    return "network_error"


def classify_url_error(error: URLError) -> str:
    reason = str(error.reason).lower()
    if "timed out" in reason or "timeout" in reason:
        return "timeout"
    if "name or service not known" in reason or "nodename nor servname" in reason:
        return "dns_error"
    return "network_error"


def next_step_for(error_type: str) -> str:
    return {
        "missing_input": "先运行 YouTube Search probe 和 review，生成 local_outputs/youtube_probe_review.json。",
        "invalid_input": "检查 local_outputs/youtube_probe_review.json 是否来自成功的 YouTube review。",
        "missing_url": "确认 YouTube probe review 中存在高相关视频 URL，或用 --url 显式传入一个 YouTube 视频链接。",
        "missing_key": "确认 .env 或系统环境变量里已配置 SCRAPECREATORS_API_KEY，然后再运行 video details tiny probe。",
        "unauthorized_401": "检查 ScrapeCreators API key 是否有效。",
        "forbidden_403": "检查账号权限、YouTube Video API 权限和 ScrapeCreators 后台状态。",
        "not_found_404": "检查视频链接是否可访问，或换一个 Search 高相关结果再试。",
        "rate_limited_429": "已被限流，请等待后再试，不要连续重复请求。",
        "quota_or_billing": "检查 ScrapeCreators credits、套餐或账单状态。",
        "dns_error": "当前运行环境无法解析 API 域名，请检查网络、代理或 DNS。",
        "timeout": "检查网络或代理状态，稍后再试。",
        "network_error": "检查网络、DNS、代理或 API 服务状态。",
        "parse_error": "接口返回不是预期 JSON，需要对照官方文档确认响应格式。",
        "unknown_error": "保留错误文件后再排查，不要重复发起请求。",
    }.get(error_type, "保留错误文件后再排查，不要重复发起请求。")


def safe_text(value: Any, max_length: int = 300) -> str:
    if isinstance(value, Mapping):
        for key in ("text", "simpleText", "title", "name"):
            if key in value:
                return safe_text(value.get(key), max_length=max_length)
        runs = value.get("runs")
        if isinstance(runs, list):
            return " ".join(safe_text(item, max_length=max_length) for item in runs if item).strip()[:max_length]
    if isinstance(value, list):
        return " ".join(safe_text(item, max_length=max_length) for item in value if item).strip()[:max_length]
    return str(value or "").strip()[:max_length]


def first_present(raw: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return ""


def candidate_from_review(payload: Mapping[str, Any]) -> str:
    for row in payload.get("llm_results", []):
        if not isinstance(row, Mapping):
            continue
        if row.get("review_label") != "可作为 YouTube 趋势候选":
            continue
        sample = row.get("sample")
        if isinstance(sample, Mapping):
            url = safe_text(sample.get("url"), max_length=500)
            if url:
                return url
    for sample in payload.get("analysis", {}).get("samples", []):
        if isinstance(sample, Mapping):
            url = safe_text(sample.get("url"), max_length=500)
            if url:
                return url
    return ""


def candidate_from_search_probe(payload: Mapping[str, Any]) -> str:
    for video in payload.get("videos", []):
        if isinstance(video, Mapping):
            url = safe_text(video.get("url"), max_length=500)
            if url:
                return url
    return ""


def select_video_url(input_file: Path, explicit_url: str) -> str:
    if explicit_url.strip():
        return explicit_url.strip()
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("YouTube video input JSON is not an object")
    return candidate_from_review(payload) or candidate_from_search_probe(payload)


def build_request_url(video_url: str, language: str) -> str:
    params = {"url": video_url}
    language = language.strip()
    if language:
        params["language"] = language[:8]
    return f"{ENDPOINT}?{parse.urlencode(params)}"


def request_video_details(
    *,
    api_key: str,
    video_url: str,
    language: str,
    timeout: float,
) -> tuple[dict[str, Any], int, Mapping[str, str]]:
    req = request.Request(
        build_request_url(video_url, language),
        headers={
            "x-api-key": api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        method="GET",
    )
    response = request.urlopen(req, timeout=timeout)
    payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("ScrapeCreators YouTube Video response JSON is not an object")
    status_code = int(getattr(response, "status", 200) or 200)
    headers = getattr(response, "headers", {}) or {}
    return payload, status_code, headers


def sanitize_channel(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "id": safe_text(value.get("id"), max_length=120),
        "title": safe_text(value.get("title"), max_length=160),
        "handle": safe_text(value.get("handle"), max_length=120),
        "url": safe_text(value.get("url"), max_length=500),
    }


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sanitize_keywords(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [safe_text(item, max_length=80) for item in value[:10] if safe_text(item, max_length=80)]


def build_description_excerpt(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) <= DESCRIPTION_EXCERPT_MAX_CHARS:
        return ""
    without_urls = re.sub(r"(?i)\bhttps?://\S+|\bwww\.\S+", "[link removed]", raw)
    candidate = safe_text(without_urls, max_length=DESCRIPTION_EXCERPT_MAX_CHARS + 1)
    if len(candidate) <= DESCRIPTION_EXCERPT_MAX_CHARS:
        return ""
    return f"{candidate[:DESCRIPTION_EXCERPT_MAX_CHARS].rstrip()}... [truncated]"


def caption_track_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, list):
        return {"count": 0, "languages": []}
    languages: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        language = safe_text(item.get("languageCode"), max_length=20)
        if language and language not in languages:
            languages.append(language)
    return {"count": len(value), "languages": languages[:10]}


def sanitize_details(payload: Mapping[str, Any], source_video_url: str) -> dict[str, Any]:
    description = build_description_excerpt(payload.get("description"))
    return {
        "id": safe_text(first_present(payload, ("id", "videoId")), max_length=120),
        "url": safe_text(first_present(payload, ("url", "videoUrl")), max_length=500) or source_video_url,
        "type": safe_text(payload.get("type"), max_length=50),
        "title": safe_text(payload.get("title"), max_length=240),
        "thumbnail": safe_text(payload.get("thumbnail"), max_length=500),
        "publish_date": safe_text(first_present(payload, ("publishDate", "publishedTime")), max_length=120),
        "publish_date_text": safe_text(first_present(payload, ("publishDateText", "publishedTimeText")), max_length=120),
        "duration_ms": safe_int(payload.get("durationMs")),
        "duration_formatted": safe_text(first_present(payload, ("durationFormatted", "lengthText")), max_length=80),
        "view_count_text": safe_text(first_present(payload, ("viewCountText", "views")), max_length=80),
        "view_count_int": safe_int(first_present(payload, ("viewCountInt", "viewCount"))),
        "like_count_text": safe_text(payload.get("likeCountText"), max_length=80),
        "like_count_int": safe_int(payload.get("likeCountInt")),
        "comment_count_text": safe_text(payload.get("commentCountText"), max_length=80),
        "comment_count_int": safe_int(payload.get("commentCountInt")),
        "genre": safe_text(payload.get("genre"), max_length=120),
        "keywords": sanitize_keywords(payload.get("keywords")),
        "channel": sanitize_channel(payload.get("channel")),
        "description_excerpt": description,
        "description_char_count": len(str(payload.get("description") or "")),
        "description_links_count": len(payload.get("descriptionLinks", [])) if isinstance(payload.get("descriptionLinks"), list) else 0,
        "chapters_count": len(payload.get("chapters", [])) if isinstance(payload.get("chapters"), list) else 0,
        "caption_tracks": caption_track_summary(payload.get("captionTracks")),
        "watch_next_count": len(payload.get("watchNextVideos", [])) if isinstance(payload.get("watchNextVideos"), list) else 0,
    }


def response_shape_notes(payload: Mapping[str, Any]) -> list[str]:
    return [
        f"{key}: {'present' if key in payload else 'missing'}"
        for key in (
            "id",
            "url",
            "title",
            "description",
            "channel",
            "viewCountText",
            "likeCountText",
            "commentCountText",
            "durationFormatted",
            "captionTracks",
            "watchNextVideos",
        )
    ]


def success_summary(
    *,
    payload: Mapping[str, Any],
    video_url: str,
    language: str,
    status_code: int,
    requested_at: str,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "success",
        "endpoint": ENDPOINT,
        "video_url": video_url,
        "language": language,
        "requested_at": requested_at,
        "http_status": status_code,
        "details": sanitize_details(payload, video_url),
        "response_shape_notes": response_shape_notes(payload),
        "raw_response_saved": False,
        "description_full_saved": False,
        "description_links_saved": False,
        "caption_track_urls_saved": False,
        "watch_next_saved": False,
        "transcripts_requested": False,
        "comments_requested": False,
        "report_files_updated": False,
    }


def failure_summary(
    *,
    error_type: str,
    video_url: str,
    requested_at: str,
    network_request_attempted: bool,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "failure",
        "error_type": error_type,
        "video_url": video_url,
        "requested_at": requested_at,
        "network_request_attempted": network_request_attempted,
        "details": {},
        "raw_response_saved": False,
        "report_files_updated": False,
    }


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    allow_outside_local_outputs: bool = False,
) -> int:
    args = parse_args(argv)
    requested_at = utc_now_iso()
    paths = ProbePaths(
        input_file=project_path(args.input_file),
        state_file=project_path(args.state_file),
        output_file=project_path(args.output),
        error_file=project_path(args.error_file),
        report_file=project_path(args.report_file),
        latest_file=project_path(args.latest_file),
        archive_dir=project_path(args.archive_dir),
    )
    if not allow_outside_local_outputs:
        path_error = validate_local_output_paths(paths)
        if path_error:
            print("ScrapeCreators YouTube video details probe：输出路径不安全，未发起网络请求。")
            print(path_error)
            print("请使用默认 local_outputs/ 路径，避免误写正式报告或其他文件。")
            return 2

    try:
        video_url = select_video_url(paths.input_file, args.url)
    except FileNotFoundError as error:
        video_url = ""
        state = base_state(
            status="missing_input",
            error_type="missing_input",
            video_url=video_url,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status="unknown",
        )
        write_json(paths.state_file, state)
        write_json(
            paths.output_file,
            failure_summary(
                error_type="missing_input",
                video_url=video_url,
                requested_at=requested_at,
                network_request_attempted=False,
            ),
        )
        write_error_markdown(
            paths.error_file,
            state=state,
            message=str(error),
            next_step=next_step_for("missing_input"),
        )
        print("ScrapeCreators YouTube video details probe：未找到输入文件，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0
    except (json.JSONDecodeError, ValueError) as error:
        video_url = ""
        state = base_state(
            status="invalid_input",
            error_type="invalid_input",
            video_url=video_url,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status="unknown",
        )
        write_json(paths.state_file, state)
        write_json(
            paths.output_file,
            failure_summary(
                error_type="invalid_input",
                video_url=video_url,
                requested_at=requested_at,
                network_request_attempted=False,
            ),
        )
        write_error_markdown(
            paths.error_file,
            state=state,
            message=str(error),
            next_step=next_step_for("invalid_input"),
        )
        print("ScrapeCreators YouTube video details probe：输入不是有效 probe 结果，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0

    values = effective_env(env, args.dotenv_file)
    readiness = check_scrapecreators_readiness(values)
    env_var, api_key = configured_api_key(values)

    if not video_url:
        state = base_state(
            status="missing_url",
            error_type="missing_url",
            video_url=video_url,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status=readiness.status,
        )
        write_json(paths.state_file, state)
        write_json(
            paths.output_file,
            failure_summary(
                error_type="missing_url",
                video_url=video_url,
                requested_at=requested_at,
                network_request_attempted=False,
            ),
        )
        write_error_markdown(
            paths.error_file,
            state=state,
            message="没有找到可用于 video details probe 的 YouTube URL。",
            next_step=next_step_for("missing_url"),
        )
        print("ScrapeCreators YouTube video details probe：没有视频 URL，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0

    if not args.confirm_live_api:
        state = base_state(
            status="not_confirmed",
            error_type="not_confirmed",
            video_url=video_url,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status=readiness.status,
        )
        write_json(paths.state_file, state)
        print("ScrapeCreators YouTube video details probe：未发起网络请求。")
        print("如需真实小测试，请显式添加 --confirm-live-api。")
        print(f"候选视频：{video_url}")
        print(f"状态已写入：{paths.state_file}")
        return 0

    if not readiness.can_attempt_api or not api_key:
        state = base_state(
            status="missing_key",
            error_type="missing_key",
            video_url=video_url,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status=readiness.status,
        )
        write_json(paths.state_file, state)
        write_json(
            paths.output_file,
            failure_summary(
                error_type="missing_key",
                video_url=video_url,
                requested_at=requested_at,
                network_request_attempted=False,
            ),
        )
        write_error_markdown(
            paths.error_file,
            state=state,
            message="未找到 SCRAPECREATORS_API_KEY。没有发起网络请求。",
            next_step=next_step_for("missing_key"),
        )
        print("ScrapeCreators YouTube video details probe：未找到 API key，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0

    try:
        payload, status_code, _headers = request_video_details(
            api_key=api_key,
            video_url=video_url,
            language=args.language,
            timeout=args.timeout,
        )
        summary = success_summary(
            payload=payload,
            video_url=video_url,
            language=args.language,
            status_code=status_code,
            requested_at=requested_at,
        )
        state = base_state(
            status="success",
            error_type="",
            video_url=video_url,
            network_request_attempted=True,
            requested_at=requested_at,
            key_status="configured",
        )
        state["configured_env_var"] = env_var
        state["detail_id"] = summary["details"].get("id", "")
        write_json(paths.output_file, summary)
        write_json(paths.state_file, state)
        print("ScrapeCreators YouTube video details probe 成功。")
        print(f"结果摘要已写入：{paths.output_file}")
        print("正式报告未更新。")
        return 0
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        error_type = classify_http_error(error, body)
        message = f"HTTP {error.code}: {redact_secret(body[:500], api_key)}"
    except (socket.timeout, TimeoutError) as error:
        error_type = "timeout"
        message = str(error)
    except URLError as error:
        error_type = classify_url_error(error)
        message = str(error)
    except (json.JSONDecodeError, ValueError) as error:
        error_type = "parse_error"
        message = str(error)
    except Exception as error:  # pragma: no cover - safety net
        error_type = "unknown_error"
        message = str(error)

    state = base_state(
        status="failure",
        error_type=error_type,
        video_url=video_url,
        network_request_attempted=True,
        requested_at=requested_at,
        key_status="configured",
    )
    state["configured_env_var"] = env_var
    write_json(paths.state_file, state)
    write_json(
        paths.output_file,
        failure_summary(
            error_type=error_type,
            video_url=video_url,
            requested_at=requested_at,
            network_request_attempted=True,
        ),
    )
    write_error_markdown(
        paths.error_file,
        state=state,
        message=message,
        next_step=next_step_for(error_type),
        secret=api_key,
    )
    print("ScrapeCreators YouTube video details probe 失败。")
    print("正式报告未更新。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
