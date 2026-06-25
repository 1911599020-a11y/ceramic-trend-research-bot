---
id: 0011
title: 真实 live 前检查清单
status: accepted
version: V0.6.2
date: 2026-06-25
supersedes: none
related:
  - docs/live-readiness-checklist.md
  - README.md
  - docs/workflow.md
  - AGENTS.md
---

## 背景 / Context

V0.6.1 已经有 ScrapeCreators readiness-only 层，但在真正进入 key-backed API live 测试前，
还需要一份更明确的人工检查清单，避免泄露 key、误消耗额度或污染成功报告。

## 决策 / Decision

新增 `docs/live-readiness-checklist.md`：

- 明确什么时候使用这份清单。
- 区分申请 key 前、拿到 key 后、第一次真实 API live 前、第一次成功后的检查。
- 明确停止条件：401、403、429、quota、billing、key 泄露、失败报告污染正式报告。
- 明确下一阶段入口：只有清单通过后，才进入 V0.6.3 的 ScrapeCreators tiny live probe。

本次只新增文档并同步报告版本标记，不配置 key，不调用 API，不修改 `last30days-skill`。

## 测试 / Testing

- `git diff --check`
- 文档只读复核：确认没有真实 key、没有要求现在调用 ScrapeCreators、没有要求安装 `yt-dlp`。

## 影响 / Consequences

- 优点：第一次真实 API live 前有明确刹车流程。
- 优点：降低 key 泄露、额度误用和报告污染风险。
- 优点：让后续 V0.6.3 的 tiny live probe 有清楚进入条件。
- 代价：这是人工清单，不会自动阻止所有误操作；后续可考虑把关键检查做成脚本。

## 回滚 / Rollback

删除 `docs/live-readiness-checklist.md`，并移除 README、workflow、AGENTS 中的链接即可。
