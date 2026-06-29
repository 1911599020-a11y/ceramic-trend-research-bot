---
id: 0028
title: YouTube probe field and DeepSeek review
status: accepted
version: V0.8.3
date: 2026-06-29
supersedes:
  - 0027
related:
  - scripts/review_youtube_probe.py
  - scripts/review_youtube_probe.sh
  - tests/test_youtube_probe_review.py
  - README.md
  - docs/workflow.md
  - AGENTS.md
---

## 背景 / Context

V0.8.0 已新增 YouTube Search tiny probe，默认不联网，真实运行只写
`local_outputs/youtube_probe.*`。用户授权后，V0.8.1 真实 probe 已成功：

- 查询词：`ceramic glaze`
- Search 返回：19 条 videos、25 条 shorts
- 本地摘要：3 条 videos
- 正式 reports 未更新

下一步需要回答两个问题：

1. YouTube Search 返回的摘要字段是否足够稳定？
2. DeepSeek 能否作为 YouTube 样本的旁路审核员，判断视频是否真陶瓷相关？

## 决策 / Decision

新增 V0.8.2/V0.8.3 旁路脚本：

- `scripts/review_youtube_probe.py`
- `scripts/review_youtube_probe.sh`
- `tests/test_youtube_probe_review.py`

行为规则：

- 默认运行不联网，只读取 `local_outputs/youtube_probe.json`。
- 默认输出字段质量和本地规则初筛到 `local_outputs/youtube_probe_review.*`。
- 只有显式加 `--confirm-live-api` 且打开 `LLM_SCORING_ENABLED=on` 时，才调用 DeepSeek。
- DeepSeek 只审核已脱敏的 YouTube 摘要字段：标题、频道、链接、视频 id、发布时间、时长、播放量。
- 不读取 YouTube 原始响应，不拉 video details、transcript 或 comments。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不把 `youtube_future` 改为正式可用数据源。

真实 V0.8.3 运行结果：

- DeepSeek 审核样本：3 条
- 可作为 YouTube 趋势候选：3 条
- 低相关或噪音：0 条
- 需要人工复核：0 条

## 测试 / Testing

- `python -m unittest tests.test_youtube_probe_review`
- `python -m py_compile scripts/review_youtube_probe.py`
- `bash scripts/review_youtube_probe.sh`
- `env LLM_SCORING_ENABLED=on bash scripts/review_youtube_probe.sh --confirm-live-api --sample-count 3`
- `python -m unittest discover tests`
- `git diff --check`

真实 DeepSeek 请求只能在用户明确同意后运行。

## 影响 / Consequences

- 优点：YouTube Search 不再只是“能请求”，现在可以产出字段质量和样本语义审核。
- 优点：DeepSeek 已开始承担更接近“审核员”的角色，但仍不直接写正式报告。
- 优点：为下一步 video details tiny probe 提供进入门槛：Search 字段稳定、样本高相关、模型判断一致。
- 代价：V0.8.3 仍不接正式报告；YouTube 仍未进入 `--data-source auto`。

## 回滚 / Rollback

删除 `scripts/review_youtube_probe.py`、`scripts/review_youtube_probe.sh`、
`tests/test_youtube_probe_review.py`，并移除 README、workflow、AGENTS 中关于 V0.8.2/V0.8.3
YouTube probe review 的说明即可。
