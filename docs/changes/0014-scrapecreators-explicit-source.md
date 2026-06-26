---
id: 0014
title: ScrapeCreators 显式候选数据源
status: accepted
version: V0.6.4
date: 2026-06-26
supersedes: none
related:
  - sources/scrapecreators_source.py
  - ceramic_report.py
  - config/data_sources.json
  - tests/test_scrapecreators_source.py
  - tests/test_data_source_selection.py
  - README.md
  - docs/workflow.md
  - docs/live-readiness-checklist.md
  - AGENTS.md
---

## 背景 / Context

V0.6.3 tiny probe 已经验证：本机 `.env` 中的 ScrapeCreators key 可用，官方 Reddit search
接口可以返回 Reddit 帖子结构。下一步需要让它进入正式报告流程，但不能突然替换默认 live 数据源，
避免无意中消耗 API 额度。

## 决策 / Decision

新增显式可选数据源 `scrapecreators_reddit`：

- `config/data_sources.json` 中 `scrapecreators_reddit` 从 `planned` 改为 `available`。
- `auto` live 默认仍然选择 `reddit_last30days`。
- 只有手动运行 `--data-source scrapecreators_reddit` 才会调用 ScrapeCreators API。
- `CERAMIC_DATA_SOURCE=scrapecreators_reddit` 不会改变默认 CLI 选择，避免环境变量误触付费源。
- `reddit_last30days` 子进程会剥离 ScrapeCreators 相关 key，避免外部工具无意读取 API key。
- `ScrapeCreatorsSource.fetch()` 将官方 `reddit/search` 返回转换为现有 `last30days` 形状。
- 转换后的数据继续走原有陶瓷相关性打分、报告生成、失败保护和归档逻辑。
- 缺 key、401、403、429、quota/billing、timeout、network、parse 等错误会被分类为 live 失败，
  不覆盖上一份成功报告。

## 测试 / Testing

- `python -m unittest tests.test_scrapecreators_source tests.test_data_source_selection tests.test_sources`
- `python -m py_compile ceramic_report.py sources/scrapecreators_source.py sources/__init__.py`
- 后续交付前运行全套 `python -m unittest discover tests`

真实 `--data-source scrapecreators_reddit` live 只在用户明确同意消耗 API 额度时运行。

## 影响 / Consequences

- 优点：Reddit public JSON 被 403/429 阻挡时，可以手动切换到 ScrapeCreators。
- 优点：不改变默认 live 行为，避免无意识消耗付费 API。
- 优点：后续可在此基础上设计人工确认 fallback。
- 代价：当前仍不是自动 fallback；需要用户明确选择数据源。
- 代价：首次正式 ScrapeCreators live 推荐使用 `config/scrapecreators_probe_topics.json`，
  只跑一个关键词但保留完整相关性规则。

## 回滚 / Rollback

将 `config/data_sources.json` 中 `scrapecreators_reddit` 改回 `planned`，并让
`ScrapeCreatorsSource.fetch()` 恢复为直接报错的占位实现即可。`auto` 默认 live 不受影响。
