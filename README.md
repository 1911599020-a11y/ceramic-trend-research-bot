# ceramic-trend-research-bot

陶瓷趋势情报总结工具。目标是输入陶瓷相关关键词，聚合 Reddit、YouTube、GitHub、Pinterest 等来源，生成中文 Markdown 趋势报告。

## Current Status

V0.9.3 是 **YouTube Search 小样本质量验证准备版本**，建立在 V0.9.0 YouTube Search 最小正式 adapter 之上：

- 注意：V0.7.5 仍是独立旁路分析版本，不提升正式报告生成版本；`ceramic_report.py` 的 `REPORT_VERSION` 仍保持 `V0.6.6`，因为正式报告流程没有接入 LLM scoring。
- 注意：V0.8.0 也是独立旁路探针版本，不提升正式报告生成版本；正式报告仍只使用规则评分和当前已启用数据源。
- V0.9.2 收紧报告推理：频道名里的 `studio` 不再单独触发经营类趋势或“工作室定价”小工具。
- V0.9.3 新增 `config/youtube_quality_topics.json`，用 `ceramic glaze`、`kiln firing`、`handmade pottery` 做 YouTube 多关键词小样本验证。
- 新增 `scripts/run_youtube_quality_live.sh`，默认 dry-run，不联网；真实运行必须显式加 `--confirm-live-api`。
- 新增 `sources/youtube_source.py`，把 ScrapeCreators YouTube Search 结果转换成统一 `last30days` 形状，进入正式 report pipeline。
- 新增显式数据源 `scrapecreators_youtube_search`；`--data-source auto` 仍然保持 Reddit，不会自动切到 YouTube。
- 新增 `scripts/run_youtube_live.sh`，默认只跑 `config/youtube_probe_topics.json` 的单关键词安全配置，失败写入 `local_outputs/youtube_live_error.md`。
- YouTube live 成功且拿到高相关/边缘相关证据时，才会更新 `reports/report.md`、`reports/latest.md` 和 `reports/archive/`。
- YouTube API 错误、空结果或全低相关结果不会覆盖上一份成功报告。
- YouTube item 会显式写入相关性分数和分层，不能因为缺少评分字段而默认算作可用证据。
- 报告文案已支持平台标签：YouTube 证据显示为频道，不会显示成 `r/频道名`。
- 新增 `scripts/probe_scrapecreators_youtube.py` / `.sh`，用于 ScrapeCreators YouTube Search tiny probe。
- YouTube tiny probe 默认 dry-run，不联网；真实请求必须显式加 `--confirm-live-api`。
- YouTube tiny probe 每次真实运行只做 1 次 Search 请求，不追分页，不拉 video details、transcript 或 comments。
- YouTube tiny probe 只保存最多 3 条摘要到 `local_outputs/youtube_probe.*`，不保存原始响应，不更新正式 reports。
- 新增 `scripts/review_youtube_probe.py` / `.sh`，读取本地 YouTube probe 摘要，生成字段质量和 DeepSeek 旁路审核报告。
- YouTube review 默认不联网；只有打开 `LLM_SCORING_ENABLED=on` 并加 `--confirm-live-api` 时才调用 DeepSeek。
- 真实 V0.8.3 小样本结果：`ceramic glaze` Search 返回 19 条 videos / 25 条 shorts，摘要 3 条 videos，DeepSeek 判断 3 条均可作为 YouTube 趋势候选。
- 新增 `scripts/probe_scrapecreators_youtube_video.py` / `.sh`，用于对 1 条高相关 YouTube 视频做 video details tiny probe。
- 新增 `scripts/review_youtube_video_probe.py` / `.sh`，用于整理 video details 字段，并可选让 DeepSeek 做详情层旁路审核。
- V0.8.4-V0.8.6 默认不联网、不拉字幕、不拉评论、不更新正式 reports；真实 video details 请求和 DeepSeek 详情层旁路审核已完成一次小样本验证。
- V0.8.7-lite 记录了 YouTube 转正判断：当时状态是 `wait`；V0.9.0 已实现最小 YouTube Search adapter，但仍然 opt-in。
- `youtube_future` 仍保持 planned，专门留给未来 transcript / comments / video understanding；DeepSeek 只参与旁路审核，不写入正式报告。
- 新增 `sources/` 适配层，定义统一的 `TrendSource` 契约：`fetch(topic, *, recommended_subreddits)`，输出统一的 `last30days` 形状报告 dict
- 新增 `scoring/llm_scorer.py`，为后续大模型辅助打分定义结构化输入、输出、mock scorer 和规则/LLM 合并结果
- 新增 `config/llm_scoring.json`，默认 `enabled=false`、`provider=deepseek`、`mode=design_only`，并用 `LLM_SCORING_ENABLED=off/on` 预留未来界面勾选开关
- 新增 `prompts/llm_scoring_prompt.md`，要求模型只返回 JSON，不直接生成最终报告
- 新增 `scripts/probe_llm_scoring.py` / `.sh`，默认 dry-run，不联网；真实 DeepSeek tiny test 必须同时打开 `LLM_SCORING_ENABLED=on` 并显式加 `--confirm-live-api`
- V0.6.8 tiny probe 只写 `local_outputs/llm_scoring_probe.md` 等本地文件，**不更新正式 reports**
- 新增 `scripts/compare_llm_scoring.py` / `.sh`，生成规则评分与 DeepSeek 评分的旁路对照报告，输出只写 `local_outputs/llm_scoring_comparison.*`
- `scripts/compare_real_llm_scoring.py` / `.sh` 已升级为真实样本质量雷达 + DeepSeek 局部质检 + 报告解析，输出只写 `local_outputs/llm_scoring_real_sample_comparison.*`
- 新增 `scripts/summarize_keyword_convergence.py` / `.sh`，读取 V0.7.3 真实小样本对照 JSON，生成下一轮关键词保留、收窄、降噪计划，输出只写 `local_outputs/keyword_convergence_plan.*`
- V0.7.5 已将小批量 active topics 收敛为 `kiln firing`、`ceramic business` 和 4 个更具体的 AI 陶瓷词，替换宽泛的 `AI ceramic design`
- `mock` 模式改由 `MockSource` 读取仓库内 `data/mock_samples.json`，**零配置、零联网、零外部依赖**，在 Windows / CI 上也能稳定出报告
- `live` 模式由 `Last30DaysSource` 承接，子进程命令构造与 V0.4.2 逐项一致，行为不变
- 新增 `config/data_sources.json`，集中记录当前可用数据源和未来预留数据源
- 新增 `--data-source auto`：mock 自动选择 `mock`，live 自动选择 `reddit_last30days`
- `scrapecreators_reddit` 已成为显式可选数据源；默认 live 仍然使用 `reddit_last30days`
- 预留 `youtube_future`、`pinterest_future`，本版本不会调用未实现数据源
- 报告、`run_state.json` 和 live 失败提示会记录本次使用的数据源
- 新增 ScrapeCreators readiness 模块和脚本，只检查 key 是否存在、清单是否就绪，不验证额度、不抓取数据、不打印 key
- 新增 `docs/live-readiness-checklist.md`，说明申请 key 前后、第一次真实 API live 前后该检查什么
- 打分（`score_reddit_item`）和渲染是**冻结行为**，输出与 V0.4.2 完全一致
- 新增 `tests/` 单元测试（`unittest`），覆盖词匹配、打分契约和数据源适配层
- 新增 `AGENTS.md` / `CLAUDE.md` 工作说明，以及 `docs/changes/` 变更记录
- 架构说明见 [docs/changes/0001-data-source-adapter.md](docs/changes/0001-data-source-adapter.md) 与 [AGENTS.md](AGENTS.md)
- 保留 V0.4.4 的 `MODEL_PROVIDER=rules`、日常 workflow 和陶瓷 AI 证据库
- 主流程统一通过 `source.fetch(...)` 获取数据，不重复调用旧 mock/live 函数

