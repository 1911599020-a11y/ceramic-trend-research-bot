---
version: V0.7.3
date: 2026-06-28
type: feature
scope: llm-scoring
---

# 真实样本质量雷达、局部质检与报告解析

## 背景

V0.7.0 已经能用 ScrapeCreators Reddit 真实小样本和 DeepSeek 做旁路对照，但报告仍偏“规则 vs 模型表格”。它能说明两边是否一致，却还不能直接帮助判断：哪些关键词值得保留、哪些要收窄、哪些只是噪音复盘。

## 改动

- V0.7.1：优化真实小样本抽样，优先让 DeepSeek 检查 AI 意图风险、边缘相关、低把握高分和跑偏信号样本。
- V0.7.1：在 JSON 输出中新增 `topic_quality`、`next_keyword_actions` 和 `sampling_strategy`。
- V0.7.1：明确真实小样本采用风险优先抽样，不代表关键词整体分布。
- V0.7.2：在每条样本上新增 `quality_gate`，标记“进入趋势候选 / 降级为噪音 / 人工复核 / 保留为背景”。
- V0.7.2：质量统计使用唯一坏样本计数，避免同一条样本既被降级又被标噪音时重复计数。
- V0.7.3：在 Markdown 输出中新增：
  - `V0.7.1 质检样本质量雷达`
  - `V0.7.2 DeepSeek 局部质检`
  - `V0.7.3 报告 + 解析`
  - `下一轮关键词动作`
- 默认 DeepSeek 分析样本数从 8 调整为 10，上限仍为 12。
- `--sample-count` 控制 DeepSeek 分析样本数；ScrapeCreators 请求数约等于本轮关键词数量。

## 安全边界

- 默认 dry-run，不调用 ScrapeCreators 或 DeepSeek。
- 真实运行仍必须同时满足 `LLM_SCORING_ENABLED=on` 和 `--confirm-live-api`。
- 输出只写入 `local_outputs/llm_scoring_real_sample_comparison.*`。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不修改 `last30days-skill`。

## 测试

- 更新 `tests/test_llm_scoring_real_sample_comparison.py`，覆盖：
  - 默认不联网
  - 输出保护
  - 成功摘要中的质量雷达字段
  - Markdown 新模块
  - 质量质检抽样优先级

## 后续

下一步可以做 V0.7.4 或 V0.8.0：

- V0.7.4：根据真实复跑结果继续调整关键词与抽样策略。
- V0.8.0：开始 YouTube tiny probe，但仍保持不进入正式报告。
