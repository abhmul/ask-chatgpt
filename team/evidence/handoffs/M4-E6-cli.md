STATUS: DONE

## F1-F8 ledger
- F1 DONE: `history`/`export` use `Session.history` and store rendering only; mock/no-probe status path does not touch channel preflight.
- F2 DONE: CLI parser dispatches `ask/create/scrape/history/export/fetch/status/loop` to documented Session methods; fake recording Session tests pin forwarded flags, `export -> history`, `create --project`, and no `ask --project`.
- F3 DONE: `ask`, `scrape`, `history`, and `export` emit stdout and additionally write `--out`; tests assert identical bytes and exact ask trailing newline behavior.
- F4 DONE: `CompletionTimeoutError` partial salvage is emitted to stdout and `--out` before the nonzero completion-timeout exit.
- F5 DONE: `status --json` uses exact fields `ok, cdp, signed_in, login_or_challenge, selector_valid, conversations, blocking_code, details`; `--no-browser-probe` has `cdp=null` and does not call channel preflight.
- F6 DONE: CLI maps `AskChatGPTError` to `ERROR <CODE>: <message>` and exact exits, JSON-mode stderr, unexpected exit 99, and redacts prompt/header/cookie/token canaries.
- F7 DONE: `Session` owns minimal `TabPool` and `AdaptiveSendBudget` stubs; no hidden message cap test sends 15 successful asks in one Session and reuses one managed tab.
- F8 DONE: `create` returns M4 draft refs and forwards project; `fetch` is local-cache only; `loop --max-iterations 2` emits exactly two bounded JSONL envelopes over mock.

## Test result
Command: `uv run pytest`

```text
warning: `VIRTUAL_ENV=/home/abhmul/.local/share/agent-python/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/abhmul/dev/ask-chatgpt
configfile: pyproject.toml
testpaths: tests
collected 183 items

tests/test_allowlist.py .......................                          [ 12%]
tests/test_capture.py .................                                  [ 21%]
tests/test_channels_base.py ...                                          [ 23%]
tests/test_cli.py .........                                              [ 28%]
tests/test_errors.py ....................                                [ 39%]
tests/test_identity.py ..............                                    [ 46%]
tests/test_mock_channel.py ........                                      [ 51%]
tests/test_models.py ................                                    [ 60%]
tests/test_selectors.py ..................                               [ 69%]
tests/test_send_completion.py ..................                         [ 79%]
tests/test_session_stubs.py ..                                           [ 80%]
tests/test_smoke.py ......                                               [ 84%]
tests/test_store_atomic_raw.py ...                                       [ 85%]
tests/test_store_attachment_path.py ...                                  [ 87%]
tests/test_store_durability.py ..                                        [ 88%]
tests/test_store_identity_resolution.py ..                               [ 89%]
tests/test_store_index.py ..                                             [ 90%]
tests/test_store_jsonl.py ..                                             [ 91%]
tests/test_store_layout.py ..                                            [ 92%]
tests/test_store_partial.py ...                                          [ 94%]
tests/test_store_payload.py ...                                          [ 96%]
tests/test_store_pending_send.py ..                                      [ 97%]
tests/test_store_read_semantics.py .                                     [ 97%]
tests/test_store_render.py .                                             [ 98%]
tests/test_store_torn_line.py ...                                        [100%]

============================= 183 passed in 0.37s ==============================
```

## Falsifiability notes
- Observed RED before implementation: targeted `uv run pytest tests/test_cli.py tests/test_smoke.py` failed 10 tests against the scaffold (`Session` absent from `cli.py`, help still scaffold, history/status still not implemented), then passed after implementation.
- Stdout-and-out: `test_cli_ask_forwards_flags_and_stdout_and_out_are_identical`, `test_cli_export_dispatches_history_not_scrape_and_out_does_not_suppress_stdout`, and scrape coverage fail if stdout is suppressed or file bytes differ.
- `export -> history`: fake RecordingSession asserts only `history` is called for `export`; a scrape-dispatch implementation fails.
- Salvage-on-timeout: fake `Session.ask` raises `CompletionTimeoutError` carrying `partial_markdown`; test asserts partial stdout/out plus exit 50 and `ERROR COMPLETION_TIMEOUT` on stderr.
- Status no-probe: CLI and Session tests assert `cdp is None`, per-selector `present is None`, and a channel whose `preflight` raises is not called with `probe_browser=False`.
- No hidden send cap: `test_repeated_successful_mock_sends_in_one_session_have_no_hidden_message_cap` performs 15 successful asks in one Session and asserts the budget count reaches 15 and one managed tab is reused.

## Commit
- Commit: `66b55334d7950ef3a130ae4008541688a2ca04ac`
- Message: `M4 step 6: cli verbs and status over mock`

```text
66b5533 M4 step 6: cli verbs and status over mock
7db36f4 M4: E4 capture + E5 send/completion manager record
274e8bc M4 step 5: verified send + completion detection over mock
```

```text
66b5533 M4 step 6: cli verbs and status over mock
 src/ask_chatgpt/cli.py      | 449 +++++++++++++++++++++++++++++++++++++++++---
 src/ask_chatgpt/session.py  | 375 ++++++++++++++++++++++++++++++++----
 tests/test_cli.py           | 336 +++++++++++++++++++++++++++++++++
 tests/test_session_stubs.py | 121 ++++++++++++
 tests/test_smoke.py         |  89 ++++++++-
 5 files changed, 1305 insertions(+), 65 deletions(-)
```

## `test_smoke.py` update
Replaced the scaffold `not yet implemented` assertion with real CLI coverage: real store-only `history`, `status --json --no-browser-probe` exact schema, and real error mapping for missing local alias. Kept version/help coverage, updated help to describe real verbs.

## Blockers
None for M4. Unrelated working-tree changes were left unstaged: `issues/cdp-send-repro/controller.mjs`, `team/state/M4-manager-state.json`, `team/state/live-state.json`, untracked `human/`, and untracked `team/contracts/M4-E6-cli.md`.

## Recommended M5 next steps
Implement attended CDP `CdpChannel` preflight/attach/open-tab/detach behind lazy Playwright imports, then wire real `scrape` header acquisition/streaming capture with the same stdout-and-out/error contracts. Keep model/tool selection fail-closed until live selector/menu evidence is captured.
