# AGENTS.md

面向在本仓库工作的 AI 编码代理（以及人类贡献者）的工作说明。本文件描述项目目标、
架构边界、命令、测试约定和不可破坏的冻结行为。修改代码前请先读完本文件。

## 1. 项目概览

`ceramic-trend-research-bot` 是一个陶瓷趋势情报工具：输入陶瓷相关关键词，聚合社媒证据，
生成面向中文陶瓷创作者 / 工作室 / 内容运营者的 Markdown 报告。

- `--mode mock`：读取仓库内 `data/mock_samples.json`，零配置、零联网，用于验证报告结构与版式。
- `--mode live`：默认接入 Reddit（经由外部 `last30days-skill` 子进程），也可显式选择 ScrapeCreators Reddit API 或 ScrapeCreators YouTube Search API，并按陶瓷相关性分层。
- 当前架构基础：**V0.5.0 — 数据源适配层（data-source adapter）**。详见 `docs/changes/0001-data-source-adapter.md`。
  当前运行选择：**V0.9.5 — YouTube 混合信号解释一致性**，`auto` live 仍默认 `reddit_last30days`；YouTube 只能通过 `scrapecreators_youtube_search` 显式 opt-in。
  注意：V0.9.x 只把 YouTube Search 元数据接入正式 report pipeline，不接字幕、评论、视频画面或 DeepSeek 正式评分；正式报告生成版本仍保持 V0.6.6。
  V0.9.2 以后，频道名里的 `studio` 不得单独触发经营类趋势或“工作室定价”小工具；经营类判断必须命中更强的 pricing/customer/order/sell 等信号。
  V0.9.4 以后，handmade / making / process 类 YouTube 制作视频优先解释为制作过程拆解、工艺复盘或器型案例，不得自动推导成销售决策工具或强趋势。
  V0.9.5 以后，同一条证据如在标题、摘要或相关性说明里同时命中 `pricing/customer/order/sales` 等强经营信号与 `glaze/kiln/handmade` 等信号，报告标题、内容理由、趋势判断和小工具灵感必须优先按强经营信号解释，避免混合信号导致前后文不一致；仅 `topic=ceramic business` 不得单独触发经营解释。
  当前 LLM 状态：`scoring/llm_scorer.py`、`config/llm_scoring.json`、`prompts/llm_scoring_prompt.md` 定义评分契约；`scripts/probe_llm_scoring.sh` 默认 dry-run，不联网。
  DeepSeek tiny probe、评分对照报告和真实小样本对照报告真实运行必须用户明确同意、打开 `LLM_SCORING_ENABLED=on` 并加 `--confirm-live-api`，输出只写入 `local_outputs/llm_scoring_probe.*`、`local_outputs/llm_scoring_comparison.*` 或 `local_outputs/llm_scoring_real_sample_comparison.*`，不写正式 reports。
  真实小样本对照采用风险优先抽样，用于质检，不代表关键词整体分布；`--sample-count` 控制 DeepSeek 分析样本数，ScrapeCreators 请求数约等于本轮关键词数量。
  当前知识库状态：V0.9.6 起 `storage/knowledge_store.py` + `config/knowledge_store.json` 在报告成功写盘后，把本轮打分证据归档进本地 SQLite（默认 `data/ceramic_knowledge.db`，已 git 忽略，纯标准库、零联网）。知识库只在渲染之后运行，不改打分与报告输出；写入失败不得影响或覆盖正式报告；live 失败轮不入库。`xiaohongshu` 与 `radar` 为预留分区，当前不得有任何代码写入。开关为 `KNOWLEDGE_STORE_ENABLED`（默认 on，设 `off` 关闭）；测试中调用 `main()` 时必须显式关闭，避免污染真实数据库。只读查询用 `python scripts/query_knowledge.py`。详见 `docs/changes/0035-knowledge-store.md`。
  最新项目决策按 `docs/changes/` 中的编号变更记录继续递增。

## 2. 架构

V0.5.0 把“证据从哪来”与“如何打分、如何渲染”彻底分开：

