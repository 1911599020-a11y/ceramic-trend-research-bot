# Ceramic AI Evidence

用于保存“陶瓷专业 + AI + 数字制造”方向的一手研究证据、产品启发和后续检索词。

## 使用原则

- 优先保存论文、数据集、项目主页等一手来源
- 区分“研究已经证明”和“产品启发”
- 未确认代码、数据下载方式或许可证时，明确标记为待核实
- 不把早期论文或少量用户测试写成成熟市场结论

## V0.5.6 使用方式

当前阶段暂不申请 ScrapeCreators key，也不新增真实联网来源。这个证据库承担三件事：

1. 保存稳定证据，避免项目被 Reddit public JSON 403 卡住。
2. 为报告里的“小工具灵感”和“长期产品方向”提供专业背景。
3. 为后续 GitHub / 论文 / YouTube source adapter 提供关键词和样本。

写入报告时要区分：

- **研究证据**：论文、数据集、系统研究，可以说明某个技术方向值得关注。
- **用户痛点证据**：Reddit / YouTube / GitHub issue 等用户表达，才能支撑“真实需求正在出现”。
- **产品假设**：从研究和痛点推导出的工具方向，必须标注为假设，不能写成已验证市场结论。

## GlazyBench

**论文：** GlazyBench: A Benchmark for Ceramic Glaze Property Prediction and Image Generation

- arXiv 摘要：[arxiv.org/abs/2605.06641](https://arxiv.org/abs/2605.06641)
- PDF：[arxiv.org/pdf/2605.06641](https://arxiv.org/pdf/2605.06641)
- DOI：[10.48550/arXiv.2605.06641](https://doi.org/10.48550/arXiv.2605.06641)
- 提交日期：2026-05-07
- 证据类型：预印本、数据集与基准研究

### 研究内容

- 整理 23,148 个真实陶瓷釉料配方
- 研究釉面属性预测
- 研究基于配方或属性的釉面图像生成
- 比较传统机器学习、语言模型和多模态模型在陶瓷釉料任务上的表现

### 对项目的启发

- 釉色灵感与配方资料检索
- 釉料实验记录和历史结果关联
- 烧成条件、配方、表面效果的结构化知识库
- “研究证据 + Reddit 实际痛点”的交叉趋势模块

### 可转化为报告模块

- **趋势判断**：釉料预测和图像生成已经有专业研究支撑，但是否形成创作者侧趋势，需要社媒证据继续验证。
- **内容选题**：釉色测试片如何记录、釉料配方如何结构化、AI 能不能辅助判断釉面效果。
- **小工具灵感**：釉料实验记录器、釉色配方检索、烧成变量对照表。

### 待核实

- 官方代码仓库
- 完整数据集下载方式
- 数据集及代码许可证
- Glazy 社区数据的再使用边界
- 是否适合直接用于商业产品训练

## ClayScape

**论文：** ClayScape: A GenAI-Supported Workflow for Designing Chinese Style Ceramics with Clay 3D Printing

- arXiv 摘要：[arxiv.org/abs/2604.25657](https://arxiv.org/abs/2604.25657)
- PDF：[arxiv.org/pdf/2604.25657](https://arxiv.org/pdf/2604.25657)
- ACM DOI：[10.1145/3800645.3812941](https://doi.org/10.1145/3800645.3812941)
- 提交日期：2026-04-28
- 证据类型：设计系统研究、陶泥 3D 打印工作流

### 研究内容

- 使用生成式 AI 支持中式陶瓷设计
- 将设计流程连接到陶泥 3D 打印
- 降低传统 CAD/CAM 对陶瓷创作者的操作门槛
- 通过 4 位陶瓷创作者进行初步评估

### 对项目的启发

- 中式陶瓷器型和纹样参考检索
- AI 概念图到可制造陶泥模型的工作流检查
- 陶泥 3D 打印失败案例与参数记录
- 数字设计和手工创作之间的决策辅助工具

### 可转化为报告模块

- **趋势判断**：AI 陶瓷设计不应只看图片生成，要重点看它是否连接到器型、纹样、泥料、打印和烧成流程。
- **内容选题**：从 AI 概念图到陶泥 3D 打印，中间有哪些工艺检查点；中式陶瓷纹样如何避免无来源借用。
- **小工具灵感**：AI 陶瓷设计可制造性检查表、纹样参考检索器、陶泥 3D 打印参数记录器。

### 证据限制与待核实

- 用户评估样本较小，属于早期证据
- 官方代码、模型和完整实现是否公开
- 软件、模型及生成资产的许可证
- 传统纹样和文化元素使用中的来源标注与版权边界

## 后续检索词

### 釉料与材料

- `AI glaze prediction`
- `ceramic glaze machine learning`
- `glaze recipe dataset`
- `ceramic material informatics`
- `kiln firing prediction`
- `ceramic glaze image generation`

### 生成式设计

- `AI pottery workflow`
- `generative ceramic pattern`
- `computational ceramics`
- `ceramic prompt design`
- `Chinese ceramic generative design`

### 数字制造

- `clay 3D printing`
- `ceramic additive manufacturing`
- `3D printed pottery`
- `clay extrusion parameters`
- `ceramic 3D printing failure`

### GitHub / 开源检索

- `glaze prediction`
- `ceramic dataset`
- `ceramic 3d printing`
- `clay 3d printing`
- `material informatics ceramic`
- `generative pattern ceramics`

### YouTube / 内容检索

- `glaze testing`
- `kiln firing schedule`
- `pottery studio business`
- `ceramic 3D printing`
- `AI pottery workflow`

## 候选产品方向

这些是研究带来的产品假设，不代表本轮数据已经证明需求：

1. 釉色灵感与证据检索库
2. 烧成与釉料实验记录器
3. 陶瓷趋势雷达
4. 纹样、器型与文化参考检索器
5. AI 设计到陶泥 3D 打印的可制造性检查表

## 近期优先观察清单

### 高优先级

- GlazyBench 是否公开完整数据集、代码和许可证
- ClayScape 是否公开系统、代码、模型或交互原型
- GitHub 是否已有 glaze prediction / ceramic dataset 相关开源项目
- YouTube 是否存在大量 glaze testing、kiln firing、ceramic 3D printing 的实操内容

### 中优先级

- Reddit 恢复稳定后，观察 glaze prediction、AI pottery workflow、clay 3D printing 是否出现真实用户讨论
- 找到陶瓷工作室经营和 AI 工具之间的交叉痛点
- 检查 Pinterest / Instagram 是否更适合视觉趋势，但不要在未配置 API 前接入

### 暂缓

- 不把 GlazyBench 数据直接用于商业训练，直到许可证确认
- 不把 ClayScape 的中式陶瓷设计流程直接做成产品，直到文化来源、版权和实现边界更清楚
- 不把单篇论文结论写成市场趋势

## 下一步

- 核实两项研究的代码、数据和许可证
- 在 Reddit live 关键词中观察 glaze prediction、clay 3D printing 是否出现真实用户痛点
- 后续增加学术来源时，将论文证据与社媒证据分开标注
- 参考 `docs/stable-data-source-roadmap.md` 安排 GitHub、论文和 YouTube 的接入顺序
