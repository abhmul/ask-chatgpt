# M-008b · E6b (pi, single editor) — Restore the GLOBAL completion-marker fallback (E6 over-scoped it; real copy button is outside the turn element)

You are the SINGLE EDITOR. OFFLINE only (no real site/network/`127.0.0.1:9222`). NEVER `git push`.

## Why (real ground truth — manager-confirmed on chatgpt.com over CDP)
E6 scoped `completion_visible` to the latest assistant turn (`completion_present_on_latest` only) and removed the GLOBAL `self._present("completion_marker")` fallback. That is WRONG for the real DOM: a read-only probe confirmed the copy button `button[data-testid="copy-turn-action-button"]` is **NOT a descendant** of `[data-message-author-role="assistant"]` (DOM probe: `copiesInsideLastAssistant: 0`, `copyHasAssistantAncestor: false`, `globalCopyCount: 2`). With the scoped-only check, `completion_visible` is NEVER true on the real site, so `wait_for_completion` TIMES OUT (`ResponseTruncatedError`) — a regression. The premature-clip protection comes from the `streaming_seen` + sustained-stop-absent + text-stable guards (added in E6), NOT from scoping. So: restore the global fallback, keep all the E6 guards.

## The change (`src/ask_chatgpt/driver.py`, `wait_for_completion` real/cdp branch)
Restore the GLOBAL completion-marker / affordance fallbacks while KEEPING the E6 guards (`streaming_seen`, `not_streaming_since`, `stable_since`, `_REAL_COMPLETION_STABILITY_S`, the absolute ceiling, and the progress deadline). Concretely, compute:
```
completion_visible = completion_present_on_latest or self._present("completion_marker")
completion_affordance_selector = self._optional_selector("completion_affordance")
if completion_affordance_selector is not None:
    completion_visible = (
        completion_visible
        or latest_assistant.locator(completion_affordance_selector).count() > 0
        or self._present("completion_affordance")
    )
```
and KEEP the completion trigger exactly as E6 left it:
```
if (streaming_seen and not streaming_visible and completion_visible
        and not_streaming_since is not None
        and (now - not_streaming_since) >= _REAL_COMPLETION_STABILITY_S
        and (now - stable_since) >= _REAL_COMPLETION_STABILITY_S):
    return latest_assistant
```
Add a code comment right there: `# completion_marker (copy-turn-action button) lives OUTSIDE the assistant turn element on the real DOM (verified M-008b), so the global presence check is required; premature completion is prevented by streaming_seen + sustained stop-absence + text stability, NOT by scoping.`

Do NOT change the constants, the ceiling, the timeout/ResponseTruncatedError, the mock path, or the `reloads_streaming_fixture` logic.

## Regression-guard test (add to `tests/test_driver.py`)
Add a scripted state `_GlobalOnlyMarkerCompletionState(_MicroPauseCompletionState)` modeling the REAL DOM (copy button global-only, NOT in the turn):
- `present("completion_marker")` → True once streaming has ended (mirror a normal turn: e.g. False while streaming, True after), i.e. the GLOBAL marker is present at completion.
- `selector_count("#complete")` (the TURN-scoped count via `_ScriptedTurnLocator`) → ALWAYS 0 (the copy button is not inside the turn element).
- `streaming_visible()` → True for an interval then False; `text()` → grows then stabilizes to `complete_text`.
Test `test_real_wait_for_completion_completes_when_marker_is_global_only_not_in_turn`: assert `wait_for_completion(timeout_s=30, max_total_wait_s=60)` returns `complete_text` (with the sentinel) — i.e. completion fires via the GLOBAL fallback even though the turn-scoped count is 0. This guards against re-introducing the E6 over-scoping. (Confirm it FAILS if the global fallback is removed.)

Keep the existing E6 RED test `test_real_wait_for_completion_does_not_return_prematurely_when_global_marker_present` PASSING (it proves streaming_seen still prevents the premature partial). Both must pass.

## Verify
- `uv sync --all-groups` then `uv run pytest -q` → MUST be `>=209 passed, 4 deselected, 0 real_site` (you added 1 test). Save to `orchestration/reports/M-008b/E6b-pytest.txt` (summary line + exit code + confirm 0 real_site).
- `uv run pytest --collect-only -q tests/test_truncation_real.py tests/test_continuity_real.py` → still 3 collected.

## Report `orchestration/reports/M-008b/E6b-worker-report.md`
STATUS; the driver diff (global fallback restored; trigger unchanged); the new regression-guard test (and confirmation the premature-clip RED test still passes); full-suite summary (>=209 passed / 4 deselected / 0 real_site); commit sha (no push); `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE: spec-gap` (E6 over-scoping vs real DOM).

Commit the slice. NEVER `git push`. OFFLINE only.
