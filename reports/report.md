# 陶瓷趋势情报报告

- 生成时间：2026-06-26 14:09
- 版本：V0.6.4 mock 本地报告
- 数据模式：MockSource `data/mock_samples.json`
- 数据源：Mock local samples (`mock`)
- 报告生成器：`rules`
- 关键词数量：10
- 相关性分层：高相关 10 条，边缘相关 5 条，跑偏样本 2 条

> 说明：当前报告使用 Mock local samples (`mock`) 验证流程与版式，不代表真实社媒趋势。

## 本轮结论摘要

- 当前是 mock 报告，只用于检查结构、分区和中文表达，不代表真实 Reddit 趋势。
- mock 中有 10 条高相关样例，可用于验证趋势摘要、选题和小工具模块的展示方式。
- 高相关样例主要落在 pottery studio、kiln firing、ceramic business，但这些不是实际社媒热度。
- 边缘相关 5 条、跑偏样本 2 条，只用于测试相关性分层是否清楚。
- 正式判断仍需要 live 模式拿到真实 Reddit 证据后再做。

## 本轮可信度

- 可信度：**低**
- 判断：当前是 mock 数据，只能验证报告流程，不能代表真实 Reddit 趋势。
- 证据结构：高相关 10 条，边缘相关 5 条，跑偏样本 2 条。

## 热门内容

- **ceramic art**：mock 热点为“Finished a ceramic art sculpture with a new glaze in my studio”（r/ceramics，412 upvotes, 57 comments），相关性：高相关（11 分）。
- **pottery**：mock 热点为“My first pottery wheel throwing session results”（r/pottery，286 upvotes, 41 comments），相关性：高相关（9 分）。
- **ceramic glaze**：mock 热点为“Cone 6 glaze recipe keeps getting pinholes on stoneware”（r/pottery，174 upvotes, 63 comments），相关性：高相关（14 分）。
- **AI ceramic design**：mock 热点为“Using AI to design a surface pattern for my ceramic mugs”（r/ceramics，198 upvotes, 74 comments），相关性：高相关（13 分）。
- **3D printed ceramics**：mock 热点为“Clay paste extrusion settings for my delta printer”（r/ceramic3dprinting，89 upvotes, 27 comments），相关性：高相关（13 分）。
- **handmade pottery**：mock 热点为“Handmade pottery mug set I made for my sister's wedding”（r/somethingimade，530 upvotes, 88 comments），相关性：高相关（11 分）。
- **ceramic business**：mock 热点为“How do you price handmade ceramic mugs on Etsy?”（r/pottery，143 upvotes, 96 comments），相关性：高相关（15 分）。
- **pottery studio**：mock 热点为“Our community studio added a beginner wheel class”（r/pottery，211 upvotes, 45 comments），相关性：高相关（17 分）。
- **ceramic texture**：mock 热点为“Carved texture experiments on a porcelain vase”（r/ceramics，324 upvotes, 39 comments），相关性：高相关（11 分）。
- **kiln firing**：mock 热点为“Bisque firing schedule for my new electric kiln”（r/pottery，167 upvotes, 58 comments），相关性：高相关（16 分）。

## 用户痛点

- **ceramic art**：创作者需要更快发现用户真正感兴趣的题材。
- **ceramic art**：从灵感、制作、展示到销售之间缺少连续的决策工具。
- **pottery**：创作者需要更快发现用户真正感兴趣的题材。
- **pottery**：从灵感、制作、展示到销售之间缺少连续的决策工具。
- **ceramic glaze**：釉色结果不稳定，配方、厚度、窑温之间的变量难追踪。
- **ceramic glaze**：新手难判断流釉、针孔、开片等问题的成因。
- **AI ceramic design**：数字设计与真实泥料、釉料、烧成之间存在落地断层。
- **AI ceramic design**：创作者需要把 AI/3D 灵感转译成可制作的工艺方案。
- **3D printed ceramics**：数字设计与真实泥料、釉料、烧成之间存在落地断层。
- **3D printed ceramics**：创作者需要把 AI/3D 灵感转译成可制作的工艺方案。
- **handmade pottery**：创作者需要更快发现用户真正感兴趣的题材。
- **handmade pottery**：从灵感、制作、展示到销售之间缺少连续的决策工具。
- **ceramic business**：工作室经营同时面对定价、排课、库存和社媒获客压力。
- **ceramic business**：手作产品很难把时间成本清楚地转化成价格。
- **pottery studio**：工作室经营同时面对定价、排课、库存和社媒获客压力。
- **pottery studio**：手作产品很难把时间成本清楚地转化成价格。
- **ceramic texture**：纹理灵感容易停留在图片收藏，缺少可执行的制作步骤。
- **ceramic texture**：表面肌理与器型、釉色的搭配需要更多案例对照。
- **kiln firing**：烧成曲线和窑位差异带来高试错成本。
- **kiln firing**：缺少可复盘的烧成记录和失败案例库。

