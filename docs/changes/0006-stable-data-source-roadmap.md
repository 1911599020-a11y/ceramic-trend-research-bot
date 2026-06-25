---
id: 0006
title: 稳定数据源路线规划
status: accepted
version: V0.5.6
date: 2026-06-25
supersedes: none
related:
  - docs/stable-data-source-roadmap.md
  - research/ceramic-ai-evidence.md
  - README.md
  - docs/workflow.md
---

## 背景 / Context

ScrapeCreators API key 将晚点再申请。当前阶段不应继续被 Reddit public JSON 403 卡住，也不应提前接 YouTube、
Pinterest 或其他需要额外配置的来源。

项目已经有 GlazyBench、ClayScape 等陶瓷 AI 研究证据，适合先沉淀为稳定素材路线。

## 决策 / Decision

新增 `docs/stable-data-source-roadmap.md`，明确短期优先级：

- 先保留 mock 和本地证据库，保证报告结构稳定。
- 把论文和研究项目作为陶瓷 AI 方向的专业证据来源。
- 后续再评估 GitHub、YouTube、ScrapeCreators Reddit。
- Reddit 继续保留，但暂时不作为唯一 live 来源。

同步更新 `research/ceramic-ai-evidence.md`、README 和 workflow，让后续接手者知道：在没有 ScrapeCreators key 时，项目仍然可以继续推进。

## 测试 / Testing

本次只更新文档和研究素材，不改变运行代码。验证方式：

- `git diff --check`
- 检查新增文档和入口链接

## 影响 / Consequences

- 优点：避免项目被 Reddit 403 卡住。
- 优点：把“陶瓷 + AI + 小工具”方向从灵感变成可执行路线。
- 优点：为后续 GitHub / 论文 / YouTube source adapter 留出顺序。
- 代价：本次不新增真实数据抓取能力，也不自动把研究证据写入报告。

## 回滚 / Rollback

删除 `docs/stable-data-source-roadmap.md`，并移除 README / workflow / evidence 中的入口即可；不会影响 mock、live、archive 或 compare 逻辑。
