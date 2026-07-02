---
id: 0036
title: DeepSeek formal report semantic review
status: implemented
version: V0.9.7
date: 2026-07-03
supersedes: []
related:
  - ceramic_report.py
  - scoring/deepseek_client.py
  - scoring/llm_scorer.py
  - config/llm_scoring.json
  - prompts/llm_scoring_prompt.md
  - prompts/ceramic_report_prompt.md
  - tests/test_llm_report_integration.py
---

## 背景 / Context

V0.9.5 质检报告指出，项目已经为 DeepSeek 搭好评分契约、prompt、旁路
probe 和对照脚本，但正式报告一直没有真正接入 DeepSeek。这造成了"永远
差一步"的问题：工程护栏很多，交付价值却没有进入用户真正阅读的报告。

V0.9.7 的目标是打通这一步：让 DeepSeek 判断真实出现在
`reports/report.md` 中，但先以两栏对照形式进入，不替代冻结规则评分。

## 改动 / Changes

- 新增 `scoring/deepseek_client.py`：把 DeepSeek base URL 校验、请求、
  response 解析、HTTP/DNS/timeout 分类和 key 脱敏抽成正式报告可复用的客户端。
- `ceramic_report.py` 新增正式报告语义质检层：
  - `ReportLLMReview` / `LLMReviewStatus` 保存 DeepSeek 复核结果和运行状态；
  - `select_llm_review_candidates()` 优先选择高相关和边缘相关证据，并受
    `max_items_per_run` 限制；
  - `maybe_build_llm_reviews()` 在 `LLM_SCORING_ENABLED=on` 且 key 可用时调用
    DeepSeek；
  - DeepSeek 失败、缺 key、开关关闭或 live 失败时，报告继续按规则评分生成。
- 正式报告新增 `## DeepSeek 语义质检` 章节：
  - 显示规则判断、DeepSeek 判断、合并建议、置信度和 DeepSeek 理由；
  - 明确本节只做语义复核，不替代规则评分；
  - 关闭、缺 key 或失败时显示简短状态说明。
- 将 `## 用户痛点` 调整为 `## 用户痛点假设`，明确当前痛点仍是关键词假设，
  尚未基于评论、字幕或长文本证据抽取。
- `config/llm_scoring.json` 更新为 `version=V0.9.7`、`mode=formal_report_review`，
  但继续默认 `enabled=false`，避免仓库默认行为误触发真实 API。
- README、AGENTS 和报告模板同步新的 V0.9.7 契约。

## 不做什么 / Non-goals

- 不让 DeepSeek 当主裁判；高相关 / 边缘 / 跑偏主分层仍由规则评分生成。
- 不让 DeepSeek 重写整份报告或直接改趋势结论。
- 不抓取 YouTube comments、transcripts、video details 或画面。
- 不改变 ScrapeCreators / 搜索引擎额度规则。
- 不移除旁路 probe / comparison 脚本；它们仍用于诊断。

## 安全 / Safety

- DeepSeek 正式报告语义质检默认关闭。
- 打开后每轮最多复核 `config/llm_scoring.json` 的 `max_items_per_run` 条候选证据
  （当前 5 条），并受代码级硬上限 10 条保护，避免配置误改导致额度失控。
- DeepSeek 失败只写 `local_outputs/llm_report_review_error.md`，不得阻断正式报告。
- 错误文件必须脱敏，不能写出真实 API key。
- 测试必须 mock 网络，不得真实调用 DeepSeek。
- 用户已授权项目需要时可使用 DeepSeek API 额度；搜索引擎额度仍需每次先申请预计条数。

## 测试 / Verification

- `tests/test_llm_report_integration.py`：
  - 未传入 DeepSeek review 时不生成假结果；
  - 正式报告可渲染 `DeepSeek 语义质检` 两栏对照；
  - 关闭 / 缺 key / HTTP 429 状态不会中断报告；
  - 候选证据选择有上限并优先高相关、边缘相关；
  - `main()` 在 mock 模式下可把 mocked DeepSeek 判断写入正式报告。
- `tests/test_llm_scoring.py`：
  - 更新配置契约为 `formal_report_review` 且默认关闭。

## 后续 / Next

- V0.9.8 可基于多轮两栏对照结果，让 DeepSeek 影响部分质量动作，例如明显噪音降级、
  规则漏判提示或人工复核标记。
- DeepSeek 当主裁判建议放到 V1.0 或更晚，前提是多轮对照稳定且可解释。
- 真正的用户痛点生成应等待评论、字幕或更长文本证据接入后再做。
