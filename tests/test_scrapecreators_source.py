from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from sources.scrapecreators_source import (
    ScrapeCreatorsSource,
    check_scrapecreators_readiness,
    configured_scrapecreators_env_var,
    scrapecreators_status_label,
)


def load_ready_script_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_scrapecreators_ready.py"
    spec = importlib.util.spec_from_file_location("check_scrapecreators_ready", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ScrapeCreatorsSourceTests(unittest.TestCase):
    def test_readiness_reports_missing_without_network(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            readiness = check_scrapecreators_readiness()

        self.assertEqual(readiness.status, "missing")
        self.assertFalse(readiness.can_attempt_api)
        self.assertIn("missing", readiness.detail)

    def test_readiness_reports_configured_without_printing_secret(self) -> None:
        with mock.patch.dict(os.environ, {"SCRAPECREATORS_API_KEY": "secret-token"}, clear=True):
            readiness = check_scrapecreators_readiness()

        self.assertEqual(readiness.status, "configured")
        self.assertTrue(readiness.can_attempt_api)
        self.assertEqual(readiness.configured_env_var, "SCRAPECREATORS_API_KEY")
        self.assertNotIn("secret-token", str(readiness))

    def test_legacy_env_name_is_accepted_without_printing_secret(self) -> None:
        env = {"SCRAPE_CREATORS_API_KEY": "legacy-secret"}

        self.assertEqual(configured_scrapecreators_env_var(env), "SCRAPE_CREATORS_API_KEY")
        self.assertEqual(scrapecreators_status_label(env), "configured")
        self.assertNotIn("legacy-secret", str(check_scrapecreators_readiness(env)))

    def test_placeholder_source_does_not_fetch(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "预留接口"):
            ScrapeCreatorsSource().fetch("ceramic glaze")

    def test_ready_script_does_not_print_secret(self) -> None:
        module = load_ready_script_module()
        output = io.StringIO()

        with mock.patch.dict(os.environ, {"SCRAPECREATORS_API_KEY": "script-secret"}, clear=True):
            with redirect_stdout(output):
                exit_code = module.main()

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("key status: configured", text)
        self.assertIn("network request: not attempted", text)
        self.assertNotIn("script-secret", text)

    def test_ready_script_reads_dotenv_without_printing_secret(self) -> None:
        module = load_ready_script_module()
        output = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(
                "SCRAPECREATORS" + "_API_KEY=" + "dotenv-secret\n",
                encoding="utf-8",
            )
            with redirect_stdout(output):
                exit_code = module.main(env={}, dotenv_path=dotenv_path)

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("key status: configured", text)
        self.assertNotIn("dotenv-secret", text)


if __name__ == "__main__":
    unittest.main()
