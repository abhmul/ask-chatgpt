DONE

## What changed
- `src/ask_chatgpt/send.py:212-256`: `verify_prompt_submitted` now accepts keyword-only `has_attachments: bool = False`; it still requires a new user turn, keeps exact normalized text equality when `has_attachments` is false, and uses normalized-prompt substring containment only when `has_attachments` is true. Returned `SubmittedTurn.normalized_prompt` remains the normalized prompt.
- `src/ask_chatgpt/send.py:288-298`: `send_prompt` passes `has_attachments=bool(attach)` to `verify_prompt_submitted`.
- `src/ask_chatgpt/session.py:423-429`: production `Session._run_send_turn` passes `has_attachments=bool(attachment_specs)` to `verify_prompt_submitted`.
- `tests/test_send_completion.py:279-347`: added direct verifier tests for attachment DOM text `"m9-upload.txt\nliteral prompt"` succeeding with `has_attachments=True` and failing without attachments to preserve the exact-match guard.
- `tests/test_session_draft_loop.py:96-107,198-216`: `_draft_scenario` can script attachment-bearing user DOM text; added production `Session.ask(..., attach=[...])` test where DOM text is `"m9-upload.txt\n<PROMPT>"`, verifying success and canonical user content stays the bare prompt.
- `tests/test_session_stubs.py:93-96`: updated one monkeypatched verifier stub to accept/assert the new `has_attachments` kwarg for no-attachment repeated sends.

## Falsifiability evidence
RED on exact-equality revert, by temporarily forcing `carries_prompt = latest_text == normalized` even when attachments are present, then restoring the substring branch:

```text
$ uv run pytest -k 'attachment_user_turn_verifies_prompt_substring or draft_ask_attach_verifies_user_turn_when_dom_includes_attachment_filename'
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/abhmul/dev/ask-chatgpt
configfile: pyproject.toml
testpaths: tests
collected 267 items / 265 deselected / 2 selected

tests/test_send_completion.py F                                          [ 50%]
tests/test_session_draft_loop.py F                                       [100%]

E               ask_chatgpt.errors.PromptNotSubmittedError: PROMPT_NOT_SUBMITTED: submit did not produce a new user turn carrying the prompt

FAILED tests/test_send_completion.py::test_attachment_user_turn_verifies_prompt_substring_and_preserves_prompt
FAILED tests/test_session_draft_loop.py::test_draft_ask_attach_verifies_user_turn_when_dom_includes_attachment_filename
====================== 2 failed, 265 deselected in 0.11s =======================
Command exited with code 1
```

Focused restored run also kept gotcha-#2/no-attachment guard green: `uv run pytest -k 'attachment_user_turn or no_attachment_user_turn or draft_ask_attach_verifies or no_op_submit_verification_raises_prompt_not_submitted or wrong_new_user_turn'` → `5 passed, 262 deselected`.

Full green suite captured in `team/evidence/reports/M9-W7-pytest.txt`:

```text
collected 267 items
...
tests/test_store_torn_line.py ...                                        [100%]

============================= 267 passed in 1.03s ==============================
```

## Artifacts (+ trust)
- `team/evidence/reports/M9-W7-pytest.txt`: direct `uv run pytest` capture, exit 0, 267 passed.
- This handoff: derived from the captured pytest outputs and the final file contents.

## Blockers
- No code/test blocker. Repository cleanliness was not fully satisfiable from current checkout: many W1-W6 files and unrelated paths, including `issues/cdp-send-repro/controller.mjs` and `human/`, were already dirty/untracked at start; I did not touch browser/CDP/chatgpt.com or those forbidden paths.

## Recommended next
- Manager review and commit the intended `src/` + `tests/` + W7 evidence changes. Live end-to-end capture re-verify is deferred because the real-send budget is spent.