继承自 V0.4.2 的 **报告归档 + 多期对比基础版本** 行为：

- `mock` 模式仍然可用，用于稳定生成示例报告
- `live` 默认仍使用 Reddit；YouTube Search 已可显式 opt-in，Pinterest / GitHub Actions 仍未接入
- Reddit 结果会按陶瓷相关 subreddit、陶瓷关键词、分类意图和跑偏词做轻量重排
- AI ceramic design、ceramic business、kiln firing 等分类有独立 required / boost / exclude 规则
- 跑偏词使用完整单词/短语匹配，降低 `cat` 这类词的误伤
- 报告会区分高相关内容、边缘相关内容和跑偏样本
- 热门内容不再把低相关结果显示成趋势，也不再输出生硬的“暂无证据（0 分）”
- 趋势判断更严格依赖高相关证据；证据不足的方向会明确标注为暂不判断
- 内容选题和小工具灵感会区分“高相关证据支撑”和“长期建议方向”
- 报告顶部新增“本轮结论摘要”，用 5 到 8 条短句说明本轮真正值得注意什么
- 新增“本轮可信度”，按高相关、边缘相关和跑偏样本数量给出高 / 中 / 低
- 新增“下一轮搜索建议”，根据证据不足的关键词自动给出更具体搜索词
- 趋势判断、内容选题和小工具灵感更严格依赖高相关证据
- 跑偏样本会说明为什么跑偏，以及下次如何减少类似误伤
- 新增本地运行脚本，避免重复复制长 Python 命令
- live 模式新增冷却提醒和本地运行状态记录，减少短时间重复请求导致的 Reddit 429
- live 成功并拿到可用 Reddit 证据时，才会更新 `reports/report.md`
- live 因 DNS / 403 / 429 / 网络问题失败时，不覆盖上一份成功报告
- live 失败详情会写入 `local_outputs/last_error.md`，运行状态会写入 `local_outputs/run_state.json`
- live 失败时会按 403 / 429 / DNS / timeout 给出更清楚的本地排障提示
- live 成功时会同步更新 `reports/report.md`、`reports/latest.md`，并归档到 `reports/archive/`
- mock 只用于结构验证，不会写入 `reports/latest.md`，也不会进入 `reports/archive/`
- 新增最近两期 archive 对比脚本，输出 `reports/trend_diff.md`
- 新增 `docs/workflow.md`，统一说明日常 mock / live / compare 操作
- 新增 `MODEL_PROVIDER=rules` 预留接口；当前不调用外部大模型
- 新增 `research/ceramic-ai-evidence.md`，收录陶瓷 AI 一手研究证据
- V0.5.4 新增 Reddit 数据源替代路径评估，说明 public JSON、ScrapeCreators API 和其他来源的取舍
- V0.5.5 新增 ScrapeCreators readiness check：只显示 `configured` / `missing`，不打印真实 key
- V0.5.6 新增稳定数据源路线图：ScrapeCreators 晚点再申请时，优先推进论文、GitHub、YouTube 和本地证据库路线
- V0.5.7 新增本地研究证据入口：报告会读取 `data/research_evidence.json` 并新增“研究证据”模块
- V0.6.0 新增数据源选择与降级说明：`auto` 默认映射当前稳定源，预留源不会偷偷联网
- V0.6.1 新增 ScrapeCreators 最小接入准备：`scripts/check_scrapecreators_ready.sh` 只做本地 readiness，不调用 API
- V0.6.2 新增真实 live 前检查清单：进入 key-backed API 测试前必须先确认不泄露 key、不烧额度、不污染报告
- V0.6.3-plan 新增 ScrapeCreators tiny live probe 方案：先设计极小探测，不直接接入正式报告流
- V0.6.3 新增 ScrapeCreators tiny live probe：默认不联网，只有显式确认时才发起一次极小 Reddit API 探测；输出只写入 `local_outputs/`，不会更新正式报告
- V0.6.4 新增显式 ScrapeCreators Reddit 数据源：`--data-source scrapecreators_reddit` 可进入正式报告流程，但 `auto` 默认仍然使用 `reddit_last30days`
- V0.6.5 新增 ScrapeCreators 正式 live 专用脚本：默认只跑单关键词配置，`--confirm-full-api` 才跑完整关键词，`--dry-run` 可检查命令但不联网
- V0.6.5 正式报告默认不再附加 prompt 模板；需要调试报告结构时再手动加 `--include-prompt-template`
- V0.6.6 新增小批量关键词质量测试配置：`config/scrapecreators_quality_topics.json`
- V0.6.6 新增 `scripts/run_keyword_quality_check.sh`：默认 dry-run，不联网；真实小批量 API 测试必须显式加 `--confirm-live-api`
- V0.6.6 新增 `scripts/summarize_keyword_quality.py`：从测试报告提取每个关键词的高相关、边缘相关、跑偏数量，并输出质量摘要到 `local_outputs/`
- V0.6.7 新增智能评分设计层：规则评分仍是正式报告唯一来源，大模型评分先作为 V0.6.8 tiny probe 的准备接口
- V0.6.8 新增 DeepSeek LLM scoring tiny probe：默认不联网，只有显式确认后才用 `DEEPSEEK_API_KEY` 测试 3 到 5 条样本；输出只写 `local_outputs/`
- V0.6.8.1 新增 DeepSeek 开关配置：`LLM_SCORING_ENABLED=off/on`，未来 UI 里的“启用 DeepSeek 评分”勾选框可以直接映射到这个开关
- V0.6.9 新增规则评分 + DeepSeek 评分对照报告：用于判断大模型是否能识别规则误判、跑偏样本和关键词意图不匹配；仍不更新正式 reports
- V0.7.0 新增真实 Reddit/ScrapeCreators 小样本对照报告：真实运行必须同时有 DeepSeek key、ScrapeCreators key、`LLM_SCORING_ENABLED=on` 和 `--confirm-live-api`
- V0.7.1 优化真实样本抽样：优先抽查 AI 意图风险、边缘相关、规则高分但低把握样本，避免只看“高分样本”
- V0.7.2 新增 DeepSeek 局部质检动作：进入趋势候选、降级为噪音/低相关、人工复核、保留为背景
- V0.7.3 新增报告 + 解析结构：旁路报告会解释哪些关键词可保留、哪些要收窄、哪些只是噪音复盘
- V0.7.4 新增关键词收敛计划：把 V0.7.3 的真实小样本 JSON 转成下一轮建议测试关键词，但不自动改正式配置
- V0.7.5 应用关键词收敛计划：保留 `kiln firing` / `ceramic business`，把宽泛 `AI ceramic design` 拆成 `AI pottery workflow`、`generative ceramic pattern`、`computational ceramics`、`ceramic prompt design`
- 不安装 `yt-dlp`
- 可以在本地 `.env` 配置 API key，但不要把真实 key 提交到 GitHub
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

