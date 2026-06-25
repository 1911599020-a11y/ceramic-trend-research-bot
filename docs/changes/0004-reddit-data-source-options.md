---
id: 0004
title: Reddit 数据源替代路径评估
status: accepted
version: V0.5.4
date: 2026-06-25
supersedes: none
related:
  - docs/reddit-data-source-options.md
  - docs/troubleshooting.md
  - README.md
---

## 背景 / Context

V0.5.3 的 Reddit 请求矩阵显示：当前网络出口可以访问 Reddit 首页，但 `search.json` 公共搜索接口返回
403 Blocked。这个结果说明问题不只是关键词、报告渲染或单个 User-Agent，而是 Reddit 搜索数据入口本身不稳定。

## 决策 / Decision

新增 `docs/reddit-data-source-options.md`，把后续 Reddit 数据源路线拆成三类：

- 继续尝试免费 Reddit public JSON。
- 使用 `last30days-skill` 已支持的 ScrapeCreators Reddit API 备份路径。
- 暂时绕开 Reddit，先推进 GitHub / 论文 / YouTube 等更稳定来源。

当前推荐下一步是先做 ScrapeCreators readiness mode，只检查配置是否准备好，不配置真实 key，不抓取真实数据。

## 测试 / Testing

本次是文档和决策入口更新，不改变运行时代码。验证方式：

- 检查新增文档、README 和 troubleshooting 入口。
- 运行 `git diff --check`。
- 运行 `/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover tests`。

## 影响 / Consequences

- 优点：后续不会把 Reddit 403 误判成报告逻辑损坏。
- 优点：明确了 public JSON、ScrapeCreators API 和其他数据源三条路线的取舍。
- 优点：为 V0.5.5 的 ScrapeCreators readiness check 留出清晰边界。
- 代价：本次不解决 Reddit live 403 本身，只做路线判断。

## 回滚 / Rollback

删除 `docs/reddit-data-source-options.md`，并移除 README / troubleshooting 里的链接即可；不会影响 mock、live、archive 或 compare 逻辑。