```text
sources/                      # 数据源适配层（“证据从哪来”）
  __init__.py                 # TrendSource Protocol：fetch(topic, *, recommended_subreddits) -> dict
  mock_source.py              # MockSource：读 data/mock_samples.json，离线
  last30days_source.py        # Last30DaysSource：shell out 到 last30days-skill（live）
  scrapecreators_source.py    # ScrapeCreators readiness + opt-in Reddit API source
  youtube_source.py           # ScrapeCreators YouTube Search opt-in source
scoring/
  llm_scorer.py               # V0.6.7 design-only LLM scoring contract + mock scorer
storage/
  knowledge_store.py          # V0.9.6 本地知识库（SQLite）：报告写盘后归档每轮打分证据，失败不影响报告
ceramic_report.py             # 打分 + 渲染（“如何消化证据”），CLI 入口
config/ceramic_topics.json    # 关键词、推荐 subreddit、相关性规则（positive/exclude/topic_rules）
config/scrapecreators_quality_topics.json # 小批量关键词质量测试配置；V0.7.5 active topics 已用更具体 AI 陶瓷词替换宽泛 AI ceramic design
config/youtube_probe_topics.json # YouTube Search 正式 live 的默认单关键词安全配置
config/youtube_quality_topics.json # YouTube Search 多关键词小样本配置，默认 dry-run runner 使用
config/llm_scoring.json       # 智能评分设计配置，默认 disabled/design_only
config/data_sources.json      # 数据源清单：mock / reddit_last30days / scrapecreators_reddit / scrapecreators_youtube_search 可用，其他来源预留
data/mock_samples.json        # mock 证据样例（last30days --emit=json 形状）
prompts/ceramic_report_prompt.md  # 中文报告结构模板
prompts/llm_scoring_prompt.md # V0.6.8 tiny probe 预备 JSON prompt
tests/                        # unittest 用例
docs/changes/                 # 变更记录（每个改动一份编号文档）
scripts/probe_scrapecreators_reddit.py  # 独立 tiny probe，只写 local_outputs/
scripts/probe_scrapecreators_youtube.py # YouTube Search 独立 tiny probe，只写 local_outputs/
scripts/review_youtube_probe.py         # YouTube Search 字段质量和 DeepSeek 旁路审核，只写 local_outputs/
scripts/probe_scrapecreators_youtube_video.py # YouTube Video Details 独立 tiny probe，只写 local_outputs/
scripts/review_youtube_video_probe.py         # YouTube Video Details 字段质量和 DeepSeek 旁路审核，只写 local_outputs/
scripts/run_scrapecreators_live.sh      # ScrapeCreators 正式 live runner，默认单关键词，带额度保护
scripts/run_youtube_live.sh             # YouTube Search 正式 live runner，默认单关键词，带额度保护
scripts/run_youtube_quality_live.sh     # YouTube Search 多关键词小样本 runner，默认 dry-run
scripts/run_keyword_quality_check.sh    # 小批量关键词质量 runner，默认 dry-run，只写 local_outputs/
scripts/summarize_keyword_quality.py    # 从测试报告生成关键词质量摘要
scripts/probe_llm_scoring.py            # DeepSeek LLM scoring tiny probe，默认不联网
scripts/probe_llm_scoring.sh            # DeepSeek tiny probe runner
scripts/compare_llm_scoring.py          # 规则评分 + DeepSeek 评分旁路对照报告，默认不联网
scripts/compare_llm_scoring.sh          # DeepSeek 对照报告 runner
scripts/compare_real_llm_scoring.py     # 真实 ScrapeCreators Reddit 小样本质量雷达 + DeepSeek 局部质检 + 报告解析，默认不联网
scripts/compare_real_llm_scoring.sh     # DeepSeek 真实小样本质量 runner
scripts/summarize_keyword_convergence.py # 从 V0.7.3 JSON 生成关键词收敛计划，默认不联网
scripts/summarize_keyword_convergence.sh # 关键词收敛计划 runner
```

