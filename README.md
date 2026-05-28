# ceramic-trend-research-bot

陶瓷趋势情报总结工具。目标是输入陶瓷相关关键词，聚合 Reddit、YouTube、GitHub、Pinterest 等来源，生成中文 Markdown 趋势报告。

## Current Status

V0.3.2 是 **分类相关性规则精修版本**：

- `mock` 模式仍然可用，用于稳定生成示例报告
- `live` 模式只测试 Reddit，不接 YouTube / Pinterest / GitHub Actions
- Reddit 结果会按陶瓷相关 subreddit、陶瓷关键词、分类意图和跑偏词做轻量重排
- AI ceramic design、ceramic business、kiln firing 等分类有独立 required / boost / exclude 规则
- 跑偏词使用完整单词/短语匹配，降低 `cat` 这类词的误伤
- 报告会区分高相关内容、边缘相关内容和跑偏样本
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
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ceramic_report.py --mode mock --output reports/report.md
```

Reddit live 最小测试：

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ceramic_report.py --mode live --output reports/report.md
```

生成文件：

```text
reports/report.md
```

`reports/report.md` 当前是示例报告，可以暂时保留在版本库里，方便确认报告结构。

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
- `live` 模式当前只访问 Reddit 公共数据源；如果当前网络无法访问 Reddit，会生成带失败原因的报告，不会影响 mock 模式。

## Project Structure

```text
ceramic_report.py                 # V0.1 wrapper entry
config/ceramic_topics.json        # Ceramic keyword, subreddit, and relevance rules
prompts/ceramic_report_prompt.md  # Chinese report structure
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
