---
version: V0.6.9
title: Rule and DeepSeek scoring comparison
date: 2026-06-28
---

# Rule And DeepSeek Scoring Comparison

## 背景

规则评分已经能稳定运行，但它对语义跑偏样本仍可能误判。V0.6.9 不把 DeepSeek 接入正式报告，而是先生成旁路对照报告，观察规则评分和 DeepSeek 判断是否一致。

## 改动

- 新增 `scripts/compare_llm_scoring.py`。
- 新增 `scripts/compare_llm_scoring.sh`。
- 输出 `local_outputs/llm_scoring_comparison.md`、`.json`、`_state.json`、`_error.md`。
- 对照报告展示规则判断、DeepSeek 判断、对照结果和合并建议。
- 复用 V0.6.8.1 的 DeepSeek API 安全门控。

## 安全边界

- 默认不联网。
- 真实请求必须同时满足 `LLM_SCORING_ENABLED=on` 和 `--confirm-live-api`。
- 输出只写入 `local_outputs/`。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不把 LLM 评分接入正式报告。

## 测试

- 新增 `tests/test_llm_scoring_comparison.py`。
- 覆盖默认不联网、开关关闭不联网、成功生成对照报告、DeepSeek 官方 base URL 限制。