**单一契约**：每个 source 的 `fetch()` 都返回同一种 `last30days` 形状的 dict
（顶层 `items_by_source` → source 名 → item 列表）。打分和渲染层永远不知道证据是哪个后端产生的。
新增数据源 = 新增一个实现 `TrendSource` 的类，不应改动打分 / 渲染逻辑。

V0.6.0 以后，数据源选择先进入 `config/data_sources.json`，再接入 `TrendSource`。预留数据源
（如 `youtube_future`、`pinterest_future`）在实现前不能偷偷发起联网请求。
V0.6.4 以后，`sources/scrapecreators_source.py` 是显式可选 source；默认 `auto` live 不会调用它。
为避免误用付费 API，`CERAMIC_DATA_SOURCE=scrapecreators_reddit` 不会改变 CLI 默认值；
必须在命令中显式写 `--data-source scrapecreators_reddit` 才能调用 ScrapeCreators。
正式 ScrapeCreators live 优先使用 `bash scripts/run_scrapecreators_live.sh`。该脚本默认只跑
`config/scrapecreators_probe_topics.json`；只有显式加 `--confirm-full-api` 才跑完整
`config/ceramic_topics.json`。
`reddit_last30days` 子进程环境必须剥离 `SCRAPECREATORS_API_KEY` 和 `SCRAPE_CREATORS_API_KEY`。
`scripts/probe_scrapecreators_reddit.py` 是 V0.6.3 的独立 tiny probe，只能在用户明确加
`--confirm-live-api` 时发起一次极小 ScrapeCreators API 请求。
`scripts/probe_scrapecreators_youtube.py` 是 V0.8.0 的独立 YouTube tiny probe，只能在用户明确加
`--confirm-live-api` 时发起一次 ScrapeCreators YouTube Search 请求。它不得追分页，不得请求 video details、
transcript 或 comments，不得保存原始响应、description 全文或 continuation token 值，不得更新
`reports/report.md`、`reports/latest.md` 或 `reports/archive/`，输出只能写入 `local_outputs/youtube_probe.*`。
`sources/youtube_source.py` 是 V0.9.0 的 ScrapeCreators YouTube Search 正式 adapter，只能通过
`--data-source scrapecreators_youtube_search` 或 `bash scripts/run_youtube_live.sh` 显式选择；`auto` live
不得选择 YouTube。该 adapter 只使用 Search 元数据，不得拉 transcript、comments、keyframes 或完整视频画面。
每条 YouTube item 必须显式写入 `ceramic_relevance_score` 和 `ceramic_relevance_level`，不能因缺字段默认成为可用证据。
`bash scripts/run_youtube_live.sh` 默认只跑 `config/youtube_probe_topics.json`；完整关键词必须显式加
`--confirm-full-api`。YouTube live 失败、空结果或全低相关结果不得覆盖 `reports/report.md`、`reports/latest.md`
或 `reports/archive/`，错误写入 `local_outputs/youtube_live_error.md`，状态写入 `local_outputs/youtube_run_state.json`。
`bash scripts/run_youtube_quality_live.sh` 默认 dry-run，只打印 3 个关键词小样本命令；真实运行必须显式加
`--confirm-live-api`。它使用 `config/youtube_quality_topics.json`，状态写入
`local_outputs/youtube_quality_run_state.json`，错误写入 `local_outputs/youtube_quality_error.md`。
`youtube_future` 继续保持 planned，留给未来 transcript / comments / video understanding，不得被当前正式报告调用。
`scripts/review_youtube_probe.py` 是 V0.8.2/V0.8.3 的独立旁路审核脚本，默认只读
`local_outputs/youtube_probe.json` 并输出字段质量报告；真实 DeepSeek 审核必须打开
`LLM_SCORING_ENABLED=on` 并加 `--confirm-live-api`。它不得读取 YouTube 原始响应，不得请求 video details、
transcript 或 comments，不得更新正式 reports。
`scripts/probe_scrapecreators_youtube_video.py` 是 V0.8.4 的独立 YouTube Video Details tiny probe，
默认只选择候选 URL，不联网；真实请求必须加 `--confirm-live-api`。它只请求 1 条视频详情，输出只能写
`local_outputs/youtube_video_probe.*`，不得保存原始响应、完整 description、字幕链接、watch-next 列表、
transcript 或 comments。
`scripts/review_youtube_video_probe.py` 是 V0.8.5/V0.8.6 的独立字段整理和 DeepSeek 旁路审核脚本，
默认不联网；真实 DeepSeek 审核必须打开 `LLM_SCORING_ENABLED=on` 并加 `--confirm-live-api`。
它不得更新正式 reports，也不得启用 `youtube_future`。
进入真实 key-backed live 前，必须先阅读并遵守 `docs/live-readiness-checklist.md`。
维护 ScrapeCreators tiny probe 前，必须先阅读 `docs/plans/2026-06-25-scrapecreators-tiny-probe.md`；
不得猜测 API endpoint 或 response shape。tiny probe 不得更新 `reports/report.md`、`reports/latest.md`
或 `reports/archive/`，输出只能写入 `local_outputs/`。
正式 ScrapeCreators live 只能在用户明确同意消耗 API 额度时运行：
`bash scripts/run_scrapecreators_live.sh`。绕过脚本直接跑完整 `config/ceramic_topics.json`
时，必须显式加 `--confirm-full-api`。
关键词质量测试默认不联网：`bash scripts/run_keyword_quality_check.sh` 只打印命令；真实测试必须显式加
`--confirm-live-api`，输出只写入 `local_outputs/keyword_quality_*`，不得污染正式 reports。
LLM 智能评分不接入正式报告：`config/llm_scoring.json` 必须默认 `enabled=false`，`.env.example`
必须默认 `LLM_SCORING_ENABLED=off`；
`scripts/probe_llm_scoring.sh` 默认不联网，真实 DeepSeek tiny probe 必须用户明确同意、打开
`LLM_SCORING_ENABLED=on` 并加
`--confirm-live-api`，输出只能写入 `local_outputs/llm_scoring_probe.*` 或
`local_outputs/llm_scoring_comparison.*` 或 `local_outputs/llm_scoring_real_sample_comparison.*`，不得把 LLM 评分写入
`reports/report.md`、`reports/latest.md` 或 `reports/archive/`。

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

