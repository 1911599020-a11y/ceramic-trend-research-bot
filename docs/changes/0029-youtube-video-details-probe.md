---
id: 0029
title: YouTube video details probe and review
status: implemented
version: V0.8.4-V0.8.6
date: 2026-06-29
supersedes:
  - 0028
related:
  - scripts/probe_scrapecreators_youtube_video.py
  - scripts/probe_scrapecreators_youtube_video.sh
  - scripts/review_youtube_video_probe.py
  - scripts/review_youtube_video_probe.sh
  - tests/test_youtube_video_probe.py
  - tests/test_youtube_video_review.py
  - README.md
  - docs/workflow.md
  - AGENTS.md
---

## 背景 / Context

V0.8.1-V0.8.3 已确认 ScrapeCreators YouTube Search 可用，并且 DeepSeek 能对 Search 摘要做旁路审核。
下一步需要验证 video details 这层是否值得继续接入：它可能提供描述摘要、频道信息、观看数、
点赞数、评论数、时长、关键词、字幕轨道数量等更适合趋势判断的字段。

本版本只实现受保护的 tiny probe 和旁路审核工具。真实 video details 请求和真实 DeepSeek
详情层旁路审核已经完成一次小样本验证，输出仍只保存在 `local_outputs/`。

## 决策 / Decision

新增 V0.8.4 video details tiny probe：

- `scripts/probe_scrapecreators_youtube_video.py`
- `scripts/probe_scrapecreators_youtube_video.sh`
- `tests/test_youtube_video_probe.py`

新增 V0.8.5/V0.8.6 video details 字段整理与 DeepSeek 旁路审核：

- `scripts/review_youtube_video_probe.py`
- `scripts/review_youtube_video_probe.sh`
- `tests/test_youtube_video_review.py`

保护规则：

- 默认运行不联网。
- 真实 ScrapeCreators video details 请求必须显式加 `--confirm-live-api`。
- video details probe 默认从 `local_outputs/youtube_probe_review.json` 中选择 DeepSeek 判断高相关的视频 URL。
- 只请求 1 条视频详情。
- 只保存安全摘要，不保存原始响应。
- 不保存完整 description；短 description 只保存字符数，长 description 只保存确定被截断且去除链接的摘要。
- 不保存字幕链接，只保存字幕轨道数量和语言。
- 不保存 watch-next 列表，只保存数量。
- 不拉 transcript，不拉 comments。
- DeepSeek 详情层审核必须打开 `LLM_SCORING_ENABLED=on` 并加 `--confirm-live-api`。
- 所有输出只写 `local_outputs/youtube_video_probe.*` 和 `local_outputs/youtube_video_review.*`。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不把 `youtube_future` 改成正式可用数据源。

## 测试 / Testing

- `python -m unittest tests.test_youtube_video_probe`
- `python -m unittest tests.test_youtube_video_review`
- `python -m py_compile scripts/probe_scrapecreators_youtube_video.py scripts/review_youtube_video_probe.py`
- `bash scripts/probe_scrapecreators_youtube_video.sh`
- `python -m unittest discover tests`
- `git diff --check`

真实 ScrapeCreators video details 请求和真实 DeepSeek 详情层审核已完成一次小样本验证；正式报告仍未更新。

## 影响 / Consequences

- 优点：为 YouTube details 层准备了安全、可测试、可回滚的旁路工具。
- 优点：保留了 transcript/comments 之前的判断门槛，避免直接进入高噪音和高成本数据层。
- 优点：DeepSeek 可以继续作为审核员，而不是直接写正式报告。
- 代价：本版本还没有把 YouTube details 接入正式报告，也没有启用 `youtube_future`。

## 回滚 / Rollback

删除 `scripts/probe_scrapecreators_youtube_video.py`、`scripts/probe_scrapecreators_youtube_video.sh`、
`scripts/review_youtube_video_probe.py`、`scripts/review_youtube_video_probe.sh`、
`tests/test_youtube_video_probe.py`、`tests/test_youtube_video_review.py`，并移除 README、workflow、
AGENTS 中关于 V0.8.4-V0.8.6 的说明即可。
