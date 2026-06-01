# Troubleshooting

本页用于排查 `bash scripts/run_live.sh` 的 Reddit live 运行问题。

当前项目的保护规则是：live 成功并拿到可用 Reddit 证据时，才更新 `reports/report.md`；live 失败时，不覆盖上一份成功报告，错误详情写入 `local_outputs/last_error.md`。

live 成功时还会更新：

- `reports/latest.md`
- `reports/archive/YYYY-MM-DD_HHMM_report.md`

live 失败时不会更新 `reports/latest.md`，也不会新增 archive 报告。这是为了避免失败说明污染历史真实数据。

## 403 Blocked

含义：

- Reddit 拒绝了当前请求。
- 常见原因是代理出口、IP、User-Agent、访问频率或 Reddit 当前访问策略。
- 这通常不代表报告生成逻辑坏了。

建议：

- 换一个代理节点或网络环境。
- 确认终端代理真的生效，不只是浏览器代理生效。
- 稍后再试，避免短时间连续强制运行。

## 429 Too Many Requests

含义：

- Reddit 临时限流。
- 通常是短时间请求太频繁，尤其是连续使用 `--force`。

建议：

- 至少等待 30 分钟。
- 不要连续使用 `bash scripts/run_live.sh --force`。
- 可以先用 mock 模式调整报告结构。

## DNS 失败

常见错误：

- `nodename nor servname provided, or not known`
- `name resolution`
- `failed to resolve`

含义：

- 当前运行环境无法解析 Reddit 域名。
- 可能是 DNS、代理、网络权限或 Codex 运行环境限制。

建议：

- 检查网络和 DNS。
- 确认终端代理生效。
- 换到本地终端运行。

## Timeout / Connection Reset

含义：

- 网络连接超时、代理出口不稳定，或连接被重置。

建议：

- 换代理节点。
- 稍后再试。
- 如果频繁出现，不要连续 `--force`，先用 mock 模式继续调报告。

## 检查终端代理

浏览器能打开 Reddit，不等于终端也能访问 Reddit。可以先检查终端环境变量：

```bash
env | grep -i proxy
```

如果这里没有看到 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 等配置，说明当前终端可能没有使用代理。

也可以做一个最小连通性检查：

```bash
python3 scripts/check_environment.py
```

## 运行 mock

mock 不访问真实 Reddit，适合调整报告结构：

```bash
bash scripts/run_mock.sh
```

mock 可以覆盖 `reports/report.md`，因为它是测试流程。

## 运行 live

普通 live：

```bash
bash scripts/run_live.sh
```

强制跳过冷却：

```bash
bash scripts/run_live.sh --force
```

## 查看最近一次成功报告

最近一次成功 live 报告在：

```text
reports/latest.md
```

如果这个文件还不存在，说明当前项目里还没有生成过可归档的成功 live 报告，或者文件尚未被提交。

## 查看历史报告

历史成功 live 报告在：

```text
reports/archive/
```

文件名类似：

```text
2026-06-02_0045_report.md
```

mock 报告不会进入这里，live 失败报告也不会进入这里。

## 查看趋势对比报告

运行：

```bash
bash scripts/compare_reports.sh
```

输出：

```text
reports/trend_diff.md
```

如果 `reports/archive/` 里不足两份成功 live 报告，脚本会生成一份“样本不足”的说明，不会崩溃。这种情况下不要把 `trend_diff.md` 当成趋势结论。

## 什么时候不要用 --force

- 刚遇到 429 时不要用。
- 刚遇到 403 时不要连续用。
- 网络或代理不稳定时不要连续用。
- 只是想改报告结构时，不要用 live，先跑 mock。

如果 live 失败，请先看：

```text
local_outputs/last_error.md
```

这个文件不会进入 GitHub。
