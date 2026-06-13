# Worker contract — M-009 T2 keystone: never-saw-streaming completion fix (RED-first)

You are a single-editor pi worker. Make ONE surgical, RED-first behavior change to the real/cdp
completion logic. Do NOT touch anything outside the two files named below. Do NOT `git push`.
Do NOT contact chatgpt.com. Use `uv run` for all python/pytest (repo venv); run
`uv sync --all-groups` first if imports fail.

## Why (verified evidence, do not re-litigate)
On the real/cdp channel, `BrowserSession.wait_for_completion` only returns when it has set
`streaming_seen=True` — which happens only if a 0.1s poll catches the stop-button
(`streaming_marker`). The production UC2 path calls `wait_for_completion` TWICE: once in
`src/ask_chatgpt/api.py` (`_ask_chatgpt_with_bundle`), then AGAIN inside
`retrieve_patch_bundle` → `_latest_completed_turn` (`src/ask_chatgpt/patch.py`). On the second
call the response has already finished, so the stop-button is gone and `streaming_seen` can never
be re-established → it loops to the deadline and raises
`ResponseTruncatedError("completion marker did not appear before timeout")`.

This was just CONFIRMED on the REAL site (manager probe): first wait `returned`, second wait
(inside retrieve) raised `ResponseTruncatedError`. The same edge also spuriously truncates an
ultra-fast short reply whose stop-button is never caught between polls. Evidence file:
`orchestration/reports/M-009/T1-uc2-roundtrip.json`.

This fix is load-bearing for T1 (real UC2 round-trip) and T2 (short-response reliability).

## Files you may edit (ONLY these two)
1. `src/ask_chatgpt/driver.py` — the `wait_for_completion` method.
2. `tests/test_driver.py` — add new tests + one new scripted-state class.

## STEP 1 — RED first. Add the failing test(s) BEFORE editing driver.py.
In `tests/test_driver.py`, near the other `_MicroPauseCompletionState` subclasses (around line 578),
add this scripted state (streaming NEVER visible; completion marker present; text stable+non-empty):

```python
class _NeverSawStreamingCompleteState(_MicroPauseCompletionState):
    sentinel = "__TURN_COMPLETE_M009_NEVER_SAW_STREAMING__"

    def text(self) -> str:
        return self.complete_text  # stable, non-empty from t=0

    def streaming_visible(self) -> bool:
        return False  # the stop control was never caught by any poll

    def completion_marker_visible(self) -> bool:
        return True  # copy-turn marker present: the turn is already complete


class _ShortReplyNeverStreamedState(_NeverSawStreamingCompleteState):
    sentinel = "PING"

    def text(self) -> str:
        return "PING"  # one-word reply, stable, non-empty
```

Then add these two tests near the other `test_real_wait_for_completion_*` tests (around line 970):

```python
def test_real_wait_for_completion_returns_when_never_saw_streaming_marker_and_text_stable(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _NeverSawStreamingCompleteState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)

    assert latest is state.turn
    assert state.sentinel in latest.inner_text()
    assert clock.now >= 3.0   # waited the stability window
    assert clock.now < 30.0   # did NOT run to the truncation deadline


def test_real_wait_for_completion_returns_short_reply_that_never_streamed(monkeypatch):
    clock = _ScriptedClock()
    page = _ScriptedCompletionPage(clock)
    state = _ShortReplyNeverStreamedState(clock)
    session = _scripted_real_completion_session(monkeypatch, state, page)

    latest = session.wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)

    assert latest.inner_text() == "PING"
    assert clock.now < 30.0
```

Run ONLY these two new tests and CONFIRM THEY FAIL (RED) on the current driver.py — the current
code raises `ResponseTruncatedError` because `streaming_seen` is never set:
```
uv run pytest tests/test_driver.py -k "never_saw_streaming or short_reply_that_never_streamed" -q
```
Save the RED output verbatim to `orchestration/reports/M-009/T2-RED.txt`.

## STEP 2 — Implement the minimal fix in `src/ask_chatgpt/driver.py`.
Inside `wait_for_completion`, the real/cdp branch currently ends with EXACTLY this block
(verify the surrounding context before editing):

```python
                    if (
                        streaming_seen
                        and not streaming_visible
                        and completion_visible
                        and not_streaming_since is not None
                        and (now - not_streaming_since) >= _REAL_COMPLETION_STABILITY_S
                        and (now - stable_since) >= _REAL_COMPLETION_STABILITY_S
                    ):
                        return latest_assistant
```

Replace that block with EXACTLY:

```python
                    stop_absent_stable = (
                        not streaming_visible
                        and completion_visible
                        and not_streaming_since is not None
                        and (now - not_streaming_since) >= _REAL_COMPLETION_STABILITY_S
                        and (now - stable_since) >= _REAL_COMPLETION_STABILITY_S
                    )
                    # streaming_seen path: streaming was observed, then stopped with completion evidence.
                    # never-saw-streaming path (M-009): the response completed before any 0.1s poll caught
                    # the stop control — an ultra-fast reply, or a SECOND wait_for_completion run on an
                    # already-finished turn (retrieve_patch_bundle re-waits after streaming has ended).
                    # bool(last_text) requires a non-empty latest-turn body so an empty/not-yet-started
                    # turn is never returned; the shared >= _REAL_COMPLETION_STABILITY_S windows above keep
                    # this from firing during a micro-pause or on a stale global marker, because in those
                    # cases the stop control reappears within the window (so streaming_seen becomes True).
                    if stop_absent_stable and (streaming_seen or bool(last_text)):
                        return latest_assistant
```

Do not change anything else. Do not touch the mock path, the `elif self.channel in {"real", "cdp"}`
branch, the deadline/reload logic, or any selector.

## STEP 3 — GREEN + full regression.
1. Re-run the two new tests; CONFIRM THEY PASS. Save to `orchestration/reports/M-009/T2-GREEN.txt`:
   `uv run pytest tests/test_driver.py -k "never_saw_streaming or short_reply_that_never_streamed" -q`
2. Run the two guard tests explicitly and CONFIRM PASS (must not be reopened):
   `uv run pytest tests/test_driver.py -k "micro_pause or premature" -q`
3. Run the FULL default suite and CONFIRM all pass with the SAME count as baseline (209 passed,
   4 deselected). Save the tail to `orchestration/reports/M-009/T2-pytest-full.txt`:
   `uv run pytest -q`

If the full count is not 209 passed / 4 deselected, STOP and report — do not "fix" by deleting tests.

## Report
Write `orchestration/reports/M-009/T2-keystone-worker-report.md` with, in order:
- `Status: DONE` (or PARTIAL/BLOCKED).
- The RED command + verbatim failing output (or a pointer to T2-RED.txt) proving it failed first.
- The exact diff of driver.py and test_driver.py (`git diff --stat` plus the driver.py hunk).
- The GREEN output + guard-test output + full-suite tail (`209 passed, 4 deselected`).
- Telemetry lines: `ESTIMATE: T2-keystone <minutes>m`, `ACTUAL: T2-keystone <minutes>m`,
  an explicit end timestamp from `date -Iseconds`, and if any rework leg:
  `REWORK-CAUSE: <spec-gap|env-drift|frozen-file|dependency-rot|other>`.
- Do NOT commit; the manager commits. Do NOT `git push`.
