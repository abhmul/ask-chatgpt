STATUS: DONE

Files changed:
- `src/ask_chatgpt/driver.py`: hardened `BrowserSession.wait_for_completion` for `real`/`cdp`; default wait is now `120.0s`; body-text progress extends the deadline; completion now requires positive completion evidence while the streaming marker is absent. Mechanism: option 1 (affordance-gated) plus progress-aware timeout. The branch uses optional `_optional_selector("completion_affordance")` when present; when absent it safely falls back to `completion_marker`. Pure body-text stability can no longer return a turn.
- `tests/test_driver.py`: added deterministic offline scripted-clock tests exercising the real `wait_for_completion` method through `channel="cdp"` seams for micro-pause clipping, optional `completion_affordance`, progress-aware long output, stable-no-evidence fail-closed timeout, and completion-marker success.

RED evidence (pre-fix targeted run):

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_real_wait_for_completion_does_not_return_midstream_micro_pause_without_completion_evidence _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f654bc8b6f0>

    def test_real_wait_for_completion_does_not_return_midstream_micro_pause_without_completion_evidence(monkeypatch):
        clock = _ScriptedClock()
        page = _ScriptedCompletionPage(clock)
        state = _MicroPauseCompletionState(clock)
        session = _scripted_real_completion_session(monkeypatch, state, page)
    
        latest = session.wait_for_completion(timeout_s=5.0)
        returned_text = latest.inner_text()
    
>       assert state.sentinel in returned_text, (
            f"returned clipped text at t={clock.now:.1f}s length={len(returned_text)} tail={returned_text[-160:]!r}"
        )
E       AssertionError: returned clipped text at t=2.2s length=5359 tail='tion payload keeps growing\nM008A-LINE-078 deterministic long completion payload keeps growing\nM008A-LINE-079 deterministic long completion payload keeps growing'
E       assert '__TURN_COMPLETE_M008A_MICRO_PAUSE__' in 'M008A-LINE-000 deterministic long completion payload keeps growing\nM008A-LINE-001 deterministic long completion payl...eterministic long completion payload keeps growing\nM008A-LINE-079 deterministic long completion payload keeps growing'
E        +  where '__TURN_COMPLETE_M008A_MICRO_PAUSE__' = <tests.test_driver._MicroPauseCompletionState object at 0x7f654c019a90>.sentinel

tests/test_driver.py:829: AssertionError
=========================== short test summary info ============================
FAILED tests/test_driver.py::test_real_wait_for_completion_does_not_return_midstream_micro_pause_without_completion_evidence
1 failed in 0.09s
```

GREEN evidence:

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
......                                                                   [100%]
6 passed in 0.69s
```

Final full-suite run:

```text
202 passed, 1 deselected in 61.96s (0:01:01)
```

Confirmation:
- Mock-channel completion path untouched: the `self.channel not in {"real", "cdp"}` completion return and mock reload polling logic were not changed; full suite passed.
- Fail-closed preserved: no completion evidence still raises `ResponseTruncatedError("completion marker did not appear before timeout")`; covered by stable-no-evidence and changing-text timeout tests.
- Optional `completion_affordance` seam is honored when present and degrades to `completion_marker` when absent.
- No real selector value populated; `src/ask_chatgpt/selector_maps/real.json` was not edited.
- No real-site contact; all tests were offline/unit/loopback.

ESTIMATE: T1 60m
ACTUAL: T1 55m
END: 2026-06-13T10:01:29-05:00
