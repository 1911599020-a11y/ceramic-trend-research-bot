---
id: 0005
title: ScrapeCreators 准备状态检查
status: accepted
version: V0.5.5
date: 2026-06-25
supersedes: none
related:
  - scripts/check_environment.py
  - scripts/run_live.sh
  - ceramic_report.py
  - tests/test_environment_check.py
  - tests/test_live_failure_guidance.py
  - docs/environment-check.md
  - docs/troubleshooting.md
  - docs/reddit-data-source-options.md
  - README.md
---

## 背景 / Context

V0.5.4 已经明确：当前网络出口可以访问 Reddit 首页，但 public Reddit `search.json` 搜索接口可能持续返回 403。
上游 `last30days-skill` 已经有 ScrapeCreators Reddit API 备份路径，但本项目还没有把“是否准备好这条备份路径”说清楚。

## 决策 / Decision

新增 ScrapeCreators readiness check：

- 环境诊断新增 `ScrapeCreators Reddit fallback` 检查项。
- 只判断 `SCRAPECREATORS_API_KEY` / `SCRAPE_CREATORS_API_KEY` 是否存在。
- 只显示 `configured` / `missing`，不打印真实 key。
- live 失败记录和 `run_state.json` 会记录 `scrapecreators_fallback`。
- 403 失败提示会根据备份状态说明下一步：检查 key / 额度，或考虑配置 ScrapeCreators / 暂时切其他来源。

本次不配置真实 key，不验证 ScrapeCreators API，不修改 `last30days-skill`。

## 测试 / Testing

- `/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover tests`
- `bash scripts/run_mock.sh`
- `git diff --check`

## 影响 / Consequences

- 优点：Reddit public JSON 403 时，用户能直接看到是否具备 API 备份条件。
- 优点：失败记录更适合排障，不会只停留在“网络失败”。
- 优点：不泄露真实 key，只记录状态。
- 代价：本次只是 readiness check，不会让 ScrapeCreators API 自动可用；真正 live 验证需要用户之后明确配置 key。

## 回滚 / Rollback

移除新增检查项、失败提示和相关测试即可；不会影响 mock、report、latest、archive 或 compare 逻辑。
