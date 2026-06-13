# M-008b / T1 worker report

STATUS: DONE

## RED evidence

RED test: `tests/test_driver.py:905` (`test_real_wait_for_completion_caps_progress_extensions_at_absolute_ceiling`). It uses `_NeverCompletesGrowingState` plus `_CeilingSafetyValvePage` so body text keeps changing, completion evidence remains absent, and an unbounded old loop trips the safety valve instead of raising `ResponseTruncatedError` at the requested ceiling.

Captured in `orchestration/reports/M-008b/T1-RED.txt` against the pre-change driver:

```text
E               TypeError: BrowserSession.wait_for_completion() got an unexpected keyword argument 'max_total_wait_s'
...
E           RuntimeError: unbounded: no ceiling
1 failed, 31 deselected in 0.11s
EXIT_CODE=1
```

## GREEN evidence + ceiling-default justification

Implemented `_REAL_COMPLETION_CEILING_S = 600.0` in `src/ask_chatgpt/driver.py:45` and added `max_total_wait_s: float | None = None` to `BrowserSession.wait_for_completion` at `src/ask_chatgpt/driver.py:325`. `None` uses the module default; tests inject `5.0` seconds. The real/CDP progress deadline still extends on body growth, but is now capped at `start + max_total_wait_s` and raises the existing `ResponseTruncatedError` timeout path when no completion evidence appears by that absolute deadline.

Default justification: 600s (10 minutes) is deliberately much larger than the existing `timeout_s=120.0` progress window and larger than expected legitimate single-turn active streams, including long code/research answers that normally finish in a few minutes. It should not clip a real response, while it bounds pathological pages whose body text grows or oscillates forever.

Driver diff summary: deleted dead `_REAL_COMPLETION_STABLE_S`; added `_REAL_COMPLETION_CEILING_S`; extended the method signature; records `start = time.monotonic()`; computes an optional real/CDP absolute deadline; clamps both initial and progress-extended deadlines to that ceiling. Positive coverage keeps a normally growing body completing before the ceiling (`test_real_wait_for_completion_extends_deadline_while_body_text_grows`).

## Full-suite result

`uv sync --all-groups` completed offline with `UV_NO_NETWORK=1`. Full suite command was `env -u ASK_CHATGPT_REAL UV_NO_NETWORK=1 uv run pytest -q`; evidence saved in `orchestration/reports/M-008b/T1-pytest.txt`.

```text
207 passed, 1 deselected in 66.40s (0:01:06)
EXIT_CODE=0
```

ASK_CHATGPT_REAL was unset; the one `real_site` test was deselected by the default marker expression, so 0 real_site tests executed.

## Dead-constant grep

Command: `grep -rn "_REAL_COMPLETION_STABLE_S" src/ tests/`

Result: no matches in `src/` or `tests/`; grep exit code `1` (expected for no matches).

## Commit sha

Implementation/evidence commit: `7a051a504ce9807c820738614bc68bb2dd779fb8`.

ESTIMATE: T1 45m
ACTUAL: T1 8m
REWORK-CAUSE: none