## 趋势判断

- 当前为 mock 模式，本节只展示报告结构，不从模拟数据生成真实趋势判断。

## 研究证据

> 本节来自本地研究证据库，用于支撑长期产品方向和下一轮搜索建议；它不是本轮 Reddit 热度，也不能单独证明市场趋势。

| 证据 | 关联方向 | 可用启发 | 限制 | 链接 |
|---|---|---|---|---|
| GlazyBench: A Benchmark for Ceramic Glaze Property Prediction and Image Generation（2026-05-07） | ceramic glaze、AI ceramic design、kiln firing | 真实釉料配方数据集；釉面属性预测；釉面图像生成 | 预印本证据，需要核实代码和完整数据下载方式；数据和代码许可证待确认 | [打开](https://arxiv.org/abs/2605.06641) |
| ClayScape: A GenAI-Supported Workflow for Designing Chinese Style Ceramics with Clay 3D Printing（2026-04-28） | AI ceramic design、3D printed ceramics、ceramic texture | 生成式 AI 支持中式陶瓷设计；陶泥 3D 打印工作流；降低 CAD/CAM 操作门槛 | 用户评估样本较小，属于早期研究证据；系统、代码、模型和生成资产许可证待核实 | [打开](https://arxiv.org/abs/2604.25657) |

## 内容选题

### 有 Reddit 高相关证据支撑的选题
- 当前为 mock 模式，暂无真实 Reddit 高相关证据支撑的选题。

### 暂无充分证据但值得后续观察的选题
- 观察方向：《陶瓷作品从灵感到烧成失败复盘》 - 长期内容方向，需用更多真实失败案例验证。
- 观察方向：《釉色测试片如何变成可售卖系列》 - 适合等待更多 glaze / business 证据后展开。
- 观察方向：《AI 生成纹样到真实陶瓷表面的完整流程》 - 只有在 AI 与陶瓷制作同时出现时，才可升级为证据支撑选题。

## 小工具灵感

### 本轮证据直接支持的小工具
- 当前为 mock 模式，不把模拟数据写成本轮证据直接支持的小工具。

### 长期产品方向
- 陶瓷内容选题雷达：长期产品方向，不是本轮数据直接证明，后续需要更多 Reddit/YouTube/Pinterest 证据验证。
- AI 陶瓷纹样 Prompt 生成器：长期产品方向，不是本轮数据直接证明，需等 AI ceramic design 出现真实高相关证据后优先化。
- 釉色实验记录器：长期产品方向，不是本轮数据直接证明，可在更多 glaze / kiln 证据出现后优先化。
- 工作室定价小工具：长期产品方向，不是本轮数据直接证明，可在更多 business / studio 证据出现后优先化。
- 釉料实验记录器：研究证据启发，来自《GlazyBench: A Benchmark for Ceramic Glaze Property Prediction and Image Generation》，不是本轮社媒数据直接证明。
- 釉色灵感与配方检索库：研究证据启发，来自《GlazyBench: A Benchmark for Ceramic Glaze Property Prediction and Image Generation》，不是本轮社媒数据直接证明。
- AI 陶瓷设计可制造性检查表：研究证据启发，来自《ClayScape: A GenAI-Supported Workflow for Designing Chinese Style Ceramics with Clay 3D Printing》，不是本轮社媒数据直接证明。
- 中式陶瓷器型和纹样参考检索器：研究证据启发，来自《ClayScape: A GenAI-Supported Workflow for Designing Chinese Style Ceramics with Clay 3D Printing》，不是本轮社媒数据直接证明。

## 下一轮搜索建议

- 当前是 mock 报告，下一轮应使用 live 模式验证真实 Reddit 结果，再根据证据调整关键词。
- **ceramic art**：只有 1 条高相关证据、1 条边缘证据，建议保留原词并加入：`handmade pottery process`、`ceramic artist studio`、`pottery critique`。
- **pottery**：只有 1 条高相关证据、0 条边缘证据，建议保留原词并加入：`handmade pottery process`、`ceramic artist studio`、`pottery critique`。
- **ceramic glaze**：只有 1 条高相关证据、1 条边缘证据，建议保留原词并加入：`ceramic glaze defects`、`cone 6 glaze`、`glaze test tiles`。
- **AI ceramic design**：只有 1 条高相关证据、0 条边缘证据，建议保留原词并加入：`AI pottery workflow`、`generative ceramic pattern`、`computational ceramics`。
- **3D printed ceramics**：只有 1 条高相关证据、0 条边缘证据，建议保留原词并加入：`ceramic 3D printing clay`、`clay paste extrusion`、`3D printed pottery`。
- **handmade pottery**：只有 1 条高相关证据、1 条边缘证据，建议保留原词并加入：`handmade pottery process`、`ceramic artist studio`、`pottery critique`。
- **ceramic business**：只有 1 条高相关证据、1 条边缘证据，建议保留原词并加入：`Etsy pottery pricing`、`pottery commission`、`ceramic studio marketing`。
- **pottery studio**：只有 1 条高相关证据、0 条边缘证据，建议保留原词并加入：`Etsy pottery pricing`、`pottery commission`、`ceramic studio marketing`。
- **ceramic texture**：只有 1 条高相关证据、0 条边缘证据，建议保留原词并加入：`ceramic surface texture`、`clay texture tools`、`handbuilt texture`。
- **kiln firing**：只有 1 条高相关证据、1 条边缘证据，建议保留原词并加入：`cone 6`、`bisque firing`、`electric kiln`。
- **过滤规则**：本轮跑偏样本包括 My cat sleeping in a mi..., This AI video of anime...；下一轮继续把 anime、gaming、地区词和非陶瓷消费品降权。
- **研究证据补充**：根据本地研究证据，下一轮可观察：`AI glaze prediction`、`ceramic glaze machine learning`、`glaze recipe dataset`、`ceramic material informatics`、`AI pottery workflow`、`generative ceramic design`、`ceramic prompt design`、`clay 3D printing`。这些是研究启发，不代表本轮社媒趋势。

## 高相关内容

| 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |
|---|---|---|---|---|---|---|
| ceramic art | r/ceramics | Finished a ceramic art sculpture with a new glaze in my studio | 412 upvotes, 57 comments | 来自推荐 subreddit r/ceramics；命中陶瓷词：ceramic, ceramics, glaze, kiln, porcelain；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/Ceramics/comments/mk0001/ceramic_art_sculpture/) |
| pottery | r/pottery | My first pottery wheel throwing session results | 286 upvotes, 41 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：clay, pottery, wheel throwing；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/Pottery/comments/mk0003/first_wheel_throwing/) |
| ceramic glaze | r/pottery | Cone 6 glaze recipe keeps getting pinholes on stoneware | 174 upvotes, 63 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：firing, glaze, pottery, stoneware；标题或 subreddit 直接相关；命中分类意图：cone, glaze, pinholes, recipe, test tile | [打开](https://www.reddit.com/r/Pottery/comments/mk0005/cone6_pinholes/) |
| AI ceramic design | r/ceramics | Using AI to design a surface pattern for my ceramic mugs | 198 upvotes, 74 comments | 来自推荐 subreddit r/ceramics；命中陶瓷词：ceramic, ceramics, clay；标题或 subreddit 直接相关；命中分类意图：ai, design, pattern；分类加权：stable diffusion | [打开](https://www.reddit.com/r/Ceramics/comments/mk0007/ai_surface_pattern/) |
| 3D printed ceramics | r/ceramic3dprinting | Clay paste extrusion settings for my delta printer | 89 upvotes, 27 comments | 来自推荐 subreddit r/ceramic3dprinting；命中陶瓷词：clay, porcelain；标题或 subreddit 直接相关；命中分类意图：printer, printing；分类加权：delta printer, gcode, paste extrusion | [打开](https://www.reddit.com/r/Ceramic3DPrinting/comments/mk0009/paste_extrusion_settings/) |
| handmade pottery | r/somethingimade | Handmade pottery mug set I made for my sister's wedding | 530 upvotes, 88 comments | 来自推荐 subreddit r/somethingimade；命中陶瓷词：clay, glaze, handmade, kiln, mug；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/somethingimade/comments/mk0010/wedding_mug_set/) |
| ceramic business | r/pottery | How do you price handmade ceramic mugs on Etsy? | 143 upvotes, 96 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：ceramic, firing, glaze, handmade, mug；标题或 subreddit 直接相关；命中分类意图：customer, etsy, pricing；分类加权：cost | [打开](https://www.reddit.com/r/Pottery/comments/mk0012/etsy_mug_pricing/) |
| pottery studio | r/pottery | Our community studio added a beginner wheel class | 211 upvotes, 45 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：firing, kiln, pottery, studio；标题或 subreddit 直接相关；命中分类意图：class, kiln, membership, studio；分类加权：beginner, booking, community studio | [打开](https://www.reddit.com/r/Pottery/comments/mk0014/community_studio_class/) |
| ceramic texture | r/ceramics | Carved texture experiments on a porcelain vase | 324 upvotes, 39 comments | 来自推荐 subreddit r/ceramics；命中陶瓷词：ceramics, clay, glaze, handmade, porcelain；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/Ceramics/comments/mk0015/carved_texture_vase/) |
| kiln firing | r/pottery | Bisque firing schedule for my new electric kiln | 167 upvotes, 58 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：firing, kiln, pottery, slab；标题或 subreddit 直接相关；命中分类意图：bisque, firing, kiln, temperature；分类加权：electric kiln, schedule | [打开](https://www.reddit.com/r/Pottery/comments/mk0016/bisque_schedule/) |

## 边缘相关内容

| 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |
|---|---|---|---|---|---|---|
| ceramic art | r/artfundamentals | Where do you find inspiration for sculptural forms? | 38 upvotes, 12 comments | 命中陶瓷词：ceramic | [打开](https://www.reddit.com/r/ArtFundamentals/comments/mk0002/sculptural_forms/) |
| ceramic glaze | r/crafts | What paint can I use to seal an unfired clay pot? | 52 upvotes, 19 comments | 来自推荐 subreddit r/crafts；命中陶瓷词：clay；标题或 subreddit 直接相关；陶瓷相关，但未命中当前关键词意图 | [打开](https://www.reddit.com/r/crafts/comments/mk0006/seal_clay_pot/) |
| handmade pottery | r/giftideas | Looking for a handmade gift idea for my mom | 21 upvotes, 16 comments | 命中陶瓷词：handmade；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/GiftIdeas/comments/mk0011/handmade_gift/) |
| ceramic business | r/smallbusiness | Starting a small handmade business from my kitchen | 67 upvotes, 33 comments | 命中陶瓷词：handmade；标题或 subreddit 直接相关；命中分类意图：business | [打开](https://www.reddit.com/r/smallbusiness/comments/mk0013/kitchen_business/) |
| kiln firing | r/bbq | Repurposing an old kiln shelf for a pizza oven | 76 upvotes, 24 comments | 命中陶瓷词：kiln；标题或 subreddit 直接相关；命中分类意图：kiln | [打开](https://www.reddit.com/r/BBQ/comments/mk0017/kiln_shelf_pizza/) |

## 跑偏样本

> 跑偏样本只用于过滤规则复盘，不计入趋势判断。

### 过滤复盘
- **My cat sleeping in a mixing bowl**：命中了跑偏信号（命中陶瓷词：bowl；标题或 subreddit 直接相关；跑偏词：cat, cats），主题不应进入陶瓷趋势判断。 下次可通过更具体关键词或排除词降低误伤。
- **This AI video of anime characters is unreal**：命中了跑偏信号（跑偏词：ai video, anime, ordinary ai video；命中分类意图：ai），主题不应进入陶瓷趋势判断。 下次可通过更具体关键词或排除词降低误伤。

| 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |
|---|---|---|---|---|---|---|
| pottery | r/cats | My cat sleeping in a mixing bowl | 951 upvotes, 103 comments | 命中陶瓷词：bowl；标题或 subreddit 直接相关；跑偏词：cat, cats | [打开](https://www.reddit.com/r/cats/comments/mk0004/cat_in_bowl/) |
| AI ceramic design | r/anime | This AI video of anime characters is unreal | 1420 upvotes, 312 comments | 跑偏词：ai video, anime, ordinary ai video；命中分类意图：ai | [打开](https://www.reddit.com/r/anime/comments/mk0008/ai_anime_video/) |

## 原始证据/链接

| 相关性 | 关键词 | Subreddit | 标题 | 互动 | 原因 | 链接 |
|---|---|---|---|---|---|---|
| 高相关 | ceramic art | r/ceramics | Finished a ceramic art sculpture with a new glaze in my studio | 412 upvotes, 57 comments | 来自推荐 subreddit r/ceramics；命中陶瓷词：ceramic, ceramics, glaze, kiln, porcelain；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/Ceramics/comments/mk0001/ceramic_art_sculpture/) |
| 边缘相关 | ceramic art | r/artfundamentals | Where do you find inspiration for sculptural forms? | 38 upvotes, 12 comments | 命中陶瓷词：ceramic | [打开](https://www.reddit.com/r/ArtFundamentals/comments/mk0002/sculptural_forms/) |
| 高相关 | pottery | r/pottery | My first pottery wheel throwing session results | 286 upvotes, 41 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：clay, pottery, wheel throwing；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/Pottery/comments/mk0003/first_wheel_throwing/) |
| 相关性较低 | pottery | r/cats | My cat sleeping in a mixing bowl | 951 upvotes, 103 comments | 命中陶瓷词：bowl；标题或 subreddit 直接相关；跑偏词：cat, cats | [打开](https://www.reddit.com/r/cats/comments/mk0004/cat_in_bowl/) |
| 高相关 | ceramic glaze | r/pottery | Cone 6 glaze recipe keeps getting pinholes on stoneware | 174 upvotes, 63 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：firing, glaze, pottery, stoneware；标题或 subreddit 直接相关；命中分类意图：cone, glaze, pinholes, recipe, test tile | [打开](https://www.reddit.com/r/Pottery/comments/mk0005/cone6_pinholes/) |
| 边缘相关 | ceramic glaze | r/crafts | What paint can I use to seal an unfired clay pot? | 52 upvotes, 19 comments | 来自推荐 subreddit r/crafts；命中陶瓷词：clay；标题或 subreddit 直接相关；陶瓷相关，但未命中当前关键词意图 | [打开](https://www.reddit.com/r/crafts/comments/mk0006/seal_clay_pot/) |
| 高相关 | AI ceramic design | r/ceramics | Using AI to design a surface pattern for my ceramic mugs | 198 upvotes, 74 comments | 来自推荐 subreddit r/ceramics；命中陶瓷词：ceramic, ceramics, clay；标题或 subreddit 直接相关；命中分类意图：ai, design, pattern；分类加权：stable diffusion | [打开](https://www.reddit.com/r/Ceramics/comments/mk0007/ai_surface_pattern/) |
| 相关性较低 | AI ceramic design | r/anime | This AI video of anime characters is unreal | 1420 upvotes, 312 comments | 跑偏词：ai video, anime, ordinary ai video；命中分类意图：ai | [打开](https://www.reddit.com/r/anime/comments/mk0008/ai_anime_video/) |
| 高相关 | 3D printed ceramics | r/ceramic3dprinting | Clay paste extrusion settings for my delta printer | 89 upvotes, 27 comments | 来自推荐 subreddit r/ceramic3dprinting；命中陶瓷词：clay, porcelain；标题或 subreddit 直接相关；命中分类意图：printer, printing；分类加权：delta printer, gcode, paste extrusion | [打开](https://www.reddit.com/r/Ceramic3DPrinting/comments/mk0009/paste_extrusion_settings/) |
| 高相关 | handmade pottery | r/somethingimade | Handmade pottery mug set I made for my sister's wedding | 530 upvotes, 88 comments | 来自推荐 subreddit r/somethingimade；命中陶瓷词：clay, glaze, handmade, kiln, mug；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/somethingimade/comments/mk0010/wedding_mug_set/) |
| 边缘相关 | handmade pottery | r/giftideas | Looking for a handmade gift idea for my mom | 21 upvotes, 16 comments | 命中陶瓷词：handmade；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/GiftIdeas/comments/mk0011/handmade_gift/) |
| 高相关 | ceramic business | r/pottery | How do you price handmade ceramic mugs on Etsy? | 143 upvotes, 96 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：ceramic, firing, glaze, handmade, mug；标题或 subreddit 直接相关；命中分类意图：customer, etsy, pricing；分类加权：cost | [打开](https://www.reddit.com/r/Pottery/comments/mk0012/etsy_mug_pricing/) |
| 边缘相关 | ceramic business | r/smallbusiness | Starting a small handmade business from my kitchen | 67 upvotes, 33 comments | 命中陶瓷词：handmade；标题或 subreddit 直接相关；命中分类意图：business | [打开](https://www.reddit.com/r/smallbusiness/comments/mk0013/kitchen_business/) |
| 高相关 | pottery studio | r/pottery | Our community studio added a beginner wheel class | 211 upvotes, 45 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：firing, kiln, pottery, studio；标题或 subreddit 直接相关；命中分类意图：class, kiln, membership, studio；分类加权：beginner, booking, community studio | [打开](https://www.reddit.com/r/Pottery/comments/mk0014/community_studio_class/) |
| 高相关 | ceramic texture | r/ceramics | Carved texture experiments on a porcelain vase | 324 upvotes, 39 comments | 来自推荐 subreddit r/ceramics；命中陶瓷词：ceramics, clay, glaze, handmade, porcelain；标题或 subreddit 直接相关 | [打开](https://www.reddit.com/r/Ceramics/comments/mk0015/carved_texture_vase/) |
| 高相关 | kiln firing | r/pottery | Bisque firing schedule for my new electric kiln | 167 upvotes, 58 comments | 来自推荐 subreddit r/pottery；命中陶瓷词：firing, kiln, pottery, slab；标题或 subreddit 直接相关；命中分类意图：bisque, firing, kiln, temperature；分类加权：electric kiln, schedule | [打开](https://www.reddit.com/r/Pottery/comments/mk0016/bisque_schedule/) |
| 边缘相关 | kiln firing | r/bbq | Repurposing an old kiln shelf for a pizza oven | 76 upvotes, 24 comments | 命中陶瓷词：kiln；标题或 subreddit 直接相关；命中分类意图：kiln | [打开](https://www.reddit.com/r/BBQ/comments/mk0017/kiln_shelf_pizza/) |

## 后续升级接口

- `--data-source auto` 当前会把 mock 映射到 `mock`，把 live 映射到 `reddit_last30days`。
- `--mode live --data-source scrapecreators_reddit` 可显式使用 ScrapeCreators Reddit API；默认 live 仍使用 `reddit_last30days`。
- YouTube、Pinterest、GitHub Actions 留到后续阶段。
- 数据源清单见 `config/data_sources.json`；预留数据源不会在没有实现时偷偷联网。
- 报告结构来自 `prompts/ceramic_report_prompt.md`，后续可替换为 LLM 中文综合。
- 自动化路线见 `docs/automation-roadmap.md`。

## 当前报告模板

```markdown
# 陶瓷趋势情报报告模板

请把来自 Reddit、YouTube、GitHub、Pinterest 等来源的原始证据，整理成面向中文陶瓷创作者、陶瓷工作室和内容运营者的 Markdown 报告。

判断证据时必须同时考虑两件事：

- 陶瓷相关性：是否真的和 ceramic、pottery、glaze、kiln、clay、studio、firing 等陶瓷语境有关
- 关键词意图：是否符合当前分类，例如 AI ceramic design 必须有 AI/生成式/数字设计/prompt/pattern 等信号，ceramic business 必须有经营/销售/定价/客户/订单/库存/营销等信号

只碰到 ceramic/pottery 但不符合该分类意图的内容，最多作为边缘相关，不要当成高相关趋势。

## 本轮结论摘要

- 放在报告顶部，用 5 到 8 条短句说明本轮真正值得注意什么
- 必须基于高相关证据；如果高相关证据不足，要明确写“本轮样本有限”
- 不要把跑偏样本当成趋势结论
- 语气要像给陶瓷创作者、工作室主理人和内容运营者看的简报
- mock 或 live 失败报告不能生成真实趋势判断，只能说明样本状态和下一步

## 本轮可信度

- 根据高相关内容数量、边缘相关数量、跑偏样本数量给出高 / 中 / 低
- 高相关 >= 8 条：可信度较高
- 高相关 4 到 7 条：可信度中等
- 高相关 < 4 条：可信度较低
- 如果 live 失败或没有证据，要明确写“本轮不适合做趋势判断”

## 热门内容

- 最近被讨论、观看、收藏或评论最多的内容是什么
- 每条内容对应的平台、互动信号和简短原因
- 必须区分高相关内容、边缘相关内容和跑偏样本
- 不要把低相关 Reddit 热帖当作陶瓷趋势结论
- 没有高质量证据时，写“证据不足”或“暂不纳入趋势判断”，不要强行总结

## 用户痛点

- 创作者、买家、学生、工作室经营者正在抱怨或反复提问的问题
- 尽量区分工艺痛点、内容痛点、商业痛点和工具痛点
- 只从高相关内容中提炼主要痛点；边缘内容只能作为补充观察

## 趋势判断

- 每条趋势判断尽量关联具体高相关证据，例如 subreddit、标题或用户讨论点
- 哪些趋势可能只是短期热度，哪些值得持续关注
- 哪些趋势可以转化为内容、产品或小工具
- 高相关证据可以进入趋势判断
- 边缘相关只能作为补充观察
- 跑偏样本只能用于过滤复盘
- 如果证据来自跑偏样本，必须明确说明它不能支撑陶瓷趋势判断
- 如果某个关键词没有高相关证据，不要生成确定性判断
- 如果证据不足，可以写“目前更像观察信号，不足以判断为趋势”
- 不要从 mock 数据或失败报告中生成确定趋势

## 研究证据

- 研究证据来自本地证据库，例如论文、数据集、系统研究或项目主页
- 研究证据可以支撑长期产品方向、下一轮搜索建议和专业背景
- 研究证据不等于本轮 Reddit 热度，也不能单独证明用户需求已经出现
- 必须标明证据限制，例如预印本、样本小、许可证待核实、数据下载方式待核实
- 如果研究证据和 Reddit 高相关证据指向同一方向，可以写成更强的观察信号
- 如果只有研究证据、没有用户痛点证据，要写成“研究启发”或“长期方向”，不要写成已验证趋势

## 高相关内容

- 来自陶瓷相关 subreddit，或标题/subreddit/正文明确包含 ceramic、pottery、glaze、kiln、clay、handmade、studio、firing 等词
- 同时符合当前关键词意图
- 可用于趋势判断、内容选题和工具灵感

## 边缘相关内容

- 与手作、艺术、创作经营、材料或视觉灵感有关，但陶瓷信号不够强
- 陶瓷相关但不符合当前分类意图的内容，也归入边缘相关
- 可以作为灵感线索，但不要单独得出趋势结论

## 跑偏样本

- 命中 pottery/ceramic 等词但主题明显偏到 anime、cosplay、cats、gaming、Naruto、FNAF、Makati、keyboards 等
- 只用于过滤规则复盘，不进入趋势判断
- 要说明为什么它们跑偏，以及下次如何减少类似误伤

## 内容选题

- 适合中文社媒、YouTube、小红书、博客或 newsletter 的选题
- 每个选题尽量说明目标受众和切入角度
- 分成“有 Reddit 高相关证据支撑的选题”和“暂无充分证据但值得后续观察的选题”
- 有证据支撑的选题必须来自高相关内容，并说明为什么值得做
- 观察方向可以来自长期方向或边缘内容，但必须标明“观察方向”
- 不要把没有证据的方向写成已经发生的趋势

## 小工具灵感

- 可以帮助陶瓷创作者或工作室节省时间的小工具
- 优先考虑轻量工具，例如记录表、Prompt 生成器、选题雷达、定价计算器、烧成排查清单
- 分成“本轮证据直接支持的小工具”和“长期产品方向”
- 本轮证据直接支持的小工具必须来自高相关内容中的真实痛点
- 长期产品方向可以来自陶瓷领域长期需求，但要说明不是本轮数据直接证明
- 来自研究证据的小工具灵感必须标注“研究证据启发”，不能写成社媒已验证需求

## 下一轮搜索建议

- 根据本轮结果自动建议下一轮关键词和搜索方向
- 如果 AI ceramic design 证据不足，可以建议 AI pottery workflow、generative ceramic pattern、computational ceramics、ceramic prompt design
- 如果 ceramic business 证据不足，可以建议 Etsy pottery pricing、pottery commission、ceramic studio marketing、handmade ceramics pricing
- 如果 kiln firing 证据不足，可以建议 cone 6、bisque firing、electric kiln、glaze defects、kiln schedule
- 建议必须结合当前关键词和证据情况，不要完全固定

## 原始证据/链接

- 保留原始标题、平台、链接和互动数据
- 保留相关性标签和简短原因
- 不要把未经验证的社媒内容写成确定事实
- 本地研究证据也要保留标题、链接和限制说明
```