当前报告生成 provider：

```text
MODEL_PROVIDER=rules
```

当前正式报告只支持 `rules`。V0.7.5 已新增 DeepSeek tiny probe、内置样本评分对照报告、真实 Reddit/ScrapeCreators 小样本对照报告、局部质检、报告解析、关键词收敛计划和收敛后的质量测试词，但它们都是独立诊断脚本，不接入正式报告流程；日常报告当前不会调用 DeepSeek。

当前数据源选择：

```text
--data-source auto
```

`auto` 会在 mock 模式使用 `mock`，在 live 模式使用 `reddit_last30days`。`scrapecreators_reddit` 和 `scrapecreators_youtube_search` 都需要手动显式选择；为避免误用付费 API，`CERAMIC_DATA_SOURCE=scrapecreators_reddit` 不会改变默认命令行选择。可用和预留的数据源见 `config/data_sources.json`。

## Run

mock 示例报告：

```bash
bash scripts/run_mock.sh
```

Reddit live 最小测试：

```bash
bash scripts/run_live.sh
```

如果刚刚跑过 live，脚本会读取 `local_outputs/run_state.json` 并提示稍后再跑，避免频繁触发 Reddit 429。确实需要立即运行时可以加：

```bash
bash scripts/run_live.sh --force
```

不要连续多次使用 `--force`，尤其是刚遇到 429 或 403 之后。live 失败不会覆盖上一份成功的 `reports/report.md`，错误详情请看 `local_outputs/last_error.md`。

