---
id: 0010
title: ScrapeCreators 最小接入准备
status: accepted
version: V0.6.1
date: 2026-06-25
supersedes: none
related:
  - sources/scrapecreators_source.py
  - scripts/check_scrapecreators_ready.py
  - scripts/check_scrapecreators_ready.sh
  - tests/test_scrapecreators_source.py
  - config/data_sources.json
  - ceramic_report.py
  - scripts/check_environment.py
---

## 背景 / Context

V0.6.0 已经新增数据源清单和 `--data-source auto`，但 `scrapecreators_reddit` 仍只是一个预留名称。
进入真实 key-backed live 验证前，需要先有一个更安全的准备层：能检查 key 是否存在、能脱敏、
能告诉用户下一步，但不发起真实 API 请求。

## 决策 / Decision

新增 ScrapeCreators readiness-only 层：

- `sources/scrapecreators_source.py` 保存 ScrapeCreators key 检查、脱敏状态和未来 source placeholder。
- `ScrapeCreatorsSource.fetch()` 在 V0.6.1 故意禁用，防止偷偷联网或消耗额度。
- `scripts/check_scrapecreators_ready.py` / `.sh` 提供专门检查命令，只检查本地 key 状态。
- `scripts/check_environment.py` 复用同一套 readiness 逻辑。
- `config/data_sources.json` 为 `scrapecreators_reddit` 标记 readiness 命令。

本次不申请 key，不配置真实 key，不调用 ScrapeCreators，不修改 `last30days-skill`。

## 测试 / Testing

- `tests/test_scrapecreators_source.py` 覆盖 missing/configured 状态、旧环境变量名、placeholder fetch 禁用、脚本不打印 secret。
- 需要运行：
  - `python -m unittest discover tests`
  - `python -m py_compile ceramic_report.py scripts/check_environment.py scripts/reddit_probe_matrix.py scripts/compare_reports.py scripts/check_scrapecreators_ready.py`
  - `bash scripts/check_scrapecreators_ready.sh`
  - `bash scripts/run_mock.sh`
  - `git diff --check`

## 影响 / Consequences

- 优点：申请 key 前后都有一个不联网、不泄露 key 的检查入口。
- 优点：未来真正接 ScrapeCreators 时，有清楚的 source 文件和测试位置。
- 优点：减少误操作，避免用户刚配置 key 就被工具自动消耗额度。
- 代价：现在 `scrapecreators_reddit` 仍不能作为 live 数据源使用，真正抓取要等下一阶段。

## 回滚 / Rollback

删除 `sources/scrapecreators_source.py`、`scripts/check_scrapecreators_ready.py` / `.sh`、
`tests/test_scrapecreators_source.py`，并把 `scripts/check_environment.py` 改回本地 presence check 即可。
