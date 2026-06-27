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
--data-source auto
```

`auto` 表示：mock 模式使用本地样例数据 `mock`；live 模式使用当前默认真实源 `reddit_last30days`。
完整数据源清单见 `config/data_sources.json`。`scrapecreators_reddit` 是显式可选 API 数据源，
不会被 `auto` 自动调用；`youtube_future`、`pinterest_future` 仍是预留入口。
为避免误用付费 API，`CERAMIC_DATA_SOURCE=scrapecreators_reddit` 不会打开 ScrapeCreators；
必须在命令里显式写 `--data-source scrapecreators_reddit`。

ScrapeCreators 准备状态：

```bash
bash scripts/check_scrapecreators_ready.sh
```

这个命令不访问 ScrapeCreators，不验证额度，不抓取 Reddit，只检查本地是否配置了 key，并且不会打印真实 key。

真实 live 前检查清单：

```text
docs/live-readiness-checklist.md
```

申请 key、配置 key 或第一次做 key-backed API live probe 前，必须先读这份清单。

ScrapeCreators tiny probe 方案：

```text
docs/plans/2026-06-25-scrapecreators-tiny-probe.md
```

这份方案已经落地为独立 tiny probe。默认运行不会联网；只有显式确认时才会发起一次极小 ScrapeCreators Reddit API 请求。

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
- 数据源是否仍使用 `--data-source auto`
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
- 申请 key 后：确认显示 `configured`；readiness 不会调用真实 API。
- 进入下一阶段前：再决定是否运行一次需要显式确认的 tiny probe。

### 8. 进入真实 API live 前

先读：

```text
docs/live-readiness-checklist.md
```

这一步不是运行命令，而是确认安全边界：key 不进 Git、不打印、不烧额度、失败不污染正式报告。

### 9. 准备实现 tiny probe 前

先读：

```text
docs/plans/2026-06-25-scrapecreators-tiny-probe.md
```

不要猜测 API endpoint。真正实现请求前，需要官方 ScrapeCreators 文档或用户提供的脱敏样例。

### 10. 运行 ScrapeCreators tiny probe 保护检查

默认不联网：

```bash
bash scripts/probe_scrapecreators_reddit.sh
```

输出：

```text
local_outputs/scrapecreators_probe_state.json
```

这一步只确认保护机制存在，不会消耗 ScrapeCreators credits。

### 11. 运行一次真实 ScrapeCreators tiny probe

只有用户明确同意消耗一次 API 请求时才运行：

```bash
bash scripts/probe_scrapecreators_reddit.sh --confirm-live-api --topic "ceramic glaze" --limit 1
```

成功或失败都不会更新：

```text
reports/report.md
reports/latest.md
reports/archive/
```

结果和错误只看：

```text
local_outputs/scrapecreators_probe.json
local_outputs/scrapecreators_probe_state.json
local_outputs/scrapecreators_probe_error.md
```

如果遇到 401、403、429、quota/billing、timeout 或 network error，先看 error 文件，不要连续重复请求。

### 12. 显式使用 ScrapeCreators 正式 live 数据源

只有在确认愿意消耗 ScrapeCreators API 额度时才运行：

```bash
bash scripts/run_scrapecreators_live.sh
```

默认安全模式只运行 `config/scrapecreators_probe_topics.json` 的单关键词配置。先检查命令但不联网：

```bash
bash scripts/run_scrapecreators_live.sh --dry-run
```

确认愿意消耗更多 API 额度后，才运行完整关键词：

```bash
bash scripts/run_scrapecreators_live.sh --confirm-full-api
```

需要在报告末尾附加 prompt 模板调试结构时，再加：

```bash
bash scripts/run_scrapecreators_live.sh --include-prompt-template
```

这一步不同于 tiny probe：它会进入正式报告流程。成功时会更新：

```text
reports/report.md
reports/latest.md
reports/archive/
```

失败时仍会保留上一份成功报告，并把错误写入：

```text
local_outputs/last_error.md
local_outputs/run_state.json
```

不要把它当成默认日常命令；默认日常 live 仍然优先用 `bash scripts/run_live.sh`。
第一次正式 ScrapeCreators live 先用 `config/scrapecreators_probe_topics.json` 的单关键词配置；
确认稳定后，再考虑使用完整 `config/ceramic_topics.json`。

### 13. 小批量关键词质量测试

V0.6.6 用于测试关键词是否值得长期追踪。默认配置见：

```text
config/scrapecreators_quality_topics.json
```

当前默认测试：

```text
kiln firing
ceramic business
AI ceramic design
```

先 dry-run，不联网、不消耗 API：

```bash
bash scripts/run_keyword_quality_check.sh
```

确认愿意消耗 API 额度后，才真实运行：

```bash
bash scripts/run_keyword_quality_check.sh --confirm-live-api
```

这一步输出只写入：

```text
local_outputs/keyword_quality_report.md
local_outputs/keyword_quality_latest.md
local_outputs/keyword_quality_summary.md
local_outputs/keyword_quality_state.json
local_outputs/keyword_quality_error.md
local_outputs/keyword_quality_archive/
```

它不会更新正式的 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
如果只想根据已有测试报告重新生成摘要，可以运行：

```bash
python scripts/summarize_keyword_quality.py
```

### 14. 智能评分设计层

V0.6.7 新增的是智能评分接口设计，不是真实大模型接入。当前配置见：

```text
config/llm_scoring.json
prompts/llm_scoring_prompt.md
scoring/llm_scorer.py
```

当前规则：

- 默认 `enabled=false`
- 默认 `provider=none`
- 默认 `mode=design_only`
- 不调用 OpenAI / Anthropic / Ollama 或其他模型 API
- 不消耗 API 额度
- 不更新 `reports/report.md`
- 不更新 `reports/latest.md`
- 不进入 `reports/archive/`

V0.6.8 如果进入大模型评分 tiny test，只能在用户明确同意后运行，并且输出只能写入：

```text
local_outputs/llm_scoring_probe.md
```

这个智能评分层的定位是：规则评分先做便宜稳定的第一轮过滤，大模型评分以后只做第二轮语义判断，用来识别真实陶瓷信号、关键词意图匹配和跑偏噪音。

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
| `local_outputs/scrapecreators_probe.json` | ScrapeCreators tiny probe 脱敏结果摘要，不进入 Git |
| `local_outputs/scrapecreators_probe_state.json` | ScrapeCreators tiny probe 运行状态，不进入 Git |
| `local_outputs/scrapecreators_probe_error.md` | ScrapeCreators tiny probe 失败说明，不进入 Git |
| `local_outputs/llm_scoring_probe.md` | 未来 LLM scoring tiny probe 输出，不进入 Git |
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
- 进入 key-backed live 前：先按 `docs/live-readiness-checklist.md` 逐项检查
- tiny probe 默认保护检查：跑 `bash scripts/probe_scrapecreators_reddit.sh`
- 真实 tiny probe：只有用户明确同意后，才跑 `bash scripts/probe_scrapecreators_reddit.sh --confirm-live-api --topic "ceramic glaze" --limit 1`
- ScrapeCreators 正式 live：只有用户明确同意消耗 API 额度时，才运行 `bash scripts/run_scrapecreators_live.sh`；完整关键词必须加 `--confirm-full-api`
- 提交前：确认 `git status` / GitHub Desktop changed files 中没有 `.env` 或 `local_outputs/`

## 交接给新 Agent

新对话可直接使用：

```text
请先读取 README.md、docs/workflow.md、docs/troubleshooting.md 和最近 Git 提交，恢复项目状态后继续。
```

这样不需要复制完整历史对话。
