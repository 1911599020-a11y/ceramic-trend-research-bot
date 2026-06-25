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
- 先运行 `bash scripts/check_environment.sh`，查看 `terminal proxy env` 和 `Reddit proxy-aware HTTP`。
- 同时查看 `ScrapeCreators Reddit fallback`。如果是 `missing`，说明当前还没有 API 备份通道；如果 public JSON 持续 403，可以后续考虑配置 `SCRAPECREATORS_API_KEY`，或先切到其他数据源。
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
bash scripts/check_environment.sh
```

诊断结果里重点看三项：

- `terminal proxy env`：终端是否设置了 `HTTPS_PROXY`、`HTTP_PROXY` 或 `ALL_PROXY`。
- `DNS www.reddit.com` / `HTTPS www.reddit.com`：直连层面能否解析和建立 HTTPS。
- `Reddit proxy-aware HTTP`：Python 通过终端代理设置访问 Reddit 时，是否被 403 / 429 / DNS / timeout 拦住。
- `ScrapeCreators Reddit fallback`：如果 public Reddit JSON 被挡，是否已经具备上游 API 备份条件。这里只显示 configured / missing，不显示真实 key。

如果浏览器能打开 Reddit，但这里仍然 403，通常说明浏览器代理和终端代理不是同一套环境，或者 Reddit 拒绝了当前代理出口。

如果 `bash scripts/check_environment.sh` 已经显示 `Reddit proxy-aware HTTP` 是 `forbidden_403`，但你想进一步判断是普通网页、global search、User-Agent 还是指定 subreddit 搜索被挡，可以运行一次：

```bash
bash scripts/reddit_probe_matrix.sh
```

这个矩阵会发起多次最小 Reddit 探测请求。它只用于排查，不保存研究数据；刚遇到 403 / 429 后不要短时间反复运行。

常见矩阵结果：

- 首页 PASS，但所有 `search.json` FAIL：当前网络出口可以打开 Reddit 页面，但 Reddit 拒绝公共 JSON 搜索接口。优先换代理出口或后续考虑 API/第三方数据源，不要只改报告逻辑。
- app User-Agent FAIL，browser User-Agent PASS：可能是 User-Agent 触发限制，后续可以考虑把 live 预检与 public Reddit 路径的浏览器 UA 对齐。
- global search FAIL，但 subreddit search PASS：后续 live 可以优先走推荐 subreddit 定向搜索，减少全站搜索依赖。
- 全部 FAIL：先查网络、DNS、代理或 VPN。

如果你看到的是“首页 PASS，但所有 `search.json` FAIL”，建议先读 [Reddit 数据源替代路径评估](reddit-data-source-options.md)。这个情况通常不是报告生成逻辑坏了，而是当前网络出口或 Reddit 访问策略不适合免费 public JSON 搜索。

常见代理变量示例：

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
export ALL_PROXY=http://127.0.0.1:7890
```

如果你的代理是 SOCKS，诊断脚本会提醒 Python 标准库可能不支持 SOCKS 代理。此时要么改用 HTTP 代理端口，要么后续再评估是否引入额外依赖。

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
