# V0.9 Minimal YouTube Adapter Implementation Plan

> **For Codex:** use the `executing-plans` skill to implement this plan task-by-task after user approval.

**Goal:** Add an explicit opt-in YouTube Search source adapter that can generate formal reports only when the user deliberately selects it, while keeping Reddit as the default live source.

**Architecture:** Reuse the existing `TrendSource` adapter layer. Add a ScrapeCreators-backed YouTube Search source that returns the same `last30days`-shaped dict as Reddit and mock sources. Keep `--data-source auto` mapped to `reddit_last30days`; YouTube must never become default in V0.9.

**Tech Stack:** Python standard library only, existing ScrapeCreators API key handling, existing `ceramic_report.py` report pipeline, `unittest`, shell wrapper scripts, Markdown docs. No new plugin, no `yt-dlp`, no transcript/comments/keyframes, no DeepSeek formal-report authority.

---

## Scope

V0.9 is **not** full YouTube understanding. It is only the smallest formal adapter that promotes the already-tested YouTube Search probe into an explicit report data source.

Do:

- Add `scrapecreators_youtube_search` as an available but explicit opt-in data source.
- Keep live default as `reddit_last30days`.
- Convert YouTube Search results into the existing `last30days` report shape.
- Add a safe runner: `bash scripts/run_youtube_live.sh`.
- Use one-topic safe config by default.
- Ensure failure does not overwrite formal reports.
- Ensure YouTube-specific errors go to `local_outputs/youtube_live_error.md`.
- Ensure every YouTube item gets explicit relevance metadata before it can count as usable evidence.
- Make report wording not pretend YouTube results are Reddit posts.

Do not:

- Do not modify `last30days-skill`.
- Do not install `yt-dlp`.
- Do not fetch transcript.
- Do not fetch comments.
- Do not fetch keyframes.
- Do not request video details in the first formal adapter.
- Do not call DeepSeek from the formal report path.
- Do not make YouTube the default `auto` live source.
- Do not let missing YouTube relevance fields default to usable evidence.

## Useful Skills / Tools

- `architecture-designer`: useful for preserving source-adapter boundaries.
- `Code`: useful during implementation and verification.
- `executing-plans`: useful after this plan is approved.
- No plugin installation is needed.
- `node_repl` is not needed.
- `video-frames` and `FFmpeg Video Editor` are not needed for V0.9 because V0.9 does not inspect video frames.

## Key Decisions

### Decision 1: Add a new source id, not reuse `youtube_future`

Use:

```text
scrapecreators_youtube_search
```

Keep:

```text
youtube_future
```

as a planned future source for transcript/video-understanding work.

Reason: `scrapecreators_youtube_search` describes what V0.9 actually does. `youtube_future` remains a reserved label for later transcript / visual understanding work.

### Decision 2: YouTube is explicit opt-in only

Allowed:

```bash
python ceramic_report.py --mode live --data-source scrapecreators_youtube_search --topics config/youtube_probe_topics.json
bash scripts/run_youtube_live.sh
```

Not allowed:

```bash
python ceramic_report.py --mode live --data-source auto
```

selecting YouTube.

### Decision 3: Failure isolation is mandatory

YouTube failure must not overwrite:

```text
reports/report.md
reports/latest.md
reports/archive/
```

YouTube success may update formal reports only when the run returns usable high/edge evidence through the normal live report path:

```text
reports/report.md
reports/latest.md
reports/archive/YYYY-MM-DD_HHMM_report.md
```

If the API call succeeds but produces no usable evidence, treat it like a protected no-update run: keep the last successful report and write a clear diagnostic to `local_outputs/youtube_live_error.md`.

YouTube live errors must be written to:

```text
local_outputs/youtube_live_error.md
```

Runner state should be written to:

```text
local_outputs/youtube_run_state.json
```

## Task 1: Add YouTube Source Unit Tests First

**Files:**

- Create: `tests/test_youtube_source.py`

**Step 1: Add missing-key test**

Test that `ScrapeCreatorsYouTubeSearchSource(env={}).fetch("ceramic glaze")` raises `missing_key` and does not call network.

**Step 2: Add response conversion test**

Mock a ScrapeCreators YouTube Search payload:

```python
payload = {
    "videos": [
        {
            "title": "Understanding Ceramic Glazes",
            "channelName": "Clay Studio",
            "url": "https://www.youtube.com/watch?v=abc123",
            "videoId": "abc123",
            "publishedTimeText": "1 month ago",
            "duration": "08:10",
            "viewCountText": "2,000 views",
        }
    ],
    "shorts": [],
}
```

