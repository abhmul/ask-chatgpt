DONE

## What changed
- `src/ask_chatgpt/send.py:10-22,97-163` — imported `AttachmentUploadError`, added attachment-chip timeout/poll constants, rewired `upload_attachments` to validate local files, collect `Path`s, call `tab.channel.upload_files(tab, selectors["file_input"], paths)`, wait for `selectors["attachment_chip"]`, and raise `AttachmentUploadError` with `details={"file_count": n}` if confirmation times out.
- `src/ask_chatgpt/errors.py:240-246,273-276` — added `AttachmentUploadError` (`ATTACHMENT_UPLOAD_FAILED`, exit 63) and exported it.
- `src/ask_chatgpt/models.py:213-214` — added `file_input` and `attachment_chip` to `SelectorMap`.
- `src/ask_chatgpt/selectors/__init__.py:23-24` — added `file_input` and `attachment_chip` to `REQUIRED_SELECTOR_KEYS` so the loader keeps them.
- `src/ask_chatgpt/selectors/real.json:10-11` — added the hypothesized production selectors.
- `src/ask_chatgpt/__init__.py:8,64` and `src/ask_chatgpt/cli.py:46` — exported/mapped the new error code for public/CLI handling.
- `src/ask_chatgpt/completion.py:256-257` — kept the internal `SelectorMap` stub complete after adding required keys.
- `tests/test_session_draft_loop.py:3,17,33-34,170-218` — added the production-path upload assertion and fail-closed missing-chip assertion, plus selector fixture updates.
- `tests/test_errors.py:9,47`, `tests/test_selectors.py:21-22,46-50`, `tests/test_send_completion.py:55-56`, `tests/test_cli.py:259-260`, `tests/test_menus.py:20-21`, `tests/test_session_stubs.py:22-23`, `tests/test_cdp_channel.py:735-736` — updated selector/error fixtures for the new required selector keys and error taxonomy.

## Falsifiability evidence
Upload-happens test RED after temporarily removing the upload wire (`uv run pytest -q tests/test_session_draft_loop.py -k test_draft_ask_uploads_attached_file_before_submit`):

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_draft_ask_uploads_attached_file_before_submit ______________

tmp_path = PosixPath('/tmp/pytest-of-abhmul/pytest-247/test_draft_ask_uploads_attache0')

    def test_draft_ask_uploads_attached_file_before_submit(tmp_path) -> None:
        attachment = tmp_path / "m9-upload.txt"
        attachment.write_text("offline upload canary", encoding="utf-8")
        clock = ScriptedClock()
        channel = MockChannel(
            replace(
                _draft_scenario(),
                selector_presence={SELECTORS["attachment_chip"]: True},
            ),
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )
        session = _session(tmp_path, channel)
    
        answer = session.ask(None, PROMPT, attach=[attachment])
    
        assert answer.conversation_id == "learned-123"
        upload_calls = [call for call in channel.calls if call.method == "upload_files"]
>       assert len(upload_calls) == 1
E       assert 0 == 1
E        +  where 0 = len([])

tests/test_session_draft_loop.py:188: AssertionError
=========================== short test summary info ============================
FAILED tests/test_session_draft_loop.py::test_draft_ask_uploads_attached_file_before_submit
1 failed, 10 deselected in 0.05s

Command exited with code 1
```

Fail-closed test RED after temporarily removing the chip wait/raise (`uv run pytest -q tests/test_session_draft_loop.py -k test_draft_ask_attach_fails_closed_when_chip_never_appears`):

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_draft_ask_attach_fails_closed_when_chip_never_appears __________

tmp_path = PosixPath('/tmp/pytest-of-abhmul/pytest-248/test_draft_ask_attach_fails_cl0')

    def test_draft_ask_attach_fails_closed_when_chip_never_appears(tmp_path) -> None:
        attachment = tmp_path / "m9-missing-chip.txt"
        attachment.write_text("offline upload canary", encoding="utf-8")
        clock = ScriptedClock()
        channel = MockChannel(
            replace(
                _draft_scenario(),
                selector_presence={SELECTORS["attachment_chip"]: False},
            ),
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )
    
>       with pytest.raises(AttachmentUploadError) as exc_info:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE <class 'ask_chatgpt.errors.AttachmentUploadError'>

tests/test_session_draft_loop.py:209: Failed
=========================== short test summary info ============================
FAILED tests/test_session_draft_loop.py::test_draft_ask_attach_fails_closed_when_chip_never_appears
1 failed, 10 deselected in 0.05s

Command exited with code 1
```

Green full-suite tail from `team/evidence/reports/M9-W1-pytest.txt`:

```text
tests/test_store_index.py ..                                             [ 93%]
tests/test_store_jsonl.py ..                                             [ 94%]
tests/test_store_layout.py ..                                            [ 94%]
tests/test_store_partial.py ...                                          [ 96%]
tests/test_store_payload.py ...                                          [ 97%]
tests/test_store_pending_send.py ..                                      [ 98%]
tests/test_store_read_semantics.py .                                     [ 98%]
tests/test_store_render.py .                                             [ 98%]
tests/test_store_torn_line.py ...                                        [100%]

============================= 259 passed in 1.01s ==============================
EXIT: 0
```

## Selector values used
- `file_input`: `input[type="file"]`
- `attachment_chip`: `[data-testid="composer-attachment"], div[data-testid*="attachment"], button[aria-label*="Remove" i]`

## Artifacts + trust level
- Artifact: `team/evidence/reports/M9-W1-pytest.txt`.
- Trust level: high for offline `MockChannel`/unit coverage and falsifiability; live DOM selector correctness remains a hypothesis for W2 as contracted. No browser, CDP, chatgpt.com, or network send was used.

## Blockers
- No code/test blocker. Full `git status --porcelain` still includes pre-existing unrelated dirty entries outside my scope (`issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, `human/`, `team/contracts/M9-finalize.md`, `team/contracts/M9-w1-upload-wire.md`, `team/evidence/reports/M9-pytest-baseline.txt`, `team/state/M9-manager-state.json`); I did not touch or clean them. If literal clean-porcelain acceptance is required, manager action is needed to account for those pre-existing entries.

## Recommended next
- W2 should validate/correct `file_input` and `attachment_chip` against the live ChatGPT composer DOM, then rerun the offline suite after selector updates.
