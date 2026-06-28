#!/usr/bin/env python3
"""Compare rule scoring with DeepSeek on real small-sample Reddit evidence.

V0.7.0 keeps this as an opt-in side experiment. It can fetch a small
ScrapeCreators Reddit sample, score the same evidence with rules and DeepSeek,
and write only to local_outputs/.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ceramic_report import (  # noqa: E402
    Evidence,
    apply_relevance_ranking,
    collect_evidence,
    load_config,
    load_relevance_config,
    load_topics,
)
from compare_llm_scoring import (  # noqa: E402
    aggregate_counts,
    build_row,
    render_comparison_markdown,
)
from probe_llm_scoring import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    LOCAL_OUTPUTS_DIR,
    classify_http_error,
    classify_url_error,
    configured_deepseek_key,
    effective_env,
    project_path,
    parse_deepseek_score_response,
    redact_secret,
    request_deepseek_score,
    resolve_base_url,
    resolve_llm_scoring_switch,
    resolve_model,
    utc_now_iso,
    validate_deepseek_base_url,
    write_json,
)
from scoring.llm_scorer import (  # noqa: E402
    LLMScoringInput,
    build_llm_scoring_prompt,
    load_llm_scoring_config,
)
from sources.scrapecreators_source import (  # noqa: E402
    ScrapeCreatorsSource,
    configured_scrapecreators_env_var,
)


SOURCE_ID = "deepseek_real_sample_scoring_comparison"
DEFAULT_TOPICS_PATH = PROJECT_ROOT / "config" / "scrapecreators_quality_topics.json"
DEFAULT_SAMPLE_COUNT = 8
MAX_SAMPLE_COUNT = 12
DEFAULT_PER_TOPIC_LIMIT = 4
EXPECTED_OUTPUTS = {
    "state-file": LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison_state.json",
    "output": LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison.md",
    "json-output": LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison.json",
    "error-file": LOCAL_OUTPUTS_DIR / "llm_scoring_real_sample_comparison_error.md",
}


@dataclass(frozen=True)
class RealComparisonPaths:
    state_file: Path
    output_file: Path
    json_file: Path
    error_file: Path
    report_file: Path
    latest_file: Path
    archive_dir: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an opt-in real Reddit/ScrapeCreators rule-vs-DeepSeek "
            "small-sample comparison. Without --confirm-live-api this command "
            "does not call the network."
        )
    )
    parser.add_argument("--confirm-live-api", action="store_true")
    parser.add_argument("--topics", default=str(DEFAULT_TOPICS_PATH))
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--per-topic-limit", type=int, default=DEFAULT_PER_TOPIC_LIMIT)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--config", default="config/llm_scoring.json")
    parser.add_argument("--prompt", default="prompts/llm_scoring_prompt.md")
    parser.add_argument("--state-file", default="local_outputs/llm_scoring_real_sample_comparison_state.json")
    parser.add_argument("--output", default="local_outputs/llm_scoring_real_sample_comparison.md")
    parser.add_argument("--json-output", default="local_outputs/llm_scoring_real_sample_comparison.json")
    parser.add_argument("--error-file", default="local_outputs/llm_scoring_real_sample_comparison_error.md")
    parser.add_argument("--dotenv-file", default=None)

    # Test-only guard paths. The comparison never writes these files.
    parser.add_argument("--report-file", default="reports/report.md", help=argparse.SUPPRESS)
    parser.add_argument("--latest-file", default="reports/latest.md", help=argparse.SUPPRESS)
    parser.add_argument("--archive-dir", default="reports/archive", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def clamp_count(value: int, *, maximum: int) -> int:
    if value < 1:
        return 1
    return min(value, maximum)


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def validate_local_output_paths(paths: RealComparisonPaths) -> str:
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


def evidence_to_llm_input(evidence: Evidence) -> LLMScoringInput:
    return LLMScoringInput(
        topic=evidence.topic,
        title=evidence.title,
        subreddit=f"r/{evidence.subreddit}" if evidence.subreddit else "",
        body=evidence.snippet,
        url=evidence.url,
        source=evidence.source,
        rule_level=evidence.relevance_level,
        rule_score=evidence.relevance_score,
        rule_notes=evidence.relevance_notes,
    )


def normalized_title_key(title: str) -> str:
    text = title.strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def select_evidence_samples(
    runs: list[tuple[str, list[Evidence]]],
    *,
    sample_count: int,
    per_topic_limit: int,
) -> list[LLMScoringInput]:
    buckets: list[list[Evidence]] = []
    seen_keys: set[tuple[str, str]] = set()
    for _topic, evidence_items in runs:
        topic_items = sorted(
            evidence_items,
            key=lambda item: (
                {"high": 3, "edge": 2, "low": 1}.get(item.relevance_level, 0),
                item.relevance_score,
            ),
            reverse=True,
        )
        unique_topic_items: list[Evidence] = []
        for evidence in topic_items:
            key = (evidence.topic.strip().lower(), normalized_title_key(evidence.title))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_topic_items.append(evidence)
            if len(unique_topic_items) >= per_topic_limit:
                break
        if unique_topic_items:
            buckets.append(unique_topic_items)

    selected: list[LLMScoringInput] = []
    max_bucket_size = max((len(bucket) for bucket in buckets), default=0)
    for index in range(max_bucket_size):
        for bucket in buckets:
            if index >= len(bucket):
                continue
            selected.append(evidence_to_llm_input(bucket[index]))
            if len(selected) >= sample_count:
                return selected
    return selected


def base_state(
    *,
    status: str,
    error_type: str,
    model: str,
    sample_count: int,
    requested_at: str,
    network_request_attempted: bool,
    key_status: str,
    scrapecreators_key_status: str,
    llm_scoring_enabled: bool,
    switch_env_var: str,
    switch_source: str,
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
        "data_source": "scrapecreators_reddit",
        "key_status": key_status,
        "scrapecreators_key_status": scrapecreators_key_status,
        "llm_scoring_enabled": llm_scoring_enabled,
        "switch_env_var": switch_env_var,
        "switch_source": switch_source,
    }


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
            "# DeepSeek 真实小样本对照错误",
            "",
            f"- 错误类型：{state.get('error_type', 'unknown_error')}",
            f"- 发生时间：{state.get('requested_at', '')}",
            f"- 样本数量：{state.get('sample_count', '')}",
            f"- 是否已发起网络请求：{state.get('network_request_attempted', False)}",
            "- 保护动作：未覆盖 reports/report.md、reports/latest.md 或 reports/archive/",
            f"- 错误说明：{redact_secret(message, secret)}",
            f"- 建议下一步：{redact_secret(next_step, secret)}",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


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
        "report_files_updated": False,
    }


def success_summary(
    *,
    model: str,
    base_url: str,
    sample_count: int,
    requested_at: str,
    topics: list[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "status": "success",
        "model": model,
        "base_url": base_url,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "data_source": "scrapecreators_reddit",
        "topics": topics,
        "counts": aggregate_counts(rows),
        "results": rows,
        "report_files_updated": False,
    }


def next_step_for(error_type: str) -> str:
    return {
        "missing_key": "确认 .env 中已配置 DEEPSEEK_API_KEY，再运行真实小样本对照。",
        "missing_scrapecreators_key": "确认 .env 中已配置 SCRAPECREATORS_API_KEY，再运行真实小样本对照。",
        "switch_off": "确认要消耗 DeepSeek 额度时，将 LLM_SCORING_ENABLED=on 写入 .env，或仅本次临时打开。",
        "no_evidence": "真实数据源没有返回可对照证据；可稍后重试或调整关键词配置。",
        "unauthorized_401": "检查 API key 是否有效，或是否需要重新生成 key。",
        "forbidden_403": "检查账号权限、模型权限、ScrapeCreators 权限或 API 访问策略。",
        "rate_limited_429": "已被限流，请等待后再试，不要连续重复请求。",
        "quota_or_billing": "检查 DeepSeek 或 ScrapeCreators 后台余额、额度或账单状态。",
        "timeout": "检查网络或代理状态，稍后再试。",
        "network_error": "检查网络、DNS、代理或 API 服务状态。",
        "parse_error": "模型返回不是预期 JSON，需要检查 prompt 或 JSON Output 支持情况。",
        "unknown_error": "保留错误文件后再排查，不要重复发起请求。",
    }.get(error_type, "保留错误文件后再排查，不要重复发起请求。")


def fetch_real_samples(
    *,
    topics_path: Path,
    env: Mapping[str, str],
    sample_count: int,
    per_topic_limit: int,
    timeout: float,
) -> tuple[list[str], list[LLMScoringInput]]:
    config = load_config(topics_path)
    topics = load_topics(topics_path)
    relevance_config = load_relevance_config(config)
    source = ScrapeCreatorsSource(env=env, timeout=timeout)
    runs: list[tuple[str, list[Evidence]]] = []
    for topic in topics:
        report = source.fetch(
            topic,
            recommended_subreddits=relevance_config.recommended_subreddits,
        )
        report = apply_relevance_ranking(report, relevance_config, topic)
        runs.append((topic, collect_evidence(topic, report)))
    return topics, select_evidence_samples(
        runs,
        sample_count=sample_count,
        per_topic_limit=per_topic_limit,
    )


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    allow_outside_local_outputs: bool = False,
) -> int:
    args = parse_args(argv)
    requested_at = utc_now_iso()
    sample_count = clamp_count(args.sample_count, maximum=MAX_SAMPLE_COUNT)
    per_topic_limit = clamp_count(args.per_topic_limit, maximum=MAX_SAMPLE_COUNT)
    paths = RealComparisonPaths(
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
            print("DeepSeek 真实小样本对照：输出路径不安全，未发起网络请求。")
            print(path_error)
            print("请使用默认 local_outputs/ 路径，避免误写正式报告或其他文件。")
            return 2

    values = effective_env(env, args.dotenv_file)
    config = load_llm_scoring_config(project_path(args.config))
    model = resolve_model(args, values, config.model or DEFAULT_MODEL)
    base_url = resolve_base_url(args, values) or DEFAULT_BASE_URL
    api_key = configured_deepseek_key(values)
    scrapecreators_env_var = configured_scrapecreators_env_var(values)
    scrapecreators_key = values.get(scrapecreators_env_var, "") if scrapecreators_env_var else ""
    llm_switch_enabled, switch_source = resolve_llm_scoring_switch(
        values,
        switch_env_var=config.switch_env_var,
        enabled_values=config.enabled_values,
    )
    topics_path = project_path(args.topics)
    prompt_template = project_path(args.prompt).read_text(encoding="utf-8")
    base_url_error = validate_deepseek_base_url(base_url)
    common_state = {
        "model": model,
        "sample_count": sample_count,
        "requested_at": requested_at,
        "key_status": "configured" if api_key else "missing",
        "scrapecreators_key_status": "configured" if scrapecreators_key else "missing",
        "llm_scoring_enabled": llm_switch_enabled,
        "switch_env_var": config.switch_env_var,
        "switch_source": switch_source,
    }
    if base_url_error:
        state = base_state(
            status="invalid_base_url",
            error_type="invalid_base_url",
            network_request_attempted=False,
            **common_state,
        )
        write_json(paths.state_file, state)
        write_error_markdown(
            paths.error_file,
            state=state,
            message=base_url_error,
            next_step="删除 DEEPSEEK_BASE_URL 或使用默认官方 API 地址后再试。",
            secret=api_key,
        )
        print("DeepSeek 真实小样本对照：base URL 不安全，未发起网络请求。")
        print(base_url_error)
        return 2

    if not args.confirm_live_api:
        state = base_state(
            status="not_confirmed",
            error_type="not_confirmed",
            network_request_attempted=False,
            **common_state,
        )
        write_json(paths.state_file, state)
        print("DeepSeek 真实小样本对照：未发起网络请求。")
        print(
            "如需真实对照，请同时打开 "
            f"{config.switch_env_var}=on 并显式添加 --confirm-live-api。"
        )
        print(f"状态已写入：{paths.state_file}")
        return 0

    if not llm_switch_enabled:
        return write_guard_failure(
            paths,
            state=base_state(
                status="switch_off",
                error_type="switch_off",
                network_request_attempted=False,
                **common_state,
            ),
            error_type="switch_off",
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            api_key=api_key,
            message=(
                f"{config.switch_env_var} 未开启。虽然已收到 --confirm-live-api，"
                "但没有发起 ScrapeCreators 或 DeepSeek 网络请求。"
            ),
        )

    if not api_key:
        return write_guard_failure(
            paths,
            state=base_state(
                status="missing_key",
                error_type="missing_key",
                network_request_attempted=False,
                **common_state,
            ),
            error_type="missing_key",
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            api_key="",
            message="未找到 DEEPSEEK_API_KEY。没有发起网络请求。",
        )

    if not scrapecreators_key:
        return write_guard_failure(
            paths,
            state=base_state(
                status="missing_scrapecreators_key",
                error_type="missing_scrapecreators_key",
                network_request_attempted=False,
                **common_state,
            ),
            error_type="missing_scrapecreators_key",
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            api_key=api_key,
            message="未找到 SCRAPECREATORS_API_KEY。没有发起网络请求。",
        )

    try:
        topics, samples = fetch_real_samples(
            topics_path=topics_path,
            env=values,
            sample_count=sample_count,
            per_topic_limit=per_topic_limit,
            timeout=args.timeout,
        )
        if not samples:
            return write_guard_failure(
                paths,
                state=base_state(
                    status="no_evidence",
                    error_type="no_evidence",
                    network_request_attempted=True,
                    **common_state,
                ),
                error_type="no_evidence",
                model=model,
                sample_count=sample_count,
                requested_at=requested_at,
                api_key=api_key,
                message="ScrapeCreators 返回后没有可用于对照的 Reddit 证据。",
                exit_code=1,
            )

        rows: list[dict[str, Any]] = []
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
            rows.append(build_row(item, result))

        state = base_state(
            status="success",
            error_type="",
            network_request_attempted=True,
            **common_state,
        )
        state["result_count"] = len(rows)
        state["topics"] = topics
        summary = success_summary(
            model=model,
            base_url=base_url,
            sample_count=len(rows),
            requested_at=requested_at,
            topics=topics,
            rows=rows,
        )
        write_json(paths.json_file, summary)
        paths.output_file.parent.mkdir(parents=True, exist_ok=True)
        paths.output_file.write_text(
            render_comparison_markdown(
                requested_at=requested_at,
                model=model,
                base_url=base_url,
                rows=rows,
                title="DeepSeek 与真实 Reddit 小样本规则评分对照报告",
                description="这是 V0.7.0 真实小样本旁路对照报告，不是正式趋势报告。",
            ),
            encoding="utf-8",
        )
        write_json(paths.state_file, state)
        print("DeepSeek 真实小样本对照报告生成成功。")
        print(f"对照报告已写入：{paths.output_file}")
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
        network_request_attempted=True,
        **common_state,
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
        next_step=next_step_for(error_type),
        secret=api_key,
    )
    print("DeepSeek 真实小样本对照报告生成失败。")
    print("正式报告未更新。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return 1


def write_guard_failure(
    paths: RealComparisonPaths,
    *,
    state: Mapping[str, Any],
    error_type: str,
    model: str,
    sample_count: int,
    requested_at: str,
    api_key: str,
    message: str,
    exit_code: int = 0,
) -> int:
    write_json(paths.state_file, state)
    write_json(
        paths.json_file,
        failure_summary(
            error_type=error_type,
            model=model,
            sample_count=sample_count,
            requested_at=requested_at,
            network_request_attempted=bool(state.get("network_request_attempted", False)),
        ),
    )
    write_error_markdown(
        paths.error_file,
        state=state,
        message=message,
        next_step=next_step_for(error_type),
        secret=api_key,
    )
    print("DeepSeek 真实小样本对照：保护机制已拦截，未更新正式报告。")
    print(f"错误类型：{error_type}")
    print(f"错误详情见：{paths.error_file}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
