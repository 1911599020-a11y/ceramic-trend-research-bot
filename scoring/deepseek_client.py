"""Reusable DeepSeek client helpers for report-path semantic review."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping
from urllib import parse, request
from urllib.error import HTTPError, URLError

from .llm_scorer import LLMScoringResult, parse_llm_score_payload

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_TIMEOUT_SECONDS = 30.0
DEEPSEEK_USER_AGENT = "ceramic-trend-research-bot/0.9.7"
ALLOWED_DEEPSEEK_HOSTS = {"api.deepseek.com"}


def validate_deepseek_base_url(base_url: str) -> str:
    parsed = parse.urlparse(base_url)
    if parsed.scheme != "https" or parsed.netloc not in ALLOWED_DEEPSEEK_HOSTS:
        return "DeepSeek base URL 必须是 https://api.deepseek.com，避免把 API key 发到非官方域名。"
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        return "DeepSeek base URL 必须固定为 https://api.deepseek.com，不能包含 path、query 或 fragment。"
    return ""


def endpoint_for(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def request_deepseek_score(
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    timeout: float,
) -> tuple[dict[str, Any], int]:
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是陶瓷趋势情报证据评分助手。请严格输出 JSON。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }
    req = request.Request(
        endpoint_for(base_url),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": DEEPSEEK_USER_AGENT,
        },
        method="POST",
    )
    response = request.urlopen(req, timeout=timeout)
    payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("DeepSeek response JSON is not an object")
    status_code = int(getattr(response, "status", 200) or 200)
    return payload, status_code


def parse_deepseek_score_response(payload: Mapping[str, Any]) -> LLMScoringResult:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("DeepSeek response missing choices")
    first = choices[0]
    if not isinstance(first, Mapping):
        raise ValueError("DeepSeek response choice is not an object")
    message = first.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("DeepSeek response missing message")
    content = str(message.get("content") or "").strip()
    if not content:
        raise ValueError("DeepSeek response message content is empty")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("DeepSeek scoring content JSON is not an object")
    result_payload = dict(parsed)
    result_payload["provider"] = "deepseek"
    return parse_llm_score_payload(result_payload)


def classify_http_error(error: HTTPError, body: str) -> str:
    lowered = body.lower()
    if error.code == 401:
        return "unauthorized_401"
    if error.code == 402:
        return "quota_or_billing"
    if error.code == 429:
        return "rate_limited_429"
    if any(
        term in lowered
        for term in ("quota", "billing", "credit", "payment", "insufficient", "balance")
    ):
        return "quota_or_billing"
    if error.code == 403:
        return "forbidden_403"
    return "network_error"


def classify_url_error(error: URLError) -> str:
    reason = str(error.reason).lower()
    if "timed out" in reason or "timeout" in reason:
        return "timeout"
    return "network_error"


def redact_secret(text: str, secret: str) -> str:
    redacted = text.replace(secret, "[hidden]") if secret else text
    redacted = re.sub(
        r"(?i)(api[_-]?key|authorization)(\s*[:=]\s*)[^\s,&]+",
        r"\1\2[hidden]",
        redacted,
    )
    redacted = re.sub(r"(?i)(bearer)\s+[A-Za-z0-9._~+/=-]+", r"\1 [hidden]", redacted)
    return redacted
