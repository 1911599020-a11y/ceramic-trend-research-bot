# YouTube Video Understanding Roadmap Implementation Plan

**Goal:** Define a staged future path for helping the ceramic trend bot understand YouTube videos beyond metadata, without derailing the current social trend report mainline.

**Architecture:** Treat video understanding as optional enrichment layers, not as the default YouTube source. Each layer must be opt-in, local-output-first, cost-aware, and blocked from overwriting formal reports until it passes a readiness memo. Text layers come before visual layers.

**Tech Stack:** Existing Python standard-library scripts, ScrapeCreators or another explicit provider only after approval, DeepSeek or another model only behind `LLM_SCORING_ENABLED=on`, optional future `ffmpeg`/`video-frames` tooling for keyframes, Markdown docs, `local_outputs/` artifacts.

---

## Current Decision

This roadmap is **not** the next coding task.

The current mainline remains:

```text
V0.9 minimal YouTube adapter design first
```

Video understanding should start only after YouTube has a minimal, explicit opt-in adapter plan. Do not start transcript, comments, keyframes, or full video understanding while YouTube is still in `wait` status from V0.8.7-lite.

## Why This Exists

YouTube is a video-first platform, but the bot currently understands only metadata and safe text fields:

- title
- channel
- URL / video id
- publish time
- duration
- views / likes / comments count
- keywords
- truncated description excerpt
- caption track count and language

This is enough for a first trend signal, but future ceramic-specific value may come from:

- transcript content: glaze recipes, firing schedules, process steps
- comments: user pain points and objections
- thumbnails/keyframes: glaze color, texture, form, studio process
- full video understanding: long-term Pro capability

## Skills / Plugins Check

No new plugin should be installed for this roadmap.

Potential future helpers:

- `video-frames`: useful only if a future local video file or downloaded clip needs keyframe extraction with ffmpeg.
- `FFmpeg Video Editor`: useful only for future local clipping, frame extraction, or audio extraction workflows.
- `node_repl`: not useful for this roadmap unless a later browser/UI verification task appears.

Current recommendation:

```text
Do not install or enable anything now.
```

## Hard Boundaries

- Do not install `yt-dlp` in this phase.
- Do not download full YouTube videos.
- Do not fetch transcript/comments/keyframes without a separate plan and explicit user approval.
- Do not update `reports/report.md`, `reports/latest.md`, or `reports/archive/` from any probe.
- All probe output must stay in ignored `local_outputs/`.
- Any model call must require an explicit switch and confirmation.
- Video understanding can support evidence quality, but cannot become final report authority without another readiness decision.

## Stage 1: Transcript Tiny Probe

**Difficulty:** medium-low  
**Priority:** first video-understanding layer  
**Goal:** Let the bot read what the video says, without watching images.

**Why first:**

Transcript is usually more useful and cheaper than visual analysis. For ceramic videos, transcript can reveal:

- glaze chemistry terms
- firing cone and temperature
- process steps
- studio workflow
- safety warnings
- beginner pain points

**Files likely involved later:**

- Create: `scripts/probe_youtube_transcript.py`
- Create: `scripts/probe_youtube_transcript.sh`
- Create: `tests/test_youtube_transcript_probe.py`
- Create: `docs/changes/00XX-youtube-transcript-tiny-probe.md`

**Required behavior later:**

- Default dry-run, no network.
- Real request requires explicit confirmation.
- Use only an approved and documented provider/API; do not guess endpoints or response shapes.
- Pull at most 1 transcript for 1 high-confidence video.
- Save only a trimmed transcript excerpt and summary metadata.
- Do not save raw provider responses, full caption payloads, or caption URLs.
- Do not save full transcript unless a later privacy/storage decision explicitly allows it.
- Do not update formal reports.

**Readiness gate:**

Transcript moves forward only if it clearly improves ceramic relevance judgment beyond title + description.

## Stage 2: Transcript Review

**Difficulty:** medium  
**Priority:** after Stage 1 succeeds  
**Goal:** Let DeepSeek or another reviewer judge transcript excerpts as ceramic evidence.

**Files likely involved later:**

- Create: `scripts/review_youtube_transcript_probe.py`
- Create: `scripts/review_youtube_transcript_probe.sh`
- Create: `tests/test_youtube_transcript_review.py`
- Create: `docs/changes/00XX-youtube-transcript-review.md`

**Required behavior later:**

- Default local-only analysis.
- DeepSeek requires `LLM_SCORING_ENABLED=on` and explicit confirmation.
- Model sees only trimmed transcript excerpts and safe metadata.
- Output stays in `local_outputs/youtube_transcript_review.*`.
- The model can recommend, but cannot write formal reports.

