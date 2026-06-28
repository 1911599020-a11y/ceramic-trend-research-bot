---
version: V0.7.5
date: 2026-06-28
type: config
scope: keyword-quality
---

# 关键词 active topics 收敛

## 背景

V0.7.3 的真实 Reddit/ScrapeCreators 小样本对照显示，`kiln firing` 和 `ceramic business` 更容易得到可用陶瓷证据，而宽泛的 `AI ceramic design` 更容易混入泛 AI、泛设计或只碰到关键词但不符合陶瓷趋势意图的内容。

V0.7.4 已经把这些观察转成关键词收敛计划。V0.7.5 只做一件小而关键的事：把收敛计划应用到默认小批量关键词质量测试配置里。

## 改动

- 更新 `config/scrapecreators_quality_topics.json` 的 active `topics`。
- 保留：
  - `kiln firing`
  - `ceramic business`
- 将宽泛的 `AI ceramic design` 拆成更具体的 AI 陶瓷测试词：
  - `AI pottery workflow`
  - `generative ceramic pattern`
  - `computational ceramics`
  - `ceramic prompt design`
- 为新增 AI 陶瓷测试词补充 `required_terms`、`boost_terms`、`exclude_terms` 和 `intent_note`。
- AI 相关 `required_terms` 收窄为 AI、生成式、prompt、计算设计或数字制造信号；普通陶瓷词只作为陶瓷相关性证据，不单独证明 AI 关键词意图成立。
- 更新 `README.md`、`docs/workflow.md`、`AGENTS.md` 和 `config/llm_scoring.json`。
- 更新 `tests/test_keyword_quality.py`，覆盖新 active topics、泛设计噪音降级规则，以及普通非 AI 陶瓷帖不能进入 AI 高相关结果。

## 行为

- `bash scripts/run_keyword_quality_check.sh` 默认仍是 dry-run，不联网、不消耗 API。
- 真实小批量测试仍必须显式加 `--confirm-live-api`。
- 真实运行时 ScrapeCreators 请求数约等于 active topic 数量；V0.7.5 当前约为 6 次。
- `candidate_topics` 仍只是候选池，不会被默认 runner 自动展开。

## 安全边界

- 不调用 ScrapeCreators。
- 不调用 DeepSeek。
- 不更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 不修改 `last30days-skill`。
- 不提交或打印任何真实 API key。

## 后续

下一步可以在用户明确授权后，用 V0.7.5 的 6 个 active topics 做一次真实小批量复跑，确认更具体的 AI 陶瓷关键词是否比原来的 `AI ceramic design` 更干净。

如果复跑结果稳定，之后就可以进入 V0.8.0：YouTube tiny probe。V0.8.0 仍应先做极小测试，不直接进入正式报告。