Expected converted shape:

```python
{
    "topic": "ceramic glaze",
    "items_by_source": {
        "youtube": [
            {
                "title": "Understanding Ceramic Glazes",
                "url": "https://www.youtube.com/watch?v=abc123",
                "container": "Clay Studio",
                "engagement": {"views": "2,000 views"},
                "metadata": {
                    "provider": "scrapecreators",
                    "platform": "youtube",
                    "video_id": "abc123",
                },
            }
        ]
    },
}
```

**Step 3: Add HTTP error tests**

Cover at least:

- 401 -> `unauthorized_401`
- 402/body quota -> `quota_or_billing`
- 403 -> `forbidden_403`
- 429 -> `rate_limited_429`
- timeout -> `timeout`
- JSON parse error -> `parse_error`

Assert secrets are redacted.

**Step 4: Run failing test**

Run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_youtube_source
```

Expected before implementation: fail because `sources.youtube_source` does not exist.

## Task 2: Implement YouTube Search TrendSource

**Files:**

- Create: `sources/youtube_source.py`
- Modify: `sources/__init__.py`

**Step 1: Create source module**

Implement:

```python
class ScrapeCreatorsYouTubeSearchSource:
    def __init__(self, *, env=None, dotenv_path=None, timeout=30, upload_date="this_month", sort_by="relevance", item_type="videos", summary_limit=3): ...

    def fetch(self, topic: str, *, recommended_subreddits: set[str] | None = None) -> dict[str, Any]: ...
```

Recommended constants:

```python
SCRAPECREATORS_YOUTUBE_SEARCH_URL = "https://api.scrapecreators.com/v1/youtube/search"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_SUMMARY_LIMIT = 3
MAX_SUMMARY_LIMIT = 3
USER_AGENT = "ceramic-trend-research-bot/0.9.0"
```

Reuse from `sources.scrapecreators_source` where practical:

- `configured_scrapecreators_env_var`
- `effective_env`
- `redact_secret`

**Step 2: Build request URL**

Use only documented search parameters already validated by V0.8 probes:

```text
query
uploadDate
sortBy
type
```

Do not request continuation pages.

**Step 3: Convert response**

Only convert `videos`. Do not convert shorts/channels/playlists in V0.9.

Each YouTube item should include:

```python
{
    "title": title,
    "body": snippet,
    "snippet": snippet,
    "url": url,
    "container": channel_name,
    "engagement": {"views": views},
    "local_rank_score": local_rank_score,
    "metadata": {
        "provider": "scrapecreators",
        "platform": "youtube",
        "video_id": video_id,
        "channel": channel_name,
        "published": published,
        "duration": duration,
    },
}
```

`snippet` can be a compact string built from channel, published time, duration, and views. Do not save raw response fields beyond the allowlist.

**Step 4: Export from source package**

Update `sources/__init__.py`:

```python
from sources.youtube_source import ScrapeCreatorsYouTubeSearchSource
```

and add it to `__all__`.

**Step 5: Run source tests**

Run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_youtube_source
```

Expected: pass.

## Task 3: Register Explicit Data Source

**Files:**

- Modify: `config/data_sources.json`
- Modify: `ceramic_report.py`
- Modify: `tests/test_data_source_selection.py`

**Step 1: Add source catalog entry**

Add:

```json
{
  "id": "scrapecreators_youtube_search",
  "label": "ScrapeCreators YouTube Search API",
  "mode": "live",
  "status": "available",
  "kind": "api_provider",
  "description": "Explicit opt-in YouTube Search source. It is not the default live source; select it explicitly with --data-source scrapecreators_youtube_search.",
  "requires_env": ["SCRAPECREATORS_API_KEY"],
  "fallback_sources": ["mock"]
}
```

Do not change:

```json
"default_by_mode": {
  "live": "reddit_last30days"
}
```

Keep `youtube_future` as `planned`.

**Step 2: Wire source builder**

Update `build_trend_source()`:

```python
if selection.source_id == "scrapecreators_youtube_search":
    return ScrapeCreatorsYouTubeSearchSource(dotenv_path=PROJECT_ROOT / ".env")
```

**Step 3: Protect full-topic runs**

Update `validate_api_topic_scope()` so `scrapecreators_youtube_search` behaves like `scrapecreators_reddit`:

