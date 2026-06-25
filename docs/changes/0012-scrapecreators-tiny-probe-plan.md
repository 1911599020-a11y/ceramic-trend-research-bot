---
id: 0012
title: ScrapeCreators tiny live probe 方案
status: accepted
version: V0.6.3-plan
date: 2026-06-25
supersedes: none
related:
  - docs/plans/2026-06-25-scrapecreators-tiny-probe.md
  - docs/live-readiness-checklist.md
  - README.md
  - docs/workflow.md
  - AGENTS.md
---

## 背景 / Context

V0.6.2 已经提供真实 live 前检查清单。下一步不是直接接入 ScrapeCreators，
而是先设计一个极小、可停止、不污染正式报告的 key-backed probe。

## 决策 / Decision

新增 `docs/plans/2026-06-25-scrapecreators-tiny-probe.md`，作为 V0.6.3 的实现方案。

方案明确：

- tiny probe 默认不联网。
- 只有用户明确加确认参数时才允许真实 API 请求。
- 输出只写入 `local_outputs/`。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不把 `scrapecreators_reddit` 改成可用数据源。
- 不猜测 ScrapeCreators API endpoint，必须基于官方文档或用户提供的样例实现。

本次只写方案，不配置 key，不调用 API，不修改 `last30days-skill`。

## 测试 / Testing

- `git diff --check`
- 敏感信息扫描：确认没有真实 key、没有 conflict marker。
- `bash scripts/check_scrapecreators_ready.sh`
- `bash scripts/run_mock.sh`

## 影响 / Consequences

- 优点：V0.6.3 实现前有明确安全边界。
- 优点：避免从 readiness 直接跳到正式 live source。
- 优点：为后续测试、脚本和错误分类提前拆好任务。
- 代价：本次仍不产生真实 ScrapeCreators 数据。

## 回滚 / Rollback

删除 `docs/plans/2026-06-25-scrapecreators-tiny-probe.md`，并移除 README、workflow、AGENTS 中的链接即可。
