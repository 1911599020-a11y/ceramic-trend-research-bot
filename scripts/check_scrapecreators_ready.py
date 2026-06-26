#!/usr/bin/env python3
"""Read-only ScrapeCreators readiness check.

This script does not call ScrapeCreators, validate quota, fetch Reddit, or
print secrets. It only checks whether the local configuration is ready for a
future key-backed Reddit fallback test.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sources.scrapecreators_source import (  # noqa: E402
    check_scrapecreators_readiness,
)


DATA_SOURCE_CATALOG = PROJECT_ROOT / "config" / "data_sources.json"
SOURCE_ID = "scrapecreators_reddit"


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
    if dotenv_path is None and env is None:
        dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path is not None:
        for key, value in parse_dotenv(dotenv_path).items():
            values.setdefault(key, value)
    return values


def load_source_entry(path: Path, source_id: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for raw in payload.get("sources", []):
        if isinstance(raw, dict) and raw.get("id") == source_id:
            return raw
    return {}


def main(
    env: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> int:
    entry = load_source_entry(DATA_SOURCE_CATALOG, SOURCE_ID)
    readiness = check_scrapecreators_readiness(effective_env(env, dotenv_path))

    print("## ScrapeCreators Readiness")
    print(f"- source id: {SOURCE_ID}")
    print(f"- catalog status: {entry.get('status', 'missing')}")
    print(f"- key status: {readiness.status}")
    print(f"- detail: {readiness.detail}")
    print("- network request: not attempted")
    print("- secret value: hidden")

    print("\n## NEXT STEPS")
    if readiness.can_attempt_api:
        print("- Key exists locally. Readiness still does not call the API.")
        print("- Run `bash scripts/probe_scrapecreators_reddit.sh` for a no-network protection check.")
        print("- Only run `--confirm-live-api` after explicitly approving one tiny real request.")
        return 0

    print("- No key is configured. Mock and Reddit public live can still run as before.")
    print("- Apply for ScrapeCreators later, then set SCRAPECREATORS_API_KEY outside Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
