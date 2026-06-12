START_TIMESTAMP: 2026-06-11T23:53:24-05:00
END_TIMESTAMP: 2026-06-11T23:58:51-05:00
ESTIMATE: T2 20m

## Result

- STEP 0 inherited tree confirmed green before edits: `uv sync --all-groups && uv run pytest -q` completed with `2 passed in 0.41s`.
- STEP 1 build landmine fixed by removing all greenlet-specific `tmp/` source/constraint/metadata blocks from `pyproject.toml` and using the preferred PyPI/uv-lock path. `uv.lock` now records `greenlet` from `https://pypi.org/simple`; no vendor fallback was needed.
- TDD performed: new tests were written first and initially failed with `ModuleNotFoundError` for `ask_chatgpt.errors`, then implementation was added.

## Files created/edited

- Edited: `pyproject.toml`
- Edited: `uv.lock`
- Created: `src/ask_chatgpt/errors.py`
- Created: `src/ask_chatgpt/session_registry.py`
- Created: `tests/test_errors.py`
- Created: `tests/test_session_registry.py`
- Created: `orchestration/reports/M-002/T2-report.md`

## STEP 1 verification

- `grep -n "tmp/" pyproject.toml` result: no output.
- `uv run pytest -q` after STEP 1 remained green: `2 passed in 0.40s`.

## Final tests

- Final `uv run pytest -q` summary: `9 passed in 0.41s`.

## Error classes

- `AskChatGPTError`
- `LoginRequiredError`
- `SessionNotFoundError`
- `ModelUnavailableError`
- `ResponseTruncatedError`
- `SelectorUnavailableError`
- `UploadUnsupportedError`
- `DownloadUnsupportedError`

## Registry API

- `ConversationRef(conversation_ref: str, url: str | None = None, model_settings: dict | None = None)`
- `SessionRegistry(store_path: pathlib.Path | str | None = None)`; default path honors `ASK_CHATGPT_STATE_DIR`, else `~/.local/state/ask-chatgpt/sessions.json`.
- `get(session_identifier) -> ConversationRef | None`
- `set(session_identifier, ref) -> None` with same-dir temp file plus `os.replace` atomic persistence.
- `list() -> dict[str, ConversationRef]`
- `delete(session_identifier) -> bool`

## Deviations

- None.

## Trust notes

- No automated work contacted `chatgpt.com`, OpenAI, or any external runtime/test service.
- The only sanctioned external setup path was uv/PyPI greenlet resolution; no additional downloads were intentionally requested, and no vendor fallback was needed.
- No credentials, cookies, session tokens, or browser-profile contents were read, stored, or logged.
- New registry tests use `tmp_path`; the real default user-state directory is not touched by tests.
- The existing uv warning says the harness `VIRTUAL_ENV` is ignored because repo `.venv` is used; commands were run via `uv` from the repo root.

T2-STATUS: DONE