- If topics path is `config/ceramic_topics.json`, require `--confirm-full-api`.
- If topics path is a safe one-topic config, no full confirmation needed.

Error text should mention YouTube and API cost clearly.

**Step 4: Update tests**

Add assertions:

- `auto` live still resolves to `reddit_last30days`.
- explicit `scrapecreators_youtube_search` resolves successfully.
- `build_trend_source()` returns `ScrapeCreatorsYouTubeSearchSource`.
- `youtube_future` remains planned and still raises "已预留但尚未实现".
- YouTube full default topics require `--confirm-full-api`.

**Step 5: Run tests**

Run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_data_source_selection tests.test_youtube_source
```

Expected: pass.

## Task 4: Add YouTube Relevance Scoring And Main-Flow Protection Tests

**Files:**

- Modify: `ceramic_report.py`
- Test: create or update focused integration tests, for example `tests/test_youtube_live_protection.py`

**Problem to prevent:**

The existing report collector must not treat unscored YouTube items as usable evidence by accident. YouTube items need explicit `ceramic_relevance_level` and `ceramic_relevance_score` before live success can update formal reports.

**Step 1: Make scoring platform-aware**

Update the scoring / collection path so YouTube items go through the same ceramic relevance rules as Reddit where possible:

- Use title, snippet/body, channel/container, URL, and metadata text as scoring text.
- Use the existing topic rules from `config/ceramic_topics.json`.
- Explicitly set `ceramic_relevance_level` to `high`, `edge`, or `low`.
- Explicitly set `ceramic_relevance_score`.
- Preserve low relevance items for diagnostics, but do not count them as usable evidence.

Do not rely on a default `edge` level when the source is `youtube`.

**Step 2: Make no-evidence errors platform-neutral**

Replace Reddit-specific no-evidence wording such as:

```text
no_usable_reddit_evidence
```

with a platform-aware or neutral error type, for example:

```text
no_usable_evidence
```

The user-facing message should say which source failed, for example YouTube or Reddit.

**Step 3: Add main-flow protection tests**

Add tests that mock the YouTube source and verify:

- YouTube API errors such as `missing_key`, `forbidden_403`, `rate_limited_429`, and `parse_error` do not write `reports/report.md`, `reports/latest.md`, or `reports/archive/`.
- Empty `videos` does not write formal reports.
- All-low YouTube evidence does not write formal reports.
- A YouTube item that scores `high` or `edge` can update the normal live output path when explicitly selected.
- The configured YouTube error file is written on protected failure.

These tests should not make network requests.

**Step 4: Run focused tests**

Run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_youtube_source tests.test_youtube_live_protection tests.test_data_source_selection
```

Expected: pass.

## Task 5: Add Safe YouTube Runner

**Files:**

- Create: `config/youtube_probe_topics.json`
- Create: `scripts/run_youtube_live.sh`

**Step 1: Create one-topic config**

Create `config/youtube_probe_topics.json`.

It should be based on `config/scrapecreators_probe_topics.json`, but its `topics` should remain:

```json
["ceramic glaze"]
```

This keeps default YouTube live small.

**Step 2: Create runner**

`scripts/run_youtube_live.sh` should mirror `scripts/run_scrapecreators_live.sh`, but use:

```bash
--data-source scrapecreators_youtube_search
--topics config/youtube_probe_topics.json
--state-file local_outputs/youtube_run_state.json
--error-file local_outputs/youtube_live_error.md
```

Support:

- `--dry-run`
- `--force`
- `--confirm-full-api`
- `--include-prompt-template`
- `--no-research-evidence`
- `--cooldown-minutes N`
- `--help`

Default behavior can run the one-topic YouTube live source only because using this script is already explicit opt-in.

On success with usable evidence, the runner should allow the existing live success path to update `reports/report.md`, `reports/latest.md`, and `reports/archive/`. On failure, empty usable evidence, or protected API errors, it must keep those report files unchanged and write the reason to `local_outputs/youtube_live_error.md`.

**Step 3: Add runner tests only if shell behavior grows**

If the runner is a simple wrapper, `git diff --check` plus dry-run is enough. If it includes custom parsing beyond the existing pattern, add a shell-related test or a focused script inspection test.

**Step 4: Dry-run**

Run:

```bash
bash scripts/run_youtube_live.sh --dry-run
```

Expected:

