#!/usr/bin/env python3
"""Environment diagnostics for ceramic-trend-research-bot.

This script is read-only: it does not fetch research data, install tools, or
print secrets. It checks whether the local machine is ready for mock mode and
the next Reddit live-mode pass.
"""

from __future__ import annotations

import os
import shutil
import socket
import ssl
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import error, parse, request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAST30DAYS_REPO = Path("/Users/zhuyixiao/Documents/GitHub/last30days-skill")
# Same resolution order as ceramic_report.py since V0.5.0:
# CERAMIC_LAST30DAYS_SCRIPT > LAST30DAYS_SCRIPT (legacy) > original Mac path.
_SCRIPT_OVERRIDE = (
    os.environ.get("CERAMIC_LAST30DAYS_SCRIPT", "").strip()
    or os.environ.get("LAST30DAYS_SCRIPT", "").strip()
)
LAST30DAYS_SCRIPT = (
    Path(_SCRIPT_OVERRIDE)
    if _SCRIPT_OVERRIDE
    else LAST30DAYS_REPO / "skills/last30days/scripts/last30days.py"
)
DOMAINS = ["www.reddit.com", "www.youtube.com", "github.com"]
REDDIT_PROBE_URL = "https://www.reddit.com/search.json?q=ceramic%20art&sort=relevance&t=month&limit=1&raw_json=1"
USER_AGENT = "ceramic-trend-research-bot/0.2"
PROXY_ENV_KEYS = [
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "https_proxy",
    "http_proxy",
    "all_proxy",
]
NO_PROXY_ENV_KEYS = [
    "NO_PROXY",
    "no_proxy",
]
ENV_KEYS = [
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "SCRAPECREATORS_API_KEY",
    "BRAVE_API_KEY",
    "EXA_API_KEY",
    "SERPER_API_KEY",
    "LAST30DAYS_MEMORY_DIR",
    "FROM_BROWSER",
]
SUPPORTED_MODEL_PROVIDERS = {"rules"}


@dataclass
class Check:
    status: str
    label: str
    detail: str


def main() -> int:
    checks: list[Check] = []
    checks.extend(check_python())
    checks.extend(check_paths())
    checks.extend(check_proxy_env())
    checks.extend(check_domains())
    checks.extend(check_reddit_policy())
    checks.extend(check_tools())
    checks.extend(check_env_files())
    checks.extend(check_model_provider())
    checks.extend(check_env_vars())
    checks = normalize_check_statuses(checks)

    print_section("PASS", checks, "PASS")
    print_section("WARN", checks, "WARN")
    print_section("FAIL", checks, "FAIL")
    print_next_steps(checks)

    return 1 if any(check.status == "FAIL" for check in checks) else 0


def normalize_check_statuses(checks: list[Check]) -> list[Check]:
    reddit_proxy_ok = any(
        check.label == "Reddit proxy-aware HTTP" and check.status == "PASS"
        for check in checks
    )
    normalized: list[Check] = []
    for check in checks:
        if reddit_proxy_ok and check.status == "FAIL" and check.label in {
            "DNS www.reddit.com",
            "HTTPS www.reddit.com",
        }:
            normalized.append(
                Check(
                    "WARN",
                    check.label,
                    f"{check.detail}; proxy-aware Reddit probe passed, so live may still work",
                )
            )
            continue
        if check.status == "FAIL" and check.label in {
            "DNS www.youtube.com",
            "HTTPS www.youtube.com",
        }:
            normalized.append(
                Check(
                    "WARN",
                    check.label,
                    f"{check.detail}; optional until the YouTube/yt-dlp phase",
                )
            )
            continue
        if check.status == "FAIL" and check.label in {
            "DNS github.com",
            "HTTPS github.com",
        }:
            normalized.append(
                Check(
                    "WARN",
                    check.label,
                    f"{check.detail}; optional for local Reddit live mode, but needed for GitHub push/Actions",
                )
            )
            continue
        normalized.append(check)
    return normalized


def check_python() -> list[Check]:
    version = sys.version_info
    detail = f"{version.major}.{version.minor}.{version.micro} at {sys.executable}"
    status = "PASS" if (version.major, version.minor) >= (3, 12) else "FAIL"
    return [Check(status, "Python >= 3.12", detail)]


def check_paths() -> list[Check]:
    return [
        exists_check("last30days-skill repo", LAST30DAYS_REPO),
        exists_check("last30days.py", LAST30DAYS_SCRIPT),
    ]


def exists_check(label: str, path: Path) -> Check:
    if path.exists():
        return Check("PASS", label, str(path))
    return Check("FAIL", label, f"missing: {path}")


def check_domains() -> list[Check]:
    checks: list[Check] = []
    for domain in DOMAINS:
        checks.append(check_dns(domain))
        checks.append(check_https(domain))
    return checks


