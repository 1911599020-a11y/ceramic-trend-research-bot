# AGENTS.md

面向在本仓库工作的 AI 编码代理（以及人类贡献者）的工作说明。本文件描述项目目标、
架构边界、命令、测试约定和不可破坏的冻结行为。修改代码前请先读完本文件。

## 1. 项目概览

`ceramic-trend-research-bot` 是一个陶瓷趋势情报工具：输入陶瓷相关关键词，聚合社媒证据，
生成面向中文陶瓷创作者 / 工作室 / 内容运营者的 Markdown 报告。

- `--mode mock`：读取仓库内 `data/mock_samples.json`，零配置、零联网，用于验证报告结构与版式。
- `--mode live`：当前只接入 Reddit（经由外部 `last30days-skill` 子进程），并按陶瓷相关性分层。
- 当前版本：**V0.5.0 — 数据源适配层（data-source adapter）**。详见 `docs/changes/0001-data-source-adapter.md`。

## 2. 架构

V0.5.0 把“证据从哪来”与“如何打分、如何渲染”彻底分开：

```text
sources/                      # 数据源适配层（“证据从哪来”）
  __init__.py                 # TrendSource Protocol：fetch(topic, *, recommended_subreddits) -> dict
  mock_source.py              # MockSource：读 data/mock_samples.json，离线
  last30days_source.py        # Last30DaysSource：shell out 到 last30days-skill（live）
ceramic_report.py             # 打分 + 渲染（“如何消化证据”），CLI 入口
config/ceramic_topics.json    # 关键词、推荐 subreddit、相关性规则（positive/exclude/topic_rules）
data/mock_samples.json        # mock 证据样例（last30days --emit=json 形状）
prompts/ceramic_report_prompt.md  # 中文报告结构模板
tests/                        # unittest 用例
docs/changes/                 # 变更记录（每个改动一份编号文档）
```

**单一契约**：每个 source 的 `fetch()` 都返回同一种 `last30days` 形状的 dict
（顶层 `items_by_source` → source 名 → item 列表）。打分和渲染层永远不知道证据是哪个后端产生的。
新增数据源 = 新增一个实现 `TrendSource` 的类，不应改动打分 / 渲染逻辑。

## 3. 环境与命令

无需安装第三方依赖（仅标准库）。在仓库根目录运行：

```bash
# 生成 mock 报告（零配置，推荐先跑这个）
python ceramic_report.py --mode mock

# 运行全部测试
python -m unittest discover tests

# Reddit live 最小测试（需要外部 last30days-skill 与可访问 Reddit 的网络）
python ceramic_report.py --mode live
# 或带冷却保护的脚本
bash scripts/run_live.sh

# 环境诊断（不打印真实 key、不抓取数据）
python scripts/check_environment.py
```

`last30days-skill` 脚本路径解析顺序：`--last30days-script` 参数 > `CERAMIC_LAST30DAYS_SCRIPT`
> `LAST30DAYS_SCRIPT`（遗留）> 代码内默认 Mac 路径。

## 4. 测试

- 测试框架：标准库 `unittest`，统一用 `python -m unittest discover tests` 运行。
- `tests/test_term_matching.py`：词边界 / 短语分隔符匹配。
- `tests/test_scoring.py`：打分契约（exclude 扣分、required 缺失压分、level 阈值）。
- `tests/test_sources.py`：MockSource 输出可被 `collect_evidence` 消化；Last30DaysSource 命令列表逐项一致（mock 掉 `subprocess`）。
- 改动 `data/mock_samples.json`、`config/ceramic_topics.json` 或打分 / 命令构造后，**必须**重新跑全套测试。
- live 相关测试一律 mock 掉 `subprocess` / 网络；测试不得发起真实联网。

## 5. 代码风格与约定

- Python 3.10+，`from __future__ import annotations`，使用内建泛型（`list[str]`、`dict[str, Any]`）。
- 数据结构优先用 `@dataclass(frozen=True)`（见 `Evidence`、`RelevanceConfig`）。
- 面向用户的报告文案、错误提示和注释用中文；标识符、CLI flag、JSON 字段名用英文。
- 纯函数优先，便于单测；新逻辑要可在不联网、不写盘的前提下测试。
- 不引入第三方运行时依赖，保持标准库可运行。

## 6. 冻结行为（不要破坏）

打分与渲染的输出在 V0.5.0 是**冻结行为**，必须与 V0.4.2 完全一致：

- `score_reddit_item` 的加减分规则、`min(score, 4)` 压分门控、`>=5 high / >=1 edge / else low` 阈值。
- `Last30DaysSource` 构造的子进程命令列表，逐项与旧 `run_last30days` 一致（含 `--mock` 插入位置、`--search` 取值、`--subreddits` 排序）。
- 报告章节结构与 `prompts/ceramic_report_prompt.md` 对齐。

如确需改动上述行为，必须同步更新对应测试，并新增一份 `docs/changes/NNNN-*.md` 说明原因。

## 7. 安全

- 不要提交 `.env`；真实 key 只放本地 `.env` / 系统环境变量 / GitHub Secrets。
- `mock` 模式不读真实 key、不联网，可覆盖 `reports/report.md`。
- `live` 失败（DNS / 403 / 429 / 网络）时不覆盖上一份成功报告，错误写入 `local_outputs/last_error.md`。
- 不修改 `last30days-skill` 原始代码；不安装 `yt-dlp`；不配置 API key（留到后续阶段）。

## 8. 提交与变更记录

- 提交信息：`type: 简短描述`（如 `test:`、`docs:`、`refactor:`），正文用中文说明动机。
- **不要自行 `git commit`**，除非用户明确要求。
- 每个有结构影响的改动新增一份 `docs/changes/NNNN-标题.md`（YAML front matter + 固定章节），编号递增。

## 9. 协作与交付偏好

- 每次完成任务后，用通俗易懂的中文告诉用户：这次做了什么、有什么用、接下来建议做什么。
- 每次最终回复末尾放一个简短“计划进程条”，让用户能快速看懂当前项目推进到哪一步。
- 每次完成后判断并明确告诉用户：这次改动是否建议保存到 GitHub；如果建议提交，说明原因；如果不建议提交，也说明原因。
- 每次对仓库文件、代码、文档、配置、数据流或报告生成逻辑做改动后，无论改动大小，最终交付前都必须启用两个独立审查者 / 子代理进行批判性 review；仅在未修改项目文件的任务中可以例外，例如纯聊天问答、状态说明、只读审查或只读分析。两个审查者应独立检查，不互相依赖；按一次任务的最终变更统一 review，不要对每个微小编辑重复触发审查以浪费额度。若审查发现问题并导致新的文件改动，交付前必须对修复后的最终 diff 再做一轮审查或明确说明为什么无需再审。若审查工具不可用，必须向用户说明原因，并执行两轮独立自审作为降级方案；必要时等待用户确认再交付。最终回复要说明两位审查者的结论、发现的问题、是否已修复，以及剩余风险。注意：两个独立审查者会明显增加模型调用、上下文和额度消耗，尤其是频繁小改动时。
