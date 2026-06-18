PASS

# M4 verification lens 1: falsifiability / mutation

Baseline in isolated copy `/tmp/m4v`: `183 passed in 0.55s` from `uv run pytest -q`.

No gaps found. Each selected wrong implementation flipped its targeted test RED, then the file was restored from `.bak` and the same targeted test returned GREEN.

| # | Acceptance/gotcha | Mutation applied in `/tmp/m4v` | Targeted test | Result |
|---|---|---|---|---|
| 1 | D6/C3 multi-string `content.parts` concatenate with no separator | `src/ask_chatgpt/capture.py`: `_extract_visible_parts` changed `"".join(parts)` to `" ".join(parts)` | `tests/test_capture.py::test_large_current_branch_linearizes_iteratively_excludes_hidden_and_preserves_parts_math` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 2 | D6 visible-vs-hidden excludes assistant code/tool prose | `src/ask_chatgpt/capture.py`: treated `assistant:code` as visible and extracted `content.text` when `parts` absent | `tests/test_capture.py::test_large_current_branch_linearizes_iteratively_excludes_hidden_and_preserves_parts_math` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 3 | D7/C4 synthetic lone `content_type="deep_research"` is not enough | `src/ask_chatgpt/capture.py`: treated `deep_research` content as visible and set `kind="deep_research"` from the label alone | `tests/test_capture.py::test_deep_research_requires_same_exchange_conjunction_and_attaches_hidden_refs` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 4 | D8 attachments remain pending; no downloaded state invented | `src/ask_chatgpt/capture.py`: changed user-upload `AttachmentRef.download_state` from `"pending"` to `"downloaded"` | `tests/test_capture.py::test_all_attachment_shapes_and_citations_normalize_separately_without_download_state_pollution` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 5 | E6/C6 no-op submit raises `PromptNotSubmittedError` | `src/ask_chatgpt/send.py`: made `verify_prompt_submitted` return `SubmittedTurn` when no newer user turn appeared | `tests/test_send_completion.py::test_no_op_submit_verification_raises_prompt_not_submitted` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 6 | E10 no hidden 600s ceiling when `max_total_wait_s=None` | `src/ask_chatgpt/completion.py`: used `600.0` as an implicit total cap when `max_total_wait_s is None` | `tests/test_send_completion.py::test_continuous_progress_past_600_without_total_cap_completes` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 7 | B4 pending local stubs hidden in default transcript reads | `src/ask_chatgpt/store.py`: default visibility filter stopped excluding pending `local:` stubs | `tests/test_store_read_semantics.py::test_load_transcript_last_writer_wins_hides_pending_and_sorts_by_turn_index` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 8 | B12/F3 stdout and `--out` both receive payload | `src/ask_chatgpt/cli.py`: `_emit_payload` wrote only to `--out` when `out` was set | `tests/test_cli.py::test_cli_ask_forwards_flags_and_stdout_and_out_are_identical` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 9 | A3/D5/M4 step 0 backend/salvage `created_at=None` is allowed | `src/ask_chatgpt/models.py`: reintroduced a `created_at is None` rejection for non-local backend turns | `tests/test_models.py::test_backend_turn_record_allows_missing_backend_created_at` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
| 10 | B7/D3 raw mapping strips auth/OAI headers | `src/ask_chatgpt/store.py`: stopped treating raw key `authorization` as sensitive | `tests/test_store_atomic_raw.py::test_write_raw_mapping_atomic_unwraps_header_wrapper_and_never_persists_auth_oai_keys` | PASS: RED (`1 failed`); restored GREEN (`1 passed`) |
