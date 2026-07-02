# DeepSeek Report Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make DeepSeek judgments appear in the formal Markdown report as a small-scope rule-vs-DeepSeek comparison, without replacing the frozen rule scorer yet.

**Architecture:** Keep the existing rule-based scoring and report order as the stable baseline. Add a post-scoring LLM review layer that selects a capped set of evidence items, asks DeepSeek or a deterministic mock scorer for semantic judgment, stores review results on the `Evidence` objects or a side map, then renders a new formal report section and optional evidence-table columns. Live failures or DeepSeek failures must not overwrite successful reports or block the rule-based report.

**Tech Stack:** Python 3.10+ standard library, existing `scoring/llm_scorer.py`, existing DeepSeek request helpers from `scripts/probe_llm_scoring.py`, `unittest`, Markdown docs. No new third-party dependency.

---

## V0.9.7 Scope

This version is only about one delivery question:

**Does DeepSeek's judgment truly appear in `reports/report.md`?**

If yes, V0.9.7 ships. If no, it is not done.

Do not add YouTube comments, transcripts, video details, Pinterest, Xiaohongshu, frontend, or opportunity radar in this version.

## Product Decisions

- DeepSeek is promoted from side probe to formal report reviewer.
- Rules stay as the first-pass scorer for V0.9.7.
- Rules act only as a low-authority gate: they can identify obvious junk, but uncertain items should still be eligible for DeepSeek review.
- DeepSeek starts as "two-column comparison", not final judge.
- Review volume is capped, initially `max_items_per_run=5`, so the report path can run without uncontrolled spending.
- User has approved DeepSeek quota use when needed.
- Search engine quota is different: every search engine use still requires a short quota request and explicit approval.

## Non-Goals

- Do not make DeepSeek rewrite the whole report.
- Do not let DeepSeek change `reports/report.md` after render as a second pass.
- Do not use DeepSeek to generate final trend conclusions yet.
- Do not fetch YouTube comments, subtitles, transcripts, or video frames.
- Do not change ScrapeCreators or search-engine quota behavior.
- Do not remove the rule scorer or break historical comparability.

## Acceptance Criteria

- `reports/report.md` contains a formal section named `## DeepSeek 语义质检` or equivalent.
- The section includes at least: topic, source, title, rule judgment, DeepSeek judgment, confidence, and DeepSeek reason.
- When DeepSeek is disabled or missing a key, the report still renders and clearly says DeepSeek review was not run.
- When DeepSeek request fails, the report still renders from rules, and failure details go to `local_outputs/` without overwriting reports incorrectly.
- Tests prove DeepSeek results are rendered in formal reports.
- Tests prove disabled/missing-key/error states do not break report generation.
- Tests prove the selected review sample count is capped.
- A new `docs/changes/0036-deepseek-report-integration.md` records the behavior change.

---

### Task 1: Pin The Current Formal Report Baseline

**Files:**
- Modify: `tests/test_llm_report_integration.py`
- Read: `ceramic_report.py`
- Read: `tests/test_research_evidence.py`

**Step 1: Add a baseline test file**

Create `tests/test_llm_report_integration.py`.

Test that calling `render_report(...)` without DeepSeek review keeps the existing rule report shape and includes no fake DeepSeek result.

**Step 2: Run the new test**

Run:

```bash
python3 -m unittest tests.test_llm_report_integration
```

Expected: fail at first because no test scaffolding exists yet, then pass once imports and baseline fixtures are correct.

**Step 3: Keep the fixture tiny**

Use one `TopicRun` with one high evidence and one edge evidence. Do not read real reports or call the network.

---

### Task 2: Add Formal Report Review Data Structures

**Files:**
- Modify: `ceramic_report.py`
- Test: `tests/test_llm_report_integration.py`

**Step 1: Add a small frozen dataclass**

Add a `ReportLLMReview` dataclass near `Evidence` / `TopicRun`.

It should contain:

- `topic`
- `source`
- `title`
- `url`
- `rule_level`
- `rule_score`
- `rule_notes`
- `llm_relevance`
- `llm_intent_match`
- `llm_evidence_type`
- `llm_can_support_trend`
- `llm_is_noise`
- `llm_confidence`
- `llm_reason`
- `combined_level`
- `combined_confidence`
- `combined_reason`

**Step 2: Test rendering input shape**