最近两期成功 live 报告对比：

```bash
bash scripts/compare_reports.sh
```

原始 Python 命令仍然可用：

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ceramic_report.py --mode live --data-source auto --output reports/report.md
```

如果手动选择尚未实现的数据源，例如 `youtube_future` 或 `pinterest_future`，程序会清楚提示该数据源只是预留接口，不会偷偷调用外部 API。

显式使用 ScrapeCreators Reddit API：

```bash
bash scripts/run_scrapecreators_live.sh
```

这个脚本默认只运行 `config/scrapecreators_probe_topics.json` 的单关键词配置。它会进入正式 live 报告流程，成功时会更新 `reports/report.md`、`reports/latest.md` 和 `reports/archive/`。它可能消耗 ScrapeCreators API 额度，因此不要连续重复运行；调整报告结构时仍先用 mock。

先检查命令但不联网：

```bash
bash scripts/run_scrapecreators_live.sh --dry-run
```

明确同意消耗更多 API 额度后，才运行完整关键词：

```bash
bash scripts/run_scrapecreators_live.sh --confirm-full-api
```

如果需要在报告末尾附加 prompt 模板用于调试：

```bash
bash scripts/run_scrapecreators_live.sh --include-prompt-template
```

显式使用 ScrapeCreators YouTube Search API：

```bash
bash scripts/run_youtube_live.sh
```

这个脚本默认只运行 `config/youtube_probe_topics.json` 的单关键词配置。它会进入正式 live 报告流程，成功且拿到高相关或边缘相关证据时才会更新 `reports/report.md`、`reports/latest.md` 和 `reports/archive/`。它不会拉字幕、评论或视频画面，也不会调用 DeepSeek 写正式报告。

先检查 YouTube live 命令但不联网：

```bash
bash scripts/run_youtube_live.sh --dry-run
```

检查 YouTube 多关键词小样本命令但不联网：

```bash
bash scripts/run_youtube_quality_live.sh
```

这个脚本默认只打印命令，使用 `config/youtube_quality_topics.json` 的 3 个关键词。只有明确同意消耗 ScrapeCreators API 额度时，才运行：

```bash
bash scripts/run_youtube_quality_live.sh --confirm-live-api
```

YouTube live 失败、空结果或全低相关结果不会覆盖上一份成功报告，单关键词 runner 的错误详情请看：

```text
local_outputs/youtube_live_error.md
local_outputs/youtube_run_state.json
```

多关键词小样本 runner 的错误详情请看：

```text
local_outputs/youtube_quality_error.md
local_outputs/youtube_quality_run_state.json
```

明确同意消耗更多 API 额度后，才运行完整关键词：

```bash
bash scripts/run_youtube_live.sh --confirm-full-api
```

小批量关键词质量测试默认不联网：

```bash
bash scripts/run_keyword_quality_check.sh
```

这一步只打印将要执行的 ScrapeCreators 小批量命令，不消耗 API。V0.7.5 默认测试 6 个词：

- `kiln firing`
- `ceramic business`
- `AI pottery workflow`
- `generative ceramic pattern`
- `computational ceramics`
- `ceramic prompt design`

真实运行时，ScrapeCreators 请求数约等于关键词数，也就是当前约 6 次。

确认愿意消耗 API 额度后，才运行真实小批量测试：

```bash
bash scripts/run_keyword_quality_check.sh --confirm-live-api
```

测试输出只写入 `local_outputs/keyword_quality_*`，不会覆盖正式 `reports/latest.md` 或 `reports/archive/`。根据运行结果会生成或更新：

```text
local_outputs/keyword_quality_report.md
local_outputs/keyword_quality_latest.md
local_outputs/keyword_quality_summary.md
local_outputs/keyword_quality_state.json
local_outputs/keyword_quality_error.md
local_outputs/keyword_quality_archive/
```

ScrapeCreators readiness 检查：

```bash
bash scripts/check_scrapecreators_ready.sh
```

这个命令不会访问 ScrapeCreators，也不会打印真实 key。它只告诉你本机是否已经配置了 `SCRAPECREATORS_API_KEY`，方便以后进入 key-backed 最小 live 验证。

ScrapeCreators tiny probe 默认不联网：

```bash
bash scripts/probe_scrapecreators_reddit.sh
```

这个命令只写入 `local_outputs/scrapecreators_probe_state.json`，用于确认探针保护机制生效。

只有在你明确同意消耗一次 ScrapeCreators 请求时，才运行：

```bash
bash scripts/probe_scrapecreators_reddit.sh --confirm-live-api --topic "ceramic glaze" --limit 1
```

tiny probe 的结果只写入：

```text
local_outputs/scrapecreators_probe.json
local_outputs/scrapecreators_probe_state.json
local_outputs/scrapecreators_probe_error.md
```

它不会更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。正式报告若要使用 ScrapeCreators，优先运行 `bash scripts/run_scrapecreators_live.sh`；如果绕过脚本直接用 Python 跑完整 `config/ceramic_topics.json`，也必须显式加 `--confirm-full-api`。

ScrapeCreators YouTube tiny probe 默认不联网：

```bash
bash scripts/probe_scrapecreators_youtube.sh
```

这个命令只写入 `local_outputs/youtube_probe_state.json`，用于确认 YouTube 探针保护机制生效。

只有在你明确同意消耗一次 ScrapeCreators YouTube Search 请求时，才运行：

```bash
bash scripts/probe_scrapecreators_youtube.sh --confirm-live-api --query "ceramic glaze"
```

tiny probe 的结果只写入：

```text
local_outputs/youtube_probe.json
local_outputs/youtube_probe_state.json
local_outputs/youtube_probe_error.md
```

它不会更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。V0.8.0 只验证 YouTube Search 入口是否可用，不接 DeepSeek，不拉视频详情、字幕或评论，也不会把 `youtube_future` 改成正式可用数据源。

YouTube probe 字段整理默认不联网：

```bash
bash scripts/review_youtube_probe.sh
```

它读取 `local_outputs/youtube_probe.json`，输出：

```text
local_outputs/youtube_probe_review.md
local_outputs/youtube_probe_review.json
local_outputs/youtube_probe_review_state.json
local_outputs/youtube_probe_review_error.md
```

真实 DeepSeek 旁路审核必须明确打开开关并确认：

```bash
LLM_SCORING_ENABLED=on bash scripts/review_youtube_probe.sh --confirm-live-api --sample-count 3
```

这一步只把已脱敏的 YouTube 摘要交给 DeepSeek：标题、频道、链接、视频 id、发布时间、时长、播放量。它不会拉视频详情、字幕或评论，也不会更新正式 reports。

YouTube video details tiny probe 默认不联网：

```bash
bash scripts/probe_scrapecreators_youtube_video.sh
```

真实 video details 小测试必须明确确认：

```bash
bash scripts/probe_scrapecreators_youtube_video.sh --confirm-live-api
```

它会从 `local_outputs/youtube_probe_review.json` 里挑选 DeepSeek 判断高相关的视频 URL，只请求 1 条视频详情。输出只写：

```text
local_outputs/youtube_video_probe.json
local_outputs/youtube_video_probe_state.json
local_outputs/youtube_video_probe_error.md
```

保护规则：不保存原始响应；短 description 只保存字符数，长 description 只保存确定被截断并去掉链接的摘要。

YouTube video details 字段整理默认不联网：

```bash
bash scripts/review_youtube_video_probe.sh
```

详情层 DeepSeek 旁路审核必须打开开关并确认：

```bash
LLM_SCORING_ENABLED=on bash scripts/review_youtube_video_probe.sh --confirm-live-api
```

输出只写：

```text
local_outputs/youtube_video_review.md
local_outputs/youtube_video_review.json
local_outputs/youtube_video_review_state.json
local_outputs/youtube_video_review_error.md
```

这一步不会拉 transcript，不会拉 comments，也不会更新正式 reports。

真实 API live 前检查清单：

```text
docs/live-readiness-checklist.md
```

智能评分设计配置：

```text
config/llm_scoring.json
prompts/llm_scoring_prompt.md
```

V0.6.7 只定义智能评分接口，不调用真实模型，不消耗 API，不更新正式报告。V0.6.8 如果进入大模型评分 tiny test，必须用户明确同意，并且输出只能写入 `local_outputs/llm_scoring_probe.*`。V0.6.8.1 增加 `LLM_SCORING_ENABLED` 开关，避免 `.env` 里有 key 时误触发真实请求。

DeepSeek LLM scoring tiny probe 默认不联网：

```bash
bash scripts/probe_llm_scoring.sh
```

只有在你明确同意消耗少量 DeepSeek API 额度、本地 `.env` 已配置 `DEEPSEEK_API_KEY`，并且已打开 `LLM_SCORING_ENABLED=on` 后，才运行：

```bash
bash scripts/probe_llm_scoring.sh --confirm-live-api
```

如果只是本次临时打开开关，也可以在命令前临时加：

```bash
LLM_SCORING_ENABLED=on bash scripts/probe_llm_scoring.sh --confirm-live-api
```

这一步只测试 3 条内置样本，输出只写入：

```text
local_outputs/llm_scoring_probe.md
local_outputs/llm_scoring_probe.json
local_outputs/llm_scoring_probe_state.json
local_outputs/llm_scoring_probe_error.md
```

它不会更新 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。

DeepSeek 与规则评分对照报告默认不联网：

```bash
bash scripts/compare_llm_scoring.sh
```

真实对照报告同样需要明确打开开关并确认消耗少量 DeepSeek API 额度：

```bash
LLM_SCORING_ENABLED=on bash scripts/compare_llm_scoring.sh --confirm-live-api
```

输出只写入：

```text
local_outputs/llm_scoring_comparison.md
local_outputs/llm_scoring_comparison.json
local_outputs/llm_scoring_comparison_state.json
local_outputs/llm_scoring_comparison_error.md
```

它用于观察“规则评分”和“DeepSeek 语义判断”是否一致，不会更新正式报告。

真实 Reddit/ScrapeCreators 小样本对照默认不联网：

```bash
bash scripts/compare_real_llm_scoring.sh
```

真实运行会同时消耗 ScrapeCreators 和 DeepSeek 的少量额度，必须明确打开开关并确认。注意：`--sample-count` 控制的是 DeepSeek 分析样本数；ScrapeCreators 请求数约等于本轮关键词数量，目前默认质量测试配置是 3 个关键词。

```bash
LLM_SCORING_ENABLED=on bash scripts/compare_real_llm_scoring.sh --confirm-live-api --sample-count 10
```

输出只写入：

```text
local_outputs/llm_scoring_real_sample_comparison.md
local_outputs/llm_scoring_real_sample_comparison.json
local_outputs/llm_scoring_real_sample_comparison_state.json
local_outputs/llm_scoring_real_sample_comparison_error.md
```

这一步用于观察 DeepSeek 在真实 Reddit 小样本里是否仍能补规则评分短板，并输出“质检样本质量雷达 / 局部质检 / 报告解析”。它采用风险优先抽样，会优先检查可疑和边缘样本，因此不代表关键词整体分布，也不会更新正式报告。

生成关键词收敛计划默认不联网：

```bash
bash scripts/summarize_keyword_convergence.sh
```

输出只写入：

```text
local_outputs/keyword_convergence_plan.md
local_outputs/keyword_convergence_plan.json
```

它会读取 `local_outputs/llm_scoring_real_sample_comparison.json`，把上一轮真实小样本质检结果转成“保留 / 收窄 / 降噪 / 继续观察”的下一轮关键词计划。它不会自动修改 `config/scrapecreators_quality_topics.json`，需要人工确认后再改。

在申请 key、配置 key 或第一次做 key-backed live probe 前，先按这份清单过一遍。

ScrapeCreators tiny probe 方案：

```text
docs/plans/2026-06-25-scrapecreators-tiny-probe.md
```

方案已落地为 `scripts/probe_scrapecreators_reddit.sh` 和 `scripts/probe_scrapecreators_reddit.py`。默认运行不会联网；真实 probe 必须显式添加 `--confirm-live-api`。

本地研究证据默认来自：

```text
data/research_evidence.json
```

临时关闭研究证据模块：

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ceramic_report.py --mode mock --no-research-evidence
```

