---
version: V0.7.0
title: Real Reddit small-sample DeepSeek comparison
date: 2026-06-28
---

# Real Reddit Small-Sample DeepSeek Comparison

## 背景

V0.6.9 用内置样本验证了 DeepSeek 可以识别规则评分误判。V0.7.0 继续保持旁路实验，不接入正式报告，但改用 ScrapeCreators Reddit 真实小样本做对照。

## 改动

- 新增 `scripts/compare_real_llm_scoring.py`。
- 新增 `scripts/compare_real_llm_scoring.sh`。
- 新增 `tests/test_llm_scoring_real_sample_comparison.py`。
- 默认读取 `config/scrapecreators_quality_topics.json` 的小批量关键词。
- 默认最多对照 8 条真实 Reddit 小样本，最高限制 12 条。
- 小样本按关键词轮流抽取，避免单个关键词填满样本。
- 同一关键词下按归一化标题去重，减少重复或近似重复帖子进入对照。
- 输出 `local_outputs/llm_scoring_real_sample_comparison.*`。

## 安全边界

- 默认不联网。
- 真实运行必须同时满足 `LLM_SCORING_ENABLED=on` 和 `--confirm-live-api`。
- 真实运行需要 `DEEPSEEK_API_KEY` 与 `SCRAPECREATORS_API_KEY`。
- 输出只写入 `local_outputs/`。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不把 DeepSeek 评分接入正式报告。

## 测试

- 覆盖默认不联网。
- 覆盖开关关闭不联网。
- 覆盖缺 ScrapeCreators key 不联网。
- 覆盖成功时只写本地对照输出，不写正式 reports。
- 覆盖 `reports/report.md` 输出保护。
