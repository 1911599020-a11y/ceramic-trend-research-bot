---
id: 0032
title: YouTube report quality tightening and quality sample runner
status: implemented
version: V0.9.2-V0.9.3
date: 2026-06-30
supersedes:
  - 0031
related:
  - ceramic_report.py
  - config/youtube_quality_topics.json
  - scripts/run_youtube_quality_live.sh
---

## 背景 / Context

V0.9.1 跑通了 YouTube Search 单关键词真实小样本，但报告中出现了一类轻微过度外推：
频道名里的 `studio` 可能被误认为经营信号，导致釉料化学视频被推导成“工作室定价与客户沟通表”。

V0.9.2 的目标是收紧报告推理；V0.9.3 的目标是在不立刻消耗 API 的前提下，为 YouTube
多关键词小样本验证准备安全入口。

## 改动 / Changes

- 收紧经营类趋势和小工具判断：`studio` 不再单独触发 business / pricing / customer 方向。
- 经营类判断必须命中更强信号，例如 `pricing`、`customer`、`order`、`sell`、`etsy`、
  `commission`、`marketing`、`inventory`。
- 釉料、烧成、AI、3D printing 等信号抽成共享常量，减少趋势判断、内容理由和工具灵感之间的规则漂移。
- 新增 `config/youtube_quality_topics.json`，默认包含 3 个 YouTube 小样本关键词：
  `ceramic glaze`、`kiln firing`、`handmade pottery`。
- 新增 `scripts/run_youtube_quality_live.sh`，默认 dry-run，不联网、不消耗 API；真实运行必须显式加
  `--confirm-live-api`。

## 不做什么 / Non-goals

- 不修改 `last30days-skill`。
- 不安装 `yt-dlp`。
- 不拉字幕、评论、Video Details 或视频画面。
- 不把 YouTube 设成 `--data-source auto` 默认源。
- 不让 DeepSeek 参与正式报告判断。
- 不自动运行 YouTube 多关键词真实 live。

## 安全边界 / Safety

- `scripts/run_youtube_quality_live.sh` 默认只打印命令。
- 多关键词样本使用独立状态文件 `local_outputs/youtube_quality_run_state.json` 和错误文件
  `local_outputs/youtube_quality_error.md`。
- 真实运行仍走正式 live 保护：失败、空结果或全低相关结果不会覆盖正式报告。

## 测试 / Verification

- 新增测试覆盖 `washington street studios + Glaze Chemistry` 不再生成经营类小工具。
- 新增测试覆盖 YouTube quality topics 是 3 个小样本关键词，不需要 `--confirm-full-api`。
- 新增测试覆盖 `scripts/run_youtube_quality_live.sh` 默认 dry-run，并使用
  `config/youtube_quality_topics.json`。

## 后续 / Next

下一步可以在用户明确同意消耗 API 后运行：

```bash
bash scripts/run_youtube_quality_live.sh --confirm-live-api
```

跑通后再判断是否需要进入 YouTube 多关键词相关性规则精修或 DeepSeek 旁路审核。