Add a test that passes one synthetic `ReportLLMReview` to report rendering and expects the DeepSeek section to show it.

Expected now: fail because `render_report` has no review argument.

---

### Task 3: Render DeepSeek Two-Column Comparison In The Formal Report

**Files:**
- Modify: `ceramic_report.py`
- Test: `tests/test_llm_report_integration.py`

**Step 1: Extend `render_report` signature**

Add an optional argument:

```python
llm_reviews: list[ReportLLMReview] | None = None
```

Default to `None` so existing tests and callers keep working.

**Step 2: Add `append_llm_review_section`**

Render after `## 本轮可信度` or after `## 热门内容`.

Recommended section:

```markdown
## DeepSeek 语义质检

> 本节只做语义复核，不替代规则评分；V0.9.7 先采用两栏对照。

| 关键词 | 来源 | 标题 | 规则判断 | DeepSeek 判断 | 合并建议 | 置信度 | 理由 | 链接 |
|---|---|---|---|---|---|---|---|---|
```

**Step 3: Disabled state**

If no review was run, render one short note only when the caller explicitly passes a status object later. For this task, keep `None` as "hide section" so existing mock reports are not noisy.

**Step 4: Run focused tests**

Run:

```bash
python3 -m unittest tests.test_llm_report_integration tests.test_research_evidence
```

Expected: pass.

---

### Task 4: Build Evidence-To-LLM Input Conversion

**Files:**
- Modify: `ceramic_report.py`
- Test: `tests/test_llm_report_integration.py`
- Reuse: `scoring/llm_scorer.py`

**Step 1: Add conversion helper**

Add:

```python
def evidence_to_llm_input(evidence: Evidence) -> LLMScoringInput:
    ...
```

Map:

- `topic` -> topic
- `title` -> title
- `subreddit` -> subreddit
- `snippet` -> body
- `url` -> url
- `source` -> source
- `relevance_level` -> rule_level
- `relevance_score` -> rule_score
- `relevance_notes` -> rule_notes

**Step 2: Add test**

Test that Reddit and YouTube evidence both preserve source, container/channel, score, level, and rule notes.

**Step 3: Run test**

Run:

```bash
python3 -m unittest tests.test_llm_report_integration
```

Expected: pass.

---

### Task 5: Select A Capped Review Sample

**Files:**
- Modify: `ceramic_report.py`
- Test: `tests/test_llm_report_integration.py`

**Step 1: Add selection helper**

Add:

```python
def select_llm_review_candidates(runs: list[TopicRun], max_items: int) -> list[Evidence]:
    ...
```

Selection rule:

1. Include high evidence first.
2. Include edge evidence second.
3. Include suspicious low evidence only if it has high rule score history or notes that suggest ambiguity. For V0.9.7, keep this simple and prefer high/edge.
4. Cap at `max_items`.

**Step 2: Add tests**

Cases:

- Returns at most 5.
- Prioritizes high before edge.
- Does not return low-only junk when enough high/edge evidence exists.
- Handles empty runs.

**Step 3: Run tests**

Run:

```bash
python3 -m unittest tests.test_llm_report_integration
```

Expected: pass.

---

### Task 6: Add A Report-Path LLM Reviewer Interface

**Files:**
- Modify: `ceramic_report.py`
- Test: `tests/test_llm_report_integration.py`
- Reuse: `scoring/llm_scorer.py`

**Step 1: Add deterministic mock report reviewer**

For tests and dry runs, use `MockLLMScorer`.

Add:

```python
def build_llm_reviews_with_mock(candidates: list[Evidence]) -> list[ReportLLMReview]:
    ...
```

It should:

- convert evidence to `LLMScoringInput`
- call `MockLLMScorer().score(...)`
- call `combine_rule_and_llm(...)`
- return `ReportLLMReview`

**Step 2: Add tests**

Test:

- noise gets combined to low
- a real ceramic item gets DeepSeek-style high or background review
- combined reason is rendered

**Step 3: Run tests**

Run:

```bash
python3 -m unittest tests.test_llm_report_integration tests.test_llm_scoring
```

Expected: pass.

---

### Task 7: Wire DeepSeek API Into The Formal Report Path

**Files:**
- Modify: `ceramic_report.py`
- Possibly reuse: `scripts/probe_llm_scoring.py`
- Read: `config/llm_scoring.json`
- Read: `prompts/llm_scoring_prompt.md`
- Test: `tests/test_llm_report_integration.py`

