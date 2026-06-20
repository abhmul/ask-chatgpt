Status: PARTIAL

RED command requested: `uv run pytest tests/test_driver.py -k "never_saw_streaming or short_reply_that_never_streamed" -q`

RED evidence: see `orchestration/reports/M-009/T2-RED.txt`. Note: the exact command was attempted before editing `driver.py`, but it did not terminate under the current fake-clock/deadline behavior; the saved RED file is the same pytest selection run with pytest faulthandler timeout enabled, proving the new test stuck in `BrowserSession.wait_for_completion` before the fix.

`git diff --stat`:

```
 src/ask_chatgpt/driver.py | 16 ++++++++++++----
 tests/test_driver.py      | 46 ++++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 58 insertions(+), 4 deletions(-)
```

`src/ask_chatgpt/driver.py` hunk:

```diff
diff --git a/src/ask_chatgpt/driver.py b/src/ask_chatgpt/driver.py
index 36e7055..4edeb39 100644
--- a/src/ask_chatgpt/driver.py
+++ b/src/ask_chatgpt/driver.py
@@ -387,14 +387,22 @@ class BrowserSession:
                             or latest_assistant.locator(completion_affordance_selector).count() > 0
                             or self._present("completion_affordance")
                         )
-                    if (
-                        streaming_seen
-                        and not streaming_visible
+                    stop_absent_stable = (
+                        not streaming_visible
                         and completion_visible
                         and not_streaming_since is not None
                         and (now - not_streaming_since) >= _REAL_COMPLETION_STABILITY_S
                         and (now - stable_since) >= _REAL_COMPLETION_STABILITY_S
-                    ):
+                    )
+                    # streaming_seen path: streaming was observed, then stopped with completion evidence.
+                    # never-saw-streaming path (M-009): the response completed before any 0.1s poll caught
+                    # the stop control — an ultra-fast reply, or a SECOND wait_for_completion run on an
+                    # already-finished turn (retrieve_patch_bundle re-waits after streaming has ended).
+                    # bool(last_text) requires a non-empty latest-turn body so an empty/not-yet-started
+                    # turn is never returned; the shared >= _REAL_COMPLETION_STABILITY_S windows above keep
+                    # this from firing during a micro-pause or on a stale global marker, because in those
+                    # cases the stop control reappears within the window (so streaming_seen becomes True).
+                    if stop_absent_stable and (streaming_seen or bool(last_text)):
                         return latest_assistant
             elif self.channel in {"real", "cdp"}:
                 now = time.monotonic()
```

`tests/test_driver.py` hunk:

```diff
diff --git a/tests/test_driver.py b/tests/test_driver.py
index df569e7..a67fab0 100644
--- a/tests/test_driver.py
+++ b/tests/test_driver.py
@@ -543,6 +543,26 @@ class _GlobalOnlyMarkerCompletionState(_MicroPauseCompletionState):
         return super().selector_count(selector)
 
 
+class _NeverSawStreamingCompleteState(_MicroPauseCompletionState):
+    sentinel = "__TURN_COMPLETE_M009_NEVER_SAW_STREAMING__"
+
+    def text(self) -> str:
+        return self.complete_text  # stable, non-empty from t=0
+
+    def streaming_visible(self) -> bool:
+        return False  # the stop control was never caught by any poll
+
+    def completion_marker_visible(self) -> bool:
+        return True  # copy-turn marker present: the turn is already complete
+
+
+class _ShortReplyNeverStreamedState(_NeverSawStreamingCompleteState):
+    sentinel = "PING"
+
+    def text(self) -> str:
+        return "PING"  # one-word reply, stable, non-empty
+
+
 class _ImmediateAffordanceCompletionState(_MicroPauseCompletionState):
     sentinel = "__TURN_COMPLETE_M008A_AFFORDANCE__"
 
@@ -897,6 +917,32 @@ def test_real_wait_for_completion_returns_after_completion_marker_visible(monkey
     assert page.wait_timeouts
 
 
+def test_real_wait_for_completion_returns_when_never_saw_streaming_marker_and_text_stable(monkeypatch):
+    clock = _ScriptedClock()
+    page = _ScriptedCompletionPage(clock)
+    state = _NeverSawStreamingCompleteState(clock)
+    session = _scripted_real_completion_session(monkeypatch, state, page)
+
+    latest = session.wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)
+
+    assert latest is state.turn
+    assert state.sentinel in latest.inner_text()
+    assert clock.now >= 3.0   # waited the stability window
+    assert clock.now < 30.0   # did NOT run to the truncation deadline
+
+
+def test_real_wait_for_completion_returns_short_reply_that_never_streamed(monkeypatch):
+    clock = _ScriptedClock()
+    page = _ScriptedCompletionPage(clock)
+    state = _ShortReplyNeverStreamedState(clock)
+    session = _scripted_real_completion_session(monkeypatch, state, page)
+
+    latest = session.wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)
+
+    assert latest.inner_text() == "PING"
+    assert clock.now < 30.0
+
+
 def test_real_wait_for_completion_times_out_when_stop_gone_and_body_stable_without_completion_evidence(monkeypatch):
     monkeypatch.setattr("ask_chatgpt.driver._POLL_INTERVAL_S", 0.005)
     page = _CompletionPollingPage(
```

GREEN command: `uv run pytest tests/test_driver.py -k "never_saw_streaming or short_reply_that_never_streamed" -q`

```
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
..                                                                       [100%]
2 passed, 34 deselected in 0.06s
```

Guard command: `uv run pytest tests/test_driver.py -k "micro_pause or premature" -q`

```
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
..                                                                       [100%]
2 passed, 34 deselected in 0.05s
```

Full-suite command: `uv run pytest -q`

```
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
........................................................................ [ 34%]
........................................................................ [ 68%]
...................................................................      [100%]
211 passed, 4 deselected in 73.21s (0:01:13)
```

Count note: full suite passed, but the observed count is `211 passed, 4 deselected`, not the contract-required `209 passed, 4 deselected`; stopped without deleting/skipping tests as instructed.

ESTIMATE: T2-keystone 20m
ACTUAL: T2-keystone 35m
END: 2026-06-13T16:08:52-05:00
REWORK-CAUSE: spec-gap