生成文件：

```text
reports/report.md       # 当前主要报告；mock 和成功 live 都可以更新
reports/latest.md       # 最近一次成功 live 报告；mock 和失败 live 不更新
reports/archive/        # 历史成功 live 报告
reports/trend_diff.md   # 最近两期 archive 的基础对比
```

`reports/report.md` 当前是示例报告，可以暂时保留在版本库里，方便确认报告结构。

如果还没有成功 live，`reports/latest.md` 可能尚未生成。live 失败不会污染 `latest.md` 和 `archive/`。

live 失败时不会覆盖 `reports/report.md`，错误详情保存在：

```text
local_outputs/last_error.md
```

`local_outputs/` 已被 `.gitignore` 忽略，不会作为报告样例提交到 GitHub。

更多排障说明见 [docs/troubleshooting.md](docs/troubleshooting.md)。

完整日常操作与项目交接流程见 [docs/workflow.md](docs/workflow.md)。

真实 live 前安全清单见 [docs/live-readiness-checklist.md](docs/live-readiness-checklist.md)。

陶瓷 AI 研究素材见 [research/ceramic-ai-evidence.md](research/ceramic-ai-evidence.md)。

ScrapeCreators 晚点再申请时，稳定数据源路线见 [docs/stable-data-source-roadmap.md](docs/stable-data-source-roadmap.md)。

