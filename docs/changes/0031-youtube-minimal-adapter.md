---
id: 0031
title: YouTube minimal adapter
status: implemented
version: V0.9.0
date: 2026-06-30
supersedes:
  - 0030
related:
  - docs/plans/2026-06-30-youtube-minimal-adapter.md
  - config/data_sources.json
  - sources/youtube_source.py
  - scripts/run_youtube_live.sh
---

## 背景 / Context

V0.8.x 已经通过旁路 tiny probe 验证 ScrapeCreators YouTube Search 和 YouTube Video Details
可以返回陶瓷相关样本，但这些结果此前都只写入 `local_outputs/`，没有进入正式报告数据源。

V0.9.0 的目标是把 YouTube Search 升级成一个最小正式 adapter，但仍保持显式 opt-in，不进入
`--data-source auto` 默认路径。

## 改动 / Changes

- 新增 `sources/youtube_source.py`，实现 `ScrapeCreatorsYouTubeSearchSource`。
- 新增数据源 `scrapecreators_youtube_search`，必须通过 CLI 或 `scripts/run_youtube_live.sh` 显式选择。
- 新增 `config/youtube_probe_topics.json`，默认只运行 `ceramic glaze` 单关键词。
- 新增 `scripts/run_youtube_live.sh`，默认安全模式，支持 `--dry-run`、`--force` 和 `--confirm-full-api`。
- YouTube live 错误写入 `local_outputs/youtube_live_error.md`，运行状态写入 `local_outputs/youtube_run_state.json`。
- YouTube item 必须显式写入 `ceramic_relevance_score` 和 `ceramic_relevance_level`，不能缺字段后默认算作可用证据。
- 报告文案改为平台感知：YouTube 证据显示为频道，不再显示成 `r/...`。

## 不做什么 / Non-goals

- 不修改 `last30days-skill`。
- 不安装 `yt-dlp`。
- 不拉 transcript。
- 不拉 comments。
- 不拉 keyframes 或视频画面。
- 不请求 YouTube Video Details 作为正式 adapter 的硬依赖。
- 不让 DeepSeek 写入正式报告或决定正式报告更新。
- 不把 YouTube 设为 `--data-source auto` 默认源。

## 安全边界 / Safety

- `auto` live 仍然是 `reddit_last30days`。
- 默认 YouTube runner 只跑 `config/youtube_probe_topics.json`。
- 使用完整 `config/ceramic_topics.json` 必须显式加 `--confirm-full-api`。
- live 成功并拿到高相关或边缘相关 YouTube 证据时，才更新 `reports/report.md`、`reports/latest.md` 和 `reports/archive/`。
- API 错误、空结果、全低相关结果不会覆盖正式报告。
- `.env` 里的真实 key 不会写入报告、状态文件或测试输出。

## 测试 / Verification

新增和更新测试覆盖：

- YouTube source 缺 key 不联网。
- YouTube Search payload 转换为统一 `last30days` 形状。
- HTTP / timeout / DNS / parse 错误分类和脱敏。
- 显式 source 选择不改变 `auto` 默认 Reddit。
- YouTube full-topic API 运行需要 `--confirm-full-api`。
- 空结果、全低相关、API 错误不会覆盖正式报告。
- 高相关 YouTube 结果可以通过正式 live 成功路径写报告。
- YouTube 报告显示频道来源，不再显示 `r/频道名`。

## 后续 / Next

V0.9.0 之后可以做一次真实小样本 YouTube live，但仍建议先从单关键词开始。
字幕、评论、Video Details enrichment、DeepSeek 正式质量门和多平台融合应另开版本规划。
