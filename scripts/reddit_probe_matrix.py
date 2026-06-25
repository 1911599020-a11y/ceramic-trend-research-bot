#!/usr/bin/env python3
"""Small Reddit request matrix for diagnosing live-mode 403 failures.

This script is intentionally narrow: it does not collect research data or write
reports. It probes a few Reddit request shapes so we can tell whether the
current environment blocks all Reddit traffic, only JSON search endpoints, or a
specific User-Agent shape.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib import error, request


APP_USER_AGENT = os.environ.get("CERAMIC_REDDIT_USER_AGENT", "ceramic-trend-research-bot/0.2")
BROWSER_USER_AGENT = os.environ.get(
    "CERAMIC_REDDIT_BROWSER_USER_AGENT",
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
)
TIMEOUT_SECONDS = float(os.environ.get("CERAMIC_REDDIT_PROBE_TIMEOUT", "8"))


@dataclass(frozen=True)
class Probe:
    key: str
    label: str
    url: str
    user_agent: str
    accept: str
    live_relevant: bool


@dataclass(frozen=True)
class ProbeResult:
    probe: Probe
    status: str
    detail: str


def build_probes() -> list[Probe]:
    global_search = "https://www.reddit.com/search.json?q=ceramic%20art&sort=relevance&t=month&limit=1&raw_json=1"
    subreddit_search = (
        "https://www.reddit.com/r/Pottery/search.json"
        "?q=ceramic%20glaze&restrict_sr=on&sort=relevance&t=month&limit=1&raw_json=1"
    )
    return [
        Probe(
            key="root_browser_html",
            label="Root page with browser UA",
            url="https://www.reddit.com/",
            user_agent=BROWSER_USER_AGENT,
            accept="text/html,application/xhtml+xml",
            live_relevant=False,
        ),
        Probe(
            key="global_search_app_json",
            label="Global search.json with app UA",
            url=global_search,
            user_agent=APP_USER_AGENT,
            accept="application/json,text/plain,*/*",
            live_relevant=True,
        ),
        Probe(
            key="global_search_browser_json",
            label="Global search.json with browser UA",
            url=global_search,
            user_agent=BROWSER_USER_AGENT,
            accept="application/json,text/plain,*/*",
            live_relevant=True,
        ),
        Probe(
            key="subreddit_search_browser_json",
            label="r/Pottery search.json with browser UA",
            url=subreddit_search,
            user_agent=BROWSER_USER_AGENT,
            accept="application/json,text/plain,*/*",
            live_relevant=True,
        ),
    ]


def run_probe(probe: Probe, timeout: float = TIMEOUT_SECONDS) -> ProbeResult:
    req = request.Request(
        probe.url,
        method="GET",
        headers={
            "User-Agent": probe.user_agent,
            "Accept": probe.accept,
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            status_code = getattr(response, "status", 0) or response.getcode()
            content_type = response.headers.get("Content-Type", "")
            sample = response.read(256)
    except error.HTTPError as exc:
        return ProbeResult(probe, "FAIL", f"HTTP {exc.code} {exc.reason}")
    except error.URLError as exc:
        return ProbeResult(probe, "FAIL", f"{type(getattr(exc, 'reason', exc)).__name__}: {getattr(exc, 'reason', exc)}")
    except OSError as exc:
        return ProbeResult(probe, "FAIL", f"{type(exc).__name__}: {exc}")

    if "search.json" in probe.url and "json" not in content_type.lower():
        return ProbeResult(
            probe,
            "WARN",
            f"HTTP {status_code}, non-json Content-Type {content_type or 'unknown'}",
        )
    if not sample:
        return ProbeResult(probe, "WARN", f"HTTP {status_code}, empty response body")
    return ProbeResult(probe, "PASS", f"HTTP {status_code}, Content-Type {content_type or 'unknown'}")


def print_results(results: list[ProbeResult]) -> None:
    print("# Reddit Probe Matrix")
    print("")
    print("| Status | Probe | Detail |")
    print("| --- | --- | --- |")
    for result in results:
        print(f"| {result.status} | {result.probe.label} | {escape_cell(result.detail)} |")
    print("")
    print("## NEXT STEPS")
    for line in next_steps(results):
        print(f"- {line}")


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def next_steps(results: list[ProbeResult]) -> list[str]:
    by_key = {result.probe.key: result for result in results}
    root = by_key.get("root_browser_html")
    app = by_key.get("global_search_app_json")
    browser = by_key.get("global_search_browser_json")
    subreddit = by_key.get("subreddit_search_browser_json")

    steps: list[str] = []
    if root and root.status == "FAIL":
        steps.append("Reddit root page also fails. Check network, DNS, proxy, or VPN first.")
    if app and app.status == "FAIL" and browser and browser.status == "PASS":
        steps.append("App User-Agent fails but browser User-Agent works. Consider aligning preflight with browser-style UA.")
    if browser and browser.status == "FAIL" and subreddit and subreddit.status == "FAIL":
        steps.append("JSON search endpoints fail even with browser UA. The current Reddit exit is likely blocking public JSON search.")
    if subreddit and subreddit.status == "PASS" and browser and browser.status != "PASS":
        steps.append("Subreddit-scoped JSON works better than global search. Prefer targeted subreddit search in future live runs.")
    if not steps:
        steps.append("No obvious workaround from this matrix. Keep mock mode available and retry live later with a different network/proxy.")
    steps.append("Do not run this matrix repeatedly in a short time window; it sends multiple Reddit probes.")
    return steps


def main() -> int:
    results = [run_probe(probe) for probe in build_probes()]
    print_results(results)
    live_results = [result for result in results if result.probe.live_relevant]
    return 0 if any(result.status == "PASS" for result in live_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
