---
id: 0007
title: 本地研究证据进入报告
status: accepted
version: V0.5.7
date: 2026-06-25
supersedes: none
related:
  - data/research_evidence.json
  - ceramic_report.py
  - tests/test_research_evidence.py
  - prompts/ceramic_report_prompt.md
  - README.md
  - docs/workflow.md
  - research/ceramic-ai-evidence.md
---

## 背景 / Context

V0.5.6 已经明确：ScrapeCreators API key 晚点再申请时，项目先靠稳定数据源和本地证据库继续推进。
但 `research/ceramic-ai-evidence.md` 主要给人阅读，报告生成器还不能稳定读取其中的研究证据。

## 决策 / Decision

新增结构化本地研究证据入口：

- 新增 `data/research_evidence.json`，保存 GlazyBench、ClayScape 等研究证据。
- `ceramic_report.py` 默认读取该 JSON，并在报告中新增 `## 研究证据` 模块。
- 研究证据只用于长期产品方向、下一轮搜索建议和专业背景，不计入 Reddit 高相关趋势。
- 新增 `--research-evidence` 参数，可指定本地证据 JSON。
- 新增 `--no-research-evidence` 参数，可临时关闭该模块。

本次不联网，不配置 API key，不修改 `last30days-skill`。

## 测试 / Testing

- `/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover tests`
- `bash scripts/run_mock.sh`
- `git diff --check`

## 影响 / Consequences

- 优点：报告现在能同时呈现社媒证据和本地研究证据，但二者明确分层。
- 优点：GlazyBench / ClayScape 可以稳定进入报告，不依赖 Reddit live。
- 优点：后续接论文或 GitHub source adapter 时已有结构化样本。
- 代价：需要手动维护 `data/research_evidence.json`，暂时不会自动从 Markdown 或网络同步。

## 回滚 / Rollback

删除 `data/research_evidence.json`、移除 `ceramic_report.py` 的 research evidence 读取与渲染逻辑，并删除对应测试即可。
