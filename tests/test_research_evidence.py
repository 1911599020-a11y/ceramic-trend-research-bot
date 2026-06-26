from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ceramic_report import (
    DEFAULT_RESEARCH_EVIDENCE_PATH,
    ResearchEvidence,
    TopicRun,
    append_research_evidence_section,
    load_research_evidence,
    long_term_tool_ideas,
    main,
    render_report,
)


class ResearchEvidenceTests(unittest.TestCase):
    def test_loads_default_research_evidence(self) -> None:
        evidence = load_research_evidence(DEFAULT_RESEARCH_EVIDENCE_PATH)
        titles = [item.title for item in evidence]

        self.assertGreaterEqual(len(evidence), 2)
        self.assertTrue(any("GlazyBench" in title for title in titles))
        self.assertTrue(any("ClayScape" in title for title in titles))
        self.assertTrue(all(isinstance(item, ResearchEvidence) for item in evidence))

    def test_missing_research_evidence_file_is_optional(self) -> None:
        missing = Path(tempfile.gettempdir()) / "missing-research-evidence.json"

        self.assertEqual(load_research_evidence(missing), [])

    def test_append_research_evidence_section_marks_limits(self) -> None:
        evidence = load_research_evidence(DEFAULT_RESEARCH_EVIDENCE_PATH)
        lines: list[str] = []

        append_research_evidence_section(lines, evidence[:1])
        rendered = "\n".join(lines)

        self.assertIn("## 研究证据", rendered)
        self.assertIn("不是本轮 Reddit 热度", rendered)
        self.assertIn("GlazyBench", rendered)
        self.assertIn("许可证", rendered)

    def test_long_term_tool_ideas_include_research_but_stay_qualified(self) -> None:
        evidence = load_research_evidence(DEFAULT_RESEARCH_EVIDENCE_PATH)
        ideas = "\n".join(long_term_tool_ideas(evidence))

        self.assertIn("研究证据启发", ideas)
        self.assertIn("不是本轮社媒数据直接证明", ideas)

    def test_render_report_includes_research_section(self) -> None:
        evidence = load_research_evidence(DEFAULT_RESEARCH_EVIDENCE_PATH)
        report = render_report(
            [TopicRun(topic="ceramic glaze", report={}, evidence=[])],
            "# template",
            mode="mock",
            model_provider="rules",
            research_evidence=evidence[:1],
        )

        self.assertIn("## 研究证据", report)
        self.assertIn("GlazyBench", report)
        self.assertIn("研究证据补充", report)
        self.assertIn("AI glaze prediction", report)
        self.assertIn("## 内容选题", report)

    def test_render_report_hides_prompt_template_by_default(self) -> None:
        report = render_report(
            [TopicRun(topic="ceramic glaze", report={}, evidence=[])],
            "# template",
            mode="mock",
            model_provider="rules",
        )

        self.assertNotIn("## 当前报告模板", report)
        self.assertNotIn("# template", report)

    def test_render_report_can_include_prompt_template_for_debugging(self) -> None:
        report = render_report(
            [TopicRun(topic="ceramic glaze", report={}, evidence=[])],
            "# template",
            mode="mock",
            model_provider="rules",
            include_prompt_template=True,
        )

        self.assertIn("## 当前报告模板", report)
        self.assertIn("# template", report)

    def test_cli_no_research_evidence_skips_research_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.md"
            state = Path(tmp) / "state.json"
            argv = [
                "ceramic_report.py",
                "--mode",
                "mock",
                "--no-research-evidence",
                "--output",
                str(output),
                "--state-file",
                str(state),
            ]

            with mock.patch("sys.argv", argv):
                exit_code = main()

            rendered = output.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertNotIn("GlazyBench", rendered)
        self.assertNotIn("ClayScape", rendered)
        self.assertNotIn("研究证据补充", rendered)


if __name__ == "__main__":
    unittest.main()