**Useful labels:**

- process tutorial
- material/glaze evidence
- firing evidence
- business/studio evidence
- visual-only topic not proven by transcript
- low relevance/noise

## Stage 3: Comments Tiny Probe

**Difficulty:** medium-high  
**Priority:** optional, after transcript proves useful  
**Goal:** Find user pain points and demand signals from comments.

**Why later:**

Comments are useful, but noisy. They can reveal:

- beginner confusion
- tool/material questions
- pricing concerns
- glaze defect pain points
- studio workflow bottlenecks

They can also contain spam, jokes, unrelated chatter, and personal data.

**Files likely involved later:**

- Create: `scripts/probe_youtube_comments.py`
- Create: `scripts/probe_youtube_comments.sh`
- Create: `tests/test_youtube_comments_probe.py`
- Create: `docs/changes/00XX-youtube-comments-tiny-probe.md`

**Required behavior later:**

- Default dry-run.
- Real request requires explicit confirmation.
- Use only an approved and documented provider/API; do not guess endpoints or response shapes.
- Fetch a very small comment sample only.
- Redact or skip personal data where practical.
- Do not save raw provider responses, commenter identifiers, profile URLs, or unnecessary personal data.
- Store only short excerpts and aggregate pain-point categories.
- Do not update formal reports.

**Readiness gate:**

Comments move forward only if they produce clear ceramic pain points that metadata/transcript did not already provide.

## Stage 4: Thumbnail / Keyframe Visual Probe

**Difficulty:** medium-high  
**Priority:** after text layers are stable  
**Goal:** Let the bot inspect a small number of still images from high-value videos.

**Possible value for ceramics:**

- glaze color and surface
- texture
- form and silhouette
- studio process
- kiln/firing visuals
- 3D printed ceramic shape
- exhibition/workshop style

**Potential helpers:**

- `video-frames` skill
- `FFmpeg Video Editor` skill

**Files likely involved later:**

- Create: `scripts/probe_youtube_keyframes.py`
- Create: `scripts/probe_youtube_keyframes.sh`
- Create: `tests/test_youtube_keyframes_probe.py`
- Create: `docs/changes/00XX-youtube-keyframes-probe.md`

**Required behavior later:**

- Do not download full videos by default.
- Prefer provider-supplied thumbnails before any frame extraction.
- If frame extraction is ever used, limit to a tiny number of frames from an explicitly approved local file or approved source.
- Save thumbnails/keyframes only in ignored local output.
- Visual model calls require explicit approval.
- Do not update formal reports.

**Readiness gate:**

Keyframes move forward only if they add ceramic visual evidence that text cannot provide.

## Stage 5: Full Video Understanding

**Difficulty:** high  
**Priority:** Pro version, not mainline  
**Goal:** Combine metadata, transcript, comments, selected visuals, and model review.

**Do not start until:**

- YouTube Search adapter is stable.
- Transcript layer is useful.
- Cost limits are clear.
- Storage rules are clear.
- Visual copyright/privacy boundaries are clear.
- Formal report failure isolation is already implemented.

**Likely output later:**

- a separate enriched evidence record
- not a direct formal trend conclusion
- possibly a Pro-only report appendix

## Recommended Future Order

```text
1. V0.9 minimal YouTube adapter design
2. V0.9 minimal YouTube Search adapter, explicit opt-in only
3. Transcript tiny probe
4. Transcript review
5. Comments tiny probe only if transcript leaves clear gaps
6. Thumbnail/keyframe visual probe
7. Full video understanding as Pro direction
```

## What Not To Do

- Do not jump straight to visual understanding.
- Do not batch-process many videos.
- Do not let DeepSeek or any model rewrite final reports directly.
- Do not combine transcript, comments, and keyframes in one version.
- Do not make YouTube the default live source before repeated evidence across multiple ceramic categories.

## Verification For This Roadmap

This file is documentation-only.

Run:

```bash
git diff --check
git status --short --untracked-files=all
```

Expected:

```text
?? docs/plans/2026-06-30-youtube-video-understanding-roadmap.md
```

Existing unsaved docs from V0.8.7-lite may also appear if not committed yet:

```text
M README.md
M AGENTS.md
?? docs/changes/0030-youtube-readiness-decision-memo.md
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
scripts/*
tests/*
```

## Review

Ask one reviewer to check:

- Is the roadmap appropriately staged?
- Does it avoid jumping to expensive visual analysis?
- Does it preserve the current V0.8.7-lite `wait` decision?
- Does it keep YouTube opt-in and formal-report-safe?
- Does it clearly say no plugin/tool installation is needed now?

Fix blocker findings before saving.
