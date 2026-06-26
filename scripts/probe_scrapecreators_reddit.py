#!/usr/bin/env python3
"""Tiny opt-in ScrapeCreators Reddit probe.

This script is deliberately separate from the formal report pipeline. It only
checks whether one tiny ScrapeCreators Reddit request can work, and it writes
sanitized output under local_outputs/.
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


SOURCE_ID = "scrapecreators_reddit"
ENDPOINT = "https://api.scrapecreators.com/v1/reddit/search"
LOCAL_OUTPUTS_DIR = PROJECT_ROOT / "local_outputs"
DEFAULT_TOPIC = "ceramic glaze"
DEFAULT_LIMIT = 1
MAX_LIMIT = 3
DEFAULT_TIMEOUT_SECONDS = 12
USER_AGENT = "ceramic-trend-research-bot/0.6.3"


@dataclass(frozen=True)
class ProbePaths:
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
            "Run a tiny opt-in ScrapeCreators Reddit probe. Without "
            "--confirm-live-api this command does not call the network."
        )
    )
    parser.add_argument("--confirm-live-api", action="store_true")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--sort", default="relevance", choices=["relevance", "new", "top", "comment_count"])
    parser.add_argument("--timeframe", default="month", choices=["all", "day", "week", "month", "year"])
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--state-file", default="local_outputs/scrapecreators_probe_state.json")
    parser.add_argument("--output", default="local_outputs/scrapecreators_probe.json")
    parser.add_argument("--error-file", default="local_outputs/scrapecreators_probe_error.md")
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
    for label, path in (
        ("state-file", paths.state_file),
        ("output", paths.output_file),
        ("error-file", paths.error_file),
    ):
        if not is_within_directory(path, LOCAL_OUTPUTS_DIR):
            return f"{label} 必须位于 local_outputs/ 目录内：{path}"
    return ""


def clamp_limit(value: int) -> int:
    if value < 1:
        return 1
    return min(value, MAX_LIMIT)


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
    env: Mapping[str, str] | None,
    dotenv_file: str | None,
) -> dict[str, str]:
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
    safe_message = redact_secret(message, secret)
    safe_next_step = redact_secret(next_step, secret)
    text = "\n".join(
        [
            "# ScrapeCreators Tiny Probe Error",
            "",
            f"- 错误类型：{state.get('error_type', 'unknown_error')}",
            f"- 发生时间：{state.get('requested_at', '')}",
            f"- 搜索主题：{state.get('topic', '')}",
            f"- 保存上限：{state.get('limit', '')}",
            f"- 是否已发起网络请求：{state.get('network_request_attempted', False)}",
            "- 保护动作：未覆盖 reports/report.md、reports/latest.md 或 reports/archive/",
            f"- 错误说明：{safe_message}",
            f"- 建议下一步：{safe_next_step}",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def base_state(
    *,
    status: str,
    error_type: str,
    topic: str,
    limit: int,
    network_request_attempted: bool,
    requested_at: str,
    key_status: str,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": status,
        "error_type": error_type,
        "topic": topic,
        "limit": limit,
        "requested_at": requested_at,
        "network_request_attempted": network_request_attempted,
        "report_files_updated": False,
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
    if error.code == 403:
        return "forbidden_403"
    if error.code == 429:
        return "rate_limited_429"
    if any(term in body_lower for term in ("quota", "billing", "credit", "payment", "insufficient")):
        return "quota_or_billing"
    return "network_error"


def classify_url_error(error: URLError) -> str:
    reason = str(error.reason).lower()
    if "timed out" in reason or "timeout" in reason:
        return "timeout"
    return "network_error"


def build_request_url(topic: str, sort: str, timeframe: str) -> str:
    # ScrapeCreators documents query/sort/timeframe/trim for this endpoint.
    # The CLI limit only controls the sanitized local summary; no undocumented
    # limit parameter is sent to the provider.
    params = parse.urlencode(
        {
            "query": topic,
            "sort": sort,
            "timeframe": timeframe,
            "trim": "true",
        }
    )
    return f"{ENDPOINT}?{params}"


def request_scrapecreators(
    *,
    api_key: str,
    topic: str,
    sort: str,
    timeframe: str,
    timeout: float,
) -> tuple[dict[str, Any], int, Mapping[str, str]]:
    req = request.Request(
        build_request_url(topic, sort, timeframe),
        headers={
            "x-api-key": api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        method="GET",
    )
    response = request.urlopen(req, timeout=timeout)
    body = response.read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("ScrapeCreators response JSON is not an object")
    status_code = int(getattr(response, "status", 200) or 200)
    headers = getattr(response, "headers", {}) or {}
    return payload, status_code, headers


def sanitize_posts(payload: Mapping[str, Any], limit: int) -> tuple[list[dict[str, Any]], int]:
    posts_raw = payload.get("posts", [])
    if not isinstance(posts_raw, list):
        return [], 0

    posts: list[dict[str, Any]] = []
    for raw in posts_raw[:limit]:
        if not isinstance(raw, Mapping):
            continue
        posts.append(
            {
                "title": raw.get("title", ""),
                "subreddit": raw.get("subreddit", ""),
                "url": raw.get("url") or raw.get("permalink") or "",
                "score": raw.get("score"),
                "comments": raw.get("num_comments", raw.get("comments")),
                "created_utc": raw.get("created_utc"),
            }
        )
    return posts, len(posts_raw)


def response_shape_notes(payload: Mapping[str, Any]) -> list[str]:
    notes: list[str] = []
    for key in ("success", "posts", "after"):
        notes.append(f"{key}: {'present' if key in payload else 'missing'}")
    if not isinstance(payload.get("posts", []), list):
        notes.append("posts is not a list")
    return notes


def success_summary(
    *,
    payload: Mapping[str, Any],
    topic: str,
    limit: int,
    sort: str,
    timeframe: str,
    status_code: int,
    requested_at: str,
) -> dict[str, Any]:
    posts, post_count = sanitize_posts(payload, limit)
    return {
        "source_id": SOURCE_ID,
        "status": "success",
        "endpoint": ENDPOINT,
        "topic": topic,
        "sort": sort,
        "timeframe": timeframe,
        "limit": limit,
        "requested_at": requested_at,
        "http_status": status_code,
        "post_count_in_response": post_count,
        "summarized_count": len(posts),
        "posts": posts,
        "response_shape_notes": response_shape_notes(payload),
        "raw_response_saved": False,
        "report_files_updated": False,
    }


def failure_summary(
    *,
    error_type: str,
    topic: str,
    limit: int,
    requested_at: str,
    network_request_attempted: bool,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "failure",
        "error_type": error_type,
        "topic": topic,
        "limit": limit,
        "requested_at": requested_at,
        "network_request_attempted": network_request_attempted,
        "post_count_in_response": 0,
        "summarized_count": 0,
        "posts": [],
        "raw_response_saved": False,
        "report_files_updated": False,
        "note": "本次 probe 失败；请以 state/error 文件为准，正式报告未更新。",
    }


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    allow_outside_local_outputs: bool = False,
) -> int:
    args = parse_args(argv)
    topic = args.topic.strip() or DEFAULT_TOPIC
    limit = clamp_limit(args.limit)
    requested_at = utc_now_iso()
    paths = ProbePaths(
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
            print("ScrapeCreators tiny probe：输出路径不安全，未发起网络请求。")
            print(path_error)
            print("请使用默认 local_outputs/ 路径，避免误写正式报告或其他文件。")
            return 2

    values = effective_env(env, args.dotenv_file)
    readiness = check_scrapecreators_readiness(values)
    env_var, api_key = configured_api_key(values)

    if not args.confirm_live_api:
        state = base_state(
            status="not_confirmed",
            error_type="not_confirmed",
            topic=topic,
            limit=limit,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status=readiness.status,
        )
        write_json(paths.state_file, state)
        print("ScrapeCreators tiny probe：未发起网络请求。")
        print("如需真实小测试，请显式添加 --confirm-live-api。")
        print(f"状态已写入：{paths.state_file}")
        return 0

    if not readiness.can_attempt_api or not api_key:
        state = base_state(
            status="missing_key",
            error_type="missing_key",
            topic=topic,
            limit=limit,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status=readiness.status,
        )
        write_json(paths.state_file, state)
        write_error_markdown(
            paths.error_file,
            state=state,
            message="未找到 SCRAPECREATORS_API_KEY。没有发起网络请求。",
            next_step="确认 .env 或系统环境变量里已配置 SCRAPECREATORS_API_KEY，然后再运行 tiny probe。",
        )
        write_json(
            paths.output_file,
            failure_summary(
                error_type="missing_key",
                topic=topic,
                limit=limit,
                requested_at=requested_at,
                network_request_attempted=False,
            ),
        )
        print("ScrapeCreators tiny probe：未找到 API key，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0

    try:
        payload, status_code, _headers = request_scrapecreators(
            api_key=api_key,
            topic=topic,
            sort=args.sort,
            timeframe=args.timeframe,
            timeout=args.timeout,
        )
        summary = success_summary(
            payload=payload,
            topic=topic,
            limit=limit,
            sort=args.sort,
            timeframe=args.timeframe,
            status_code=status_code,
            requested_at=requested_at,
        )
        state = base_state(
            status="success",
            error_type="",
            topic=topic,
            limit=limit,
            network_request_attempted=True,
            requested_at=requested_at,
            key_status="configured",
        )
        state["configured_env_var"] = env_var
        state["post_count_in_response"] = summary["post_count_in_response"]
        state["summarized_count"] = summary["summarized_count"]
        write_json(paths.output_file, summary)
        write_json(paths.state_file, state)
        print("ScrapeCreators tiny probe 成功。")
        print(f"结果摘要已写入：{paths.output_file}")
        print("正式报告未更新。")
        return 0
    except HTTPError as error:
        body_bytes = error.read()
        body = body_bytes.decode("utf-8", errors="replace")
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

    next_steps = {
        "unauthorized_401": "检查 API key 是否有效，或是否需要重新生成 key。",
        "forbidden_403": "检查账号权限、接口权限和 ScrapeCreators 后台状态。",
        "rate_limited_429": "已被限流，请等待后再试，不要连续重复请求。",
        "quota_or_billing": "检查 ScrapeCreators 后台 credits、套餐或账单状态。",
        "timeout": "检查网络或代理状态，稍后再试。",
        "network_error": "检查网络、DNS、代理或 API 服务状态。",
        "parse_error": "接口返回不是预期 JSON，需要对照官方文档确认响应格式。",
        "unknown_error": "保留错误文件后再排查，不要重复发起请求。",
    }
    state = base_state(
        status="failure",
        error_type=error_type,
        topic=topic,
        limit=limit,
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
            topic=topic,
            limit=limit,
            requested_at=requested_at,
            network_request_attempted=True,
        ),
    )
    write_error_markdown(
        paths.error_file,
        state=state,
        message=message,
        next_step=next_steps.get(error_type, next_steps["unknown_error"]),
        secret=api_key,
    )
    print("ScrapeCreators tiny probe 失败。")
    print("正式报告未更新。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
