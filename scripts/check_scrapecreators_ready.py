#!/usr/bin/env python3
"""Read-only ScrapeCreators readiness check.

This script does not call ScrapeCreators, validate quota, fetch Reddit, or
print secrets. It only checks whether the local configuration is ready for a
future key-backed Reddit fallback test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sources.scrapecreators_source import (  # noqa: E402
    check_scrapecreators_readiness,
)


DATA_SOURCE_CATALOG = PROJECT_ROOT / "config" / "data_sources.json"
SOURCE_ID = "scrapecreators_reddit"


def load_source_entry(path: Path, source_id: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for raw in payload.get("sources", []):
        if isinstance(raw, dict) and raw.get("id") == source_id:
            return raw
    return {}


def main() -> int:
    entry = load_source_entry(DATA_SOURCE_CATALOG, SOURCE_ID)
    readiness = check_scrapecreators_readiness()

    print("## ScrapeCreators Readiness")
    print(f"- source id: {SOURCE_ID}")
    print(f"- catalog status: {entry.get('status', 'missing')}")
    print(f"- key status: {readiness.status}")
    print(f"- detail: {readiness.detail}")
    print("- network request: not attempted")
    print("- secret value: hidden")

    print("\n## NEXT STEPS")
    if readiness.can_attempt_api:
        print("- Key exists locally. V0.6.1 still does not call the API.")
        print("- Next approved phase can add a tiny ScrapeCreators live probe with strict quota protection.")
        return 0

    print("- No key is configured. Mock and Reddit public live can still run as before.")
    print("- Apply for ScrapeCreators later, then set SCRAPECREATORS_API_KEY outside Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
