---
id: 0016
title: Small-batch keyword quality check
version: V0.6.6
date: 2026-06-26
files:
  - config/scrapecreators_quality_topics.json
  - scripts/run_keyword_quality_check.sh
  - scripts/summarize_keyword_quality.py
  - README.md
  - docs/workflow.md
  - AGENTS.md
  - tests/test_keyword_quality.py
---

## 背景

V0.6.4 已经验证 ScrapeCreators 正式 live 可以生成真实 Reddit 报告。
V0.6.5 又加入了正式 live runner 和 API 额度保护。
下一步需要判断哪些关键词值得长期追踪，但不应该直接跑完整 10 个关键词。

## 决策

新增小批量关键词质量测试流程：

- `config/scrapecreators_quality_topics.json`：默认只测试 `kiln firing`、`ceramic business`、`AI ceramic design`，并保留完整相关性规则。
- `scripts/run_keyword_quality_check.sh`：默认 dry-run，不联网、不消耗 API。
- 真实小批量测试必须显式加 `--confirm-live-api`。
- 真实测试输出只写入 `local_outputs/keyword_quality_*`，不更新正式 `reports/latest.md` 或 `reports/archive/`。
- `scripts/summarize_keyword_quality.py` 从测试报告里解析每个关键词的高相关、边缘相关、跑偏数量，生成质量摘要。

## 影响

- 可以逐步判断关键词质量，而不污染正式报告历史。
- 可以在 V0.6.7 “报告 + 解析”前，先知道哪些关键词真的有料。
- 仍然保持 ScrapeCreators API 消耗必须显式确认。

## 验证

- `bash scripts/run_keyword_quality_check.sh`
- `python scripts/summarize_keyword_quality.py`
- `python -m unittest discover tests`
- `git diff --check`

## 回滚

- 删除 `config/scrapecreators_quality_topics.json`。
- 删除 `scripts/run_keyword_quality_check.sh` 和 `scripts/summarize_keyword_quality.py`。
- 删除对应测试和文档说明。
