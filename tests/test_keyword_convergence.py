from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def load_keyword_convergence_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "summarize_keyword_convergence.py"
    )
    spec = importlib.util.spec_from_file_location("summarize_keyword_convergence", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class KeywordConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_keyword_convergence_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)
        self.input_file = self.root / "llm_scoring_real_sample_comparison.json"
        self.output_file = self.root / "keyword_convergence_plan.md"
        self.json_file = self.root / "keyword_convergence_plan.json"
        self.topics_file = self.root / "topics.json"
        self.topics_file.write_text(
            json.dumps({"topics": ["kiln firing", "ceramic business", "AI ceramic design"]}),
            encoding="utf-8",
        )

    def args(self, *extra: str) -> list[str]:
        return [
            "--input",
            str(self.input_file),
            "--output",
            str(self.output_file),
            "--json-output",
            str(self.json_file),
            "--topics",
            str(self.topics_file),
            *extra,
        ]

    def test_missing_input_writes_clear_plan_without_crashing(self) -> None:
        exit_code = self.module.main(self.args(), allow_outside_local_outputs=True)

        payload = json.loads(self.json_file.read_text(encoding="utf-8"))
        markdown = self.output_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "missing_input")
        self.assertFalse(payload["report_files_updated"])
        self.assertFalse(payload["config_files_updated"])
        self.assertIn("尚未找到 V0.7.3", markdown)
        self.assertIn("kiln firing", markdown)

    def test_success_generates_keyword_convergence_plan(self) -> None:
        self.input_file.write_text(
            json.dumps(
                {
                    "status": "success",
                    "sample_count": 5,
                    "sampling_strategy": "risk_prioritized_quality_check",
                    "sampling_strategy_note": "风险优先抽样，不代表关键词整体分布。",
                    "counts": {"total": 5},
                    "topic_quality": [
                        {
                            "topic": "kiln firing",
                            "sample_count": 2,
                            "agree_high": 2,
                            "support_trend": 2,
                            "bad_sample_count": 0,
                            "review_required": 0,
                            "average_confidence": 88,
                            "quality_label": "可保留",
                            "recommendation": "保留当前关键词。",
                            "suggested_keywords": ["cone 6", "bisque firing"],
                        },
                        {
                            "topic": "AI ceramic design",
                            "sample_count": 3,
                            "agree_high": 0,
                            "support_trend": 0,
                            "bad_sample_count": 2,
                            "review_required": 2,
                            "average_confidence": 75,
                            "quality_label": "降噪优先",
                            "recommendation": "改成更具体 AI 陶瓷词。",
                            "suggested_keywords": [
                                "AI pottery workflow",
                                "ceramic glaze prediction",
                                "generative ceramic pattern",
                            ],
                        },
                    ],
                    "next_keyword_actions": [
                        {
                            "topic": "kiln firing",
                            "action": "keep",
                            "suggested_keywords": ["cone 6", "bisque firing"],
                            "reason": "保留当前关键词。",
                        },
                        {
                            "topic": "AI ceramic design",
                            "action": "de-noise",
                            "suggested_keywords": [
                                "AI pottery workflow",
                                "ceramic glaze prediction",
                                "generative ceramic pattern",
                            ],
                            "reason": "改成更具体 AI 陶瓷词。",
                        },
                    ],
                    "results": [
                        {
                            "sample": {
                                "topic": "AI ceramic design",
                                "title": "Generic AI video with ceramic texture",
                            },
                            "quality_gate": {
                                "review_required": True,
                                "action": "降级为噪音/低相关",
                                "formal_report_policy": "不进入趋势判断。",
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        exit_code = self.module.main(self.args(), allow_outside_local_outputs=True)

        payload = json.loads(self.json_file.read_text(encoding="utf-8"))
        markdown = self.output_file.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["report_files_updated"])
        self.assertFalse(payload["config_files_updated"])
        self.assertIn("AI pottery workflow", payload["proposed_next_round_topics"])
        self.assertIn("ceramic glaze prediction", payload["proposed_next_round_topics"])
        self.assertIn("质检", markdown)
        self.assertIn("风险优先抽样", markdown)
        self.assertIn("Generic AI video", markdown)
        self.assertIn("ScrapeCreators 请求数约等于关键词数", markdown)

    def test_default_rejects_reports_output(self) -> None:
        exit_code = self.module.main(
            [
                "--output",
                "reports/keyword_convergence_plan.md",
                "--json-output",
                "local_outputs/keyword_convergence_plan.json",
            ]
        )

        self.assertEqual(exit_code, 2)

    def test_default_rejects_output_outside_local_outputs(self) -> None:
        exit_code = self.module.main(
            [
                "--output",
                "keyword_convergence_plan.md",
                "--json-output",
                "local_outputs/keyword_convergence_plan.json",
            ]
        )

        self.assertEqual(exit_code, 2)

    def test_dirty_numeric_fields_do_not_crash(self) -> None:
        self.input_file.write_text(
            json.dumps(
                {
                    "status": "success",
                    "sample_count": "abc",
                    "topic_quality": [
                        {
                            "topic": "kiln firing",
                            "sample_count": "abc",
                            "agree_high": "oops",
                            "support_trend": None,
                            "bad_sample_count": "x",
                            "review_required": [],
                            "average_confidence": {},
                            "quality_label": "继续观察",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        exit_code = self.module.main(self.args(), allow_outside_local_outputs=True)

        payload = json.loads(self.json_file.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["topic_quality"][0]["sample_count"], 0)
        self.assertEqual(payload["topic_quality"][0]["agree_high"], 0)


if __name__ == "__main__":
    unittest.main()