# ScrapeCreators tiny probe 默认保护检查（不联网）
bash scripts/probe_scrapecreators_reddit.sh

# ScrapeCreators tiny probe 真实小测试（必须用户明确同意后才运行）
bash scripts/probe_scrapecreators_reddit.sh --confirm-live-api --topic "ceramic glaze" --limit 1

# ScrapeCreators YouTube tiny probe 默认保护检查（不联网）
bash scripts/probe_scrapecreators_youtube.sh

# ScrapeCreators YouTube tiny probe 真实小测试（必须用户明确同意后才运行）
bash scripts/probe_scrapecreators_youtube.sh --confirm-live-api --query "ceramic glaze"

# YouTube probe 字段整理（默认不联网）
bash scripts/review_youtube_probe.sh

# YouTube probe DeepSeek 旁路审核（必须用户明确同意后才运行）
LLM_SCORING_ENABLED=on bash scripts/review_youtube_probe.sh --confirm-live-api --sample-count 3

# YouTube video details tiny probe 默认保护检查（不联网）
bash scripts/probe_scrapecreators_youtube_video.sh

# YouTube video details tiny probe 真实小测试（必须用户明确同意后才运行）
bash scripts/probe_scrapecreators_youtube_video.sh --confirm-live-api

# YouTube video details 字段整理（默认不联网）
bash scripts/review_youtube_video_probe.sh

# YouTube video details DeepSeek 旁路审核（必须用户明确同意后才运行）
LLM_SCORING_ENABLED=on bash scripts/review_youtube_video_probe.sh --confirm-live-api

# ScrapeCreators 正式 live（默认单关键词，显式选择，可能消耗 API 额度）
bash scripts/run_scrapecreators_live.sh