**Step 1: Avoid importing script internals blindly**

Move only stable, generic DeepSeek helpers into a reusable module if needed, for example:

- Create: `scoring/deepseek_client.py`

Include:

- base URL validation
- request payload construction
- response parsing wrapper
- secret redaction helper if needed

If moving code is too much for V0.9.7, import carefully from `scripts/probe_llm_scoring.py`, but prefer a reusable module because formal report code should not depend on a probe script.

**Step 2: Add report runner helper**

Add:

```python
def maybe_build_llm_reviews(runs: list[TopicRun], *, env: Mapping[str, str] | None = None) -> tuple[list[ReportLLMReview], str]:
    ...
```

Return:

- reviews
- status note, such as `success`, `disabled`, `missing_key`, `failure: timeout`

**Step 3: Switch behavior**

Use `config/llm_scoring.json`.

Rules:

- If `LLM_SCORING_ENABLED` is not on, do not call DeepSeek.
- If enabled but key missing, do not call DeepSeek; report a status note.
- If enabled and key present, call DeepSeek for capped candidates.
- Default cap comes from `max_items_per_run`.
- Do not write DeepSeek output outside the report/state unless there is an error; errors go under `local_outputs/`.

**Step 4: Tests must mock network**

Patch the DeepSeek request function. No test may make a real network request.

Test:

- enabled + key + fake response -> report contains DeepSeek section.
- switch off -> report still succeeds.
- missing key -> report still succeeds.
- HTTP error -> report still succeeds and returns status note.

---

### Task 8: Connect LLM Reviews In `main()`

**Files:**
- Modify: `ceramic_report.py`
- Test: `tests/test_llm_report_integration.py`
- Test: `tests/test_youtube_live_protection.py`
- Test: `tests/test_research_evidence.py`

**Step 1: Build reviews after scoring and before render**

In `main()`, after all `runs` are collected and before `render_report(...)`, call `maybe_build_llm_reviews(...)`.

Pass `llm_reviews` and `llm_review_status` into `render_report(...)`.

**Step 2: Live failure protection**

For live runs that fail before usable evidence, do not call DeepSeek.

Reason: no usable report evidence, and live failure must stay cheap and safe.

**Step 3: Mock mode behavior**

For mock mode:

- If DeepSeek is off, no DeepSeek call.
- If DeepSeek is on, allow mock scorer or fake patched client in tests.
- Do not require real DeepSeek for normal tests.

**Step 4: Run affected tests**

Run:

```bash
KNOWLEDGE_STORE_ENABLED=off python3 -m unittest tests.test_llm_report_integration tests.test_youtube_live_protection tests.test_research_evidence
```

Expected: pass.

---

### Task 9: Update User-Facing Report Copy

**Files:**
- Modify: `ceramic_report.py`
- Modify: `prompts/ceramic_report_prompt.md` if it documents report sections
- Test: `tests/test_llm_report_integration.py`

**Step 1: Add honest copy**

Report note should say:

- V0.9.7 DeepSeek is semantic review, not final report author.
- Rules still determine the existing high/edge/low buckets.
- DeepSeek disagreement is used for quality review and later promotion.

**Step 2: Add disabled/missing status copy**

If `LLM_SCORING_ENABLED` is off:

```markdown
> DeepSeek 语义质检未开启；本报告仅使用规则评分。
```

If key missing:

```markdown
> DeepSeek 语义质检已请求但未找到 API key；本报告仅使用规则评分。
```

**Step 3: Keep it short**

Do not let the DeepSeek note dominate the report.

---

### Task 10: Downgrade Fake User-Pain Certainty

**Files:**
- Modify: `ceramic_report.py`
- Test: existing report tests or new `tests/test_report_labels.py` case

**Step 1: Rename or qualify current pain section**

For V0.9.7, do not generate real DeepSeek pain points yet unless they are already in the review result.

Change copy from absolute "用户痛点" to something like:

```markdown
## 用户痛点假设
```

or add a note:

```markdown
> 本节仍是按关键词生成的初步假设，尚未基于评论/字幕/长文本证据抽取。
```

**Step 2: Add a test**

Assert that the report no longer presents template pain points as data-backed conclusions.

**Step 3: Run report tests**

Run:

