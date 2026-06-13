---
id: 0001
title: 数据源适配层（data-source adapter）
status: accepted
version: V0.5.0
date: 2026-06-13
supersedes: none
related:
  - sources/__init__.py
  - sources/mock_source.py
  - sources/last30days_source.py
  - ceramic_report.py
  - data/mock_samples.json
  - tests/test_sources.py
  - tests/test_scoring.py
---

## 背景 / Context

V0.4.2 的 `ceramic_report.py` 把“取证据”和“打分 + 渲染”揉在一个文件里：mock 与 live
两种模式都通过 shell out 到外部 `last30days-skill` 取数据。这带来两个问题：

- mock 模式仍然依赖外部 skill 与其运行环境，在 Windows / CI 上无法零配置生成示例报告。
- 数据获取与打分耦合，新增数据源（YouTube、Pinterest 等）必须改动核心打分逻辑。

## 决策 / Decision

引入 `sources/` 适配层，定义统一的 `TrendSource` 契约：

```python
def fetch(self, topic: str, *, recommended_subreddits: set[str] | None = None) -> dict[str, Any]: ...
```

每个 source 返回同一种 `last30days` 形状的报告 dict（顶层 `items_by_source` → source 名 →
item 列表）。`ceramic_report.py` 只负责消化这种 dict，不再关心证据来自哪个后端。

- `MockSource`：读取仓库内 `data/mock_samples.json`，离线、零配置、零联网。
- `Last30DaysSource`：把 V0.4.2 的子进程调用逐字搬入，仅 `--mode live` 使用。

## 架构变化 / Architecture

```text
sources/__init__.py          # TrendSource Protocol + 重导出
sources/mock_source.py       # MockSource（离线样例）
sources/last30days_source.py # Last30DaysSource（外部 skill 子进程）
ceramic_report.py            # 打分 + 渲染 + CLI；按 mode 选择 source
data/mock_samples.json       # mock 证据样例（新增）
```

`main()` 中的接线：`live → Last30DaysSource(script_path, mode="live")`，
其余 `→ MockSource()`。`run_last30days` 等遗留函数仍从 `last30days_source` 重导出，保持向后兼容。

## 行为一致性 / Behavior parity

打分与渲染是**冻结行为**，输出必须与 V0.4.2 完全一致：

- `score_reddit_item` 的加减分、`min(score, 4)` 压分门控、`>=5 / >=1` 的 level 阈值未变。
- `Last30DaysSource` 构造的命令列表逐项与旧 `run_last30days` 一致：`--mock` 插入到 index 3、
  mock 用 `--search=reddit,youtube`、live 用 `--search=reddit`、live 才追加排序后的 `--subreddits`。
- 报告章节结构与 `prompts/ceramic_report_prompt.md` 对齐。

## 测试 / Testing

- `tests/test_scoring.py`：用手工构造的 `RelevanceConfig` 钉死 exclude 扣分、required 缺失压分、level 阈值。
- `tests/test_sources.py`：MockSource 输出能被 `collect_evidence` 消化并完成分层；
  Last30DaysSource 命令列表逐项断言（`subprocess.run` 被 mock）。
- 运行方式：`python -m unittest discover tests`（38 个用例全绿）。

## 影响 / Consequences

- 优点：mock 报告在任意机器零配置生成；新增数据源不再触碰打分逻辑；live 路径行为不变。
- 代价：多一个 `sources/` 包与一份样例数据需要维护；改样例数据后需重跑测试以保证分层覆盖。

## 回滚 / Rollback

`ceramic_report.py` 仍重导出全部 `run_last30days*` 函数，旧调用方式不受影响；如需回滚，
可在 `main()` 中把 source 选择改回直接调用 `run_last30days`，并移除 `sources/` 包与样例数据。

## 参考 / References

- `AGENTS.md` 第 2、6 节（架构与冻结行为）
- `prompts/ceramic_report_prompt.md`（报告章节契约）
