---
version: V0.6.8.1
title: DeepSeek tiny probe switch config
date: 2026-06-27
---

# DeepSeek Tiny Probe Switch Config

## 背景

V0.6.8 已经有 DeepSeek tiny probe，但真实请求只靠 `--confirm-live-api` 保护。用户希望未来做成界面里的勾选按钮，因此需要一个明确的开关配置。

## 改动

- 新增 `LLM_SCORING_ENABLED=off/on` 作为 DeepSeek 评分开关。
- `config/llm_scoring.json` 记录 `switch_env_var` 和可识别的开启值。
- `scripts/probe_llm_scoring.py` 在真实请求前同时检查开关和确认参数。
- 开关关闭时，即使存在 `DEEPSEEK_API_KEY` 和 `--confirm-live-api`，也不会发起网络请求。
- `prompts/llm_scoring_prompt.md` 明确 `confidence` 必须使用 0 到 100 的百分制，避免模型返回 0 到 10 分。

## 安全边界

- 默认不联网。
- 默认不消耗 DeepSeek API 额度。
- 输出仍然只写入 `local_outputs/llm_scoring_probe.*`。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不把 LLM 评分接入正式报告。

## 测试

- 新增开关关闭时不联网的测试。
- 真实 tiny test 需要用户明确授权后执行。
