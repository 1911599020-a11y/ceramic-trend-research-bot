---
id: 0034
title: YouTube mixed signal consistency
status: implemented
version: V0.9.5
date: 2026-07-01
supersedes:
  - 0033
related:
  - ceramic_report.py
  - tests/test_report_labels.py
---

## 背景 / Context

V0.9.4 已经把 `handmade pottery` 等制作类 YouTube 视频从销售/经营结论中降权，
但仍存在一种混合信号风险：同一条证据可能同时包含 `glaze`、`kiln`、`handmade`
和 `pricing`、`customer`、`order`、`sales`。如果不同报告模块各自独立判断，
就可能出现标题像经营内容、理由却像釉料或烧成内容的前后不一致。

## 改动 / Changes

- 新增统一的 evidence 主信号判断：强经营信号优先，其次才是 kiln、glaze、AI、
  3D printing 和 making process。
- 内容选题标题、选题理由、趋势判断和本轮证据支持的小工具共用这套主信号判断。
- 当同一条 YouTube 证据同时命中经营、釉料、烧成或制作信号时，报告优先按
  `pricing/customer/order/sales` 等强经营意图解释。
- 强经营判断只读取标题、摘要和相关性说明，不让 `topic=ceramic business`
  这类搜索词本身单独触发经营解释。
- 增加回归测试，确保 `Pricing kiln firing services for handmade pottery glaze customers`
  这类混合样本不会同时触发釉料工具、烧成工具和经营工具。
- 增加反向测试，确保 `ceramic business` 关键词下只有 glaze 证据时，仍按釉料解释。

## 不做什么 / Non-goals

- 不接新数据源。
- 不跑真实 YouTube / Reddit API。
- 不安装 `yt-dlp`。
- 不让 DeepSeek 进入正式报告。
- 不修改 `last30days-skill`。
- 不改正式报告归档规则。

## 测试 / Verification

- 混合命中 `pricing/customer/order` 与 `glaze/kiln/handmade` 的证据，内容理由优先解释为经营场景。
- `topic=ceramic business` 但标题、摘要和相关性说明没有强经营信号时，不强行解释为经营。
- 同一混合证据只触发“工作室定价与客户沟通表”，不触发“烧成失败诊断卡”或“釉色实验记录器”。
- 趋势判断不再让同一条强经营证据同时贡献釉料趋势和烧成趋势。
- V0.9.4 的制作类视频解释测试继续通过。

## 后续 / Next

下一步可以继续观察真实 YouTube 多关键词样本：如果某些视频标题同时有经营、釉料、
烧成和教程词，需要根据真实案例再决定是否引入更细的二级标签，而不是只用一个主信号。
