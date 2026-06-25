---
id: 0008
title: 主线结束后研究产品
status: accepted
version: V0.5.8
date: 2026-06-25
supersedes: none
related:
  - AGENTS.md
  - research/ceramic-ai-evidence.md
  - data/research_evidence.json
---

## 背景 / Context

V0.5.7 已经把 GlazyBench、ClayScape 等本地研究证据接入报告。
继续深挖后，可以发展成自动搜索论文、自动读 PDF、自动总结、自动判断可信度的研究系统。
但这会偏离当前主线：先把社媒趋势情报工具做稳。

## 决策 / Decision

将该方向命名为 **主线结束后研究产品**，并暂时封存为后续延伸产品：

- 当前不启动自动论文研究系统。
- 当前只保留轻量本地证据库和报告补充入口。
- 主线仍优先推进 Reddit / YouTube / Pinterest 等社媒数据源、报告生成、归档和自动运行。
- 主线完成后，再回来评估陶瓷 AI 研究助手 / Ceramic AI Research Product。

保留的接口：

- `research/ceramic-ai-evidence.md`：人读资料入口。
- `data/research_evidence.json`：程序读取入口。
- `ceramic_report.py --research-evidence`：报告接入入口。
- `ceramic_report.py --no-research-evidence`：临时关闭入口。

## 测试 / Testing

- 文档与记忆文件更新，不涉及运行时代码。
- 需执行 `git diff --check` 检查 Markdown / 文本尾随空格。

## 影响 / Consequences

- 优点：把延伸产品方向留住，后续不会丢失上下文。
- 优点：避免当前项目被论文研究系统带偏，主线仍回到社媒趋势情报。
- 优点：已有接口足够后续继续扩展，不需要现在大改架构。
- 代价：暂时不会自动搜索论文、读取 PDF 或判断论文可信度。

## 回滚 / Rollback

删除 `AGENTS.md` 和 `research/ceramic-ai-evidence.md` 中关于“主线结束后研究产品”的段落，并删除本变更记录即可。
