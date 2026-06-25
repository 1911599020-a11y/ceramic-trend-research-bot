# Reddit 数据源替代路径评估

本页记录 V0.5.4 对 Reddit live 卡点的判断。它不是新功能，也不会配置真实 API key；目的是让后续接手的人知道：当前问题更像 Reddit 数据入口受限，而不是报告生成逻辑坏了。

## 当前结论

V0.5.3 的请求矩阵显示：

- Reddit 首页请求可以通过。
- `www.reddit.com/search.json` 会返回 403 Blocked。
- `www.reddit.com/r/Pottery/search.json` 也会返回 403 Blocked。
- 换成浏览器 User-Agent 后，公共 JSON 搜索接口仍然被挡。

这说明当前网络出口能打开 Reddit 页面，但 Reddit 公共 JSON 搜索接口对该出口或请求形状不友好。继续只改报告渲染、关键词或 User-Agent，不能稳定解决 live 数据源问题。

## 现有上游能力

本项目的 live 模式通过外部 `last30days-skill` 获取 Reddit 数据，主项目不修改它的源码。

上游 `last30days-skill` 的 Reddit 流程是：

1. 先走免费 Reddit public JSON。
2. 如果 public JSON 没有拿到结果，并且配置了 `SCRAPECREATORS_API_KEY`，再走 ScrapeCreators Reddit API 作为备份。
3. 如果没有配置 `SCRAPECREATORS_API_KEY`，public JSON 又被挡，就只能返回空结果。

相关上游文件：

- `/Users/zhuyixiao/Documents/GitHub/last30days-skill/skills/last30days/scripts/lib/pipeline.py`
- `/Users/zhuyixiao/Documents/GitHub/last30days-skill/skills/last30days/scripts/lib/reddit_public.py`
- `/Users/zhuyixiao/Documents/GitHub/last30days-skill/skills/last30days/scripts/lib/reddit.py`

## 可选路线

### 路线 A：继续尝试免费 Reddit public JSON

适合情况：

- 你有稳定的本地代理或不同网络出口。
- 你希望暂时不配置任何第三方 API key。
- 你接受 live 偶尔失败，先用 mock 和历史报告继续调报告结构。

优点：

- 免费。
- 不需要新增账号或密钥。
- 当前代码已经支持。

风险：

- 当前出口的 `search.json` 已经被 403。
- 反复 `--force` 可能触发 429。
- 未来稳定性不可控。

建议做法：

- 不要短时间重复跑 live。
- 优先运行 `bash scripts/check_environment.sh` 和 `bash scripts/reddit_probe_matrix.sh` 判断网络形态。
- 如果矩阵仍然是“首页 PASS、搜索 JSON 全 FAIL”，就不要继续只调 User-Agent。

### 路线 B：使用 ScrapeCreators Reddit API

适合情况：

- 你希望 Reddit live 更稳定。
- 你愿意配置一个本地 API key。
- 你希望尽量复用 `last30days-skill` 已经写好的 Reddit API 备份路径。

优点：

- 上游已经支持 `SCRAPECREATORS_API_KEY`。
- 不需要修改 `last30days-skill` 源码。
- 可以保留当前数据源适配层架构。
- 更适合之后继续扩展 Pinterest、Instagram、YouTube comments 等同类 API 数据源。

风险：

- 需要第三方服务账号和 API key。
- 可能有额度、费用或请求限制。
- 需要把 key 放在本地 `.env`、系统环境变量或部署平台 Secrets，不能提交到 GitHub。

建议做法：

- 先不直接配置真实 key。
- 下一步可以做 V0.5.5：ScrapeCreators readiness mode，只检查 key 是否存在、提示如何配置、确保不打印真实 key。
- 等你确认要走这条路线后，再在本地配置真实 key，并跑一次小规模 live。

### 路线 C：暂时绕开 Reddit，先接更稳定来源

适合情况：

- 你暂时不想处理代理或 API key。
- 你希望项目继续向“陶瓷 AI 情报工具”推进。
- 你更关心论文、GitHub、YouTube 或长期资料库。

优点：

- 不被 Reddit 403 卡住。
- 可以继续建设报告质量、素材库、自动归档和多期对比。
- 对陶瓷 AI 方向，论文和 GitHub 往往更适合做“小工具灵感”。

风险：

- Reddit 用户痛点会暂时变少。
- 社群热帖和评论证据不足时，趋势判断仍然需要保守。

建议做法：

- 保留 Reddit live 入口，但不要把它作为唯一数据源。
- 后续评估 GitHub issues/discussions、论文证据、YouTube transcript 等来源。
- 报告里继续明确样本来源和可信度。

## 推荐决策

当前不建议继续反复请求 public Reddit JSON。V0.5.3 的矩阵已经说明：当前出口不是单个关键词失败，而是 Reddit 搜索 JSON 入口整体受限。

更稳的下一步是走路线 B，但分两步做：

1. V0.5.5 先做 ScrapeCreators readiness mode：只做配置检查和说明，不放真实 key，不真实抓取。当前项目已具备该检查。
2. 你确认后，再配置 `SCRAPECREATORS_API_KEY` 并进行一次最小 Reddit live 验证。

如果你暂时不想配置第三方 API，则走路线 C：先推进 GitHub / 论文 / YouTube 等来源，把 Reddit 当作“可用时加分”的数据源。

## 下一步建议

优先建议：

- 运行 `bash scripts/check_environment.sh`，查看 `ScrapeCreators Reddit fallback` 是 configured 还是 missing。
- 如果 public JSON 403 且 ScrapeCreators 仍是 missing，再决定是否配置 key，或先切到其他数据源。
- 真正配置 key 前，继续保持 mock 和历史 live 报告保护机制。

暂不建议：

- 不要现在安装 `yt-dlp`。
- 不要现在接 YouTube。
- 不要现在把真实 key 写入仓库。
- 不要修改 `last30days-skill` 源码。
