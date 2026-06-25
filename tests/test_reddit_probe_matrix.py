from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib import error


def load_probe_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "reddit_probe_matrix.py"
    spec = importlib.util.spec_from_file_location("reddit_probe_matrix", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe_matrix = load_probe_module()


class RedditProbeMatrixTests(unittest.TestCase):
    def test_build_probes_includes_live_relevant_json_shapes(self) -> None:
        probes = probe_matrix.build_probes()
        keys = {probe.key for probe in probes}

        self.assertIn("global_search_app_json", keys)
        self.assertIn("global_search_browser_json", keys)
        self.assertIn("subreddit_search_browser_json", keys)
        live_relevant = [probe for probe in probes if probe.live_relevant]
        self.assertTrue(all("search.json" in probe.url for probe in live_relevant))

    def test_run_probe_returns_pass_for_json_response(self) -> None:
        class FakeHeaders(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class FakeResponse:
            status = 200
            headers = FakeHeaders({"Content-Type": "application/json; charset=utf-8"})

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def getcode(self):
                return 200

            def read(self, _size):
                return b'{"data":{"children":[]}}'

        sample_probe = probe_matrix.build_probes()[1]
        with mock.patch.object(probe_matrix.request, "urlopen", return_value=FakeResponse()):
            result = probe_matrix.run_probe(sample_probe)

        self.assertEqual(result.status, "PASS")
        self.assertIn("HTTP 200", result.detail)

    def test_run_probe_reports_http_error(self) -> None:
        sample_probe = probe_matrix.build_probes()[1]
        http_error = error.HTTPError(
            sample_probe.url,
            403,
            "Blocked",
            hdrs=None,
            fp=None,
        )
        with mock.patch.object(probe_matrix.request, "urlopen", side_effect=http_error):
            result = probe_matrix.run_probe(sample_probe)

        self.assertEqual(result.status, "FAIL")
        self.assertIn("HTTP 403", result.detail)

    def test_next_steps_detects_user_agent_difference(self) -> None:
        probes = {probe.key: probe for probe in probe_matrix.build_probes()}
        results = [
            probe_matrix.ProbeResult(probes["root_browser_html"], "PASS", "HTTP 200"),
            probe_matrix.ProbeResult(probes["global_search_app_json"], "FAIL", "HTTP 403"),
            probe_matrix.ProbeResult(probes["global_search_browser_json"], "PASS", "HTTP 200"),
            probe_matrix.ProbeResult(probes["subreddit_search_browser_json"], "PASS", "HTTP 200"),
        ]

        steps = "\n".join(probe_matrix.next_steps(results))

        self.assertIn("App User-Agent fails but browser User-Agent works", steps)


if __name__ == "__main__":
    unittest.main()
