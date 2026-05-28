# ceramic-trend-research-bot

陶瓷趋势情报总结工具。目标是输入陶瓷相关关键词，聚合 Reddit、YouTube、GitHub、Pinterest 等来源，生成中文 Markdown 趋势报告。

## Current Status

V0.1 是 **mock 报告生成版本**。V0.1.1 只做项目安全整理与自检：

- 不真实联网
- 不安装 `yt-dlp`
- 不配置 API key
- 不修改 `last30days-skill` 原始代码
- 使用本地 `last30days-skill` 的 `--mock --quick` 模式验证流程
- 输出中文 Markdown 到 `reports/report.md`

上游依赖路径：

```text
/Users/zhuyixiao/Documents/GitHub/last30days-skill/skills/last30days/scripts/last30days.py
```

推荐 Python：

```text
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
```

## Run V0.1

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ceramic_report.py --mode mock --output reports/report.md
```

生成文件：

```text
reports/report.md
```

`reports/report.md` 当前是示例报告，可以暂时保留在版本库里，方便确认报告结构。

## Safety

- 不要把 `.env` 提交到 GitHub。
- 真实 key 只放在本地 `.env`、系统环境变量、GitHub Secrets 或服务器密钥管理中。
- `.env.example` 只保留空变量，用作配置模板。
- 当前 mock 模式不会读取真实 API key，也不会发起真实联网搜索。

## Project Structure

```text
ceramic_report.py                 # V0.1 wrapper entry
config/ceramic_topics.json        # Ceramic keyword list
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
- 用户痛点
- 趋势判断
- 内容选题
- 小工具灵感
- 原始证据/链接