## Tests

本仓库使用标准库 `unittest`，无需安装第三方依赖。在仓库根目录运行：

```bash
python -m unittest discover tests
```

测试覆盖：

```text
tests/test_term_matching.py   # 词边界 / 短语分隔符匹配
tests/test_scoring.py         # 打分契约：exclude 扣分、required 缺失压分、level 阈值
tests/test_sources.py         # MockSource 可被消化；Last30DaysSource 命令逐项一致（mock subprocess）
tests/test_environment_check.py # 环境诊断的代理脱敏与错误分类
tests/test_live_failure_guidance.py # live 失败提示与 ScrapeCreators 状态脱敏
tests/test_research_evidence.py # 本地研究证据加载和报告模块
tests/test_scrapecreators_source.py # ScrapeCreators readiness、source 转换与 key 脱敏
tests/test_scrapecreators_probe.py # tiny probe 的默认不联网、缺 key、limit 和错误分类
tests/test_scrapecreators_youtube_probe.py # YouTube tiny probe 的默认不联网、输出保护、单请求和错误分类
tests/test_youtube_probe_review.py # YouTube probe 字段整理和 DeepSeek 旁路审核保护
tests/test_youtube_video_probe.py # YouTube video details tiny probe 保护和摘要脱敏
tests/test_youtube_video_review.py # YouTube video details 字段整理和 DeepSeek 旁路审核保护
tests/test_youtube_source.py # YouTube Search adapter 转换、错误分类和脱敏
tests/test_youtube_live_protection.py # YouTube live 错误、空结果、全低相关不覆盖正式报告
tests/test_report_labels.py # YouTube 报告显示频道来源，并避免把频道名 studio 误判为经营证据
tests/test_llm_scoring.py # LLM scoring 契约、mock scorer 和规则/LLM 合并
tests/test_llm_scoring_probe.py # DeepSeek tiny probe 默认不联网、缺 key、输出保护和错误分类
tests/test_llm_scoring_comparison.py # DeepSeek 与规则评分对照报告保护和统计
tests/test_llm_scoring_real_sample_comparison.py # 真实小样本 DeepSeek 对照报告保护和统计
tests/test_keyword_convergence.py # V0.7.4 关键词收敛计划保护和输出
```

