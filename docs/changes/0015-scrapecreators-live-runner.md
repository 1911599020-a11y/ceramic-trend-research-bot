---
id: 0015
title: ScrapeCreators live runner with quota guard
version: V0.6.5
date: 2026-06-26
files:
  - ceramic_report.py
  - scripts/run_scrapecreators_live.sh
  - README.md
  - docs/workflow.md
  - AGENTS.md
  - tests/test_data_source_selection.py
  - tests/test_research_evidence.py
---

## 背景

V0.6.4 已经验证 `scrapecreators_reddit` 可以作为显式可选正式数据源进入报告流程。
但手写完整 Python 命令太长，且容易误跑完整关键词列表，造成不必要的 API 额度消耗。
同时正式报告末尾固定附加 prompt 模板，适合开发期排查，但不适合日常阅读。

## 决策

新增 `scripts/run_scrapecreators_live.sh` 作为正式 ScrapeCreators live 入口：

- 默认只使用 `config/scrapecreators_probe_topics.json` 的单关键词配置。
- `--dry-run` 只打印命令，不联网、不消耗 API。
- 只有显式加 `--confirm-full-api` 才使用完整 `config/ceramic_topics.json`。
- 继续使用 `reports/report.md`、`reports/latest.md` 和 `reports/archive/` 的成功归档机制。

报告渲染新增 `--include-prompt-template`：

- 默认不再把 `prompts/ceramic_report_prompt.md` 附加到正式报告末尾。
- 需要调试报告结构时，可以显式打开。

## 影响

- ScrapeCreators 正式 live 更适合日常手动运行。
- 默认路径更省 API 额度。
- 正式报告更短、更像给陶瓷创作者阅读的趋势简报。
- `run_live.sh` 仍然默认使用 `reddit_last30days`，不会自动切到 ScrapeCreators。

## 验证

- `bash scripts/run_scrapecreators_live.sh --dry-run`
- `bash scripts/run_scrapecreators_live.sh --dry-run --confirm-full-api`
- `python -m unittest discover tests`
- `python -m py_compile ceramic_report.py sources/last30days_source.py sources/scrapecreators_source.py scripts/probe_scrapecreators_reddit.py`
- `git diff --check`

## 回滚

- 删除 `scripts/run_scrapecreators_live.sh`。
- 将 `render_report(..., include_prompt_template=False)` 恢复为固定附加 prompt 模板。
- 移除 README / workflow / AGENTS 中关于 V0.6.5 runner 的说明。
