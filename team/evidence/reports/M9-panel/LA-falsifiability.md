PASS

TREE RESTORED: yes — `git diff --stat -- src tests` at start and end is identical (sha256 `ecb2556f6bb5b61fb80e5b112da08a0fb3810c0c506d1f4434a53f3ef5d175b8`; stat diff empty).

Start/end `git diff --stat -- src tests`:

```text
 src/ask_chatgpt/__init__.py           |   2 +
 src/ask_chatgpt/channels/cdp.py       |  69 ++++++++++++------
 src/ask_chatgpt/channels/mock.py      |  10 ++-
 src/ask_chatgpt/cli.py                |   1 +
 src/ask_chatgpt/completion.py         |   3 +
 src/ask_chatgpt/errors.py             |   8 +++
 src/ask_chatgpt/menus.py              |  89 +++++++++++++++++++++--
 src/ask_chatgpt/models.py             |   3 +
 src/ask_chatgpt/selectors/__init__.py |   3 +
 src/ask_chatgpt/selectors/real.json   |   3 +
 src/ask_chatgpt/send.py               |  80 +++++++++++++++++++--
 src/ask_chatgpt/session.py            |  16 ++++-
 tests/test_cdp_channel.py             |   3 +
 tests/test_cli.py                     |   3 +
 tests/test_errors.py                  |   2 +
 tests/test_menus.py                   | 128 ++++++++++++++++++++++++++++++++--
 tests/test_selectors.py               |   6 ++
 tests/test_send_completion.py         |  78 +++++++++++++++++++++
 tests/test_session_draft_loop.py      | 108 +++++++++++++++++++++++++++-
 tests/test_session_stubs.py           |   6 +-
 20 files changed, 577 insertions(+), 44 deletions(-)
```

## Mutations

1. Upload wire — target `tests/test_session_draft_loop.py::test_draft_ask_uploads_attached_file_before_submit`. RED evidence: pytest rc 1; `E       assert 0 == 1` at `assert len(upload_calls) == 1`. Restore: `src/ask_chatgpt/send.py` restored from `/tmp/vA-M1-send.py.bak`; `cmp` rc 0.

2. Fail-closed chip — target `tests/test_session_draft_loop.py::test_draft_ask_attach_fails_closed_when_chip_never_appears`. RED evidence: pytest rc 1; `E       Failed: DID NOT RAISE <class 'ask_chatgpt.errors.AttachmentUploadError'>`. Restore: `src/ask_chatgpt/send.py` restored from `/tmp/vA-M2-send.py.bak`; `cmp` rc 0.

3. Send-enable-after-attach — target `tests/test_session_draft_loop.py::test_draft_ask_attach_waits_past_default_send_enable_settle`. RED evidence: pytest rc 1; `E       ask_chatgpt.errors.SelectorNotFoundError: SELECTOR_NOT_FOUND: send button did not become visible and enabled`. Restore: `src/ask_chatgpt/session.py` restored from `/tmp/vA-M3-session.py.bak`; `cmp` rc 0.

4. Verify substring for attachments — target `tests/test_send_completion.py::test_attachment_user_turn_verifies_prompt_substring_and_preserves_prompt`. RED evidence: pytest rc 1; `E       ask_chatgpt.errors.PromptNotSubmittedError: PROMPT_NOT_SUBMITTED: submit did not produce a new user turn carrying the prompt`. Restore: `src/ask_chatgpt/send.py` restored from `/tmp/vA-M4-send.py.bak`; `cmp` rc 0.

5. DR chip reflection — target `tests/test_menus.py::test_set_tools_verifies_menu_unchecked_tool_by_matching_composer_chip`. RED evidence: pytest rc 1; `E       ask_chatgpt.errors.ToolSelectionNotReflectedError: TOOL_SELECTION_NOT_REFLECTED: requested tool was selected but not reflected`. Restore: `src/ask_chatgpt/menus.py` restored from `/tmp/vA-M5-menus.py.bak`; `cmp` rc 0.

6. Family submenu — target `tests/test_menus.py::test_select_model_finds_differently_named_gpt55_family_subradio`. RED evidence: pytest rc 1; `E       ask_chatgpt.errors.ModelSelectionNotReflectedError: MODEL_SELECTION_NOT_REFLECTED: family submenu selection disabled`. Restore: `src/ask_chatgpt/menus.py` restored from `/tmp/vA-M6-menus.py.bak`; `cmp` rc 0.

## Vacuousness findings

None. The M9 additions scanned from `git diff main -- tests` include behavioral assertions for the six required targets: upload call count/selector/order, fail-closed exception and no fill/click, delayed enable crossing the 2s boundary plus click/order, attachment substring verification returning the new user id/count/prompt, Deep Research chip-specific reflection plus fail-closed nonmatching/no-chip cases, and GPT-5.4 family submenu reflected label plus submenu/open-select click sequence. No M9 test identified as shape-only or unable to fail.

## Final pytest

`uv run pytest` rc 0: `268 passed in 1.00s`.
