---
id: 0009
title: 数据源选择与降级说明
status: accepted
version: V0.6.0
date: 2026-06-25
supersedes: none
related:
  - config/data_sources.json
  - ceramic_report.py
  - tests/test_data_source_selection.py
  - README.md
  - docs/workflow.md
  - AGENTS.md
---

## 背景 / Context

V0.5.0 已经把数据获取和报告生成拆成 `TrendSource` 适配层。
但日常运行时还不够清楚：mock、Reddit live、未来 ScrapeCreators / YouTube / Pinterest 分别处于什么状态。
当 Reddit live 失败时，也容易误判为报告生成逻辑坏了。

## 决策 / Decision

新增 `config/data_sources.json` 作为数据源清单：

- `mock`：当前可用，读取本地 `data/mock_samples.json`。
- `reddit_last30days`：当前可用，live 模式通过本地 `last30days-skill` 获取 Reddit 数据。
- `scrapecreators_reddit`：预留 API 源，本版本不调用。
- `youtube_future`：预留 YouTube 源，本版本不安装 `yt-dlp`。
- `pinterest_future`：预留视觉趋势源，本版本不配置 provider。

新增 `--data-source` 参数：

- `auto`：mock 模式映射到 `mock`，live 模式映射到 `reddit_last30days`。
- 选择已预留但未实现的数据源时，程序会清楚报错，不会偷偷联网。

运行状态和失败记录会写入本次数据源，live 失败时明确说明这是数据源访问失败，不代表报告生成器或历史报告保护逻辑损坏。

## 测试 / Testing

- `tests/test_data_source_selection.py` 覆盖 `auto` 映射、预留源保护、run_state 数据源字段。
- 需要运行：
  - `python -m unittest discover tests`
  - `python -m py_compile ceramic_report.py scripts/check_environment.py scripts/reddit_probe_matrix.py scripts/compare_reports.py`
  - `bash scripts/run_mock.sh`
  - `git diff --check`

## 影响 / Consequences

- 优点：日常运行时能清楚知道当前用的是哪个数据源。
- 优点：未来接 ScrapeCreators、YouTube、Pinterest 时有明确入口。
- 优点：Reddit live 失败时更容易判断是数据源问题，而不是报告生成器坏了。
- 代价：多维护一份 `config/data_sources.json`，新增数据源时需要同步更新文档和测试。

## 回滚 / Rollback

删除 `config/data_sources.json` 和 `--data-source` 相关解析逻辑，主流程改回按 `--mode` 直接选择 `MockSource` / `Last30DaysSource`。
