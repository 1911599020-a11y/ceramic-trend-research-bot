# V0.8.7-lite YouTube Readiness Decision Memo Implementation Plan

**Goal:** Create a lightweight V0.8.7-lite decision memo that decides whether YouTube should move from protected side probes toward a minimal formal source adapter.

**Architecture:** This is a documentation-first decision step, not a new data pipeline. It reads existing local probe results under `local_outputs/`, summarizes current evidence, writes one decision record, and updates project docs only if needed. It must not make new API calls, run DeepSeek again, update formal reports, or enable `youtube_future`.

**Tech Stack:** Markdown documentation, existing JSON artifacts in `local_outputs/`, standard shell checks, no new runtime dependency.

---

## Scope

This plan follows the reviewer recommendation to merge the previous V0.8.7 and V0.8.8 ideas into one small step:

- Do: write one **YouTube 转正决策备忘录**.
- Do: make a clear `go / wait / no-go` decision.
- Do: define the smallest possible V0.9 adapter scope if the answer is `go` or `wait`.
- Do not: create another probe.
- Do not: call ScrapeCreators.
- Do not: call DeepSeek.
- Do not: pull transcript, comments, subtitles, watch-next, or batch details.
- Do not: update `reports/report.md`, `reports/latest.md`, or `reports/archive/`.
- Do not: enable `youtube_future` as a formal source.

Expected current decision, unless the evidence says otherwise:

```text
wait
```

Reason: current evidence is promising but narrow. It mostly proves `ceramic glaze` works well, not that YouTube is broadly stable across all ceramic trend categories.

## Useful Skills / Tools

- Use `writing-plans` for this planning document.
- Use normal code/document workflow for implementation.
- Because the memo decides whether a future data source can move toward V0.9, final implementation should use 2 reviewers, or explicitly count the 2 prior route reviewers plus 1 final reviewer in the final response.
- No plugin installation is needed.
- No browser automation is needed.
- No extra skill is needed unless implementation expands beyond this plan.

## Inputs To Read

Read these files before writing the memo:

```text
docs/changes/0027-youtube-tiny-probe.md
docs/changes/0028-youtube-probe-review.md
docs/changes/0029-youtube-video-details-probe.md
config/data_sources.json
local_outputs/youtube_probe.json
local_outputs/youtube_probe_review.json
local_outputs/youtube_video_probe.json
local_outputs/youtube_video_review.json
```

If any `local_outputs/` file is missing, do not rerun live probes. Write the decision memo with a clear note that the corresponding local evidence was unavailable.

## Task 1: Read Existing Evidence

**Files:**

- Read: `docs/changes/0027-youtube-tiny-probe.md`
- Read: `docs/changes/0028-youtube-probe-review.md`
- Read: `docs/changes/0029-youtube-video-details-probe.md`
- Read: `config/data_sources.json`
- Read: `local_outputs/youtube_probe.json`
- Read: `local_outputs/youtube_probe_review.json`
- Read: `local_outputs/youtube_video_probe.json`
- Read: `local_outputs/youtube_video_review.json`

**Step 1: Summarize local evidence**

Collect only these facts:

- YouTube Search query used.
- Number of Search video samples saved.
- Search DeepSeek review counts.
- Video Details sample title and channel.
- Video Details DeepSeek review result.
- Whether any formal report was updated.
- Whether `youtube_future` is still planned.

**Step 2: Confirm no new network**

Do not run any command with `--confirm-live-api`.

**Expected output:**

A short private working summary, not committed unless it becomes part of the memo.

## Task 2: Create Decision Memo

**Files:**

- Create: `docs/changes/0030-youtube-readiness-decision-memo.md`

**Step 1: Create the memo**

Use this exact structure:

