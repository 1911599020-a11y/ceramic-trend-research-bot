"""TrendSource adapter for the external last30days-skill subprocess.

The command construction, environment handling, timeout, and JSON extraction
below are moved verbatim from ceramic_report.py V0.4.2 (run_last30days and
its helpers), so live-mode behaviour stays identical. tests/test_sources.py
pins the constructed command list item by item against the legacy layout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_LAST30DAYS_SCRIPT = Path(
    "/Users/zhuyixiao/Documents/GitHub/last30days-skill/"
    "skills/last30days/scripts/last30days.py"
)
LAST30DAYS_REPO_HINT = "/Users/zhuyixiao/Documents/GitHub/last30days-skill"
SCRAPECREATORS_ENV_KEYS = ("SCRAPECREATORS_API_KEY", "SCRAPE_CREATORS_API_KEY")

# Resolution order for the script path when no CLI value is given. The legacy
# LAST30DAYS_SCRIPT variable predates V0.5.0 and is kept as a fallback.
SCRIPT_PATH_ENV_VARS = ("CERAMIC_LAST30DAYS_SCRIPT", "LAST30DAYS_SCRIPT")


def resolve_last30days_script(cli_value: str | None = None) -> Path:
    """Resolve the last30days.py path.

    Priority: CLI argument > CERAMIC_LAST30DAYS_SCRIPT > LAST30DAYS_SCRIPT
    (legacy) > the original Mac default path.
    """
    if cli_value:
        return Path(cli_value)
    for env_name in SCRIPT_PATH_ENV_VARS:
        value = os.environ.get(env_name, "").strip()
        if value:
            return Path(value)
    return DEFAULT_LAST30DAYS_SCRIPT


def build_query_plan(topic: str, sources: list[str]) -> dict[str, Any]:
    source_weights = {source: 1.0 for source in sources}
    return {
        "intent": "opinion",
        "freshness_mode": "balanced_recent",
        "cluster_mode": "debate",
        "source_weights": source_weights,
        "subqueries": [
            {
                "label": "community discussion",
                "search_query": topic,
                "ranking_query": (
                    "What are makers, collectors, and viewers saying about "
                    f"{topic}, including trends, pain points, workflows, and content ideas?"
                ),
                "sources": sources,
                "weight": 1.0,
            }
        ],
        "notes": ["ceramic-trend-research-bot V0.2 plan"],
    }


def assert_last30days_script(script_path: Path) -> None:
    if not script_path.exists():
        raise FileNotFoundError(
            "找不到 last30days-skill 运行脚本。\n"
            f"当前查找路径：{script_path}\n"
            f"请确认 last30days-skill 已克隆到 {LAST30DAYS_REPO_HINT}"
        )


def run_last30days_mock(topic: str, script_path: Path) -> dict[str, Any]:
    return run_last30days(topic, script_path, mode="mock")


def run_last30days_live(
    topic: str,
    script_path: Path,
    recommended_subreddits: set[str] | None = None,
) -> dict[str, Any]:
    return run_last30days(
        topic,
        script_path,
        mode="live",
        recommended_subreddits=recommended_subreddits,
    )


def run_last30days(
    topic: str,
    script_path: Path,
    mode: str,
    recommended_subreddits: set[str] | None = None,
) -> dict[str, Any]:
    assert_last30days_script(script_path)
    if mode not in {"mock", "live"}:
        raise ValueError(f"Unsupported mode: {mode}")

    sources = ["reddit", "youtube"] if mode == "mock" else ["reddit"]
    command = [
        sys.executable,
        str(script_path),
        topic,
        "--quick",
        "--emit=json",
        f"--search={','.join(sources)}",
        "--plan",
        json.dumps(build_query_plan(topic, sources), ensure_ascii=False),
    ]
    if mode == "mock":
        command.insert(3, "--mock")
    if mode == "live" and recommended_subreddits:
        command.extend(["--subreddits", ",".join(sorted(recommended_subreddits))])

    env = os.environ.copy()
    # Public Reddit live must not accidentally hand API-provider keys to the
    # external last30days-skill subprocess. ScrapeCreators is opt-in via its
    # own TrendSource only.
    for key in SCRAPECREATORS_ENV_KEYS:
        env.pop(key, None)
    env.setdefault("FROM_BROWSER", "off")
    env.setdefault("LAST30DAYS_CONFIG_DIR", "")

    result = subprocess.run(
        command,
        cwd=str(script_path.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"last30days {mode} run failed\n"
            f"topic: {topic}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return extract_json(result.stdout)


def extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON payload found in last30days output:\n{stdout}")
    return json.loads(stdout[start : end + 1])


class Last30DaysSource:
    """TrendSource backed by the external last30days-skill subprocess."""

    def __init__(self, script_path: Path, mode: str = "live") -> None:
        self.script_path = Path(script_path)
        self.mode = mode

    def fetch(
        self,
        topic: str,
        *,
        recommended_subreddits: set[str] | None = None,
    ) -> dict[str, Any]:
        return run_last30days(
            topic,
            self.script_path,
            mode=self.mode,
            recommended_subreddits=recommended_subreddits,
        )
