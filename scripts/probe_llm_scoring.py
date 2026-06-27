#!/usr/bin/env python3
"""Tiny opt-in DeepSeek scoring probe.

This script is deliberately separate from the formal report pipeline. It only
checks whether a very small set of ceramic evidence samples can be scored by
DeepSeek, and it writes sanitized output under local_outputs/.
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
from string import Template
from typing import Any, Mapping
from urllib import parse
from urllib import request
from urllib.error import HTTPError, URLError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scoring.llm_scorer import (  # noqa: E402
    LLMScoringInput,
    LLMScoringResult,
    build_llm_scoring_prompt,
    load_llm_scoring_config,
    parse_llm_score_payload,
)


SOURCE_ID = "deepseek_llm_scoring"
LOCAL_OUTPUTS_DIR = PROJECT_ROOT / "local_outputs"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_SAMPLE_COUNT = 3
MAX_SAMPLE_COUNT = 5
USER_AGENT = "ceramic-trend-research-bot/0.6.8"
EXPECTED_OUTPUTS = {
    "state-file": LOCAL_OUTPUTS_DIR / "llm_scoring_probe_state.json",
    "output": LOCAL_OUTPUTS_DIR / "llm_scoring_probe.md",
    "json-output": LOCAL_OUTPUTS_DIR / "llm_scoring_probe.json",
    "error-file": LOCAL_OUTPUTS_DIR / "llm_scoring_probe_error.md",
}
ALLOWED_DEEPSEEK_HOSTS = {"api.deepseek.com"}


@dataclass(frozen=True)
class ProbePaths:
    state_file: Path
    output_file: Path
    json_file: Path
    error_file: Path
    report_file: Path
    latest_file: Path
    archive_dir: Path


SAMPLE_ITEMS: tuple[LLMScoringInput, ...] = (
    LLMScoringInput(
        topic="kiln firing",
        title="Cone 6 glaze defect after firing, need help diagnosing pinholes",
        subreddit="r/Pottery",
        body="Electric kiln, cone 6, pinholes on stoneware test tile.",
        url="https://example.com/kiln-firing",
        rule_level="high",
        rule_score=8,
        rule_notes="命中 kiln、firing、glaze、cone。",
    ),
    LLMScoringInput(
        topic="AI ceramic design",
        title="Naruto gaming AI video with ceramic skin",
        subreddit="r/gaming",
        body="A general AI anime video, not a pottery workflow.",
        url="https://example.com/noise",
        rule_level="high",
        rule_score=6,
        rule_notes="规则命中 AI 和 ceramic，但 subreddit 与语境跑偏。",
    ),
    LLMScoringInput(
        topic="ceramic business",
        title="How do you price handmade ceramic mugs on Etsy?",
        subreddit="r/Pottery",
        body="Trying to include clay, glaze, firing, labor, packaging and customer expectations.",
        url="https://example.com/business",
        rule_level="high",
        rule_score=9,
        rule_notes="命中 pricing、Etsy、customer、handmade。",
    ),
    LLMScoringInput(
        topic="AI ceramic design",
        title="Using generative AI to explore surface patterns for ceramic mugs",
        subreddit="r/Ceramics",
        body="The design is later transferred to underglaze tests on clay.",
        url="https://example.com/ai-ceramic",
        rule_level="high",
        rule_score=8,
        rule_notes="命中 AI、design、pattern、ceramic。",
    ),
    LLMScoringInput(
        topic="ceramic glaze",
        title="What paint can I use to seal an unfired clay pot?",
        subreddit="r/crafts",
        body="Beginner craft question, not a fired ceramic glaze workflow.",
        url="https://example.com/edge",
        rule_level="edge",
        rule_score=2,
        rule_notes="命中 clay，但未命中 glaze firing intent。",
    ),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a tiny opt-in DeepSeek LLM scoring probe. Without "
            "--confirm-live-api this command does not call the network."
        )
    )
    parser.add_argument("--confirm-live-api", action="store_true")
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--config", default="config/llm_scoring.json")
    parser.add_argument("--prompt", default="prompts/llm_scoring_prompt.md")
    parser.add_argument("--state-file", default="local_outputs/llm_scoring_probe_state.json")
    parser.add_argument("--output", default="local_outputs/llm_scoring_probe.md")
    parser.add_argument("--json-output", default="local_outputs/llm_scoring_probe.json")
    parser.add_argument("--error-file", default="local_outputs/llm_scoring_probe_error.md")
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
        ("json-output", paths.json_file),
        ("error-file", paths.error_file),
    ):
        if not is_within_directory(path, LOCAL_OUTPUTS_DIR):
            return f"{label} 必须位于 local_outputs/ 目录内：{path}"
        expected = EXPECTED_OUTPUTS[label]
        if path.resolve() != expected.resolve():
            return f"{label} 必须固定为 {expected.relative_to(PROJECT_ROOT)}"
    return ""


def validate_deepseek_base_url(base_url: str) -> str:
    parsed = parse.urlparse(base_url)
    if parsed.scheme != "https" or parsed.netloc not in ALLOWED_DEEPSEEK_HOSTS:
        return "DeepSeek base URL 必须是 https://api.deepseek.com，避免把 API key 发到非官方域名。"
    return ""


def clamp_sample_count(value: int) -> int:
    if value < 1:
        return 1
    return min(value, MAX_SAMPLE_COUNT)


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


def configured_deepseek_key(env: Mapping[str, str]) -> str:
    return env.get("DEEPSEEK_API_KEY", "")


def redact_secret(text: str, secret: str) -> str:
    redacted = text.replace(secret, "[hidden]") if secret else text
    redacted = re.sub(r"(?i)(api[_-]?key|authorization)(\s*[:=]\s*)[^\s,&]+", r"\1\2[hidden]", redacted)
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
            "# DeepSeek LLM Scoring Probe Error",
            "",
            f"- 错误类型：{state.get('error_type', 'unknown_error')}",
            f"- 发生时间：{state.get('requested_at', '')}",
            f"- 样本数量：{state.get('sample_count', '')}",
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
    model: str,
    sample_count: int,
    network_request_attempted: bool,
    requested_at: str,
    key_status: str,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": status,
        "error_type": error_type,
        "model": model,
        "sample_count": sample_count,
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
            "User-Agent": USER_AGENT,
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
    payload = dict(parsed)
    payload["provider"] = "deepseek"
    return parse_llm_score_payload(payload)


def classify_http_error(error: HTTPError, body: str) -> str:
    lowered = body.lower()
    if error.code == 401:
        return "unauthorized_401"
    if error.code == 429:
        return "rate_limited_429"
    if any(term in lowered for term in ("quota", "billing", "credit", "payment", "insufficient", "balance")):
        return "quota_or_billing"
    if error.code == 403:
        return "forbidden_403"
    return "network_error"


def classify_url_error(error: URLError) -> str:
    reason = str(error.reason).lower()
    if "timed out" in reason or "timeout" in reason:
        return "timeout"
    return "network_error"


def sample_to_dict(item: LLMScoringInput) -> dict[str, Any]:
    return {
        "topic": item.topic,
        "title": item.title,
        "subreddit": item.subreddit,
        "source": item.source,
        "rule_level": item.rule_level,
        "rule_score": item.rule_score,
        "rule_notes": item.rule_notes,
        "url": item.url,
    }


def result_to_dict(result: LLMScoringResult) -> dict[str, Any]:
    return {
        "ceramic_relevance": result.ceramic_relevance,
        "keyword_intent_match": result.keyword_intent_match,
        "evidence_type": result.evidence_type,
        "can_support_trend": result.can_support_trend,
        "is_noise": result.is_noise,
        "confidence": result.confidence,
        "reason": result.reason,
        "provider": result.provider,
    }


def render_markdown_summary(
    *,
    requested_at: str,
    model: str,
    base_url: str,
    rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# DeepSeek 陶瓷证据评分 Tiny Probe",
        "",
        f"- 生成时间：{requested_at}",
        f"- 模型：{model}",
        f"- Base URL：{base_url}",
        "- 说明：这是 V0.6.8 tiny probe，不是正式趋势报告。",
        "- 保护动作：未覆盖 reports/report.md、reports/latest.md 或 reports/archive/。",
        "",
        "## 评分结果",
        "",
        "| 关键词 | 标题 | 规则层 | DeepSeek 相关性 | 意图匹配 | 证据类型 | 可支撑趋势 | 置信度 | 理由 |",
        "|---|---|---|---|---|---|---|---:|---|",
    ]
    for row in rows:
        sample = row["sample"]
        result = row["result"]
        lines.append(
            "| {topic} | {title} | {rule} | {relevance} | {intent} | {etype} | {trend} | {confidence} | {reason} |".format(
                topic=escape_cell(sample["topic"]),
                title=escape_cell(sample["title"]),
                rule=escape_cell(f"{sample['rule_level']} / {sample['rule_score']}"),
                relevance=escape_cell(result["ceramic_relevance"]),
                intent=escape_cell(result["keyword_intent_match"]),
                etype=escape_cell(result["evidence_type"]),
                trend="是" if result["can_support_trend"] else "否",
                confidence=result["confidence"],
                reason=escape_cell(result["reason"]),
            )
        )
    lines.extend(
        [
            "",
            "## 下一步",
            "",
            "- 对比规则评分和 DeepSeek 判断是否一致。",
            "- 如果 DeepSeek 能稳定识别跑偏样本和关键词意图不匹配，再考虑 V0.6.9 接入正式报告流程。",
            "- 如果成本高或判断不稳定，只保留为手动诊断工具。",
        ]
    )
    return "\n".join(lines) + "\n"


def escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def failure_summary(
    *,
    error_type: str,
    model: str,
    sample_count: int,
    requested_at: str,
    network_request_attempted: bool,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "failure",
        "error_type": error_type,
        "model": model,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "network_request_attempted": network_request_attempted,
        "results": [],
        "raw_response_saved": False,
        "report_files_updated": False,
    }


def probe_success_summary(
    *,
    model: str,
    base_url: str,
    sample_count: int,
    requested_at: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "success",
        "model": model,
        "base_url": base_url,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "results": rows,
        "raw_response_saved": False,
        "report_files_updated": False,
    }


def resolve_model(args: argparse.Namespace, env: Mapping[str, str], config_model: str) -> str:
    return (
        args.model
        or env.get("DEEPSEEK_MODEL")
        or config_model
        or DEFAULT_MODEL
    )


def resolve_base_url(args: argparse.Namespace, env: Mapping[str, str]) -> str:
    return args.base_url or env.get("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    allow_outside_local_outputs: bool = False,
) -> int:
    args = parse_args(argv)
    requested_at = utc_now_iso()
    sample_count = clamp_sample_count(args.sample_count)
    paths = ProbePaths(
        state_file=project_path(args.state_file),
        output_file=project_path(args.output),
        json_file=project_path(args.json_output),
        error_file=project_path(args.error_file),
        report_file=project_path(args.report_file),
        latest_file=project_path(args.latest_file),
        archive_dir=project_path(args.archive_dir),
    )
    if not allow_outside_local_outputs:
        path_error = validate_local_output_paths(paths)
        if path_error:
            print("DeepSeek LLM scoring probe：输出路径不安全，未发起网络请求。")
            print(path_error)
            print("请使用默认 local_outputs/ 路径，避免误写正式报告或其他文件。")
            return 2

    values = effective_env(env, args.dotenv_file)
    config = load_llm_scoring_config(project_path(args.config))
    model = resolve_model(args, values, config.model)
    base_url = resolve_base_url(args, values)
    api_key = configured_deepseek_key(values)
    prompt_template = project_path(args.prompt).read_text(encoding="utf-8")
    base_url_error = validate_deepseek_base_url(base_url)
    if base_url_error:
        state = base_state(
            status="invalid_base_url",
            error_type="invalid_base_url",
            model=model,
            sample_count=sample_count,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status="configured" if api_key else "missing",
        )
        write_json(paths.state_file, state)
        write_error_markdown(
            paths.error_file,
            state=state,
            message=base_url_error,
            next_step="删除 DEEPSEEK_BASE_URL 或使用默认官方 API 地址后再试。",
            secret=api_key,
        )
        print("DeepSeek LLM scoring probe：base URL 不安全，未发起网络请求。")
        print(base_url_error)
        return 2

    if not args.confirm_live_api:
        state = base_state(
            status="not_confirmed",
            error_type="not_confirmed",
            model=model,
            sample_count=sample_count,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status="configured" if api_key else "missing",
        )
        write_json(paths.state_file, state)
        print("DeepSeek LLM scoring probe：未发起网络请求。")
        print("如需真实 tiny test，请显式添加 --confirm-live-api。")
        print(f"状态已写入：{paths.state_file}")
        return 0

    if not api_key:
        state = base_state(
            status="missing_key",
            error_type="missing_key",
            model=model,
            sample_count=sample_count,
            network_request_attempted=False,
            requested_at=requested_at,
            key_status="missing",
        )
        write_json(paths.state_file, state)
        write_json(
            paths.json_file,
            failure_summary(
                error_type="missing_key",
                model=model,
                sample_count=sample_count,
                requested_at=requested_at,
                network_request_attempted=False,
            ),
        )
        write_error_markdown(
            paths.error_file,
            state=state,
            message="未找到 DEEPSEEK_API_KEY。没有发起网络请求。",
            next_step="确认 .env 或系统环境变量里已配置 DEEPSEEK_API_KEY，然后再运行 tiny probe。",
        )
        print("DeepSeek LLM scoring probe：未找到 API key，未发起网络请求。")
        print(f"错误详情见：{paths.error_file}")
        return 0

    try:
        rows: list[dict[str, Any]] = []
        samples = SAMPLE_ITEMS[:sample_count]
        for item in samples:
            prompt = build_llm_scoring_prompt(prompt_template, item)
            payload, _status_code = request_deepseek_score(
                api_key=api_key,
                base_url=base_url,
                model=model,
                prompt=prompt,
                timeout=args.timeout,
            )
            result = parse_deepseek_score_response(payload)
            rows.append({"sample": sample_to_dict(item), "result": result_to_dict(result)})

        summary = probe_success_summary(
            model=model,
            base_url=base_url,
            sample_count=sample_count,
            requested_at=requested_at,
            rows=rows,
        )
        state = base_state(
            status="success",
            error_type="",
            model=model,
            sample_count=sample_count,
            network_request_attempted=True,
            requested_at=requested_at,
            key_status="configured",
        )
        state["result_count"] = len(rows)
        write_json(paths.json_file, summary)
        paths.output_file.parent.mkdir(parents=True, exist_ok=True)
        paths.output_file.write_text(
            render_markdown_summary(
                requested_at=requested_at,
                model=model,
                base_url=base_url,
                rows=rows,
            ),
            encoding="utf-8",
        )
        write_json(paths.state_file, state)
        print("DeepSeek LLM scoring probe 成功。")
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
        "unauthorized_401": "检查 DEEPSEEK_API_KEY 是否有效，或是否需要重新生成 key。",
        "forbidden_403": "检查 DeepSeek 账号权限、模型权限或 API 访问策略。",
        "rate_limited_429": "已被限流，请等待后再试，不要连续重复请求。",
        "quota_or_billing": "检查 DeepSeek 后台余额、额度或账单状态。",
        "timeout": "检查网络或代理状态，稍后再试。",
        "network_error": "检查网络、DNS、代理或 DeepSeek API 服务状态。",
        "parse_error": "模型返回不是预期 JSON，需要检查 prompt 或 JSON Output 支持情况。",
        "unknown_error": "保留错误文件后再排查，不要重复发起请求。",
    }
    state = base_state(
        status="failure",
        error_type=error_type,
        model=model,
        sample_count=sample_count,
        network_request_attempted=True,
        requested_at=requested_at,
        key_status="configured",
    )
    write_json(paths.state_file, state)
    write_json(
        paths.json_file,
        failure_summary(
            error_type=error_type,
            model=model,
            sample_count=sample_count,
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
    print("DeepSeek LLM scoring probe 失败。")
    print("正式报告未更新。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