mock 报告零配置生成（不联网、不依赖外部 skill）：

```bash
python ceramic_report.py --mode mock
```

## Environment Check

在继续真实 Reddit / YouTube 接入前，可以先运行环境诊断：

```bash
bash scripts/check_environment.sh
```

诊断脚本会自动使用项目已验证的 Python 3.12。诊断会检查 Python、`last30days-skill` 路径、终端代理环境变量、Reddit/YouTube/GitHub DNS 与 HTTPS、Reddit 代理感知 HTTP 状态、ScrapeCreators Reddit 备份是否 ready、`yt-dlp`、`MODEL_PROVIDER`、`.env` 文件和关键环境变量。它不会打印真实 key，也不会保存研究数据。它会发起一次最小 Reddit 探测请求，所以刚遇到 403 / 429 后不要短时间反复运行。更多说明见 `docs/environment-check.md`。

如果只想检查 ScrapeCreators key 是否准备好，不想发起 Reddit 网络探测，运行 `bash scripts/check_scrapecreators_ready.sh`。

如果浏览器能打开 Reddit，但 live 仍然 403，请先运行环境诊断。浏览器代理不一定会自动应用到终端命令；诊断会提示当前终端是否设置了 `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY`。

如果环境诊断已经明确是 Reddit 403，但还不清楚是 User-Agent、global search 还是 subreddit search 被挡，可以运行一次请求矩阵：

```bash
bash scripts/reddit_probe_matrix.sh
```

这个命令会发起多次最小 Reddit 探测请求，只用于排查，不保存研究数据。刚遇到 403 / 429 后不要短时间反复运行。

如果矩阵显示“Reddit 首页 PASS，但 `search.json` 搜索接口全部 403”，说明当前出口能打开页面但不适合走免费 Reddit JSON 搜索。后续路线评估见 [docs/reddit-data-source-options.md](docs/reddit-data-source-options.md)。如果环境诊断里的 `ScrapeCreators Reddit fallback` 是 `missing`，当前 live 就还没有 API 备份通道。

## Safety

- 不要把 `.env` 提交到 GitHub。
- 真实 key 只放在本地 `.env`、系统环境变量、GitHub Secrets 或服务器密钥管理中。
- `.env.example` 只保留空变量，用作配置模板。
- `mock` 模式不会读取真实 API key，也不会发起真实联网搜索。
- `mock` 模式可以覆盖 `reports/report.md`，因为它是测试流程。
- `live` 模式默认只访问 Reddit 公共数据源；如果当前网络无法访问 Reddit，会保留上一份成功报告，并把失败原因写入 `local_outputs/last_error.md`。
- live 失败时会标明本次数据源，方便判断是 Reddit 数据源失败、网络失败，还是报告生成逻辑问题。
- ScrapeCreators 正式数据源优先用 `bash scripts/run_scrapecreators_live.sh`；它不是 `auto` 默认源，可能消耗 API 额度。默认只跑单关键词，完整关键词必须显式加 `--confirm-full-api`。
- ScrapeCreators tiny probe 不是正式报告流程；它只写 `local_outputs/`，不会覆盖 `reports/report.md`、`reports/latest.md` 或 `reports/archive/`。
- 只有带 `--confirm-live-api` 时 tiny probe 才会发起真实 API 请求；默认运行只做本地保护检查。
- YouTube tiny probe 不是正式报告流程；它只写 `local_outputs/youtube_probe.*`，不会覆盖正式 reports，不追分页，不拉视频详情、字幕或评论。

## Project Structure

