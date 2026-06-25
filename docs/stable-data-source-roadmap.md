# 稳定数据源路线图

V0.5.6 的目标是：在暂不申请 `SCRAPECREATORS_API_KEY` 的情况下，让项目继续向“陶瓷趋势情报 + 陶瓷 AI 小工具灵感”推进。

这不是新抓取功能，也不配置真实 API key。它是一份路线说明：当 Reddit public JSON 不稳定、ScrapeCreators 晚点再申请时，项目优先用哪些更稳定的数据源。

## 当前判断

- Reddit 仍然有价值，尤其适合看用户痛点、工作室问题和社区讨论。
- 但当前 public Reddit JSON 容易 403，不能把它当作唯一 live 来源。
- ScrapeCreators 可以作为未来 Reddit API 备份，但暂时不配置。
- 陶瓷 AI 方向已经出现更对口的研究证据，适合先沉淀到本地资料库。

## 数据源优先级

### 第一层：本地 mock 和本地证据库

用途：

- 保证报告结构稳定。
- 保存 GlazyBench、ClayScape、釉料预测、陶泥 3D 打印等长期证据。
- 不联网、不需要 key、不受平台封锁影响。

适合做：

- 报告结构验证。
- 长期产品方向梳理。
- 陶瓷 AI 关键词池维护。
- 后续 source adapter 的样本数据。

### 第二层：论文和研究项目

用途：

- 追踪陶瓷材料、釉料预测、生成式设计、数字制造。
- 给“小工具灵感”提供更专业的证据。
- 补足 Reddit 无法稳定获取时的专业趋势判断。

优先方向：

- `ceramic glaze machine learning`
- `AI glaze prediction`
- `ceramic material informatics`
- `clay 3D printing`
- `ceramic additive manufacturing`
- `generative ceramic design`
- `computational ceramics`

适合输出：

- 研究摘要。
- 对陶瓷创作者的启发。
- 可能的小工具方向。
- 证据限制与待核实事项。

### 第三层：GitHub

用途：

- 观察是否有开源工具、数据集、实验代码、issue 讨论。
- 连接“研究论文”与“可做成工具”的实现可能。

优先搜索：

- `glaze prediction`
- `ceramic dataset`
- `ceramic 3d printing`
- `clay 3d printing`
- `material informatics ceramic`
- `generative pattern ceramics`

注意：

- GitHub 不一定有陶瓷垂直项目，可能样本少。
- 如果接 GitHub source adapter，建议先只抓 repo metadata、README、issues 标题，不做大规模爬取。
- `GITHUB_TOKEN` 后续可以提高额度，但当前阶段不配置。

### 第四层：YouTube

用途：

- 观察陶瓷教学、工作室经验、釉料测试、窑炉问题。
- 提供中文内容选题参考。

适合方向：

- glaze testing
- kiln firing
- pottery studio business
- ceramic 3D printing
- AI pottery workflow

注意：

- 当前不安装 `yt-dlp`。
- 等决定进入 YouTube 阶段后，再处理 transcript、视频元数据和版权边界。

### 第五层：Reddit + ScrapeCreators

用途：

- 继续作为用户痛点和社区讨论的高价值来源。
- 当 public JSON 不稳定时，用 ScrapeCreators 作为 API 备份。

进入条件：

- 用户决定申请并配置 `SCRAPECREATORS_API_KEY`。
- 环境诊断显示 `ScrapeCreators Reddit fallback: configured`。
- 先做最小 live 验证，不连续强制运行。

暂不做：

- 不把真实 key 写入仓库。
- 不在未确认额度前大规模跑 live。
- 不因为 Reddit 403 就反复请求 public JSON。

## 陶瓷 AI 方向优先级

### 1. 釉料预测与釉色知识库

关联证据：

- GlazyBench
- AI glaze prediction
- ceramic glaze machine learning
- glaze recipe dataset

可能工具：

- 釉色灵感库。
- 釉料实验记录器。
- 配方、烧成条件、效果图的检索工具。
- 釉面缺陷复盘表。

### 2. AI 辅助陶瓷设计与可制造性检查

关联证据：

- ClayScape
- generative ceramic design
- Chinese ceramic design
- ceramic prompt design

可能工具：

- 器型和纹样参考检索器。
- AI 概念图到陶瓷工艺的检查表。
- 中式陶瓷纹样来源标注和风格说明工具。

### 3. 陶泥 3D 打印和数字制造

关联证据：

- clay 3D printing
- ceramic additive manufacturing
- extrusion parameters
- ceramic 3D printing failure

可能工具：

- 陶泥 3D 打印参数记录器。
- 失败案例库。
- 材料、挤出参数、干燥、烧成的流程检查表。

### 4. 工作室经营与内容选题

关联证据：

- Reddit live 成功时的用户痛点。
- YouTube 教学和工作室经验。
- GitHub/论文无法覆盖的真实创作者问题。

可能工具：

- 陶瓷内容选题雷达。
- 工作室定价和订单沟通表。
- 中文内容脚本生成前的证据卡片。

## 建议版本顺序

### V0.5.7：本地证据库到报告的手动入口

目标：

- 让 `research/ceramic-ai-evidence.md` 里的重点证据能稳定进入报告的“长期产品方向”或“研究证据”模块。
- 不联网，不接 API。

### V0.6：GitHub / 论文来源最小 source adapter

目标：

- 先做一个稳定、低频、可测试的数据源。
- 保持 `TrendSource.fetch(...)` 契约不变。

### V0.7：YouTube 准备阶段

目标：

- 再决定是否安装 `yt-dlp`。
- 明确 transcript、视频元数据、版权和缓存规则。

### V0.8：ScrapeCreators Reddit live 验证

目标：

- 用户申请 key 后，做最小 Reddit API 备份验证。
- 不大规模抓取，先观察额度和稳定性。

## 当前阶段不要做

- 不申请或配置真实 `SCRAPECREATORS_API_KEY`。
- 不安装 `yt-dlp`。
- 不接 Instagram / Pinterest。
- 不修改 `last30days-skill` 源码。
- 不把 Reddit 403 当成报告逻辑错误。

## 成功标准

V0.5.6 完成后，项目应该具备：

- 一份明确的稳定数据源路线。
- 一份更清楚的陶瓷 AI 证据库使用方式。
- README 和 workflow 能告诉接手者：ScrapeCreators 晚点再申请时，项目该怎么继续推进。
