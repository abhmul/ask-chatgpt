# M-008b · E6 (pi, single editor) — Hardened real/cdp completion (T2 stability fallback) — fixes intermittent short-response clip

You are the SINGLE EDITOR. OFFLINE only (no real site/network/`127.0.0.1:9222`). RED-first TDD. NEVER `git push`. This is a CORE driver change — be precise and keep the WHOLE suite green.

## Why (real ground truth — manager-observed on chatgpt.com over CDP)
A multi-turn temp-chat continuity probe INTERMITTENTLY clipped a short assistant response: a recall reply `ASKCG-NONCE-<32hex>` was captured as just `ASKC` (4 chars), and a plant reply read empty — i.e. `wait_for_completion` returned **prematurely**, mid-stream. Root cause in `src/ask_chatgpt/driver.py:wait_for_completion` (real/cdp branch, ~352-371): completion fires on `not streaming_visible AND completion_visible`, where
```
completion_visible = completion_present_on_latest or self._present("completion_marker")
```
The GLOBAL `self._present("completion_marker")` is True because a PRIOR turn's copy button persists; and the latest turn's own copy button appears EARLY during streaming. So for turn N≥2, `completion_visible` is trivially True from the start, collapsing completion to "stop button momentarily absent" — which fires before/at the very start of streaming (before the stop button registers) and clips the response. This is the same failure class as the retracted M-007 `…1F3845_` clip. The fix is the hardened stability fallback the M-008a gate + MISSION-008b T2.3 anticipated.

## Required design (transcribe exactly)
In the real/cdp branch of `wait_for_completion`, replace the completion trigger with: **complete only when streaming was SEEN, is now SUSTAINEDLY absent, AND body text has been STABLE — both for a sustained window — with the latest turn's own completion affordance present.** Concretely, track across poll iterations:
- `streaming_seen` (bool): set True once `self._present("streaming_marker")` (stop button) is observed True at least once this wait.
- `not_streaming_since` (float|None): timestamp when the stop button most recently became absent; reset to None whenever the stop button is present.
- `stable_since` (float): timestamp when `latest_text` most recently CHANGED (reset on every text change; the progress-deadline extension already keys on text change — reuse that point).
- New constant `_REAL_COMPLETION_STABILITY_S = 3.0` (clearly named; this is the reintroduced stability window MISSION-008b T1.2 said to name. Justify 3.0 in your report: it must exceed the largest real mid-stream pause — the M-008a micro-pause was ~2.3s — with margin, while keeping per-turn completion latency acceptable.)

Scope the completion affordance to the **latest turn** (remove the GLOBAL `or self._present("completion_marker")` / `or self._present("completion_affordance")` fallbacks): use only `completion_present_on_latest` (and, when a `completion_affordance` selector is mapped, `latest_assistant.locator(completion_affordance_selector).count() > 0`).

Completion condition (real/cdp):
```
completion_visible = <latest-turn-scoped copy/affordance present>
if (streaming_seen
        and not streaming_visible
        and completion_visible
        and not_streaming_since is not None
        and (now - not_streaming_since) >= _REAL_COMPLETION_STABILITY_S
        and (now - stable_since) >= _REAL_COMPLETION_STABILITY_S):
    return latest_assistant
```
Keep the existing absolute wall-clock ceiling (`max_total_wait_s` / `_REAL_COMPLETION_CEILING_S`) and the progress-aware `deadline` extension and the `ResponseTruncatedError` timeout EXACTLY as they are — this change only makes the *positive* completion trigger stricter; it must NOT fail open and must NOT remove the ceiling/timeout.

Edge to respect: the FIRST poll's text seeds `last_text` WITHOUT counting as a change (so `stable_since` starts at the wait start). `streaming_seen` starting False prevents returning a stale PRIOR turn before the new turn's streaming begins.

## RED-first (capture RED)
Add a scripted state `_PrematureGlobalMarkerState(_MicroPauseCompletionState)` (in `tests/test_driver.py`, reuse `_ScriptedClock`/`_ScriptedCompletionPage`/`_scripted_real_completion_session`) modeling the real bug:
- `completion_marker_visible()` → **True from t=0** (simulates the persistent global/prior-turn copy button).
- `streaming_visible()` → False for t<0.4 (stop button not yet registered), True for 0.4<=t<1.2 (streaming), False for t>=1.2 (done).
- `text()` → returns a partial early fragment for small t (e.g. first ~4 chars of the sentinel-bearing body), grows while streaming, and reaches the full `complete_text` at t>=1.2 and stays stable after.
RED test `test_real_wait_for_completion_does_not_return_prematurely_when_global_marker_present`: with `_scripted_real_completion_session`, assert `wait_for_completion(timeout_s=30, max_total_wait_s=60)` returns the FULL `complete_text` (containing the terminal sentinel), NOT the early partial. Against the CURRENT code this FAILS (returns the early partial fragment, missing the sentinel) — capture that RED to `orchestration/reports/M-008b/E6-RED.txt` (run the new test BEFORE implementing the fix). Then implement → GREEN.

## No-regression (the hard part — update affected scripted tests)
The added stability/seen requirements change WHEN completion fires for the existing real/cdp scripted tests. Re-run and UPDATE as needed so ALL pass (advance the scripted clock / hold text+markers stable long enough for the 3s windows; the scripted `wait_for_timeout` advances the `_ScriptedClock`, so the windows are reached deterministically):
- `test_real_wait_for_completion_returns_after_completion_marker_visible`
- `test_real_wait_for_completion_does_not_return_midstream_micro_pause_without_completion_evidence` (MUST still prove NO premature return during the micro-pause AND eventual complete return)
- `test_real_wait_for_completion_honors_optional_completion_affordance_when_marker_absent`
- `test_real_wait_for_completion_extends_deadline_while_body_text_grows`
- `test_real_wait_for_completion_times_out_when_body_text_never_stabilizes`
- `test_real_wait_for_completion_caps_progress_extensions_at_absolute_ceiling` (T1 ceiling — must still fire `ResponseTruncatedError` at the ceiling)
Do NOT weaken any assertion to pass — adjust the SCRIPTED STATE timing/clock so the real behavior is exercised. If a test's intent conflicts with the new design, fix the state, not the assertion; explain in your report.

## Verify
- `uv sync --all-groups` then `uv run pytest -q` → MUST be `>=208 passed, 4 deselected, 0 real_site` (you added >=1 test). Save to `orchestration/reports/M-008b/E6-pytest.txt` with the summary line + exit code + confirm 0 real_site.
- `uv run pytest --collect-only -q tests/test_truncation_real.py tests/test_continuity_real.py` → still 3 collected.

## Report `orchestration/reports/M-008b/E6-worker-report.md`
STATUS; the RED evidence (quote E6-RED.txt; the new test file:line; what the old code returned — the partial fragment); the driver diff summary + the exact new completion condition + constant + your 3.0s justification; which existing tests you updated and HOW (scripted-state timing changes, not assertion weakening); full-suite summary (>=208 passed / 4 deselected / 0 real_site); commit sha (no push); `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE: spec-gap` (the M-008a affordance-only design was insufficient for real multi-turn).

Commit the slice. NEVER `git push`. OFFLINE only.