# ScrapeCreators YouTube Search 正式 live（默认单关键词，显式选择，可能消耗 API 额度）
bash scripts/run_youtube_live.sh

# ScrapeCreators YouTube Search 正式 live dry-run（不联网、不消耗 API）
bash scripts/run_youtube_live.sh --dry-run

# ScrapeCreators YouTube Search 多关键词小样本 dry-run（默认不联网、不消耗 API）
bash scripts/run_youtube_quality_live.sh

# ScrapeCreators YouTube Search 多关键词小样本真实运行（必须用户明确同意后才运行）
bash scripts/run_youtube_quality_live.sh --confirm-live-api

# 小批量关键词质量测试（默认 dry-run，不联网、不消耗 API）
bash scripts/run_keyword_quality_check.sh

# DeepSeek LLM scoring tiny probe（默认 dry-run，不联网、不消耗 API）
bash scripts/probe_llm_scoring.sh

# DeepSeek 规则评分对照报告（默认 dry-run，不联网、不消耗 API）
bash scripts/compare_llm_scoring.sh

# DeepSeek 真实 Reddit/ScrapeCreators 小样本质量雷达 / 局部质检 / 报告解析（默认 dry-run，不联网、不消耗 API）
bash scripts/compare_real_llm_scoring.sh

# 关键词收敛计划（默认不联网、不消耗 API，只读 local_outputs/llm_scoring_real_sample_comparison.json）
bash scripts/summarize_keyword_convergence.sh
```

`last30days-skill` 脚本路径解析顺序：`--last30days-script` 参数 > `CERAMIC_LAST30DAYS_SCRIPT`
> `LAST30DAYS_SCRIPT`（遗留）> 代码内默认 Mac 路径。

## 4. 测试

- 测试框架：标准库 `unittest`，统一用 `python -m unittest discover tests` 运行。
- `tests/test_term_matching.py`：词边界 / 短语分隔符匹配。
- `tests/test_scoring.py`：打分契约（exclude 扣分、required 缺失压分、level 阈值）。
- `tests/test_sources.py`：MockSource 输出可被 `collect_evidence` 消化；Last30DaysSource 命令列表逐项一致（mock 掉 `subprocess`）。
- `tests/test_scrapecreators_probe.py`：tiny probe 的默认不联网、缺 key、limit、HTTP 错误分类和脱敏摘要。
- `tests/test_scrapecreators_youtube_probe.py`：YouTube tiny probe 的默认不联网、缺 key、输出保护、单 Search 请求、HTTP 错误分类和脱敏摘要。
- `tests/test_youtube_probe_review.py`：YouTube probe 字段整理、DeepSeek 旁路审核的开关保护、输出保护和错误分类。
- `tests/test_youtube_video_probe.py`：YouTube Video Details tiny probe 的默认不联网、缺 key、输出保护、单请求、摘要脱敏和错误分类。
- `tests/test_youtube_video_review.py`：YouTube Video Details 字段整理、DeepSeek 旁路审核的开关保护、输出保护和错误分类。
- `tests/test_youtube_source.py`：YouTube Search adapter 的缺 key 保护、响应转换、HTTP / DNS / timeout / parse 错误分类和脱敏。
- `tests/test_youtube_live_protection.py`：YouTube formal live 的 API 错误、空结果、全低相关不覆盖正式报告，以及高相关样本成功写报告。
- `tests/test_report_labels.py`：YouTube 报告显示频道来源，不显示成 `r/频道名` 或 Reddit 热点，并避免把频道名 `studio` 误判为经营证据。
- `tests/test_scrapecreators_source.py`：ScrapeCreators readiness、`.env` 读取、API 响应转换和 key 脱敏。
- `tests/test_llm_scoring.py`：V0.6.7 智能评分接口、JSON schema、mock scorer 和规则/LLM 合并契约。
- `tests/test_llm_scoring_probe.py`：DeepSeek tiny probe 的默认不联网、缺 key、输出路径保护、HTTP 错误分类和脱敏摘要。
- `tests/test_llm_scoring_comparison.py`：规则评分 + DeepSeek 评分对照报告的默认不联网、开关保护、输出保护和对照统计。
- `tests/test_llm_scoring_real_sample_comparison.py`：真实小样本 DeepSeek 对照报告的默认不联网、key 保护、输出保护、样本质量雷达、局部质检和报告解析。
- `tests/test_keyword_convergence.py`：关键词收敛计划的缺输入处理、输出保护和成功摘要。
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
- ScrapeCreators tiny probe 默认不联网；真实请求必须显式加 `--confirm-live-api`，输出只能写入 `local_outputs/`，不得覆盖正式报告。
- YouTube tiny probe 默认不联网；真实请求必须显式加 `--confirm-live-api`，输出只能写入 `local_outputs/youtube_probe.*`，不得覆盖正式报告，不得追分页，不得拉视频详情、字幕或评论。
- ScrapeCreators 正式 source 不是默认源；优先用 `bash scripts/run_scrapecreators_live.sh` 显式调用，成功时会更新正式报告。该脚本默认单关键词，`--confirm-full-api` 才跑完整关键词。
- YouTube Search 正式 source 不是默认源；优先用 `bash scripts/run_youtube_live.sh` 显式调用。该脚本默认单关键词，`--confirm-full-api` 才跑完整关键词；API 错误、空结果或全低相关不得覆盖正式报告。
- YouTube 多关键词小样本 runner 默认不联网：`bash scripts/run_youtube_quality_live.sh` 只打印命令；真实运行必须用户明确同意并加 `--confirm-live-api`。
- 小批量关键词质量测试默认 dry-run；真实运行必须显式加 `--confirm-live-api`，输出只写入 `local_outputs/keyword_quality_*`。
- DeepSeek LLM scoring probe、scoring comparison 和 real sample comparison 默认 dry-run；真实运行必须显式打开 `LLM_SCORING_ENABLED=on` 并加 `--confirm-live-api`，输出只写入 `local_outputs/llm_scoring_probe.*`、`local_outputs/llm_scoring_comparison.*` 或 `local_outputs/llm_scoring_real_sample_comparison.*`。
- 关键词收敛计划默认不联网，只读 `local_outputs/llm_scoring_real_sample_comparison.json`，输出只写入 `local_outputs/keyword_convergence_plan.*`，不得自动修改正式报告或 active keyword config。
- 不修改 `last30days-skill` 原始代码；不安装 `yt-dlp`；不要把真实 API key 写进代码、文档或提交内容。

## 8. 主线结束后研究产品

GlazyBench、ClayScape、AI glaze prediction、陶瓷 3D 打印等研究证据目前只作为趋势报告的补充背景，
不改变本项目主线。当前主线仍是：社媒数据源稳定化、Reddit / YouTube / Pinterest 等来源接入、
中文趋势报告生成、归档和自动运行。

主线完成后，可以把研究证据延伸成一个单独产品方向：**陶瓷 AI 研究助手 / Ceramic AI Research Product**。
这个延伸产品可以继续探索自动搜索论文、自动读取 PDF、自动总结、自动判断可信度、自动写入报告等能力。
但在主线未完成前，不启动自动论文研究系统，不让论文资料库替代社媒趋势情报工具。

为后续保留的接口：

- 人读资料入口：`research/ceramic-ai-evidence.md`
- 程序读取入口：`data/research_evidence.json`
- 报告入口：`ceramic_report.py --research-evidence`
- 关闭入口：`ceramic_report.py --no-research-evidence`

研究证据进入报告时必须保持分层：

- 它可以启发长期产品方向和下一轮关键词。
- 它不能计入 Reddit / YouTube 等社媒热度。
- 它不能单独证明市场需求已经成立。
- 许可证、代码、数据下载方式未核实时，要明确标记为待核实。

### 8.1 同一前端陶瓷情报系统

用户的长期目标不是单一脚本，而是一个“同一前端使用”的陶瓷情报系统。当前
`ceramic-trend-research-bot` 是其中的板块二：偏中国外社媒、Reddit、YouTube、Pinterest、
GitHub 等自动收集与中文/多语言趋势报告。

长期系统构想：

- 板块一：用户自己的机器人，负责中国外信息自动收集。
- 板块二：当前项目 `ceramic-trend-research-bot`，继续作为社媒趋势情报与报告生成主线。
- 板块三：MediaCrawler 方向，偏中国国内平台采集。用户倾向个人自用阶段直接参考/复用其模式，
  放在同一个前端壳子内使用；若未来对外开放，必须重新评估许可证、合规、平台规则与替代实现。
- 板块四：陶瓷机会雷达，关注未来 30/60/90/120 天内的陶瓷机会，例如竞赛、双年展、节会、
  艺博会、公开征集、展览申请、驻留或投稿节点。
- 共同数据库：多板块数据最终进入同一数据库，但必须按来源、地域、用途和风险分区存储，避免把
  社媒热度、国内平台内容、机会日历和研究证据混成一种证据。
- 数据分类总结工具：后续可以接入大模型 API 做主管式筛选、分类、审核、去噪、可信度判断和多语言输出。
  这条路线可行，但应先保留人工复核和证据分层，不要让模型直接改写事实或跳过来源记录。
- 输出语言：最终输出不只限中文，还需要支持英文等其他语言；报告生成层应预留 `language` / `locale`
  配置，而不是把中文写死成唯一输出形态。

当前优先级仍是先把主线做成可用：稳定社媒数据源、报告质量、归档和自动运行。MediaCrawler、
陶瓷机会雷达、共同数据库和多语言输出属于后续产品化方向，不应在未规划前打乱 V0.9 YouTube
Search 最小 adapter 主线。

## 9. 提交与变更记录

- 提交信息：`type: 简短描述`（如 `test:`、`docs:`、`refactor:`），正文用中文说明动机。
- **不要自行 `git commit`**，除非用户明确要求。
- 每个有结构影响的改动新增一份 `docs/changes/NNNN-标题.md`（YAML front matter + 固定章节），编号递增。

## 10. 协作与交付偏好

- 每次完成任务后，用通俗易懂的中文告诉用户：这次做了什么、有什么用、接下来建议做什么。
- 每次最终回复末尾放一个简短“计划进程条”，让用户能快速看懂当前项目推进到哪一步。
- 每次完成后判断并明确告诉用户：这次改动是否建议保存到 GitHub；如果建议提交，说明原因；如果不建议提交，也说明原因。
- 在开始较大任务、新功能、API 接入、数据源接入、报告生成逻辑、架构调整、安全/额度相关任务前，先快速检查是否有合适的 skills、tools、plugins、connectors、联网搜索或审查者可以辅助。不要为纯聊天和小状态同步触发复杂流程。插件或新 skill 的安装/启用必须先告知用户用途、风险和成本，并获得确认。
- 为节省额度，审查采用分级规则，而不是所有改动都强制两个子代理。纯聊天问答、状态说明、只读审查或只读分析没有修改项目文件时，不启用审查者。纯文档小修、协作规则小修、README 小改等低风险变更，至少执行自审、`git diff --check` 或等价检查，并在最终回复说明未启用子代理的原因。普通代码、配置、脚本、测试改动，至少启用 1 个独立审查者 / 子代理，或在工具不可用时执行两轮独立自审。涉及架构、数据流、报告生成逻辑、live 运行保护、发布保存、依赖、安全、API key、自动化或大版本变更时，最终交付前必须启用 2 个独立审查者 / 子代理进行批判性 review。若用户明确规定审查者数量或审查者作用，并且不违反安全与工具边界，则优先按用户意向执行；如果用户指定的审查强度低于当前风险所需，先解释风险并请求确认。审查按一次任务的最终变更统一执行，不要对每个微小编辑重复触发。若审查发现问题并导致新的文件改动，交付前必须对修复后的最终 diff 再审，或明确说明为什么无需再审。最终回复要说明审查方式、发现的问题、是否已修复、剩余风险，以及本次审查对额度的影响。
