---
id: 0030
title: YouTube readiness decision memo
status: implemented
version: V0.8.7-lite
date: 2026-06-30
supersedes:
  - 0029
related:
  - docs/changes/0027-youtube-tiny-probe.md
  - docs/changes/0028-youtube-probe-review.md
  - docs/changes/0029-youtube-video-details-probe.md
  - config/data_sources.json
---

## 背景 / Context

V0.8.0 到 V0.8.6 已经验证了 YouTube 的几层旁路能力：

- YouTube Search tiny probe 可以通过 ScrapeCreators 返回陶瓷相关视频摘要。
- YouTube Search review 可以让 DeepSeek 对脱敏摘要做旁路审核。
- YouTube Video Details tiny probe 可以对 1 条高相关视频读取详情摘要。
- YouTube Video Details review 可以让 DeepSeek 对详情层样本做旁路审核。

这些能力都只写入 `local_outputs/`，没有更新 `reports/report.md`、`reports/latest.md` 或
`reports/archive/`，也没有把 `youtube_future` 改成正式数据源。

本备忘录的目的不是继续加探针，而是决定 YouTube 是否应该进入 V0.9 正式接入设计。

## 本轮证据 / Evidence Reviewed

本轮只读取已有本地结果，没有新增 API 请求，也没有再次调用 DeepSeek。

| Evidence | Result |
|---|---|
| Search query | `ceramic glaze` |
| Search saved videos | 3 条摘要 |
| Search DeepSeek review | 3/3 被判断为 YouTube 趋势候选 |
| Video Details sample | `Understanding Pottery Chapter 8 Glaze Chemistry Part 1` |
| Channel | `Washington Street Studios` |
| Details metrics | 77,088 views / 2,394 likes / 155 comments / 01:16:21 |
| Details description handling | 原简介 2994 字符，只保存截断摘要，不保存完整正文 |
| Details DeepSeek review | 1/1 被判断为详情层趋势候选 |
| Formal reports updated | No |
| Current data source status | `youtube_future` 仍为 `planned`，live 默认仍为 `reddit_last30days` |

DeepSeek 对详情层样本的判断理由是：内容直接讲解陶瓷釉料化学，与 `ceramic glaze` 高度匹配，
且来自专业陶艺频道，播放量和互动较高，可以作为高质量趋势证据。

## 转正判断 / Decision

```text
wait
```

YouTube 值得继续推进，但当前不应立刻进入默认正式报告主线。

## 判断原因 / Rationale

当前证据说明 YouTube 对“陶瓷釉料 / glaze education”方向很有价值。Search 摘要和 Video Details
都能提供比 Reddit 更接近教学、知识、创作者内容的数据，DeepSeek 旁路审核也没有把样本判断为噪音。

但样本范围仍然偏窄：真实验证主要围绕 `ceramic glaze` 一个 query，还不能证明 YouTube 对
`ceramic business`、`kiln firing`、`AI ceramic design`、`3D printed ceramics` 等方向都稳定有效。

因此当前结论是：可以设计 V0.9 最小 YouTube adapter，但不能默认启用，也不能直接把 transcript、
comments、批量 details 或 DeepSeek 正式评分放进主线。

## Readiness Gate

| Gate | Status | Notes |
|---|---|---|
| Search API can return ceramic results | pass | `ceramic glaze` 返回了可用视频摘要。 |
| Search summaries can be reviewed without formal report pollution | pass | Search review 输出只写 `local_outputs/youtube_probe_review.*`。 |
| Details can add useful context | pass | 详情层提供频道、播放、点赞、评论、时长、简介摘要和字幕语言数量。 |
| Evidence covers multiple ceramic categories | wait | 当前真实样本主要覆盖 `ceramic glaze`，还不能代表全部陶瓷方向。 |
| Cost/rate-limit risk is understood | wait | tiny probe 可控，但正式 adapter 的运行频率、失败状态和额度预算还未定义。 |
| Formal report failure protection is defined | wait | 未来 YouTube 失败不得覆盖 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`；错误只能写入 ignored `local_outputs/youtube_live_error.md`。 |
| YouTube can remain opt-in, not default auto | pass | `config/data_sources.json` 里 live 默认仍是 `reddit_last30days`。 |
| `youtube_future` stays out of `auto` | pass | V0.8.7-lite 不修改 source registry，不启用正式 YouTube source。 |

## V0.9 最小范围 / Minimal V0.9 Scope

如果进入 V0.9，只做最小 adapter：

- 新增显式 opt-in 的 YouTube Search source。
- 不进入默认 `--data-source auto`。
- 第一版只使用 Search 摘要字段。
- 最多允许 1 条可选 Video Details enrichment，但不能作为第一版硬依赖。
- 失败不得覆盖 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 错误必须写入 ignored `local_outputs/youtube_live_error.md`。
- `youtube_future` 不得偷偷变成默认 live source。
- 不拉 transcript。
- 不拉 comments。
- 不保存 watch-next。
- 不让 DeepSeek 拥有最终正式报告写入权。

## 暂缓事项 / Deferred

以下事项不进入下一步：

- transcript probe
- comments probe
- batch details
- YouTube-specific complex scoring
- multi-source fusion ranking
- front-end integration
- shared database integration
- multilingual report output

这些方向都有价值，但它们不是让当前陶瓷趋势工具变得可用的最短路径。

## 下一步 / Next Step

推荐下一步不是继续加探针，而是设计 V0.9 最小 YouTube adapter 的范围。

任何新增 YouTube Search 样本、Video Details 请求或 DeepSeek 审核都必须另开变更、另获用户授权；
不应塞进 V0.8.7-lite 决策备忘录。
