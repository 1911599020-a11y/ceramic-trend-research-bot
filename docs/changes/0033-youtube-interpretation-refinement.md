---
id: 0033
title: YouTube interpretation refinement
status: implemented
version: V0.9.4
date: 2026-07-01
supersedes:
  - 0032
related:
  - ceramic_report.py
  - tests/test_report_labels.py
---

## 背景 / Context

V0.9.3 跑通了 YouTube 三关键词真实小样本，但报告里对 `handmade pottery`
这类制作视频仍有轻微过度外推风险：单条制作过程视频不应自动推导为销售、工作室经营或强趋势。

## 改动 / Changes

- 新增制作类信号判断，用于识别 handmade、making、process、teapot、wheel throwing、
  handbuilding、throwing、trimming 等制作过程语境。
- `handmade pottery` 的痛点文案改为制作步骤、器型选择、修坯节奏、材料和时间成本复盘。
- YouTube 制作类内容选题改为“制作过程拆解 / 工艺复盘 / 器型案例”，不再使用“真实问题讲透”。
- 长期经营工具文案改为等待 `pricing / customer / order / sell` 等强经营信号，而不是 `business / studio` 弱信号。
- `ceramic studio` 的下一轮关键词建议改为工作室流程、空间、窑炉和组织管理，不再默认跳到 Etsy / pricing。

## 不做什么 / Non-goals

- 不接新数据源。
- 不跑真实 YouTube / Reddit API。
- 不安装 `yt-dlp`。
- 不让 DeepSeek 进入正式报告。
- 不修改 `last30days-skill`。

## 测试 / Verification

- `infer_pain_points("handmade pottery")` 不再输出销售/决策工具类痛点。
- YouTube handmade 制作视频报告选题使用制作过程/工艺复盘/器型案例措辞。
- `studio` 频道名仍不触发经营工具。
- 真正的 `pricing / customer / order` 强经营信号仍可触发经营工具。
- 长期工具文案不再使用 `business / studio` 作为经营优先化条件。
- `ceramic studio` 关键词建议不再默认进入 Etsy / pricing。

## 后续 / Next

下一步可以继续观察真实 YouTube 多关键词报告里哪些制作类视频适合升级为“教程内容机会”，
哪些只能作为单条案例，避免把播放量高的制作视频直接解释成市场趋势。