```markdown
---
id: 0030
title: YouTube readiness decision memo
status: implemented
version: V0.8.7-lite
date: 2026-06-30
supersedes:
  - 0029
related:
  - docs/changes/0027-youtube-tiny-probe.md
  - docs/changes/0028-youtube-probe-review.md
  - docs/changes/0029-youtube-video-details-probe.md
  - config/data_sources.json
---

## 背景 / Context

Explain that YouTube Search, Search review, Video Details, and Details review have all been tested as protected side probes.

## 本轮证据 / Evidence Reviewed

Summarize current local evidence from `local_outputs/`.

## 转正判断 / Decision

Use one of:

- `go`
- `wait`
- `no-go`

Expected current decision: `wait`.

## 判断原因 / Rationale

Explain why the evidence is promising but still narrow.

## Readiness Gate

Create a table:

| Gate | Status | Notes |
|---|---|---|
| Search API can return ceramic results | pass | ... |
| Search summaries can be reviewed without formal report pollution | pass | ... |
| Details can add useful context | pass | ... |
| Evidence covers multiple ceramic categories | wait | ... |
| Cost/rate-limit risk is understood | wait | ... |
| Formal report failure protection is defined | wait | Future YouTube failures must not overwrite `reports/report.md`, `reports/latest.md`, or `reports/archive/`; errors should go to `local_outputs/last_error.md` or a YouTube-specific ignored local error file. |
| YouTube can remain opt-in, not default auto | pass | ... |
| `youtube_future` stays out of `auto` | pass | `config/data_sources.json` must keep live default on `reddit_last30days` unless a later explicit change is approved. |

## V0.9 最小范围 / Minimal V0.9 Scope

If V0.9 happens, it should only include:

- explicit opt-in YouTube Search source
- not default `auto`
- search summaries first
- at most one optional video details enrichment
- failure must not overwrite `reports/report.md`, `reports/latest.md`, or `reports/archive/`
- errors must stay in ignored `local_outputs/`
- `youtube_future` must not become the default live source
- no transcript
- no comments
- no watch-next
- no DeepSeek final-report authority

## 暂缓事项 / Deferred

List what will not be done now:

- transcript probe
- comments probe
- batch details
- YouTube-specific complex scoring
- multi-source fusion ranking
- frontend/database/multilingual work

## 下一步 / Next Step

Recommend either:

- design V0.9 minimal adapter, or
- first collect 2 more tiny Search samples if the user explicitly agrees to API usage.
```

**Step 2: Keep it concise**

The decision memo should be useful, not huge. Aim for roughly 120-200 lines maximum.

## Task 3: Update Current Status Docs

**Files:**

- Modify: `README.md`
- Modify: `AGENTS.md`

**Step 1: Update README if needed**

If `Current Status` does not mention V0.8.7-lite, add one short bullet:

```markdown
- V0.8.7-lite records a YouTube readiness decision: current status is `wait`; YouTube is promising but remains opt-in/planned until a minimal V0.9 adapter is explicitly implemented.
```

Do not rewrite the whole README.

**Step 2: Update AGENTS if needed**

If the agent rules do not mention V0.8.7-lite, add one short line near the current YouTube status:

```markdown
V0.8.7-lite is a decision memo only: YouTube remains planned/opt-in and must not become the default live source.
```

Do not change frozen behavior or source defaults.

## Task 4: Verification

**Files:**

- Check: all modified docs
- Check: no formal reports changed
- Check: no local outputs staged

**Step 1: Run formatting check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

**Step 2: Confirm changed files**

Run:

```bash
git status --short --untracked-files=all
```

Expected changed files:

```text
M README.md
M AGENTS.md
?? docs/changes/0030-youtube-readiness-decision-memo.md
```

It is acceptable if this plan file also appears when the plan itself has not yet been committed:

```text
?? docs/plans/2026-06-30-youtube-readiness-decision-memo.md
```

Unexpected:

```text
reports/report.md
reports/latest.md
reports/archive/*
local_outputs/*
config/data_sources.json
ceramic_report.py
sources/*
```

If any unexpected file appears, stop and investigate before committing.

**Step 3: Tests**

Because the implementation should be documentation-only, full tests are optional. If any code/config is touched accidentally, run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover tests
```

Expected: all tests pass.

## Task 5: Review

**Files:**

- Review: `docs/changes/0030-youtube-readiness-decision-memo.md`
- Review: `README.md`
- Review: `AGENTS.md`

Ask one reviewer to check:

- Is the decision clear?
- Is `wait` justified by the evidence?
- Does the memo avoid overengineering?
- Does it avoid enabling YouTube as a formal/default source?
- Does it clearly defer transcript/comments/details batching?

Fix any blocker before final response.

## Task 6: Final Response

Tell the user in plain Chinese:

- What was planned or implemented.
- Why it helps.
- Whether GitHub save is recommended.
- What the next step should be.

End with a progress bar:

```text
V0.8.7-lite 计划：[██████████] 已写好
V0.8.7-lite 实施：[░░░░░░░░░░] 待用户同意
V0.9 最小 YouTube adapter：[░░░░░░░░░░] 暂缓
```
