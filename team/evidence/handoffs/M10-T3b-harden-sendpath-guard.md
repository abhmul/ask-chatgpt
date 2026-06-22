STATUS: DONE

## New test

- `tests/test_session_draft_loop.py::test_draft_send_capture_uses_exact_conversation_header_harvest_not_ambient` drives a draft `session.ask(None, ...)` through the mock send path, exposes both a generic `/backend-api/accounts/check` request and the exact `/backend-api/conversation/<id>` request with distinguishable mock auth values, and asserts the streamed final conversation capture used the exact conversation auth. It falsifies changing send-final `capture_conversation` to `header_mode="ambient_backend"` or changing `capture_conversation`'s default harvest mode away from exact conversation matching.

## Falsifiability check

- Temporarily mutated `_run_send_turn` to pass `header_mode="ambient_backend"` to the send-final `capture_conversation` call.
- Result: the new test FAILED as expected; the recorded streamed capture auth was the generic mock auth instead of the exact mock auth.
- Restored the mutation and reran the new test: `1 passed in 0.04s`.

## Final verification

- Final `uv run pytest` summary line: `============================= 276 passed in 1.03s ==============================`.

## Commit

- Test commit hash: `112b6370f43d338522a16b1746087a9cea5620fa`.
