# M-008b / E6 worker report

STATUS: DONE

## RED evidence

RED was captured before the driver change in `orchestration/reports/M-008b/E6-RED.txt` for `tests/test_driver.py:921` (`test_real_wait_for_completion_does_not_return_prematurely_when_global_marker_present`). The scripted `_PrematureGlobalMarkerState` models a persistent global prior-turn marker from t=0, no stop button until t=0.4, streaming from 0.4s to 1.2s, and full sentinel-bearing text only at t>=1.2.

```text
E       AssertionError: returned premature partial at t=0.0s length=4 text='M008'
E       assert 'M008' == 'M008A-LINE-0...TURE_GLOBAL__'
...
FAILED tests/test_driver.py::test_real_wait_for_completion_does_not_return_prematurely_when_global_marker_present
1 failed in 0.09s
EXIT_CODE=1
```

Old code returned the early partial fragment `M008`, missing `__TURN_COMPLETE_M008B_PREMATURE_GLOBAL__`; the hardened code returns the full `complete_text`.

## Driver diff summary

Implemented `_REAL_COMPLETION_STABILITY_S = 3.0` in `src/ask_chatgpt/driver.py`, tracked `streaming_seen`, `not_streaming_since`, and `stable_since`, seeded first-poll body text without treating it as progress, and kept the existing `deadline`, `_REAL_COMPLETION_CEILING_S`/`max_total_wait_s`, and `ResponseTruncatedError("completion marker did not appear before timeout")` timeout path intact. Removed the global positive-evidence fallbacks from the real/CDP completion trigger: completion evidence is now only latest-turn-scoped `completion_marker`, plus latest-turn-scoped optional `completion_affordance` when mapped. I also let CDP attached to the loopback mock fixture use the existing reload-to-advance-streaming fixture path; this is test-harness-only for `_is_loopback_http_url(self._base_url)` and does not weaken real-site completion.

Exact new positive completion condition:

```python
completion_visible = completion_present_on_latest
if completion_affordance_selector is not None:
    completion_visible = completion_visible or latest_assistant.locator(completion_affordance_selector).count() > 0
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

The 3.0s stability window intentionally exceeds the largest observed real mid-stream pause from M-008a (~2.3s) with ~0.7s margin, while adding only a bounded per-turn latency after actual streaming stops.

## Tests updated

- Added `_PrematureGlobalMarkerState` and `test_real_wait_for_completion_does_not_return_prematurely_when_global_marker_present` to prove the old global fallback returned `M008` and the new logic waits for the full sentinel-bearing text.
- Added `_StableMarkerCompletionState` and converted `test_real_wait_for_completion_returns_after_completion_marker_visible` to scripted-clock timing: streaming is seen until 0.2s, latest marker appears after 0.2s, and assertions require the 3s stability wait.
- Kept `test_real_wait_for_completion_does_not_return_midstream_micro_pause_without_completion_evidence` assertions intact; the existing micro-pause state already delays latest completion evidence and now naturally returns only after the final stable window.
- Updated `_ImmediateAffordanceCompletionState` and `test_real_wait_for_completion_honors_optional_completion_affordance_when_marker_absent`: streaming is seen until 0.2s, the latest-turn affordance appears after 0.2s, timeout is long enough for the 3s window, and the assertion now requires waits/clock progress rather than immediate return because immediate return conflicts with the new design.
- Updated `test_real_wait_for_completion_extends_deadline_while_body_text_grows` timing to `timeout_s=3.5, max_total_wait_s=6.0`; the initial deadline would be too early, body growth extends it, and the test still asserts full text before the ceiling.
- Strengthened `test_real_wait_for_completion_times_out_when_body_text_never_stabilizes` so streaming is seen and completion evidence is present; the timeout now depends on unstable body text rather than absent completion evidence.
- `test_real_wait_for_completion_caps_progress_extensions_at_absolute_ceiling` remains unchanged and still proves `ResponseTruncatedError` at the absolute ceiling.
- Updated CDP loopback attach tests to script a one-read streaming mock response and use `timeout_s=6`, so the real/CDP branch observes streaming before completing under the new stability rule.

## Verification

`orchestration/reports/M-008b/E6-pytest.txt`:

```text
208 passed, 4 deselected in 72.10s (0:01:12)
PYTEST_EXIT_CODE=0
real_site executed: 0 (ASK_CHATGPT_REAL unset; pytest addopts deselect real_site)
```

`orchestration/reports/M-008b/E6-collect-only.txt` confirms the targeted real-tier collect-only check still lists 3 tests and exits 0.

## Commit

Implementation/evidence commit sha: `a058237a30ef6c48aa2260eea726ffe28d43dd71`.

ESTIMATE: E6 60m
ACTUAL: E6 95m
REWORK-CAUSE: spec-gap