def check_dns(domain: str) -> Check:
    try:
        infos = socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        return Check("FAIL", f"DNS {domain}", str(exc))
    addresses = sorted({item[4][0] for item in infos})
    return Check("PASS", f"DNS {domain}", ", ".join(addresses[:3]))


def check_https(domain: str) -> Check:
    context = ssl.create_default_context()
    request = (
        f"HEAD / HTTP/1.1\r\n"
        f"Host: {domain}\r\n"
        f"User-Agent: {USER_AGENT}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    try:
        infos = socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        return Check("FAIL", f"HTTPS {domain}", str(exc))

    ordered_infos = sorted(infos, key=lambda item: item[0] == socket.AF_INET6)
    errors: list[str] = []
    for family, socktype, proto, _canonname, sockaddr in ordered_infos:
        address = sockaddr[0]
        raw_sock: socket.socket | None = None
        try:
            raw_sock = socket.socket(family, socktype, proto)
            raw_sock.settimeout(4)
            raw_sock.connect(sockaddr)
            with raw_sock as sock:
                with context.wrap_socket(sock, server_hostname=domain) as tls:
                    tls.settimeout(4)
                    tls.sendall(request)
                    response = tls.recv(128).decode("latin-1", errors="replace").strip()
            first_line = response.splitlines()[0] if response else "connected, no response line"
            return Check("PASS", f"HTTPS {domain}", f"{first_line} via {address}")
        except OSError as exc:
            errors.append(f"{address}: {exc}")
            if raw_sock is not None:
                raw_sock.close()

    detail = "; ".join(errors[:4]) if errors else "no address succeeded"
    return Check("FAIL", f"HTTPS {domain}", detail)


def check_proxy_env() -> list[Check]:
    configured = [(key, os.environ[key]) for key in PROXY_ENV_KEYS if os.environ.get(key)]
    no_proxy = [(key, os.environ[key]) for key in NO_PROXY_ENV_KEYS if os.environ.get(key)]
    checks: list[Check] = []
    if not configured:
        checks.append(
            Check(
                "WARN",
                "terminal proxy env",
                "missing; terminal requests go direct unless your shell or tool config sets a proxy elsewhere",
            )
        )
    else:
        details = ", ".join(f"{key}={redact_proxy_value(value)}" for key, value in configured)
        checks.append(Check("PASS", "terminal proxy env", details))
        socks = [key for key, value in configured if proxy_uses_socks(value)]
        if socks:
            checks.append(
                Check(
                    "WARN",
                    "SOCKS proxy env",
                    f"{', '.join(socks)} uses SOCKS; Python stdlib urllib may not support SOCKS without extra dependencies",
                )
            )

    if no_proxy:
        details = ", ".join(f"{key}=configured" for key, _value in no_proxy)
        checks.append(
            Check(
                "WARN",
                "terminal no_proxy env",
                f"{details}; this is an exclusion list, not a proxy server",
            )
        )
    return checks


def redact_proxy_value(value: str) -> str:
    parsed = parse.urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return "configured"
    host = parsed.hostname or ""
    try:
        port_value = parsed.port
    except ValueError:
        port_value = None
    port = f":{port_value}" if port_value else ""
    credentials = "***@" if parsed.username or parsed.password else ""
    netloc = f"{credentials}{host}{port}"
    return parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def proxy_uses_socks(value: str) -> bool:
    return parse.urlsplit(value).scheme.lower().startswith("socks")


def check_reddit_policy() -> list[Check]:
    probe = request.Request(
        REDDIT_PROBE_URL,
        method="GET",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    try:
        with request.urlopen(probe, timeout=8) as response:
            status = getattr(response, "status", 0) or response.getcode()
            return [Check("PASS", "Reddit proxy-aware HTTP", f"HTTP {status}; terminal can reach Reddit via urllib")]
    except error.HTTPError as exc:
        error_type = classify_http_status(exc.code)
        status = "FAIL" if error_type in {"forbidden_403", "rate_limited_429"} else "WARN"
        return [
            Check(
                status,
                "Reddit proxy-aware HTTP",
                f"{error_type}: HTTP {exc.code} {exc.reason}; terminal reached Reddit but Reddit refused the request",
            )
        ]
    except error.URLError as exc:
        message = str(getattr(exc, "reason", exc))
        error_type = classify_network_error(message)
        return [Check("FAIL", "Reddit proxy-aware HTTP", f"{error_type}: {message}")]
    except OSError as exc:
        error_type = classify_network_error(str(exc))
        return [Check("FAIL", "Reddit proxy-aware HTTP", f"{error_type}: {exc}")]


def classify_http_status(status: int) -> str:
    if status == 403:
        return "forbidden_403"
    if status == 429:
        return "rate_limited_429"
    if 400 <= status < 500:
        return "client_error"
    if status >= 500:
        return "server_error"
    return "ok"


def classify_network_error(message: str) -> str:
    normalized = message.lower()
    if (
        "nodename nor servname" in normalized
        or "name resolution" in normalized
        or "failed to resolve" in normalized
        or "temporary failure in name resolution" in normalized
    ):
        return "dns_error"
    if "timed out" in normalized or "timeout" in normalized:
        return "timeout"
    if "connection reset" in normalized or "connection aborted" in normalized:
        return "connection_reset"
    if "proxy" in normalized:
        return "proxy_error"
    return "network_error"


def check_tools() -> list[Check]:
    ytdlp = shutil.which("yt-dlp")
    if ytdlp:
        return [Check("PASS", "yt-dlp", ytdlp)]
    return [Check("WARN", "yt-dlp", "missing; YouTube live mode will stay disabled")]


def check_env_files() -> list[Check]:
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"
    checks = []
    checks.append(
        Check(
            "WARN" if env_path.exists() else "PASS",
            ".env",
            "exists locally and should never be committed" if env_path.exists() else "missing; OK for mock and Reddit public tests",
        )
    )
    checks.append(exists_check(".env.example", example_path))
    return checks


def check_env_vars() -> list[Check]:
    checks = []
    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value:
            checks.append(Check("PASS", f"env {key}", "configured"))
        else:
            checks.append(Check("WARN", f"env {key}", "missing"))
    return checks


def check_model_provider() -> list[Check]:
    configured = os.environ.get("MODEL_PROVIDER", "rules").strip().lower()
    if configured in SUPPORTED_MODEL_PROVIDERS:
        source = "environment" if os.environ.get("MODEL_PROVIDER") else "default"
        return [Check("PASS", "MODEL_PROVIDER", f"{configured} ({source})")]
    supported = ", ".join(sorted(SUPPORTED_MODEL_PROVIDERS))
    return [
        Check(
            "FAIL",
            "MODEL_PROVIDER",
            f"unsupported: {configured}; currently supported: {supported}",
        )
    ]


def print_section(title: str, checks: list[Check], status: str) -> None:
    print(f"\n## {title}")
    section = [check for check in checks if check.status == status]
    if not section:
        print("- none")
        return
    for check in section:
        print(f"- {check.label}: {check.detail}")


def print_next_steps(checks: list[Check]) -> None:
    print("\n## NEXT STEPS")
    failures = {check.label: check.detail for check in checks if check.status == "FAIL"}
    warnings = {check.label: check.detail for check in checks if check.status == "WARN"}

    reddit_policy = failures.get("Reddit proxy-aware HTTP") or warnings.get("Reddit proxy-aware HTTP")
    if (
        any(label.startswith("DNS www.reddit.com") or label.startswith("HTTPS www.reddit.com") for label in failures)
        and not reddit_policy
    ):
        print("- Fix Reddit DNS/HTTPS access before expecting `--mode live` to return real Reddit evidence.")
    if reddit_policy:
        if "forbidden_403" in reddit_policy:
            print("- Reddit returned 403. Usually this is proxy exit/IP/User-Agent/access-policy related, not a report-generation bug.")
            print("- Try another proxy node, verify terminal proxy variables, then wait before retrying live mode.")
        elif "rate_limited_429" in reddit_policy:
            print("- Reddit returned 429. Wait at least 30 minutes and avoid repeated `--force` runs.")
        elif "dns_error" in reddit_policy:
            print("- Reddit DNS failed through Python urllib. Check DNS, proxy, or run from a local terminal with network access.")
        elif "proxy_error" in reddit_policy:
            print("- Python reported a proxy error. Check proxy URL format and whether the proxy is reachable from this terminal.")
        else:
            print("- Reddit proxy-aware HTTP failed. Compare browser access with terminal proxy settings before retrying live mode.")
    if "terminal proxy env" in warnings:
        print("- Browser proxy does not automatically apply to terminal commands. Configure HTTPS_PROXY/HTTP_PROXY/ALL_PROXY if needed.")
    if "last30days-skill repo" in failures or "last30days.py" in failures:
        print("- Clone last30days-skill to /Users/zhuyixiao/Documents/GitHub/last30days-skill.")
    if "Python >= 3.12" in failures:
        print("- Run with the Codex Python 3.12 path documented in README.md.")
    if "yt-dlp" in warnings:
        print("- Keep YouTube disabled until the project moves past Reddit live mode.")
    if ".env.example" in failures:
        print("- Restore .env.example from the repository before configuring live-mode keys.")
    if "MODEL_PROVIDER" in failures:
        print("- Set MODEL_PROVIDER=rules. Other model providers are reserved for future versions.")
    if not failures:
        reddit_proxy_ok = any(
            check.label == "Reddit proxy-aware HTTP" and check.status == "PASS"
            for check in checks
        )
        if reddit_proxy_ok:
            print("- Mock mode is ready. Reddit proxy-aware HTTP is PASS; live has a terminal HTTP path to Reddit.")
        else:
            print("- Mock mode is ready. For Reddit live mode, verify Reddit proxy-aware HTTP PASS in this report.")
    print("- Do not commit .env or real API keys.")


if __name__ == "__main__":
    raise SystemExit(main())
