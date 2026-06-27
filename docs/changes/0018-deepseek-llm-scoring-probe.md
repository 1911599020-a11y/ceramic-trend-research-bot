---
version: V0.6.8
title: DeepSeek 大模型评分 tiny probe
date: 2026-06-27
---

## 背景

V0.6.7 已经定义了智能评分接口，但没有真实调用模型。用户决定 V0.6.8 使用 DeepSeek
作为第一版大模型评分 tiny test 的 provider。

本版本只新增独立 probe，不接入正式报告流程。

## 改动

- 新增 `scripts/probe_llm_scoring.py`，通过 DeepSeek OpenAI-compatible chat completions 接口对 3 到 5 条内置样本做语义评分。
- 新增 `scripts/probe_llm_scoring.sh`，本地运行入口。
- 更新 `config/llm_scoring.json`：provider 设为 `deepseek`，model 默认 `deepseek-chat`，但仍保持 `enabled=false`。
- 更新 `.env.example`，预留 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`。
- 新增 `tests/test_llm_scoring_probe.py`，覆盖默认不联网、缺 key 不请求、输出路径保护、成功脱敏摘要、HTTP 错误分类和 parse error。
- 更新 README / AGENTS / workflow，说明 DeepSeek tiny probe 的运行和安全边界。

## 安全边界

- 默认运行 `bash scripts/probe_llm_scoring.sh` 不联网、不消耗 API。
- 真实运行必须显式加 `--confirm-live-api`。
- 缺少 `DEEPSEEK_API_KEY` 时不发起网络请求。
- 输出只能写入 `local_outputs/llm_scoring_probe.*`。
- 不覆盖 `reports/report.md`。
- 不覆盖 `reports/latest.md`。
- 不写入 `reports/archive/`。
- 不把 API key 写入输出、错误文件或终端提示。
- 正式报告仍只使用 `rules`，`ceramic_report.py` 的 `REPORT_VERSION` 仍保持 V0.6.6。

## 后续

- 用户把 `DEEPSEEK_API_KEY` 放入本地 `.env` 后，先运行 dry-run。
- 用户明确同意消耗少量额度后，运行：

```bash
bash scripts/probe_llm_scoring.sh --confirm-live-api
```

- 如果 tiny probe 结果显示 DeepSeek 能稳定识别跑偏样本和关键词意图不匹配，再考虑 V0.6.9 作为可关闭增强层接入正式报告。
