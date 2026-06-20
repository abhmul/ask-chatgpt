DONE

## What changed

### Fix 1 — send-enable-after-attach

- `src/ask_chatgpt/send.py:18-20` adds `_SEND_BUTTON_ATTACHMENT_SETTLE_TIMEOUT_S = 60.0` while keeping the no-attachment settle timeout at 2s.
- `src/ask_chatgpt/send.py:178-210` threads an optional `settle_timeout_s` through `submit_composer`; default remains `_SEND_BUTTON_SETTLE_TIMEOUT_S`.
- `src/ask_chatgpt/send.py:271-286` makes `send_prompt` pass the 60s settle timeout only when `attach` is non-empty.
- `src/ask_chatgpt/session.py:41-42, 411-422` makes the production `_run_send_turn` path materialize `attachment_specs`, upload them, and pass the 60s settle timeout only when attachments are present.
- `tests/test_session_draft_loop.py:35, 197-220` adds `test_draft_ask_attach_waits_past_default_send_enable_settle`, with a send button disabled past 2s and enabled before 60s.

### Fix 2 — DR/tool reflection by composer chip

- `src/ask_chatgpt/selectors/__init__.py:14-27`, `src/ask_chatgpt/models.py:204-217`, `src/ask_chatgpt/selectors/real.json:10-13` add/project `active_tool_chip = button[aria-label*="click to remove" i]`.
- `src/ask_chatgpt/menus.py:25, 183-204, 350-363` keeps the menu-reopen checked-state path, then falls back to visible `selectors["active_tool_chip"]`; if neither signal exists, it still raises `TOOL_SELECTION_NOT_REFLECTED`.
- `src/ask_chatgpt/channels/mock.py:145, 232-235, 640-644` adds mock support for DR-like menu reopens that remain unchecked after selection.
- `src/ask_chatgpt/completion.py:252-260` updates the local selector stub to include `active_tool_chip`.
- `tests/test_menus.py:22, 332-366, 368-381` adds chip-reflection and fail-closed tests, and keeps the old no-reflection failure closed by setting no chip.
- `tests/test_selectors.py:12-25, 39-52`, `tests/test_send_completion.py:45-60`, `tests/test_cli.py:249-264`, `tests/test_session_stubs.py:12-26`, `tests/test_cdp_channel.py:724-740`, `tests/test_session_draft_loop.py:22-38` update selector fixtures for strict loading/projection.

## Falsifiability evidence

### RED on reverting Fix 1 to 2s for attachments

Command: `uv run pytest -q -k draft_ask_attach_waits_past_default_send_enable_settle`

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_draft_ask_attach_waits_past_default_send_enable_settle __________

>       answer = session.ask(None, PROMPT, attach=[attachment])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_session_draft_loop.py:213:
src/ask_chatgpt/session.py:368: in ask
    answer, _ref = self._run_send_turn(
src/ask_chatgpt/session.py:414: in _run_send_turn
    submit_composer(
src/ask_chatgpt/send.py:185: in submit_composer
    _wait_for_enabled_send_button(
src/ask_chatgpt/send.py:320: in _wait_for_enabled_send_button
    raise SelectorNotFoundError(
E   ask_chatgpt.errors.SelectorNotFoundError: SELECTOR_NOT_FOUND: send button did not become visible and enabled
=========================== short test summary info ============================
FAILED tests/test_session_draft_loop.py::test_draft_ask_attach_waits_past_default_send_enable_settle
1 failed, 263 deselected in 0.11s
```

### RED on reverting Fix 2 chip fallback

Command: `uv run pytest -q -k set_tools_verifies_menu_unchecked_tool_by_composer_chip`

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_set_tools_verifies_menu_unchecked_tool_by_composer_chip _________

>       results = set_tools(_tab(channel), SELECTORS, ("Deep research",))
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_menus.py:343:
src/ask_chatgpt/menus.py:198: in set_tools
    raise ToolSelectionNotReflectedError(
E   ask_chatgpt.errors.ToolSelectionNotReflectedError: TOOL_SELECTION_NOT_REFLECTED: requested tool was selected but not reflected
=========================== short test summary info ============================
FAILED tests/test_menus.py::test_set_tools_verifies_menu_unchecked_tool_by_composer_chip
1 failed, 263 deselected in 0.10s
```

### GREEN full suite

`team/evidence/reports/M9-W5-pytest.txt` was produced by `set -o pipefail; uv run pytest 2>&1 | tee team/evidence/reports/M9-W5-pytest.txt`; command exit was 0.

```text
collected 264 items
...
tests/test_store_torn_line.py ...                                        [100%]

============================= 264 passed in 1.02s ==============================
```

## W6 live-verify notes

- Confirm `ask(attach=[/tmp/m9-upload.txt])` now sends end-to-end: file stages, send button remains visible while upload completes, send button becomes enabled after upload, click creates a new user turn carrying the attachment, and assistant capture succeeds.
- Confirm `set_tools(["Deep research"])` returns verified from the composer chip path when the reopen menu `aria-checked` remains false; expected live chip selector is `button[aria-label*="click to remove" i]`, with DR label like `Deep research, click to remove`.

## Selector values now in real.json

- `attachment_chip`: `button[aria-label*="Remove file" i]`
- `active_tool_chip`: `button[aria-label*="click to remove" i]`

## Artifacts (+trust)

- `team/evidence/reports/M9-W5-pytest.txt` — trusted full offline pytest capture, 264 passed, exit 0.
- RED outputs are embedded above from temporary offline revert runs (`/tmp/m9w5-red-fix1.txt`, `/tmp/m9w5-red-fix2.txt`).

## Blockers

- None for the offline fixes.
- Working tree was already dirty before this worker with unrelated modified/untracked files; I did not touch live browser/CDP implementation paths, live-state, human, archive, or cache, and did not commit.

## Recommended next

- Run W6 live verification only: upload send end-to-end and DR verification via composer chip. If both pass, manager can commit the intended `src/`, `tests/`, and M9-W5 evidence changes.
