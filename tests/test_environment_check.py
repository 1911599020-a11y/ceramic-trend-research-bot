from __future__ import annotations

import importlib.util
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


def load_environment_check_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_environment.py"
    spec = importlib.util.spec_from_file_location("check_environment", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


env_check = load_environment_check_module()


class EnvironmentCheckTests(unittest.TestCase):
    def test_redacts_proxy_credentials(self) -> None:
        self.assertEqual(
            env_check.redact_proxy_value("http://user:secret@example.com:8080"),
            "http://***@example.com:8080",
        )

    def test_redacts_proxy_without_printing_raw_value_when_unparseable(self) -> None:
        self.assertEqual(env_check.redact_proxy_value("localhost:7890"), "configured")
        self.assertEqual(env_check.redact_proxy_value("http://localhost:notaport"), "http://localhost")

    def test_detects_socks_proxy(self) -> None:
        self.assertTrue(env_check.proxy_uses_socks("socks5h://127.0.0.1:7890"))
        self.assertFalse(env_check.proxy_uses_socks("http://127.0.0.1:7890"))

    def test_no_proxy_does_not_count_as_proxy_server(self) -> None:
        env = {key: "" for key in env_check.PROXY_ENV_KEYS + env_check.NO_PROXY_ENV_KEYS}
        env["NO_PROXY"] = "localhost,127.0.0.1"
        with mock.patch.dict(os.environ, env, clear=True):
            checks = env_check.check_proxy_env()

        statuses = {check.label: check.status for check in checks}
        self.assertEqual(statuses["terminal proxy env"], "WARN")
        self.assertEqual(statuses["terminal no_proxy env"], "WARN")

    def test_proxy_env_passes_only_for_proxy_server_vars(self) -> None:
        env = {key: "" for key in env_check.PROXY_ENV_KEYS + env_check.NO_PROXY_ENV_KEYS}
        env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
        with mock.patch.dict(os.environ, env, clear=True):
            checks = env_check.check_proxy_env()

        statuses = {check.label: check.status for check in checks}
        self.assertEqual(statuses["terminal proxy env"], "PASS")

    def test_classifies_http_statuses(self) -> None:
        self.assertEqual(env_check.classify_http_status(403), "forbidden_403")
        self.assertEqual(env_check.classify_http_status(429), "rate_limited_429")
        self.assertEqual(env_check.classify_http_status(404), "client_error")
        self.assertEqual(env_check.classify_http_status(503), "server_error")
        self.assertEqual(env_check.classify_http_status(200), "ok")

    def test_classifies_network_errors(self) -> None:
        self.assertEqual(
            env_check.classify_network_error("nodename nor servname provided"),
            "dns_error",
        )
        self.assertEqual(env_check.classify_network_error("The operation timed out"), "timeout")
        self.assertEqual(env_check.classify_network_error("connection reset by peer"), "connection_reset")
        self.assertEqual(env_check.classify_network_error("proxy CONNECT failed"), "proxy_error")
        self.assertEqual(env_check.classify_network_error("something else"), "network_error")

    def test_normalizes_optional_network_failures(self) -> None:
        checks = [
            env_check.Check("FAIL", "HTTPS www.reddit.com", "timed out"),
            env_check.Check("PASS", "Reddit proxy-aware HTTP", "HTTP 200"),
            env_check.Check("FAIL", "HTTPS www.youtube.com", "timed out"),
            env_check.Check("FAIL", "HTTPS github.com", "timed out"),
        ]

        normalized = env_check.normalize_check_statuses(checks)
        statuses = {check.label: check.status for check in normalized}

        self.assertEqual(statuses["HTTPS www.reddit.com"], "WARN")
        self.assertEqual(statuses["HTTPS www.youtube.com"], "WARN")
        self.assertEqual(statuses["HTTPS github.com"], "WARN")

    def test_reddit_probe_matches_live_preflight_shape(self) -> None:
        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def getcode(self):
                return 200

        def fake_urlopen(probe, timeout):
            captured["probe"] = probe
            captured["timeout"] = timeout
            return FakeResponse()

        with mock.patch.object(env_check.request, "urlopen", side_effect=fake_urlopen):
            checks = env_check.check_reddit_policy()

        probe = captured["probe"]
        self.assertEqual(checks[0].status, "PASS")
        self.assertIn("/search.json?", probe.full_url)
        self.assertIn("q=ceramic%20art", probe.full_url)
        self.assertEqual(probe.get_method(), "GET")
        self.assertEqual(probe.get_header("User-agent"), "ceramic-trend-research-bot/0.2")

    def test_scrapecreators_readiness_warns_when_missing(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            checks = env_check.check_scrapecreators_readiness()

        self.assertEqual(checks[0].status, "WARN")
        self.assertEqual(checks[0].label, "ScrapeCreators Reddit fallback")
        self.assertIn("missing", checks[0].detail)

    def test_scrapecreators_readiness_does_not_print_secret(self) -> None:
        with mock.patch.dict(os.environ, {"SCRAPECREATORS_API_KEY": "dummy-token-for-test"}, clear=True):
            checks = env_check.check_scrapecreators_readiness()

        self.assertEqual(checks[0].status, "PASS")
        self.assertIn("configured", checks[0].detail)
        self.assertNotIn("dummy-token-for-test", checks[0].detail)

    def test_forbidden_next_steps_mentions_missing_scrapecreators(self) -> None:
        checks = [
            env_check.Check("FAIL", "Reddit proxy-aware HTTP", "forbidden_403: HTTP 403 Blocked"),
            env_check.Check("WARN", "ScrapeCreators Reddit fallback", "missing"),
        ]
        output = io.StringIO()

        with redirect_stdout(output):
            env_check.print_next_steps(checks)

        text = output.getvalue()
        self.assertIn("ScrapeCreators fallback is missing", text)
        self.assertIn("SCRAPECREATORS_API_KEY", text)


if __name__ == "__main__":
    unittest.main()