- no network
- command includes `--data-source scrapecreators_youtube_search`
- command includes `--topics config/youtube_probe_topics.json`
- command includes `local_outputs/youtube_live_error.md`

## Task 6: Make Report Labels Platform-Aware

**Files:**

- Modify: `ceramic_report.py`
- Test: create or update a focused report-rendering test, for example `tests/test_report_labels.py`

**Problem:**

Current report wording often says "Reddit" and formats containers as `r/...`. This is wrong for YouTube channels.

**Step 1: Add origin-label helpers**

Add helper functions near `evidence_ref()`:

```python
def source_platform_label(source: str) -> str:
    if source == "youtube":
        return "YouTube"
    if source == "reddit":
        return "Reddit"
    return source or "未知来源"

def evidence_origin_label(item: Evidence) -> str:
    if item.source == "youtube":
        return f"YouTube 频道 {item.subreddit}" if item.subreddit else "YouTube"
    if item.source == "reddit":
        return f"r/{item.subreddit}" if item.subreddit else "Reddit"
    return item.subreddit or item.source or "未知来源"
```

Note: keep `Evidence.subreddit` field name for compatibility in V0.9, but display it as channel when `source == "youtube"`.

**Step 2: Update wording**

Update only minimal user-facing report labels:

- `evidence_ref()`
- "热门内容" best-item origin
- source/evidence tables that show `r/...`
- low relevance explanation that says subreddit
- generic report note if it says "Reddit" where it should say current source
- `REPORT_VERSION` / title note if it still says this is only a Reddit live report
- `report_note()` text if it still says YouTube is not connected after V0.9 explicit opt-in is selected

Do not rewrite the whole report.

**Step 3: Add tests**

Create a tiny test with a YouTube `Evidence` item and assert:

- it displays `YouTube`
- it does not display `r/Clay Studio`
- it does not call the content "Reddit 热点"

**Step 4: Run tests**

Run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_report_labels
```

Expected: pass.

## Task 7: Docs And Change Record

**Files:**

- Create: `docs/changes/0031-youtube-minimal-adapter.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify if useful: `docs/workflow.md`

**Step 1: Write change record**

`0031` should state:

- V0.9 adds explicit YouTube Search source.
- YouTube is not default `auto`.
- Default runner uses one topic.
- No transcript/comments/keyframes/video downloads.
- No DeepSeek formal report authority.
- Failure does not overwrite reports.
- YouTube live errors go to `local_outputs/youtube_live_error.md`.

**Step 2: Update README**

Add run command:

```bash
bash scripts/run_youtube_live.sh --dry-run
bash scripts/run_youtube_live.sh
```

Make clear:

- this may consume ScrapeCreators API credits
- it is explicit opt-in
- failure keeps prior report

**Step 3: Update AGENTS**

Add frozen boundary:

- YouTube Search source is explicit opt-in only.
- `auto` live remains `reddit_last30days`.
- No transcript/comments/keyframes in V0.9.
- Do not install `yt-dlp`.

## Task 8: Verification

**Step 1: Run focused tests**

Run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_youtube_source tests.test_data_source_selection tests.test_youtube_live_protection tests.test_report_labels
```

**Step 2: Run full tests**

Run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover tests
```

Expected: all tests pass.

**Step 3: Run dry-run**

Run:

```bash
bash scripts/run_youtube_live.sh --dry-run
```

Expected: no network, no API use.

**Step 4: Check diff**

Run:

```bash
git diff --check
git status --short --untracked-files=all
```

Unexpected changed files:

```text
reports/report.md
reports/latest.md
reports/archive/*
local_outputs/*
```

## Task 9: Review

Because V0.9 touches data source, live behavior, report wording, and API-cost boundaries, final implementation must use 2 reviewers.

Reviewer A should focus on:

- source adapter contract
- response conversion
- no secret leaks
- error classification
- no unintended network in tests

Reviewer B should focus on:

- report wording
- default source remains Reddit
- YouTube opt-in boundary
- failure protection
- docs clarity

Fix blockers before final response.

## Task 10: Final Response

Explain in plain Chinese:

- what V0.9 implemented
- how to run dry-run
- how to run explicit YouTube live
- whether reports were protected
- whether tests passed
- whether to save GitHub

End with:

```text
V0.9 计划：[██████████] 已执行
YouTube explicit opt-in source：[██████████] 已完成
默认 auto：[██████████] 仍保持 Reddit
字幕/评论/画面理解：[░░░░░░░░░░] 未开始，仍暂缓
```
