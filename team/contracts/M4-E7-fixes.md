# M4-E7 — Fix the verification-panel findings (SINGLE EDITOR, TDD)

**READ FIRST, IN FULL:** `team/contracts/M4-common.md` (safety + 12 MANAGER DECISIONS — esp. **3** stdout-AND-out, **Q6/clipboard fail-closed**). The terminal verification panel (5 lenses over commit `66b5533`, suite 183 passed) found 3 REAL defects + 2 cheap correctness notes that block M4 DONE. Fix them, TDD, each with a NEW falsifiable test that exercises the ADVERSARIAL path the current tests miss. Branch `rewrite-v2`; build on committed E1–E6; keep the existing 183 tests GREEN; OFFLINE only; do not touch `cli.py`'s loop/JSONL behavior beyond what's needed.

The panel lens reports are at `team/evidence/reports/M4-verify-lens-{1..5}.md` (read lens-2 and lens-4 for context). The manager has re-derived all three defects from the committed code — they are real.

## DEFECT D-A [HIGH, gotcha #4] — `--out` failure suppresses stdout on the REAL Session path
`Session.ask` (`src/ask_chatgpt/session.py:316-317`) and `Session.scrape` (`:335-336`) write `--out` INTERNALLY via `self.store.emit_payload(..., stdout=_NullStdout())` BEFORE the CLI prints stdout. If that out-write raises, the exception propagates and the CLI never prints stdout → gotcha #4 violated; on success the out file is written twice. Current CLI tests use a fake `RecordingSession`, so the real path is uncovered.
**Fix:** Make the **CLI the single owner** of stdout-AND-out for `ask`/`scrape`. REMOVE the `if out is not None: ...emit_payload(..., stdout=_NullStdout())` blocks from `Session.ask`/`Session.scrape`. In `cli.py`, for `ask`/`scrape`: print the payload to **stdout FIRST** (via the stdout-first store helper), THEN atomic-write `--out`; if the out-write fails, stdout was already emitted and the `StoreError` maps to stderr + its exit code. (Keep the `out` kwarg in the Session signatures for API compatibility, but it no longer writes — or drop it from the internal flow; CLI owns output.)
**New falsifiable test:** drive the REAL `Session.ask(channel=mock)` (successful send) through the CLI with an `--out` path whose write is injected to FAIL (e.g. monkeypatch `atomic_write_payload`/`emit_payload` out-write to raise, or point `--out` at an unwritable path); assert the assistant `content_markdown` STILL appears on stdout (gotcha #4 holds), and the error is surfaced on stderr with the right exit. A reverted fix (out-before-stdout) must RED this.

## DEFECT D-B [MED-HIGH, Q6 clipboard fail-closed] — salvage auto-reads the clipboard
`completion.salvage_partial` (`src/ask_chatgpt/completion.py:232`) calls `tab.channel.read_clipboard(tab)` UNCONDITIONALLY (it only avoids using the result when the mock raises). Lead decision Q6 / M3 §4.4: **never auto-read the clipboard**; copy/clipboard salvage is allowed ONLY behind an explicit attended opt-in (which M4 does not expose).
**Fix:** Default salvage order = backend partial → **DOM** (skip the clipboard/copy step entirely unless an explicit `allow_clipboard=True` opt-in is threaded — defaults `False`, not wired in M4). Do NOT call `read_clipboard` by default. If neither backend nor DOM yields salvageable content, fail closed (`CaptureFailedClosedError`/`HumanActionNeededError`), never a fabricated complete record.
**New falsifiable test:** a mock whose `read_clipboard` WOULD return text (grant it) — assert salvage with the default (no opt-in) does NOT call `read_clipboard` (assert via the mock call counter / a `read_clipboard` that raises `AssertionError` if invoked) and uses the DOM partial instead. A reverted fix must RED this.

## DEFECT D-C [MED, gotcha #2 hardening] — stale-assistant escape hatch
`_select_new_assistant` (`src/ask_chatgpt/session.py:555-566`) returns `assistants[-1]` whenever the verified completion `assistant_message_id` is NOT found among captured assistants. In a capture-lag/inconsistent case this can return an older (non-baseline) assistant's content instead of failing closed.
**Fix:** When `assistant_message_id is not None` and it is NOT present among the captured (non-baseline) assistants → **fail closed** (raise `InternalError`/`CaptureFailedClosedError` so the caller salvages), do NOT substitute `assistants[-1]`. The `assistants[-1]` fallback may remain ONLY for the defensive `assistant_message_id is None` case.
**New falsifiable test:** completion returns a verified new id `a-new` that is ABSENT from the captured records, while an older non-baseline assistant `a-mid` IS present → `_select_new_assistant` (and `Session.ask`) must NOT return `a-mid`; it fails closed (and salvages). A reverted fix must RED this.

## NOTE N1 [conservative default] — `stream_status` must not be the default
`poll_backend_completion(..., prefer_lightweight=True)` defaults to `/backend-api/conversation/<id>/stream_status`, which M3 §5 says is a HYPOTHESIS not to be relied on before M5 evidence. **Fix:** make the conservative default NOT prefer `stream_status` (e.g. default `prefer_lightweight=False`, or gate `stream_status` behind an explicit flag), so the future real channel does not depend on an unverified endpoint. Mock tests that exercise the lightweight path may pass the flag explicitly. Add/adjust a test pinning the conservative default.

## NOTE N2 [correctness] — per-message `model.slug`
`capture.py` sets `model.slug` only from top-level `default_model_slug`/send-context, ignoring per-message `message.metadata.model_slug`. M3 §3.3: slug from per-message metadata WHERE AVAILABLE, else top-level default. **Fix:** prefer per-message `metadata.model_slug` when present, else top-level default. **New test:** a fixture where one assistant message has a message-level `model_slug` differing from the top-level default → that record's `model.slug` is the message-level value.

## (N3 `completion` node-id fallback is DEFERRED to M5 — note it in your handoff, do not fix now unless trivial.)

## TDD + acceptance
Vertical slices; observe RED before GREEN for each NEW test (revert-the-fix → RED). Keep ALL existing 183 tests green. Final `uv run pytest` GREEN. The new tests must exercise the real/adversarial paths (failing `--out`, clipboard-would-succeed, completion-id-absent, message-level model_slug, conservative stream_status default).

## Commit + handoff
- Commit on `rewrite-v2`: `git add src/ask_chatgpt tests`. Plain message e.g. `M4: fix verification-panel findings (out-stdout coupling, clipboard fail-closed, stale-assistant guard, conservative defaults)`. **NO `git add -A`, NO Co-Authored-By.** `git status --porcelain` first; never stage `issues/...controller.mjs`, `team/state/live-state.json`, `human/`.
- Handoff to **`team/evidence/handoffs/M4-E7-fixes.md`**: STATUS line 1; pasted FULL `uv run pytest` summary; for EACH of D-A/D-B/D-C/N1/N2: the fix + the new test name + the RED-on-revert evidence; commit hash + `git log -1 --oneline` + `git show --stat HEAD`; confirm gotcha #4 now holds on the REAL Session path; blockers; note N3 deferral to M5.
