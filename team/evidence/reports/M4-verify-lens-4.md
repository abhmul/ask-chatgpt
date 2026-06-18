FAIL

# M4 verification lens 4 — adversarial gotcha/safety check

Read: `team/contracts/M4-common.md`, `docs/REWRITE-SPEC.md`, `team/evidence/reports/M4-test-plan.md`, `team/evidence/reports/M4-pytest-authoritative.txt`, `src/ask_chatgpt/`, and `tests/`. Authoritative pytest artifact says: `183 passed in 0.40s`.

## Failing findings

1. **Gotcha #4 is not truly fixed on real CLI ask/scrape `--out` failure paths.** `cli._handle_ask` forwards `out=args.out` into `Session.ask` before it emits stdout itself (`src/ask_chatgpt/cli.py:190-201`), and `Session.ask` writes `--out` using `stdout=_NullStdout()` before returning (`src/ask_chatgpt/session.py:316-317`). If that first file write fails, the exception reaches CLI `main` before `cli._emit_payload(...)`; the payload was written only to `_NullStdout`, so real stdout is suppressed. `scrape` has the same pattern (`src/ask_chatgpt/cli.py:225-226`, `src/ask_chatgpt/session.py:335-336`). The store helper itself is stdout-first, but Session bypasses the real stdout. Current CLI tests use a fake `RecordingSession`, so they do not exercise this real regression.

2. **Gotcha #2 still has a stale-assistant escape hatch after completion.** `Session.ask` passes the completion assistant id into `_select_new_assistant`, but `_select_new_assistant` falls back to `return assistants[-1]` for any assistant whose id differs from `baseline.latest_assistant_id` if the completion id is absent from capture (`src/ask_chatgpt/session.py:555-565`). In a capture-lag or inconsistent-capture case with older pre-baseline assistant ids, this can return stale assistant content instead of failing closed. Tests cover no-op verification and one successful new-id path, but not the adversarial “completion id missing from capture while older assistant exists” case.

## Other checked points

- Gotcha #1: backend capture uses `"".join(parts)` with strict list-of-strings validation (`src/ask_chatgpt/capture.py:552-561`), so it does not invent separators or convert `\widehat`, `\ne`, or `\frac{}{}` to Unicode. Tests pin these tokens and `≠` absence.
- Gotcha #3: `max_total_wait_s` defaults to `None`, progress tokens reset no-activity timing, and timeout salvage persists `created_at=None`. However, a literal `activity_timeout_s: float = 600.0` remains in `Session` (`src/ask_chatgpt/session.py:174`); it is a no-activity default rather than a total cap, but it violates a strict “no hardcoded 600s” grep reading.
- Safety grep: no `datetime.now`, `datetime.utcnow`, `utcnow`, or `time.time` matches in `src/ask_chatgpt`; backend timestamps use backend-derived parsing, and salvage records set `created_at=None`.
- Safety grep: no Playwright import in `src/ask_chatgpt` (only a MockChannel docstring mention). No module-level browser launch was found; CDP real channel is deferred behind `NotImplementedError`.
- Header safety: `HeaderBundle` is `repr=False`, exposes only header names in `redacted()`, and raw mapping persistence strips `authorization`, `cookie`, `headers`, `request_headers`, and `oai-*` keys. I did not find auth/OAI header values being written to JSONL/raw mapping/status by current source paths.
- Offline paths: `history`/`export` are store-only, mock channel methods are scripted, and `chatgpt.com`/`backend-api` strings in offline code are URL construction or BrowserChannel-seam calls, not module-import network activity.