```bash
python3 -m unittest tests.test_report_labels tests.test_research_evidence tests.test_llm_report_integration
```

Expected: pass.

---

### Task 11: Update Config And Environment Guidance

**Files:**
- Modify: `config/llm_scoring.json`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `AGENTS.md`

**Step 1: Update config notes**

Keep default conservative unless the user explicitly wants default-on in repo config.

Recommended:

- `enabled` may stay false in config.
- `LLM_SCORING_ENABLED=on` in `.env` enables formal report review.
- `max_items_per_run` remains 5.
- Update notes to say V0.9.7 can write DeepSeek review into formal reports.

**Step 2: Update AGENTS.md**

Replace older "LLM 不接入正式报告" freeze language with the new V0.9.7 contract:

- DeepSeek formal report review is allowed only as capped semantic review.
- It does not rewrite report conclusions yet.
- It must be tested with mocked network.
- Real DeepSeek usage is allowed when needed.
- Search engine quota still requires prior user approval.

**Step 3: Update README**

Add:

```bash
LLM_SCORING_ENABLED=on python3 ceramic_report.py --mode mock
```

and explain the cap.

---

### Task 12: Add V0.9.7 Change Record

**Files:**
- Create: `docs/changes/0036-deepseek-report-integration.md`

**Step 1: Document why**

Explain:

- V0.9.5 quality report identified DeepSeek as the highest-priority delivery gap.
- V0.9.7 breaks the "forever almost integrated" pattern.
- The acceptance standard is visible DeepSeek judgment in the formal report.

**Step 2: Document behavior**

Include:

- capped review count
- disabled/missing/error behavior
- formal report section
- no YouTube comments/transcripts yet
- rules remain baseline

**Step 3: Document tests**

List test files and commands.

---

### Task 13: Verification

**Files:**
- Test only

**Step 1: Run focused tests**

Run:

```bash
KNOWLEDGE_STORE_ENABLED=off python3 -m unittest tests.test_llm_report_integration tests.test_llm_scoring tests.test_research_evidence tests.test_youtube_live_protection
```

Expected: pass.

**Step 2: Run full tests**

Run:

```bash
KNOWLEDGE_STORE_ENABLED=off python3 -m unittest discover tests
```

Expected: no new failures. If the two known `test_youtube_probe_review` failures remain, document them as pre-existing and unrelated.

**Step 3: Run formatting check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

**Step 4: Run one local report without DeepSeek**

Run:

```bash
KNOWLEDGE_STORE_ENABLED=off LLM_SCORING_ENABLED=off python3 ceramic_report.py --mode mock
```

Expected:

- report writes successfully
- no DeepSeek network request
- no knowledge DB pollution

**Step 5: Run one controlled DeepSeek report if API key is present**

Run only when environment has a DeepSeek key:

```bash
KNOWLEDGE_STORE_ENABLED=off LLM_SCORING_ENABLED=on python3 ceramic_report.py --mode mock
```

Expected:

- formal report writes successfully
- `## DeepSeek 语义质检` appears
- reviewed item count is at most 5

---

### Task 14: Review Gate

**Files:**
- Final diff

**Step 1: First independent review**

Review for:

- report-generation regressions
- live failure behavior
- accidental uncapped DeepSeek calls
- secret leakage
- test pollution of `data/ceramic_knowledge.db`

**Step 2: Second independent review**

Required because this touches LLM/API/report generation.

Review for:

- prompt/response contract mismatch
- unclear user-facing copy
- accidental search-engine quota use
- docs contradicting implementation

**Step 3: Fix review findings**

If fixes touch behavior, rerun focused tests and at least one final review pass.

---

## Suggested Commit Plan

Do not commit unless the user asks.

If asked to commit later:

1. `test: pin DeepSeek report review behavior`
2. `feat: add DeepSeek semantic review to formal report`
3. `docs: record V0.9.7 DeepSeek report integration`

---

## Plain-Language Summary

We are planning to let the project stop merely "testing DeepSeek on the side" and start showing DeepSeek's opinion inside the real report.

This version does not ask DeepSeek to write the whole report. It asks DeepSeek to review a few important pieces of evidence and show its judgment next to the old rule judgment, like:

`规则说：高相关` / `DeepSeek 说：边缘相关，因为这个只是泛陶瓷背景，不够支撑趋势`

That is enough to break the "almost integrated, never delivered" problem.
