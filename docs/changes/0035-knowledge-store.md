---
id: 0035
title: Knowledge store foundation (共同数据库)
status: implemented
version: V0.9.6
date: 2026-07-02
supersedes: []
related:
  - storage/knowledge_store.py
  - config/knowledge_store.json
  - scripts/query_knowledge.py
  - ceramic_report.py
  - tests/test_knowledge_store.py
  - tests/test_research_evidence.py
  - tests/test_youtube_live_protection.py
---

## 背景 / Context

到 V0.9.5 为止，机器人是"做完就忘"的：每轮抓取、打分的证据只存在于当轮报告
里，跨轮之间没有任何记忆。趋势工具的核心价值是跨期对比（"这条内容上个月就出
现过""这个话题的热度在涨"），没有存储层，这类能力无从谈起。产品蓝图中的
"共同数据库（分区存储）"也需要一个真实的落脚点，供未来的小红书导入
（MediaCrawler 手动采集）和陶瓷机会雷达使用。

## 改动 / Changes

- 新增 `storage/knowledge_store.py`：本地 SQLite 知识库（纯标准库 `sqlite3`，
  零联网、零第三方依赖）。三张表：
  - `runs`：每轮运行档案（时间、mode、数据源、REPORT_VERSION、关键词、分层统计）；
  - `items`：去重后的证据条目，按 `(platform, topic, dedup_key)` 唯一，
    重复出现时 `seen_count` 递增并更新 `last_seen_*`（跨期记忆的核心）；
  - `sightings`：每次出现的原始记录（分数、层级、互动），支持将来的跨期变化分析。
- 新增 `config/knowledge_store.json`：默认 `enabled=true`，数据库固定在
  `data/`（`allowed_db_root` 守卫，模式与 local_outputs 护栏一致），
  开关 env 为 `KNOWLEDGE_STORE_ENABLED`。
- `ceramic_report.py` 增加 `save_scored_run_to_knowledge_store()` 并在两条成功
  路径（live 成功归档后、mock 写盘后）调用；任何异常折叠成一行提示，
  绝不影响报告；live 失败轮不入库。
- 新增 `scripts/query_knowledge.py`：只读查询 CLI（总览 / --runs / --repeats /
  --topic），不写任何文件。
- `data/ceramic_knowledge.db` 加入 `.gitignore`（个人档案不进仓库）；
  `.env.example` 增加 `KNOWLEDGE_STORE_ENABLED=on`。
- `tests/test_research_evidence.py` 与 `tests/test_youtube_live_protection.py`
  中所有调用 `main()` 的端到端用例显式关闭知识库开关，避免单测污染真实数据库
  （新增测试如需调用 `main()`，必须同样设 `KNOWLEDGE_STORE_ENABLED=off`）。
- `platform` 分区当前只会出现 `reddit` / `youtube`；`xiaohongshu` 与 `radar`
  为预留分区，本版没有任何代码写入。

## 不做什么 / Non-goals

- 不改打分、分层、渲染逻辑；正式报告输出保持字节不变（REPORT_VERSION 仍为 V0.6.6）。
- 不接新数据源，不接 MediaCrawler / 小红书导入（预留分区，后续版本另立变更）。
- 不把知识库内容读回报告（报告不依赖历史数据，冻结行为不变）。
- 不联网、不安装第三方依赖。
- 不让 DeepSeek 进入正式报告。

## 测试 / Verification

- `tests/test_knowledge_store.py`：
  - 仓库配置默认启用、路径固定在 data/、预留分区存在；
  - env 开关优先于 config（on/off 双向覆盖）；
  - `db_path` 逃出 `allowed_db_root` 时抛错拒绝；
  - 首轮建库：runs/items/sightings 行数与分层统计正确，reddit/youtube 分区正确；
  - 第二轮重逢：同 URL 不重复建行，`seen_count=2`、first/last_seen 正确更新，
    新条目照常新增；
  - 开关关闭时不建库、不写任何文件，返回空提示；
  - 空证据轮照样记入 runs（运行档案完整）。
- 全量测试基线对比：改动前 Windows 环境 227 例、3 失败 + 13 错误（均为既有的
  bash 依赖 / 路径分隔符问题）；改动后不得新增失败。

## 后续 / Next

- 小红书导入脚本（读 MediaCrawler 导出文件，写入 `xiaohongshu` 分区，手动执行）。
- 机会雷达事件表（展会/竞赛日历，`radar` 分区 + 截止日期字段）。
- 基于 `sightings` 的跨期对比报告（独立输出到 local_outputs/，不动正式报告）。
- 图片只存 URL / 本地路径，不入库存二进制；小红书内容商用有法律红线，导入功能
  必须保持"学习/自用"定位。
