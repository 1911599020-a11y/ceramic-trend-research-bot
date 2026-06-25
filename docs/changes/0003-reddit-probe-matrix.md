---
id: 0003
title: Reddit 请求矩阵诊断
status: accepted
version: V0.5.3
date: 2026-06-25
supersedes: none
related:
  - scripts/reddit_probe_matrix.py
  - scripts/reddit_probe_matrix.sh
  - tests/test_reddit_probe_matrix.py
  - README.md
  - docs/troubleshooting.md
---

## 背景 / Context

V0.5.2 已经能判断 Reddit live 失败是 403、429、DNS、timeout 还是代理问题，但它只有一个
Reddit `search.json` 探测点。真实排障时还需要知道：Reddit 首页是否可访问、global search 是否被挡、
browser User-Agent 是否更容易通过、指定 subreddit search 是否比全站搜索稳定。

## 决策 / Decision

新增一个独立请求矩阵：

```bash
bash scripts/reddit_probe_matrix.sh
```

它对少量 Reddit 请求形状做最小探测，只输出诊断结果，不保存研究数据，不写报告，不修改
`last30days-skill`。

## 探测项 / Probes

- Reddit 首页 + browser User-Agent
- 全站 `search.json` + app User-Agent
- 全站 `search.json` + browser User-Agent
- `r/Pottery/search.json` + browser User-Agent

## 测试 / Testing

新增 `tests/test_reddit_probe_matrix.py`，覆盖：

- 请求矩阵包含 live 相关 JSON 搜索形状。
- JSON 响应返回 PASS。
- HTTP 403 返回 FAIL。
- app User-Agent 失败但 browser User-Agent 成功时，给出明确下一步建议。

真实联网不进入单元测试；实际网络结果通过手动运行 wrapper 查看。

## 影响 / Consequences

- 优点：能把 “Reddit 403” 进一步拆成请求形状问题，而不是只停在网络失败。
- 优点：为后续是否调整 preflight User-Agent、优先 subreddit search 或代理出口提供依据。
- 代价：该矩阵会发起多次 Reddit 探测请求，不能短时间反复运行，尤其是刚遇到 403 / 429 后。

## 回滚 / Rollback

删除 `scripts/reddit_probe_matrix.py`、`scripts/reddit_probe_matrix.sh`、对应测试和文档入口即可；
不会影响 mock、live、report、latest 或 archive 逻辑。
