# E6b Worker Report

STATUS: complete; global completion-marker fallback restored and regression-covered offline.

Driver diff: `src/ask_chatgpt/driver.py` now computes `completion_visible = completion_present_on_latest or self._present("completion_marker")`; optional `completion_affordance` also checks both turn-scoped and global presence. The E6 trigger guards are unchanged: `streaming_seen`, `not streaming_visible`, `not_streaming_since >= 3.0s`, `stable_since >= 3.0s`, progress deadline, ceiling, and timeout behavior remain intact. Added the requested comment documenting that the real copy-turn-action button is outside the assistant turn.

New guard test: `tests/test_driver.py::test_real_wait_for_completion_completes_when_marker_is_global_only_not_in_turn` adds `_GlobalOnlyMarkerCompletionState`, where global `present("completion_marker")` becomes true after streaming but turn-scoped `selector_count("#complete")` stays 0. It asserts `wait_for_completion(timeout_s=30.0, max_total_wait_s=60.0)` returns the complete sentinel text. Existing RED guard `test_real_wait_for_completion_does_not_return_prematurely_when_global_marker_present` still passes; targeted run of both tests: 2 passed.

Suite summary: `UV_OFFLINE=1 uv sync --all-groups` succeeded. `UV_OFFLINE=1 uv run pytest -q` exited 0 with `209 passed, 4 deselected`; default marker deselection means 0 `real_site` executed. `UV_OFFLINE=1 uv run pytest --collect-only -q tests/test_truncation_real.py tests/test_continuity_real.py` collected 3 tests.

Commit sha: PENDING until git commit is created; final worker response records HEAD.

ESTIMATE: small targeted driver/test/report slice.

ACTUAL: restored global fallback, added regression guard, ran sync/full suite/collect-only, saved pytest output.

REWORK-CAUSE: spec-gap; E6 over-scoped completion visibility to the latest assistant turn, but the real DOM places the copy/completion button outside the turn element.
