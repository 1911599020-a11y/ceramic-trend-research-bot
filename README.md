# ceramic-trend-research-bot

陶瓷趋势情报总结工具。目标是输入陶瓷相关关键词，聚合 Reddit、YouTube、GitHub、Pinterest 等来源，生成中文 Markdown 趋势报告。

## Current Status

V0.3.5 是 **live 失败保护版本**：

- `mock` 模式仍然可用，用于稳定生成示例报告
- `live` 模式只测试 Reddit，不接 YouTube / Pinterest / GitHub Actions
- Reddit 结果会按陶瓷相关 subreddit、陶瓷关键词、分类意图和跑偏词做轻量重排
- AI ceramic design、ceramic business、kiln firing 等分类有独立 required / boost / exclude 规则
- 跑偏词使用完整单词/短语匹配，降低 `cat` 这类词的误伤
- 报告会区分高相关内容、边缘相关内容和跑偏样本
- 热门内容不再把低相关结果显示成趋势，也不再输出生硬的“暂无证据（0 分）”
- 趋势判断更严格依赖高相关证据；证据不足的方向会明确标注为暂不判断
- 内容选题和小工具灵感会区分“高相关证据支撑”和“长期建议方向”
- 新增本地运行脚本，避免重复复制长 Python 命令
- live 模式新增冷却提醒和本地运行状态记录，减少短时间重复请求导致的 Reddit 429
- live 成功并拿到可用 Reddit 证据时，才会更新 `reports/report.md`
- live 因 DNS / 403 / 429 / 网络问题失败时，不覆盖上一份成功报告
- live 失败详情会写入 `local_outputs/last_error.md`，运行状态会写入 `local_outputs/run_state.json`
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

原始 Python 命令仍然可用：

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ceramic_report.py --mode live --output reports/report.md
```

生成文件：

```text
reports/report.md
```

`reports/report.md` 当前是示例报告，可以暂时保留在版本库里，方便确认报告结构。

live 失败时不会覆盖 `reports/report.md`，错误详情保存在：

```text
local_outputs/last_error.md
```

`local_outputs/` 已被 `.gitignore` 忽略，不会作为报告样例提交到 GitHub。

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
local_outputs/last_error.md       # Ignored live failure details
local_outputs/run_state.json      # Ignored local run state
reports/                          # Generated Markdown reports
docs/automation-roadmap.md        # Future automation paths
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

- 热门内容
- 高相关内容
- 边缘相关内容
- 跑偏样本
- 用户痛点
- 趋势判断
- 内容选题
- 小工具灵感
- 原始证据/链接
