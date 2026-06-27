---
version: V0.6.7
title: 产品可用性转向与智能评分接口设计
date: 2026-06-27
---

## 背景

外部评审指出项目当前“工程保护强、产品洞察弱”：mock、live 保护、测试、文档和
API 额度防护已经比较完整，但报告仍偏规则化，距离“每天能用的陶瓷趋势简报”还有距离。

V0.6.7 的目标不是继续接新数据源，而是把后续智能评分的接口先定清楚。

## 改动

- 新增 `scoring/llm_scorer.py`，定义 LLM 辅助评分的数据结构、prompt 构造、返回值解析、mock scorer 和规则/LLM 合并结果。
- 新增 `config/llm_scoring.json`，默认 `enabled=false`、`provider=none`、`mode=design_only`。
- 新增 `prompts/llm_scoring_prompt.md`，要求模型只输出结构化 JSON，不直接生成最终报告。
- 新增 `tests/test_llm_scoring.py`，覆盖配置、prompt、JSON schema、mock scorer、规则/LLM 合并逻辑。
- 新增临时记忆文件 `local_outputs/temp_v0_6_7_v0_6_8_plan.md`，记录 V0.6.7/V0.6.8 两阶段计划；该文件不进入 GitHub。
- 更新 README / AGENTS / workflow，说明 V0.6.7 是设计阶段，不调用真实大模型 API。

## 安全边界

- 本版本不会调用 OpenAI、Anthropic、Ollama 或其他外部模型。
- 本版本不会消耗 API 额度。
- LLM 评分不接入正式 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 规则评分仍是当前正式报告的唯一评分来源。
- V0.6.8 若做 tiny probe，必须用户明确同意，并且输出只能写入 `local_outputs/llm_scoring_probe.md`。
- V0.6.7 是项目设计版本，不提升 `ceramic_report.py` 的 `REPORT_VERSION`；正式报告生成版本仍保持 V0.6.6。

## 后续

- V0.6.8：实现大模型评分 tiny probe，取 3 到 5 条样本，输出到 `local_outputs/llm_scoring_probe.md`。
- 如果 tiny probe 证明有效，再考虑 V0.6.9 把智能评分作为可关闭增强层接入正式报告流程。
