STATUS: DONE

Verification:
- `uv run pytest`
- Summary: `============================= 123 passed in 0.11s ==============================`
- `tests/test_smoke.py` stayed green; `src/ask_chatgpt/cli.py` was not touched.
- Offline only: store/history paths are file-only; no CDP/browser/Playwright/chatgpt.com use was added.

Falsifiability notes:
- Torn-line: `tests/test_store_torn_line.py::test_one_torn_trailing_line_warns_and_loads_prior_valid_records` first failed with `StoreError`/no `StoreWarning`; implementation now warns on exactly one torn trailing line while mid-file and two trailing invalid lines raise.
- Supersession: `tests/test_store_pending_send.py` first failed with missing `begin_send`; tests assert literal `local:<client_send_id>`, preserved JSONL stub line, canonical `supersedes_message_id`, and default read showing only the confirmed user.
- Atomic raw/header leak: `tests/test_store_atomic_raw.py` first failed with missing `write_raw_mapping_atomic`; tests assert invalid candidate leaves old raw intact and a wrapper containing `authorization`/`oai-device-id` persists only backend `mapping`/`current_node` with those keys/secrets absent.
- Payload stdout+out: `tests/test_store_payload.py` first failed with missing `emit_payload`; tests assert literal stdout plus identical out bytes, bytes payload `abc\x00def`, and stdout emitted before an injected out-file replace failure raises `StoreError`.

Commit:
- Hash: `b6d954c`
- `git log -1 --oneline`: `b6d954c M4 step 2: store.py JSONL persistence, atomic writes, pending-stub supersession, render, payload helper`
- `git show --stat HEAD --oneline`:

```text
b6d954c M4 step 2: store.py JSONL persistence, atomic writes, pending-stub supersession, render, payload helper
 src/ask_chatgpt/__init__.py             |   4 +
 src/ask_chatgpt/identity.py             |  11 +-
 src/ask_chatgpt/store.py                | 714 ++++++++++++++++++++++++++++++++
 tests/test_identity.py                  |  22 +-
 tests/test_store_atomic_raw.py          |  89 ++++
 tests/test_store_attachment_path.py     |  47 +++
 tests/test_store_durability.py          |  83 ++++
 tests/test_store_identity_resolution.py |  68 +++
 tests/test_store_index.py               |  74 ++++
 tests/test_store_jsonl.py               | 129 ++++++
 tests/test_store_layout.py              |  39 ++
 tests/test_store_partial.py             |  32 ++
 tests/test_store_payload.py             |  54 +++
 tests/test_store_pending_send.py        |  76 ++++
 tests/test_store_read_semantics.py      | 102 +++++
 tests/test_store_render.py              | 117 ++++++
 tests/test_store_torn_line.py           |  73 ++++
 17 files changed, 1728 insertions(+), 6 deletions(-)
```

Blockers: none.

Deferrals to E3+: MockChannel fixtures, capture linearizer/parser, send/completion orchestration, and CLI verb wiring over the store payload helper.
