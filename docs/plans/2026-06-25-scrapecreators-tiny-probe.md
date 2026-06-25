# ScrapeCreators Tiny Live Probe Implementation Plan

> **For Claude / Codex:** REQUIRED READING: read `AGENTS.md`, `docs/live-readiness-checklist.md`, and this plan before implementing. Do not call ScrapeCreators API unless the user explicitly confirms a real key-backed probe.

**Goal:** Build a tiny, opt-in ScrapeCreators Reddit probe that can verify one key-backed request without updating formal reports or consuming API quota accidentally.

**Architecture:** Keep the probe separate from the normal report pipeline. The tiny probe should live under `scripts/`, write only to `local_outputs/`, and keep `scrapecreators_reddit` as `planned` in `config/data_sources.json` until a later version turns it into a real `TrendSource`.

**Tech Stack:** Python standard library only, existing `sources/scrapecreators_source.py` readiness helpers, local ignored outputs under `local_outputs/`, standard `unittest`.

---

## Plain-Language Summary

V0.6.3 should be a safe “knock once” test.

It should answer only one question:

> Can this machine, with this key, make one tiny ScrapeCreators Reddit request?

It should not generate a formal trend report. It should not run all ceramic keywords. It should not update `reports/report.md`, `reports/latest.md`, or `reports/archive/`.

## Hard Boundaries

V0.6.3 must not:

- Update `reports/report.md`.
- Update `reports/latest.md`.
- Write to `reports/archive/`.
- Mark `scrapecreators_reddit` as `available`.
- Make ScrapeCreators the default live source.
- Run without an explicit live confirmation flag.
- Print `SCRAPECREATORS_API_KEY` or `SCRAPE_CREATORS_API_KEY`.
- Store API output outside `local_outputs/`.
- Install `yt-dlp`.
- Connect YouTube, Pinterest, Instagram, or GitHub Actions.
- Modify `/Users/zhuyixiao/Documents/GitHub/last30days-skill`.

V0.6.3 may:

- Read `SCRAPECREATORS_API_KEY` from the environment.
- Make one tiny request only after explicit confirmation.
- Write sanitized probe state to `local_outputs/scrapecreators_probe_state.json`.
- Write a sanitized API response summary to `local_outputs/scrapecreators_probe.json`.
- Write errors to `local_outputs/scrapecreators_probe_error.md`.
- Classify common failures: missing key, unauthorized, forbidden, rate limited, quota/billing, timeout, network error, parse error.

## Before Implementation

Do not guess the ScrapeCreators endpoint or response shape.

Before writing the actual request code, use one of these sources:

- Official ScrapeCreators documentation supplied by the user.
- Official ScrapeCreators website/API docs, if the user asks Codex to look it up.
- A small redacted sample response supplied by the user.

If the endpoint, parameters, or auth header are unknown, implement only the dry-run/readiness path and leave the network call disabled.

## Proposed CLI

Readiness-only, no network:

```bash
bash scripts/probe_scrapecreators_reddit.sh
```

Explicit real tiny probe:

```bash
bash scripts/probe_scrapecreators_reddit.sh --confirm-live-api
```

Optional narrow overrides:

```bash
bash scripts/probe_scrapecreators_reddit.sh --confirm-live-api --topic "ceramic glaze" --limit 2
```

Rules:

- Default topic: `ceramic glaze`
- Default limit: `1`
- Maximum limit: `3`
- No confirmation flag means no network.
- Missing key means no network.
- Planned source guard remains in place for the main report CLI.

## Output Files

All probe outputs must stay ignored by Git:

```text
local_outputs/scrapecreators_probe.json
local_outputs/scrapecreators_probe_state.json
local_outputs/scrapecreators_probe_error.md
```

Do not add these files to Git.

The state file should include:

```json
{
  "source_id": "scrapecreators_reddit",
  "status": "success_or_failure",
  "error_type": "missing_key_or_401_or_403_or_429_or_quota_or_timeout_or_network_error",
  "topic": "ceramic glaze",
  "limit": 1,
  "requested_at": "ISO timestamp",
  "network_request_attempted": false,
  "report_files_updated": false
}
```

Never include the API key in state, error, or JSON output.

## Task 1: Tests For Probe Safety

**Files:**

- Create: `tests/test_scrapecreators_probe.py`
- Modify: none

**Step 1: Write tests for no-network default**

Test that calling the probe main function without `--confirm-live-api`:

- exits successfully,
- does not call `urllib.request.urlopen`,
- writes state with `network_request_attempted: false`,
- does not create or touch report paths.

**Step 2: Write tests for missing key**

Test that calling with `--confirm-live-api` but no key:

- does not call `urlopen`,
- returns a clear missing-key status,
- writes an error markdown under `local_outputs` when an output path is provided,
- never prints a secret.

**Step 3: Write tests for limit guard**

Test that `--limit 99` is rejected or clamped to `3`.

**Step 4: Write tests for HTTP classification**

