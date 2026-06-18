STATUS: DONE

Verification:
- `uv run pytest` summary: `============================= 170 passed in 0.32s ==============================`
- RED observed before GREEN: initial send test failed with `ModuleNotFoundError: No module named 'ask_chatgpt.send'`; expanded send/completion/session tests then failed with `ModuleNotFoundError: No module named 'ask_chatgpt.completion'`; implementation made the same tests green.

Falsifiability notes:
- No-op submit: `test_session_no_op_preserves_pending_and_never_calls_completion` monkeypatches `ask_chatgpt.session.wait_for_completion` to raise `AssertionError("completion sentinel was reached")`; no-op submit raises `PROMPT_NOT_SUBMITTED`, leaves only hidden pending stub, and never reaches completion.
- Newer-id gating: `test_successful_ask_returns_new_assistant_and_supersedes_pending` returns `assistant-new-2`, not `baseline-assistant-1`/user/stub; `test_old_stable_assistant_is_not_completion` times out on stable baseline assistant.
- No hidden ceiling: `test_continuous_progress_past_600_without_total_cap_completes` advances fake clock to literal `1500.0` with `max_total_wait_s=None`; `test_explicit_total_cap_raises_even_with_continuous_progress` raises `MAX_TOTAL_WAIT_EXCEEDED` at literal `900.0`.
- Timeout salvage: `test_session_timeout_salvage_persists_partial_assistant` raises `COMPLETION_TIMEOUT` and persists an assistant partial with `content_markdown == "partial only"`, `status == "partial"`, `capture_source == "dom_text"`.
- Sparse backend cadence: `test_sparse_backend_cadence_uses_fresh_one_use_headers` asserts 3 backend checks/header acquisitions vs >=30 DOM polls and 0 full raw fetches during wait; `test_backend_interval_none_uses_sparse_mock_default_not_dom_cadence` asserts `None` does not collapse to DOM cadence.
- Model/tool fail-closed: requested model mismatch raises `MODEL_SELECTION_NOT_REFLECTED` before fill/click and commits no canonical user.

Commit:
- `274e8bc8cd282a41ea307d24c631a0e668f8eed5` — `M4 step 5: verified send + completion detection over mock`

`git log --oneline -3`:
```text
274e8bc M4 step 5: verified send + completion detection over mock
de96e20 M4 step 4c: cover capture fallback degradation
3d30e2d M4 step 4b: add offline capture parser
```

`git show --stat HEAD`:
```text
274e8bc M4 step 5: verified send + completion detection over mock
 src/ask_chatgpt/capture.py       |   5 +-
 src/ask_chatgpt/channels/mock.py |   2 +
 src/ask_chatgpt/completion.py    | 507 +++++++++++++++++++++++++++++++
 src/ask_chatgpt/menus.py         | 106 +++++++
 src/ask_chatgpt/send.py          | 243 +++++++++++++++
 src/ask_chatgpt/session.py       | 245 ++++++++++++++-
 src/ask_chatgpt/store.py         |  12 +-
 tests/__init__.py                |   1 +
 tests/conftest.py                |   8 +
 tests/test_send_completion.py    | 639 +++++++++++++++++++++++++++++++++++++++
 10 files changed, 1750 insertions(+), 18 deletions(-)
```

Blockers: none.

Deferrals to E6/M7:
- No `cli.py` changes; CLI/status/pool/budget/loop remain deferred.
- CDP/live browser paths remain unimplemented; all new behavior is mock/fake-clock only.
- Full Radix model/tool mutation remains M7; M4 menu path is fail-closed/no-op-reflection only.
