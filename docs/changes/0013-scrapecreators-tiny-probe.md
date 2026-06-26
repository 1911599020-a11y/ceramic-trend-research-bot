---
id: 0013
title: ScrapeCreators tiny live probe
status: accepted
version: V0.6.3
date: 2026-06-25
supersedes:
  - 0012
related:
  - scripts/probe_scrapecreators_reddit.py
  - scripts/probe_scrapecreators_reddit.sh
  - tests/test_scrapecreators_probe.py
  - docs/plans/2026-06-25-scrapecreators-tiny-probe.md
  - docs/live-readiness-checklist.md
  - README.md
  - docs/workflow.md
  - AGENTS.md
---

## 背景 / Context

V0.6.2 已经完成真实 live 前检查清单，V0.6.3-plan 已经明确 tiny probe 的安全边界。
用户已经在本机 `.env` 中配置 ScrapeCreators API key，并授权查阅官方 API 文档。

在正式把 ScrapeCreators 变成报告数据源之前，需要先验证一个更小的问题：

> 当前机器、当前 key、当前网络是否能完成一次极小 Reddit API 请求？

## 决策 / Decision

新增独立 tiny probe：

- `scripts/probe_scrapecreators_reddit.py`
- `scripts/probe_scrapecreators_reddit.sh`
- `tests/test_scrapecreators_probe.py`

probe 行为：

- 默认运行不联网，只写 `local_outputs/scrapecreators_probe_state.json`。
- 只有显式添加 `--confirm-live-api` 才会发起真实 ScrapeCreators 请求。
- 默认 topic 为 `ceramic glaze`。
- 本地保存摘要上限为 1 条，最大不超过 3 条。
- 使用官方 Reddit search endpoint：`https://api.scrapecreators.com/v1/reddit/search`。
- 使用 `x-api-key` header，不打印、不保存 key。
- 输出只写入 `local_outputs/scrapecreators_probe*`。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不把 `scrapecreators_reddit` 改为正式可用数据源。

## 测试 / Testing

- `python -m unittest tests.test_scrapecreators_probe`
- `python -m py_compile scripts/probe_scrapecreators_reddit.py sources/scrapecreators_source.py`
- `python -m unittest discover tests`
- `bash scripts/check_scrapecreators_ready.sh`
- `bash scripts/probe_scrapecreators_reddit.sh`
- `bash scripts/run_mock.sh`
- `git diff --check`

真实 `--confirm-live-api` 请求只能在用户明确同意后运行。

## 影响 / Consequences

- 优点：可以在不污染正式报告的前提下验证 ScrapeCreators key-backed 请求。
- 优点：失败会分类为 missing key、401、403、429、quota/billing、timeout、network、parse 等。
- 优点：为 V0.6.4 是否实现正式 `ScrapeCreatorsSource.fetch()` 提供依据。
- 代价：本版本仍不会把 ScrapeCreators 数据写入正式趋势报告。

## 回滚 / Rollback

删除 `scripts/probe_scrapecreators_reddit.py`、`scripts/probe_scrapecreators_reddit.sh`、
`tests/test_scrapecreators_probe.py`，并移除 README、workflow、live readiness checklist、AGENTS
中关于 V0.6.3 tiny probe 的说明即可。