```text
ceramic_report.py                 # 打分 + 渲染 + CLI 入口
scoring/llm_scorer.py             # Design-only LLM scoring contract and mock scorer
sources/__init__.py               # TrendSource 契约（数据源适配层）
sources/mock_source.py            # MockSource：读 data/mock_samples.json，离线
sources/last30days_source.py      # Last30DaysSource：外部 last30days-skill 子进程（live）
sources/scrapecreators_source.py  # ScrapeCreators readiness 和显式可选 Reddit API source
config/ceramic_topics.json        # Ceramic keyword, subreddit, and relevance rules
config/scrapecreators_probe_topics.json # Single-topic ScrapeCreators live config with full relevance rules
config/scrapecreators_quality_topics.json # Small-batch keyword quality test config
config/llm_scoring.json           # LLM scoring design config, disabled by default
config/data_sources.json          # 当前可用和未来预留的数据源清单
data/mock_samples.json            # mock 证据样例（last30days --emit=json 形状）
data/research_evidence.json       # 本地研究证据，供报告“研究证据”模块读取
prompts/ceramic_report_prompt.md  # Chinese report structure
prompts/llm_scoring_prompt.md     # Future semantic scoring JSON prompt
tests/                            # unittest 用例（term matching / scoring / sources）
tests/test_llm_scoring.py         # Design-only LLM scoring contract tests
tests/test_data_source_selection.py # 数据源 auto 映射、预留源保护、run_state 字段
docs/changes/                     # 变更记录（每个改动一份编号文档）
AGENTS.md                         # 代理 / 贡献者工作说明
CLAUDE.md                         # 指向 AGENTS.md
scripts/run_mock.sh               # Local mock runner
scripts/run_live.sh               # Local live runner with cooldown
scripts/check_environment.sh       # Local environment diagnostic runner
scripts/check_scrapecreators_ready.sh # ScrapeCreators readiness check without network/API calls
scripts/probe_scrapecreators_reddit.py # ScrapeCreators tiny opt-in Reddit API probe
scripts/probe_scrapecreators_reddit.sh # Local tiny probe runner
scripts/probe_scrapecreators_youtube.py # ScrapeCreators tiny opt-in YouTube Search API probe
scripts/probe_scrapecreators_youtube.sh # Local YouTube tiny probe runner
scripts/review_youtube_probe.py # Analyze YouTube probe fields and optional DeepSeek side review
scripts/review_youtube_probe.sh # Local YouTube probe review runner
scripts/probe_scrapecreators_youtube_video.py # ScrapeCreators YouTube Video Details tiny probe
scripts/probe_scrapecreators_youtube_video.sh # Local YouTube video details probe runner
scripts/review_youtube_video_probe.py # Analyze YouTube video details and optional DeepSeek side review
scripts/review_youtube_video_probe.sh # Local YouTube video details review runner
scripts/run_scrapecreators_live.sh # ScrapeCreators formal live runner with API quota guard
scripts/run_keyword_quality_check.sh # Small-batch keyword quality runner, dry-run by default
scripts/summarize_keyword_quality.py # Parse keyword quality report into local_outputs summary
scripts/probe_llm_scoring.py    # DeepSeek LLM scoring tiny probe, opt-in only
scripts/probe_llm_scoring.sh    # Local DeepSeek tiny probe runner
scripts/compare_llm_scoring.py  # Rule-vs-DeepSeek scoring comparison, opt-in only
scripts/compare_llm_scoring.sh  # Local DeepSeek comparison runner
scripts/compare_real_llm_scoring.py # Real Reddit sample quality + DeepSeek gate + analysis report
scripts/compare_real_llm_scoring.sh # Local real-sample DeepSeek quality runner
scripts/summarize_keyword_convergence.py # Build next-round keyword convergence plan
scripts/summarize_keyword_convergence.sh # Local keyword convergence runner
scripts/reddit_probe_matrix.sh     # Optional Reddit 403 request-shape diagnostic
scripts/compare_reports.py        # Compare latest two archived live reports
scripts/compare_reports.sh        # Local compare runner
local_outputs/last_error.md       # Ignored live failure details
local_outputs/run_state.json      # Ignored local run state
local_outputs/scrapecreators_probe*.json/md # Ignored tiny probe state/output/error files
local_outputs/llm_scoring_probe*.json/md # Ignored DeepSeek tiny probe files
local_outputs/llm_scoring_comparison*.json/md # Ignored DeepSeek comparison files
local_outputs/llm_scoring_real_sample_comparison*.json/md # Ignored real-sample DeepSeek comparison files
local_outputs/keyword_convergence_plan*.json/md # Ignored keyword convergence plan files
reports/                          # Generated Markdown reports
reports/latest.md                 # Latest successful live report
reports/archive/                  # Archived successful live reports
reports/trend_diff.md             # Latest archive comparison
docs/automation-roadmap.md        # Future automation paths
docs/troubleshooting.md           # Local live failure troubleshooting
docs/reddit-data-source-options.md # Reddit public JSON / ScrapeCreators / other sources decision notes
docs/stable-data-source-roadmap.md # Stable source roadmap while ScrapeCreators is deferred
docs/workflow.md                  # Daily operations and agent handoff
docs/live-readiness-checklist.md  # Checklist before key-backed live/API testing
docs/plans/2026-06-25-scrapecreators-tiny-probe.md # V0.6.3 tiny probe implementation plan
research/ceramic-ai-evidence.md   # Ceramic + AI primary research evidence
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

- 本轮结论摘要
- 本轮可信度
- 热门内容
- 高相关内容
- 边缘相关内容
- 跑偏样本
- 用户痛点
- 趋势判断
- 内容选题
- 小工具灵感
- 下一轮搜索建议
- 原始证据/链接
