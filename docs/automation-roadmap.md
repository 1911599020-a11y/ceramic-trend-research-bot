# Automation Roadmap

V0.1 只实现本地 mock 报告生成，不接真实联网、不安装额外工具、不配置 API key。下面三条路线用于后续升级。

## A. 本地 Mac 定时任务

适合个人使用和早期验证。

- 使用 `launchd` 或 cron 定时运行 `ceramic_report.py --mode live`
- 本地保存 `.env`，配置 `FROM_BROWSER=off`，按需加入 `GITHUB_TOKEN`、`SCRAPECREATORS_API_KEY`、`BRAVE_API_KEY`
- 本地安装 `yt-dlp` 后启用 YouTube
- 报告输出到 `reports/report.md` 或 `~/Documents/CeramicTrendReports/`
- 可选：运行后用 AppleScript、邮件、飞书或 Slack webhook 推送报告路径

优点：配置简单，适合用自己的浏览器登录态和本机工具。  
限制：电脑需要开机，环境只在本机稳定。

## B. GitHub Actions 定时任务

适合自动提交报告和保留历史版本。

- 增加 `.github/workflows/report.yml`
- 使用 schedule 定时触发，例如每天或每周
- 在 GitHub Secrets 中保存 API keys
- 运行 `ceramic_report.py --mode live --output reports/report.md`
- 自动 commit 报告，或按日期输出到 `reports/YYYY-MM-DD-report.md`

优点：报告历史天然进入 Git，适合长期追踪趋势。  
限制：YouTube、Reddit 等来源可能受 GitHub runner 网络环境限制；浏览器 cookie 类数据源不适合放在 Actions。

## C. 服务器 / VPS / 云函数 Pro 版

适合稳定生产化和多人使用。

- 部署到 VPS、云函数或容器平台
- 用定时任务触发 live pipeline
- 把原始证据保存到 SQLite、Postgres 或对象存储
- 增加 Web dashboard、订阅推送、关键词管理、报告归档和失败重试
- 可拆分为采集层、报告生成层、分发层

优点：稳定、可扩展，适合接入更多来源和付费 API。  
限制：需要处理密钥管理、成本控制、任务监控和平台反爬限制。
