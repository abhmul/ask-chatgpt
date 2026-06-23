DONE

## Files changed
- `src/ask_chatgpt/send.py:48`: split idle wait from reload; already-idle sends return without `reload`, while a send that observed `stop_visible` still reloads after the page becomes idle.
- `tests/test_session_draft_loop.py:86`: added in-progress backend fixture helper; `tests/test_session_draft_loop.py:158`: added reusable two-turn loop scenario with DOM idle before the next turn.
- `tests/test_session_draft_loop.py:637`: added persisted-loop open-tab/reload accounting test; `tests/test_session_draft_loop.py:684`: added header-harvest regression recording capture fetch header names and target paths.
- `team/evidence/handoffs/M17/editor-b.md:1`: this handoff.

## RELOAD ACCOUNTING
- REMOVED: the unconditional per-send start reload when `wait_for_idle_and_reload_if_needed` finds the page already idle. This is the steady-state loop amplifier; persisted `Session.loop` turns now keep the single acquired tab and issue `reload == 0` when no in-flight generation is observed.
- KEPT: the same helper still reloads if it first observes `stop_visible == True` and must wait for an existing generation to clear, preserving the prior stale/mid-flight recovery behavior.
- KEPT: the draft/new-conversation post-completion reload at `src/ask_chatgpt/session.py:455` is unchanged; it remains the header-harvest trigger for draft capture. No path-specific non-draft reload was needed for harvest in the offline regression.

## FALSIFIABILITY PROOF
- TEST 1 red command against the pre-change unconditional-reload body: `uv run pytest tests/test_session_draft_loop.py::test_loop_persisted_tab_opens_once_and_does_not_reload_when_already_idle tests/test_session_draft_loop.py::test_loop_capture_harvests_required_headers_without_steady_state_reloads -q`
- TEST 1 red snippet: `tests/test_session_draft_loop.py:655: AssertionError` with `E       AssertionError: assert 2 == 0` for `channel.method_counts.get("reload", 0)`.
- TEST 2 red snippet from the same command: `tests/test_session_draft_loop.py:733: AssertionError` with `E       AssertionError: assert 2 == 0` for `channel.method_counts.get("reload", 0)`; before that assertion the test had already proven backend capture happened twice with all 8 `REQUIRED_CAPTURE_HEADERS` by name and target path `/backend-api/conversation/<mock-id>`.
- Green confirmation: the same targeted command now returns `2 passed in 0.04s`.
- Header-harvest falsifiability: TEST 2 records only canonical capture `fetch_in_page(..., stream_to=...)` headers; if harvest is starved, `capture_source == "backend_api"`, `len(conversation_fetch_header_names) == 2`, and the required-header subset assertions fail before reload accounting.

## FULL-suite gate
- `uv run pytest 2>&1 | tail -25` summary: `============================= 284 passed in 1.30s ==============================`.
- Existing pins still pass: `test_draft_ask_reloads_learned_chat_before_capture_when_backend_get_requires_reload` (current `tests/test_session_draft_loop.py:396`) and `test_draft_send_capture_uses_exact_conversation_header_harvest_not_ambient` (current `tests/test_session_draft_loop.py:421`) returned `2 passed in 0.04s`.
