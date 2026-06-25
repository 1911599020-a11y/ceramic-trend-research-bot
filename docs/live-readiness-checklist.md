# Live Readiness Checklist

这份清单用于进入真实 key-backed live 测试前自检，尤其是未来启用 ScrapeCreators Reddit 备份前。

当前阶段：V0.6.2 只提供检查清单，不调用 ScrapeCreators API，不配置真实 key，不修改 `last30days-skill`。

## 什么时候使用

使用场景：

- 准备申请 `SCRAPECREATORS_API_KEY` 前。
- 已经拿到 key，但还没有做第一次真实 API live 测试。
- Reddit public JSON 连续 403 / 429，准备评估 API 备份路线。
- 新 agent 接手项目，准备碰 live / key / 数据源逻辑前。

不要用于：

- 单纯修改报告文案。
- 单纯跑 mock。
- 没有 key、也不准备真实测试 API 的日常开发。

## 当前允许做什么

当前允许：

- 跑 `bash scripts/run_mock.sh` 验证报告结构。
- 跑 `bash scripts/check_scrapecreators_ready.sh` 检查 key 是否存在。
- 跑 `bash scripts/check_environment.sh` 做完整环境诊断，但注意它会做一次最小 Reddit 探测。
- 查看 `config/data_sources.json` 了解数据源状态。
- 阅读 `local_outputs/last_error.md` 判断上次 live 为什么失败。

当前不允许：

- 把真实 key 写进仓库文件。
- 把 `.env` 提交到 GitHub。
- 在未确认额度、限流、失败保护前大规模请求 API。
- 因为 Reddit 403 就连续 `--force`。
- 安装 `yt-dlp` 或接 YouTube。
- 修改 `/Users/zhuyixiao/Documents/GitHub/last30days-skill` 源码。

## 申请 key 前

确认目标：

- 只是为了 Reddit 备份，不是为了接 YouTube / Pinterest。
- 只做最小验证，不做大规模抓取。
- 失败时不覆盖 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。

先运行：

```bash
bash scripts/check_scrapecreators_ready.sh
```

预期结果：

- `key status: missing`
- `network request: not attempted`
- `secret value: hidden`

如果这里显示 `configured`，说明本地已经有 key。不要继续重复配置，先确认 key 来源和保存位置。

## 拿到 key 后

保存位置：

- 本地 `.env`
- 当前 shell 环境变量
- GitHub Secrets
- 服务器密钥管理

不要保存到：

- README
- docs
- config JSON
- reports
- screenshots
- GitHub commit message

推荐环境变量名：

```bash
SCRAPECREATORS_API_KEY=
```

兼容但不优先：

```bash
SCRAPE_CREATORS_API_KEY=
```

再次运行：

```bash
bash scripts/check_scrapecreators_ready.sh
```

预期结果：

- `key status: configured`
- 不出现真实 key 内容
- `network request: not attempted`

如果真实 key 出现在终端输出、报告、错误文件或 Git diff 里，立刻停止，先清理泄露位置，再继续。

## 第一次真实 API live 前

必须确认：

- `git status` / GitHub Desktop changed files 里没有 `.env`。
- `git status` / GitHub Desktop changed files 里没有 `local_outputs/`。
- `bash scripts/run_mock.sh` 成功。
- `bash scripts/check_scrapecreators_ready.sh` 显示 `configured`。
- `config/data_sources.json` 里 `scrapecreators_reddit` 仍是 `planned`，除非已经进入下一阶段并明确改为可用。
- `reports/report.md` 有上一份可读报告。
- 知道失败会写到 `local_outputs/last_error.md`。
- 知道不要连续使用 `--force`。

第一次真实 API live 应该满足：

- 只跑极小样本。
- 只验证一个很窄的 Reddit 数据路径。
- 不跑全部关键词。
- 不生成长期定时任务。
- 不接 YouTube / Pinterest。
- 不把 API 返回原文直接提交到 GitHub。

## 停止条件

遇到下面任何情况，立即停止 live 测试：

- 返回 401 / unauthorized。
- 返回 403 / forbidden。
- 返回 429 / rate limited。
- 返回 quota / billing / payment 相关错误。
- 错误信息里出现真实 key。
- `reports/report.md` 被失败内容覆盖。
- `reports/latest.md` 被失败内容覆盖。
- `reports/archive/` 出现失败报告。

停止后先做：

```bash
bash scripts/run_mock.sh
```

注意：mock 会覆盖 `reports/report.md`，但不会更新 `reports/latest.md` 或 `reports/archive/`。
真实成功 live 报告以后者为准。

再看：

```text
local_outputs/last_error.md
local_outputs/run_state.json
```

## 第一次成功后

成功后检查：

- `reports/report.md` 是否是可读中文报告。
- `reports/latest.md` 是否更新。
- `reports/archive/` 是否新增一份成功报告。
- 报告是否标明数据源。
- 报告是否仍区分高相关、边缘相关、跑偏样本。
- 没有真实 key 进入报告。

再运行：

```bash
bash scripts/compare_reports.sh
```

如果 archive 不足两份，对比报告显示样本不足是正常的。

## 下一阶段入口

只有当这份清单全部通过，才进入下一阶段：

**V0.6.3：ScrapeCreators tiny live probe**

V0.6.3 只考虑：

- 做一个独立的单关键词、低频、可停止的 API probe。
- 明确请求上限和错误分类。
- 输出只写入 `local_outputs/`。
- 保持失败不覆盖成功报告。
- 不接入正式 `TrendSource.fetch()`。

真实 `ScrapeCreatorsSource.fetch()` 和 `--data-source scrapecreators_reddit` 可用化，放到 V0.6.4 以后再考虑。

## 快速判断

可以继续：

- mock 成功。
- readiness 显示 configured。
- key 没有出现在输出里。
- 用户明确同意做最小真实 API 测试。

不要继续：

- key 没配置。
- key 出现在任何输出里。
- 用户还没同意真实 API 测试。
- 你只是想改报告结构。
- 刚遇到 403 / 429。
