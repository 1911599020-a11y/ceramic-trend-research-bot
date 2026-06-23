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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAST30DAYS_REPO = Path("/Users/zhuyixiao/Documents/GitHub/last30days-skill")
LAST30DAYS_SCRIPT = LAST30DAYS_REPO / "skills/last30days/scripts/last30days.py"
DOMAINS = ["www.reddit.com", "www.youtube.com", "github.com"]
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
    checks.extend(check_domains())
    checks.extend(check_tools())
    checks.extend(check_env_files())
    checks.extend(check_model_provider())
    checks.extend(check_env_vars())

    print_section("PASS", checks, "PASS")
    print_section("WARN", checks, "WARN")
    print_section("FAIL", checks, "FAIL")
    print_next_steps(checks)

    return 1 if any(check.status == "FAIL" for check in checks) else 0


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
        "User-Agent: ceramic-trend-research-bot-env-check/0.2.1\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    try:
        with socket.create_connection((domain, 443), timeout=8) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as tls:
                tls.settimeout(8)
                tls.sendall(request)
                response = tls.recv(128).decode("latin-1", errors="replace").strip()
    except OSError as exc:
        return Check("FAIL", f"HTTPS {domain}", str(exc))
    first_line = response.splitlines()[0] if response else "connected, no response line"
    return Check("PASS", f"HTTPS {domain}", first_line)


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

    if any(label.startswith("DNS www.reddit.com") or label.startswith("HTTPS www.reddit.com") for label in failures):
        print("- Fix Reddit DNS/HTTPS access before expecting `--mode live` to return real Reddit evidence.")
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
        print("- Mock mode is ready. For Reddit live mode, verify Reddit DNS/HTTPS PASS in this report.")
    print("- Do not commit .env or real API keys.")


if __name__ == "__main__":
    raise SystemExit(main())
