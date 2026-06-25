# Daily Workflow

这份操作手册用于 Mac mini 上的日常运行，也方便 Codex、Claude Code 或其他开发者快速接手项目。

## 开始前

项目路径：

```text
/Users/zhuyixiao/Documents/GitHub/ceramic-trend-research-bot
```

上游 `last30days-skill` 路径：

```text
/Users/zhuyixiao/Documents/GitHub/last30days-skill
```

当前报告生成方式：

```text
MODEL_PROVIDER=rules
```

`rules` 表示报告由本地规则生成，不调用外部大模型，不需要 API key。

当前数据源选择：

```text
CERAMIC_DATA_SOURCE=auto
```

`auto` 表示：mock 模式使用本地样例数据 `mock`；live 模式使用当前真实源 `reddit_last30days`。
完整数据源清单见 `config/data_sources.json`。`scrapecreators_reddit`、`youtube_future`、`pinterest_future`
只是预留入口，本阶段不会自动调用。

ScrapeCreators 准备状态：

```bash
bash scripts/check_scrapecreators_ready.sh
```

这个命令不访问 ScrapeCreators，不验证额度，不抓取 Reddit，只检查本地是否配置了 key，并且不会打印真实 key。

本地研究证据：

```text
data/research_evidence.json
```

报告会默认读取这份文件，并生成“研究证据”模块。它用于长期产品方向和专业背景，不代表本轮 Reddit 热度。

## 日常推荐顺序

### 1. 进入项目目录

```bash
cd /Users/zhuyixiao/Documents/GitHub/ceramic-trend-research-bot
```

### 2. 先跑环境诊断

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/check_environment.py
```

重点看：

- Reddit DNS / HTTPS 是否可用
- `last30days-skill` 路径是否存在
- `MODEL_PROVIDER` 是否为 `rules`
- `CERAMIC_DATA_SOURCE` 是否为 `auto`
- `.env` 是否安全

### 3. 调整报告结构时跑 mock

```bash
bash scripts/run_mock.sh
```

mock 会更新：

```text
reports/report.md
```

mock 默认也会带上本地研究证据，方便检查研究证据模块。如果只想看社媒/mock 结构，可以运行：

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ceramic_report.py --mode mock --no-research-evidence
```

mock 不会更新：

```text
reports/latest.md
reports/archive/
```

因此 mock 不会污染真实历史报告。

### 4. 获取真实 Reddit 数据时跑 live

```bash
bash scripts/run_live.sh
```

只有 live 成功并取得可用 Reddit 证据时，才会更新：

```text
reports/report.md
reports/latest.md
reports/archive/YYYY-MM-DD_HHMM_report.md
```

`reports/latest.md` 是最近一次成功 live 报告；`reports/archive/` 保存历史成功 live 报告。

### 5. 强制跳过冷却

```bash
bash scripts/run_live.sh --force
```

只在明确需要时使用。遇到 403、429、DNS 或 timeout 后不要连续使用 `--force`。

### 6. 对比最近两期报告

```bash
bash scripts/compare_reports.sh
```

输出：

```text
reports/trend_diff.md
```

如果 archive 不足两份，脚本会生成“样本不足”说明，不会崩溃。

### 7. 只检查 ScrapeCreators 准备状态

```bash
bash scripts/check_scrapecreators_ready.sh
```

使用场景：

- 申请 key 前：确认当前是 `missing`，不会影响 mock 和 Reddit public live。
- 申请 key 后：确认显示 `configured`，但 V0.6.1 仍不会调用真实 API。
- 进入下一阶段前：再决定是否做一次极小规模 key-backed live probe。

## live 失败时看哪里

错误详情：

```text
local_outputs/last_error.md
```

运行状态：

```text
local_outputs/run_state.json
```

常见错误：

- `forbidden_403`：Reddit 拒绝当前请求
- `rate_limited_429`：请求过于频繁
- `dns_error`：无法解析 Reddit 域名
- `timeout`：网络或代理连接不稳定
- `network_error`：其他网络连接问题

如果 live 失败，先看 `local_outputs/last_error.md` 里的“本次数据源”。如果写的是
`reddit_last30days`，通常先排查 Reddit / 代理 / 403 / 429，不要急着改报告生成逻辑。

live 失败不会覆盖：

```text
reports/report.md
reports/latest.md
reports/archive/
```

详细排障见 [troubleshooting.md](troubleshooting.md)。

如果暂时不申请 ScrapeCreators key，不要把项目卡在 Reddit live 上。下一阶段路线见 [stable-data-source-roadmap.md](stable-data-source-roadmap.md)，优先维护论文、GitHub、YouTube 和本地证据库方向。

## 报告文件说明

| 文件 | 用途 |
|---|---|
| `reports/report.md` | 当前主要报告，mock 或成功 live 都可以更新 |
| `reports/latest.md` | 最近一次成功 live 报告 |
| `reports/archive/` | 历史成功 live 报告 |
| `reports/trend_diff.md` | 最近两期成功 live 报告的基础对比 |
| `local_outputs/last_error.md` | 最近一次 live 失败详情，不进入 Git |
| `local_outputs/run_state.json` | 冷却、状态和错误类型，不进入 Git |
| `data/research_evidence.json` | 本地研究证据，进入报告的“研究证据”模块 |
| `config/data_sources.json` | 数据源清单，区分可用源和预留源 |

## 推荐的日常节奏

- 改代码或报告格式：跑 mock
- 网络正常且需要新数据：跑一次 live
- live 数据源失败：看 `last_error.md`，确认是不是 `reddit_last30days` 被挡
- live 成功积累两期以上：跑 compare
- live 失败：先看错误，不要连续重试
- ScrapeCreators 晚点申请：先维护 `research/ceramic-ai-evidence.md` 和稳定数据源路线
- 申请 ScrapeCreators key 后：先跑 `bash scripts/check_scrapecreators_ready.sh`，不要直接改 live 抓取逻辑
- 提交前：确认 `git status` 中没有 `.env` 或 `local_outputs/`

## 交接给新 Agent

新对话可直接使用：

```text
请先读取 README.md、docs/workflow.md、docs/troubleshooting.md 和最近 Git 提交，恢复项目状态后继续。
```

这样不需要复制完整历史对话。
