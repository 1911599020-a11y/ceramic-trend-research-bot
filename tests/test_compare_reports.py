from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "compare_reports.py"
    spec = importlib.util.spec_from_file_location("compare_reports", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CompareReportsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_comparison_copy_is_platform_neutral(self) -> None:
        previous = self.module.ParsedReport(
            path=Path("reports/archive/previous_report.md"),
            high_count=2,
            edge_count=1,
            low_count=0,
            summary_keywords={"ceramic glaze"},
            high_keywords={"ceramic glaze"},
            suggested_keywords=set(),
            noise_keywords=set(),
        )
        latest = self.module.ParsedReport(
            path=Path("reports/archive/latest_report.md"),
            high_count=5,
            edge_count=2,
            low_count=0,
            summary_keywords={"ceramic glaze", "kiln firing"},
            high_keywords={"ceramic glaze", "kiln firing"},
            suggested_keywords={"handmade pottery"},
            noise_keywords=set(),
        )

        text = self.module.render_comparison(previous, latest, archive_count=3)

        self.assertIn("最新一期 live 抓取结果", text)
        self.assertIn("如果 live 继续失败", text)
        self.assertNotIn("Reddit 抓取结果", text)
        self.assertNotIn("Reddit live 继续失败", text)


if __name__ == "__main__":
    unittest.main()
