# ceramic-trend-research-bot

陶瓷趋势情报总结工具。目标是输入陶瓷相关关键词，聚合 Reddit、YouTube、GitHub、Pinterest 等来源，生成中文 Markdown 趋势报告。

## Current Status

V0.1 是 **mock 报告生成版本**：

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

## Project Structure

```text
ceramic_report.py                 # V0.1 wrapper entry
config/ceramic_topics.json        # Ceramic keyword list
prompts/ceramic_report_prompt.md  # Chinese report structure
reports/                          # Generated Markdown reports
docs/automation-roadmap.md        # Future automation paths
.env.example                      # Future live-mode environment variables
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
