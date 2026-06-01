# ceramic-trend-research-bot

陶瓷趋势情报总结工具。目标是输入陶瓷相关关键词，聚合 Reddit、YouTube、GitHub、Pinterest 等来源，生成中文 Markdown 趋势报告。

## Current Status

V0.4.2 是 **报告归档 + 多期对比基础版本**：

- `mock` 模式仍然可用，用于稳定生成示例报告
- `live` 模式只测试 Reddit，不接 YouTube / Pinterest / GitHub Actions
- Reddit 结果会按陶瓷相关 subreddit、陶瓷关键词、分类意图和跑偏词做轻量重排
- AI ceramic design、ceramic business、kiln firing 等分类有独立 required / boost / exclude 规则
- 跑偏词使用完整单词/短语匹配，降低 `cat` 这类词的误伤
- 报告会区分高相关内容、边缘相关内容和跑偏样本
- 热门内容不再把低相关结果显示成趋势，也不再输出生硬的“暂无证据（0 分）”
- 趋势判断更严格依赖高相关证据；证据不足的方向会明确标注为暂不判断
- 内容选题和小工具灵感会区分“高相关证据支撑”和“长期建议方向”
- 报告顶部新增“本轮结论摘要”，用 5 到 8 条短句说明本轮真正值得注意什么
- 新增“本轮可信度”，按高相关、边缘相关和跑偏样本数量给出高 / 中 / 低
- 新增“下一轮搜索建议”，根据证据不足的关键词自动给出更具体搜索词
- 趋势判断、内容选题和小工具灵感更严格依赖高相关证据
- 跑偏样本会说明为什么跑偏，以及下次如何减少类似误伤
- 新增本地运行脚本，避免重复复制长 Python 命令
- live 模式新增冷却提醒和本地运行状态记录，减少短时间重复请求导致的 Reddit 429
- live 成功并拿到可用 Reddit 证据时，才会更新 `reports/report.md`
- live 因 DNS / 403 / 429 / 网络问题失败时，不覆盖上一份成功报告
- live 失败详情会写入 `local_outputs/last_error.md`，运行状态会写入 `local_outputs/run_state.json`
- live 失败时会按 403 / 429 / DNS / timeout 给出更清楚的本地排障提示
- live 成功时会同步更新 `reports/report.md`、`reports/latest.md`，并归档到 `reports/archive/`
- mock 只用于结构验证，不会写入 `reports/latest.md`，也不会进入 `reports/archive/`
- 新增最近两期 archive 对比脚本，输出 `reports/trend_diff.md`
- 不安装 `yt-dlp`
- 不配置 API key
- 不修改 `last30days-skill` 原始代码
- `live` 模式调用本地 `last30days-skill --quick --search=reddit`，并传入推荐 subreddit
- 输出中文 Markdown 到 `reports/report.md`

上游依赖路径：

```text
/Users/zhuyixiao/Documents/GitHub/last30days-skill/skills/last30days/scripts/last30days.py
```

推荐 Python：

```text
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
```

## Run

mock 示例报告：

```bash
bash scripts/run_mock.sh
```

Reddit live 最小测试：

```bash
bash scripts/run_live.sh
```

如果刚刚跑过 live，脚本会读取 `local_outputs/run_state.json` 并提示稍后再跑，避免频繁触发 Reddit 429。确实需要立即运行时可以加：

```bash
bash scripts/run_live.sh --force
```

不要连续多次使用 `--force`，尤其是刚遇到 429 或 403 之后。live 失败不会覆盖上一份成功的 `reports/report.md`，错误详情请看 `local_outputs/last_error.md`。

最近两期成功 live 报告对比：

```bash
bash scripts/compare_reports.sh
```

原始 Python 命令仍然可用：

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ceramic_report.py --mode live --output reports/report.md
```

生成文件：

```text
reports/report.md       # 当前主要报告；mock 和成功 live 都可以更新
reports/latest.md       # 最近一次成功 live 报告；mock 和失败 live 不更新
reports/archive/        # 历史成功 live 报告
reports/trend_diff.md   # 最近两期 archive 的基础对比
```

`reports/report.md` 当前是示例报告，可以暂时保留在版本库里，方便确认报告结构。

如果还没有成功 live，`reports/latest.md` 可能尚未生成。live 失败不会污染 `latest.md` 和 `archive/`。

live 失败时不会覆盖 `reports/report.md`，错误详情保存在：

```text
local_outputs/last_error.md
```

`local_outputs/` 已被 `.gitignore` 忽略，不会作为报告样例提交到 GitHub。

更多排障说明见 [docs/troubleshooting.md](docs/troubleshooting.md)。

## Environment Check

在继续真实 Reddit / YouTube 接入前，可以先运行环境诊断：

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/check_environment.py
```

诊断会检查 Python、`last30days-skill` 路径、Reddit/YouTube/GitHub DNS 与 HTTPS、`yt-dlp`、`.env` 文件和关键环境变量。它不会打印真实 key，也不会抓取研究数据。更多说明见 `docs/environment-check.md`。

## Safety

- 不要把 `.env` 提交到 GitHub。
- 真实 key 只放在本地 `.env`、系统环境变量、GitHub Secrets 或服务器密钥管理中。
- `.env.example` 只保留空变量，用作配置模板。
- `mock` 模式不会读取真实 API key，也不会发起真实联网搜索。
- `mock` 模式可以覆盖 `reports/report.md`，因为它是测试流程。
- `live` 模式当前只访问 Reddit 公共数据源；如果当前网络无法访问 Reddit，会保留上一份成功报告，并把失败原因写入 `local_outputs/last_error.md`。

## Project Structure

```text
ceramic_report.py                 # V0.1 wrapper entry
config/ceramic_topics.json        # Ceramic keyword, subreddit, and relevance rules
prompts/ceramic_report_prompt.md  # Chinese report structure
scripts/run_mock.sh               # Local mock runner
scripts/run_live.sh               # Local live runner with cooldown
scripts/compare_reports.py        # Compare latest two archived live reports
scripts/compare_reports.sh        # Local compare runner
local_outputs/last_error.md       # Ignored live failure details
local_outputs/run_state.json      # Ignored local run state
reports/                          # Generated Markdown reports
reports/latest.md                 # Latest successful live report
reports/archive/                  # Archived successful live reports
reports/trend_diff.md             # Latest archive comparison
docs/automation-roadmap.md        # Future automation paths
docs/troubleshooting.md           # Local live failure troubleshooting
.env.example                      # Future live-mode environment variables
.gitignore                        # Ignore local secrets and temp files
```

## Future Sources

后续阶段会逐步接入：

- Reddit live search
- YouTube transcripts via `yt-dlp`
- Pinterest / Instagram / TikTok through optional providers
- GitHub issues / discussions
- GitHub Actions scheduled report generation
- Server / VPS / cloud-function deployment

## V0.1 Output Sections

报告固定包含：

- 本轮结论摘要
- 本轮可信度
- 热门内容
- 高相关内容
- 边缘相关内容
- 跑偏样本
- 用户痛点
- 趋势判断
- 内容选题
- 小工具灵感
- 下一轮搜索建议
- 原始证据/链接
