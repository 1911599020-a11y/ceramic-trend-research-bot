---
version: V0.7.4
date: 2026-06-28
type: feature
scope: keyword-quality
---

# 关键词质量收敛计划

## 背景

V0.7.3 已经能用真实 Reddit/ScrapeCreators 小样本和 DeepSeek 做风险优先质检，但下一步还需要把质检结果转成“下一轮搜什么、少搜什么、保留什么”的人工可读计划。

## 改动

- 新增 `scripts/summarize_keyword_convergence.py`。
- 新增 `scripts/summarize_keyword_convergence.sh`。
- 新增 `tests/test_keyword_convergence.py`。
- 更新 `config/scrapecreators_quality_topics.json`，新增 `quality_convergence.candidate_topics`，作为下一轮人工确认候选池。
- 更新 `README.md`、`AGENTS.md` 和 `docs/workflow.md`。

## 行为

- 默认读取 `local_outputs/llm_scoring_real_sample_comparison.json`。
- 输出：
  - `local_outputs/keyword_convergence_plan.md`
  - `local_outputs/keyword_convergence_plan.json`
- 如果缺少 V0.7.3 输入文件，会生成清楚说明，不崩溃。
- 输出中包含：
  - 关键词动作表
  - 下一轮建议测试关键词
  - 需要人工复核的样本
  - 成本说明
  - 使用说明

## 安全边界

- 不联网。
- 不调用 DeepSeek。
- 不调用 ScrapeCreators。
- 不修改 `reports/`。
- 不自动修改 `config/scrapecreators_quality_topics.json` 的 active `topics`。
- 不修改 `last30days-skill`。

## 后续

下一步可以在用户明确授权后真实复跑 V0.7.3，再运行 V0.7.4 收敛计划；如果结果稳定，再人工调整 `config/scrapecreators_quality_topics.json` 的 active `topics`。
