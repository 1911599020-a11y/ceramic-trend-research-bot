from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import ceramic_report


def load_keyword_quality_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "summarize_keyword_quality.py"
    )
    spec = importlib.util.spec_from_file_location("summarize_keyword_quality", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


quality = load_keyword_quality_module()


class KeywordQualityTests(unittest.TestCase):
    def test_quality_topics_keep_relevance_rules(self) -> None:
        path = ceramic_report.PROJECT_ROOT / "config" / "scrapecreators_quality_topics.json"
        config = ceramic_report.load_config(path)
        relevance = ceramic_report.load_relevance_config(config)

        self.assertEqual(
            ceramic_report.load_topics(path),
            ["kiln firing", "ceramic business", "AI ceramic design"],
        )
        self.assertIn("pottery", relevance.recommended_subreddits)
        self.assertIn("kiln", relevance.positive_terms)
        self.assertIn("kiln firing", {key.lower() for key in relevance.topic_rules})
        self.assertIn("ceramic business", {key.lower() for key in relevance.topic_rules})
        self.assertIn("ai ceramic design", {key.lower() for key in relevance.topic_rules})

    def test_keyword_quality_runner_defaults_to_dry_run_local_outputs(self) -> None:
        result = subprocess.run(
            ["bash", "scripts/run_keyword_quality_check.sh"],
            cwd=ceramic_report.PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout
        self.assertIn("Dry run", output)
        self.assertIn("--data-source scrapecreators_reddit", output)
        self.assertIn("config/scrapecreators_quality_topics.json", output)
        self.assertIn("local_outputs/keyword_quality_report.md", output)
        self.assertIn("local_outputs/keyword_quality_latest.md", output)
        self.assertIn("local_outputs/keyword_quality_archive", output)
        self.assertIn("真实运行请加：--confirm-live-api", output)

    def test_keyword_quality_runner_dry_run_does_not_create_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "quality"
            result = subprocess.run(
                ["bash", "scripts/run_keyword_quality_check.sh", "--dry-run"],
                cwd=ceramic_report.PROJECT_ROOT,
                env={**os.environ, "KEYWORD_QUALITY_OUTPUT_DIR": str(output_dir)},
                capture_output=True,
                text=True,
                check=True,
            )

        self.assertIn("Dry run", result.stdout)
        self.assertFalse(output_dir.exists())

    def test_keyword_quality_runner_confirm_live_api_disables_dry_run_in_script(self) -> None:
        script = (
            ceramic_report.PROJECT_ROOT / "scripts" / "run_keyword_quality_check.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("--confirm-live-api", script)
        self.assertIn("DRY_RUN=0", script)
        self.assertIn("local_outputs", script)

    def test_keyword_quality_runner_does_not_summarize_stale_success_state(self) -> None:
        real_python = "/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
        local_outputs = ceramic_report.PROJECT_ROOT / "local_outputs"
        local_outputs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=local_outputs,
            prefix="keyword_quality_test_",
        ) as output_tmp, tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = Path(output_tmp)
            state_path = output_dir / "keyword_quality_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "mode": "live",
                        "last_status": "success",
                        "status": "success",
                        "last_run_at": "2000-01-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            marker = tmp_path / "summary_called"
            fake_python = tmp_path / "fake_python.sh"
            fake_python.write_text(
                f"""#!/usr/bin/env bash
if [[ "$1" == "-B" && "$2" == "ceramic_report.py" ]]; then
  echo "刚刚跑过 live（状态：success）。"
  exit 0
fi
if [[ "$1" == "-B" && "$2" == "scripts/summarize_keyword_quality.py" ]]; then
  echo called > "{marker}"
  exit 0
fi
exec "{real_python}" "$@"
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            result = subprocess.run(
                ["bash", "scripts/run_keyword_quality_check.sh", "--confirm-live-api"],
                cwd=ceramic_report.PROJECT_ROOT,
                env={
                    **os.environ,
                    "CERAMIC_PYTHON": str(fake_python),
                    "KEYWORD_QUALITY_OUTPUT_DIR": str(output_dir),
                },
                capture_output=True,
                text=True,
                check=True,
            )

        self.assertIn("本次不生成摘要", result.stdout)
        self.assertFalse(marker.exists())

    def test_keyword_quality_runner_does_not_summarize_same_second_stale_success(self) -> None:
        real_python = "/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
        local_outputs = ceramic_report.PROJECT_ROOT / "local_outputs"
        local_outputs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=local_outputs,
            prefix="keyword_quality_test_",
        ) as output_tmp, tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = Path(output_tmp)
            same_second = "2026-06-26T10:00:00+08:00"
            state_path = output_dir / "keyword_quality_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "mode": "live",
                        "last_status": "success",
                        "status": "success",
                        "last_run_at": same_second,
                    }
                ),
                encoding="utf-8",
            )
            marker = tmp_path / "summary_called"
            fake_python = tmp_path / "fake_python.sh"
            fake_python.write_text(
                f"""#!/usr/bin/env bash
if [[ "$1" == "-" && "$#" -eq 1 ]]; then
  cat >/dev/null
  echo "{same_second}"
  exit 0
fi
if [[ "$1" == "-B" && "$2" == "ceramic_report.py" ]]; then
  echo "刚刚跑过 live（状态：success）。"
  exit 0
fi
if [[ "$1" == "-B" && "$2" == "scripts/summarize_keyword_quality.py" ]]; then
  echo called > "{marker}"
  exit 0
fi
exec "{real_python}" "$@"
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            result = subprocess.run(
                ["bash", "scripts/run_keyword_quality_check.sh", "--confirm-live-api"],
                cwd=ceramic_report.PROJECT_ROOT,
                env={
                    **os.environ,
                    "CERAMIC_PYTHON": str(fake_python),
                    "KEYWORD_QUALITY_OUTPUT_DIR": str(output_dir),
                },
                capture_output=True,
                text=True,
                check=True,
            )

        self.assertIn("本次不生成摘要", result.stdout)
        self.assertFalse(marker.exists())

    def test_keyword_quality_runner_rejects_real_run_outside_local_outputs(self) -> None:
        result = subprocess.run(
            ["bash", "scripts/run_keyword_quality_check.sh", "--confirm-live-api"],
            cwd=ceramic_report.PROJECT_ROOT,
            env={
                **os.environ,
                "KEYWORD_QUALITY_OUTPUT_DIR": str(ceramic_report.PROJECT_ROOT / "reports"),
            },
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("真实关键词质量测试只允许写入", result.stderr)

    def test_keyword_quality_runner_success_does_not_touch_formal_reports(self) -> None:
        real_python = "/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
        reports_dir = ceramic_report.PROJECT_ROOT / "reports"
        formal_paths = [
            reports_dir / "report.md",
            reports_dir / "latest.md",
        ]

        def snapshot(path: Path) -> tuple[bool, bytes | None, int | None, int | None]:
            if not path.exists():
                return False, None, None, None
            stat = path.stat()
            return True, path.read_bytes(), stat.st_mtime_ns, stat.st_size

        formal_before = {path: snapshot(path) for path in formal_paths}
        archive_before = (
            sorted(path.name for path in (reports_dir / "archive").iterdir())
            if (reports_dir / "archive").exists()
            else []
        )

        local_outputs = ceramic_report.PROJECT_ROOT / "local_outputs"
        local_outputs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=local_outputs,
            prefix="keyword_quality_test_",
        ) as output_tmp, tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = Path(output_tmp)
            fake_python = tmp_path / "fake_python.sh"
            fake_python.write_text(
                f"""#!/usr/bin/env bash
if [[ "$1" == "-B" && "$2" == "ceramic_report.py" ]]; then
  shift 2
  output=""
  latest=""
  archive=""
  state=""
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --output) output="$2"; shift 2 ;;
      --latest) latest="$2"; shift 2 ;;
      --archive-dir) archive="$2"; shift 2 ;;
      --state-file) state="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  mkdir -p "$(dirname "$output")" "$(dirname "$latest")" "$archive" "$(dirname "$state")"
  cat > "$output" <<'REPORT'
# 陶瓷趋势情报报告

## 原始证据/链接

| 相关性 | 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |
|---|---|---|---|---|---|---|
| 高相关 | kiln firing | r/Pottery | Cone 6 firing issue | 10 upvotes | 命中 kiln | [打开](https://example.com/a) |
REPORT
  cp "$output" "$latest"
  cp "$output" "$archive/2099-01-01_0000_report.md"
  cat > "$state" <<'JSON'
{{"mode":"live","status":"success","last_status":"success","last_run_at":"2099-01-01T00:00:00+08:00"}}
JSON
  exit 0
fi
exec "{real_python}" "$@"
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            result = subprocess.run(
                ["bash", "scripts/run_keyword_quality_check.sh", "--confirm-live-api"],
                cwd=ceramic_report.PROJECT_ROOT,
                env={
                    **os.environ,
                    "CERAMIC_PYTHON": str(fake_python),
                    "KEYWORD_QUALITY_OUTPUT_DIR": str(output_dir),
                },
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertIn("已生成", result.stdout)
            self.assertTrue((output_dir / "keyword_quality_summary.md").exists())

        self.assertEqual(formal_before, {path: snapshot(path) for path in formal_paths})
        archive_after = (
            sorted(path.name for path in (reports_dir / "archive").iterdir())
            if (reports_dir / "archive").exists()
            else []
        )
        self.assertEqual(archive_before, archive_after)

    def test_summarize_report_extracts_keyword_quality(self) -> None:
        report = """# 陶瓷趋势情报报告

## 原始证据/链接

| 相关性 | 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |
|---|---|---|---|---|---|---|
| 高相关 | kiln firing | r/Pottery | Cone 6 firing issue | 10 upvotes | 命中 kiln | [打开](https://example.com/a) |
| 边缘相关 | ceramic business | r/crafts | Selling pottery at markets | 5 comments | business | [打开](https://example.com/b) |
| 跑偏样本 | AI ceramic design | r/gaming | AI video about ceramic skin | 1 upvote | gaming | [打开](https://example.com/c) |
"""
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.md"
            report_path.write_text(report, encoding="utf-8")
            summary = quality.summarize_report(
                report_path,
                ["kiln firing", "ceramic business", "AI ceramic design"],
            )

        by_keyword = {item.keyword: item for item in summary}
        self.assertEqual(by_keyword["kiln firing"].high_count, 1)
        self.assertEqual(by_keyword["kiln firing"].top_subreddits, "r/Pottery")
        self.assertEqual(by_keyword["ceramic business"].edge_count, 1)
        self.assertEqual(by_keyword["AI ceramic design"].low_count, 1)
        self.assertIn("改写", by_keyword["AI ceramic design"].decision)

    def test_summarize_report_handles_escaped_pipe_and_dashes(self) -> None:
        report = """# 陶瓷趋势情报报告

## 原始证据/链接

| 相关性 | 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |
|---|---|---|---|---|---|---|
| 高相关 | kiln firing | r/Pottery | Cone 6 \\| kiln --- issue | 10 upvotes | glaze --- kiln signal | [打开](https://example.com/a) |
"""
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.md"
            report_path.write_text(report, encoding="utf-8")
            summary = quality.summarize_report(report_path, ["kiln firing"])

        self.assertEqual(summary[0].high_count, 1)
        self.assertEqual(summary[0].example_text, "Cone 6 | kiln --- issue")

    def test_render_summary_escapes_pipe_in_example_title(self) -> None:
        item = quality.KeywordQuality(keyword="kiln firing", high_count=1)
        item.examples.append("Cone 6 | kiln --- issue")

        text = quality.render_summary(Path("local_outputs/report.md"), [item])

        self.assertIn("Cone 6 \\| kiln --- issue", text)
        self.assertNotIn("Cone 6 | kiln --- issue", text)

    def test_summary_script_rejects_reports_output_path(self) -> None:
        forbidden = ceramic_report.PROJECT_ROOT / "reports" / "keyword_quality_forbidden_test.md"
        self.assertFalse(forbidden.exists())
        result = subprocess.run(
            [
                "/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
                "-B",
                "scripts/summarize_keyword_quality.py",
                "--output",
                str(forbidden),
            ],
            cwd=ceramic_report.PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("不能写入正式 reports", result.stderr)
        self.assertFalse(forbidden.exists())

    def test_missing_report_writes_clear_next_step(self) -> None:
        text = quality.render_missing_report(
            Path("local_outputs/keyword_quality_report.md"),
            ["kiln firing"],
        )

        self.assertIn("尚未找到关键词质量测试报告", text)
        self.assertIn("run_keyword_quality_check.sh --dry-run", text)
        self.assertIn("run_keyword_quality_check.sh --confirm-live-api", text)


if __name__ == "__main__":
    unittest.main()