Mock `urlopen` errors and assert:

- 401 -> `unauthorized_401`
- 403 -> `forbidden_403`
- 429 -> `rate_limited_429`
- quota/billing text -> `quota_or_billing`
- timeout -> `timeout`

**Step 5: Run tests**

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_scrapecreators_probe
```

Expected: tests fail before implementation, then pass after the probe exists.

## Task 2: Probe Script Skeleton

**Files:**

- Create: `scripts/probe_scrapecreators_reddit.py`
- Create: `scripts/probe_scrapecreators_reddit.sh`
- Modify: none

**Step 1: Add argument parsing**

Required arguments:

- `--confirm-live-api`
- `--topic`, default `ceramic glaze`
- `--limit`, default `1`, max `3`
- `--state-file`, default `local_outputs/scrapecreators_probe_state.json`
- `--output`, default `local_outputs/scrapecreators_probe.json`
- `--error-file`, default `local_outputs/scrapecreators_probe_error.md`

**Step 2: Add readiness gate**

Use `check_scrapecreators_readiness()` from `sources/scrapecreators_source.py`.

If no key:

- print missing-key guidance,
- write state,
- do not call network,
- exit cleanly.

**Step 3: Add confirmation gate**

If key exists but `--confirm-live-api` is absent:

- print that no network was attempted,
- write state,
- do not call network,
- exit cleanly.

## Task 3: Real Request Path

**Files:**

- Modify: `scripts/probe_scrapecreators_reddit.py`
- Test: `tests/test_scrapecreators_probe.py`

**Step 1: Confirm official API details**

Before implementing this step, confirm:

- base URL,
- endpoint path,
- auth method,
- query parameter names,
- response shape,
- rate-limit headers if documented.

Do not invent these values.

**Step 2: Add a tiny request helper**

The helper should:

- include the API key only in the required auth location,
- request one topic,
- request at most three results,
- use a short timeout,
- use a clear User-Agent if allowed.

**Step 3: Save response locally**

Write a sanitized response summary only to:

```text
local_outputs/scrapecreators_probe.json
```

Default output should include only the fields needed to confirm the probe worked, such as status, item count, a few title/url/subreddit fields if present, and response-shape notes.

Raw response saving must stay disabled by default. Only add a separate explicit debug flag after confirming the official response never contains secrets, request headers, account data, billing data, or private metadata.

## Task 4: Error Handling

**Files:**

- Modify: `scripts/probe_scrapecreators_reddit.py`
- Test: `tests/test_scrapecreators_probe.py`

**Step 1: Classify known failures**

Use these error types:

- `missing_key`
- `not_confirmed`
- `unauthorized_401`
- `forbidden_403`
- `rate_limited_429`
- `quota_or_billing`
- `timeout`
- `network_error`
- `parse_error`
- `unknown_error`

**Step 2: Write local error report**

Write to:

```text
local_outputs/scrapecreators_probe_error.md
```

Include:

- error type,
- time,
- topic,
- limit,
- whether a network request was attempted,
- next step,
- reminder that formal reports were not touched.

Never include the API key.

## Task 5: Documentation Update

**Files:**

- Modify: `README.md`
- Modify: `docs/workflow.md`
- Modify: `docs/live-readiness-checklist.md`
- Add: `docs/changes/NNNN-scrapecreators-tiny-probe.md`

**Required wording:**

- Tiny probe is opt-in.
- It writes only to `local_outputs/`.
- It does not update formal reports.
- It is not the final ScrapeCreators data source.
- `scrapecreators_reddit` remains `planned` until a later version.

## Task 6: Verification

Run:

```bash
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m py_compile scripts/probe_scrapecreators_reddit.py sources/scrapecreators_source.py
/Users/zhuyixiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover tests
bash scripts/check_scrapecreators_ready.sh
bash scripts/run_mock.sh
git diff --check
```

If no real key is configured, do not run the confirmed live probe.

If a real key is configured, only run the confirmed probe after the user explicitly approves the exact command.

## Task 7: Review

Because this touches API-key and live-network boundaries, final review should include:

- security review for key leakage,
- flow review for report protection,
- check that `local_outputs/` is ignored,
- check that `reports/report.md`, `reports/latest.md`, and `reports/archive/` are not touched by the probe.

## Exit Criteria

V0.6.3 is complete when:

- no-confirm mode is safe and tested,
- missing-key mode is safe and tested,
- confirmed live mode is implemented only from official API details,
- probe output stays in `local_outputs/`,
- formal reports are untouched,
- no key appears in terminal output, markdown, JSON, state, tests, or Git diff.

## Follow-Up

Only after a successful tiny probe should V0.6.4 consider:

- a real `ScrapeCreatorsSource.fetch()`,
- converting ScrapeCreators response into the `last30days` shape,
- changing `scrapecreators_reddit` from `planned` to `available`,
- allowing `--data-source scrapecreators_reddit` in the main report flow.
