---
id: 0027
title: YouTube tiny probe
status: accepted
version: V0.8.0
date: 2026-06-29
supersedes: []
related:
  - scripts/probe_scrapecreators_youtube.py
  - scripts/probe_scrapecreators_youtube.sh
  - tests/test_scrapecreators_youtube_probe.py
  - README.md
  - docs/workflow.md
  - AGENTS.md
---

## 背景 / Context

当前正式报告主线已经能稳定使用 mock、Reddit public live 和显式 ScrapeCreators Reddit live。
下一步需要验证 YouTube 是否能作为后续视频数据源，但不能直接把 YouTube 接进正式报告，避免污染
`reports/report.md`、误消耗 API 额度或引入 `yt-dlp` 依赖。

## 决策 / Decision

新增 V0.8.0 YouTube tiny probe：

- `scripts/probe_scrapecreators_youtube.py`
- `scripts/probe_scrapecreators_youtube.sh`
- `tests/test_scrapecreators_youtube_probe.py`

probe 使用 ScrapeCreators YouTube Search endpoint：

```text
https://api.scrapecreators.com/v1/youtube/search
```

默认参数：

- `query=ceramic glaze`
- `uploadDate=this_month`
- `sortBy=relevance`
- `type=videos`

保护规则：

- 默认运行不联网，只写 `local_outputs/youtube_probe_state.json`。
- 只有显式添加 `--confirm-live-api` 才会发起一次真实 API 请求。
- 每次真实 probe 只做 Search 请求，不追分页，不拉 video details、transcript 或 comments。
- 只保存最多 3 条 allowlist 摘要字段：标题、频道、链接、视频 id、发布时间、时长、播放量。
- 不保存原始响应、不保存 description 全文、不保存 continuation token 值。
- 输出只能写入 `local_outputs/youtube_probe.*`。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不修改 `ceramic_report.py`，不把 `youtube_future` 标为 available，不接 DeepSeek。

## 测试 / Testing

- `python -m unittest tests.test_scrapecreators_youtube_probe`
- `python -m py_compile scripts/probe_scrapecreators_youtube.py`
- `bash scripts/probe_scrapecreators_youtube.sh`
- `python -m unittest discover tests`
- `git diff --check`

真实 `--confirm-live-api` 请求只能在用户明确同意后运行。

## 影响 / Consequences

- 优点：可以在不影响正式报告的前提下验证 YouTube Search 数据入口。
- 优点：失败会分类为 missing key、401、403、429、quota/billing、DNS、timeout、network、parse 等。
- 优点：为后续 V0.8.1 字段确认、V0.8.2 DeepSeek 旁路质检做准备。
- 代价：V0.8.0 仍不会让正式报告使用 YouTube；YouTube 仍是 planned source。

## 回滚 / Rollback

删除 `scripts/probe_scrapecreators_youtube.py`、`scripts/probe_scrapecreators_youtube.sh`、
`tests/test_scrapecreators_youtube_probe.py`，并移除 README、workflow、AGENTS 中关于 V0.8.0
YouTube tiny probe 的说明即可。
