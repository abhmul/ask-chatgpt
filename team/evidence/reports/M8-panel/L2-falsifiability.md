# M8 Panel Lens L2 — Falsifiability report

## Summary

Mutation-tested 9 load-bearing targeted tests across the 4 gotchas plus core-store invariants. All 9 were confirmed falsifiable: each targeted test was green before mutation and went RED after the temporary source mutation. Vacuous/green-by-triviality findings: 0. Every temporary source edit used `cp F F.m8bak` before mutation and `cp F.m8bak F && rm F.m8bak` after; each restore reported `restore_sha_match=yes`.

## Results table

| behavior | test node-id | source file:line mutated | before | after (RED?) | falsifiable? |
|---|---|---:|---|---|---|
| Math fidelity: renderer must not rewrite literal markdown math | `tests/test_store_render.py::test_render_markdown_visible_only_literal_math_and_exact_trailing_newline` | `src/ask_chatgpt/store.py:290` | `1 passed`, exit 0 | RED: assertion diff showed `\\widehat` became `\\hat`; `1 failed`, exit 1 | Y |
| Math fidelity: backend capture must preserve visible `content.parts` math literally | `tests/test_capture.py::test_large_current_branch_linearizes_iteratively_excludes_hidden_and_preserves_parts_math` | `src/ask_chatgpt/capture.py:732` | `1 passed`, exit 0 | RED: expected literal `\\ne`/`\\neq`; mutation produced rendered inequality glyph; `1 failed`, exit 1 | Y |
| Verified send: no silent no-op accepted | `tests/test_send_completion.py::test_no_op_submit_verification_raises_prompt_not_submitted` | `src/ask_chatgpt/send.py:180` | `1 passed`, exit 0 | RED: `Failed: DID NOT RAISE <class 'ask_chatgpt.errors.PromptNotSubmittedError'>`; `1 failed`, exit 1 | Y |
| Completion timeout semantics: no implicit hard 600s ceiling when progress continues | `tests/test_send_completion.py::test_continuous_progress_past_600_without_total_cap_completes` | `src/ask_chatgpt/completion.py:151` | `1 passed`, exit 0 | RED: raised `MaxTotalWaitExceededError` from `src/ask_chatgpt/completion.py:157`; `1 failed`, exit 1 | Y |
| Partial salvage honesty: partial text remains `status="partial"` | `tests/test_store_partial.py::test_record_partial_appends_honest_partial_salvage_with_redacted_details` | `src/ask_chatgpt/store.py:324` | `1 passed`, exit 0 | RED: `AssertionError: assert 'error' == 'partial'`; `1 failed`, exit 1 | Y |
| `--out` mirrors stdout: stdout must not be suppressed by out-file write | `tests/test_store_payload.py::test_emit_payload_writes_stdout_and_out_with_identical_string_bytes` | `src/ask_chatgpt/store.py:378` | `1 passed`, exit 0 | RED: `AssertionError: assert '' == 'héllo\nline'`; `1 failed`, exit 1 | Y |
| Core-store read semantics: last-writer-wins dedupe by `message_id` | `tests/test_store_read_semantics.py::test_load_transcript_last_writer_wins_hides_pending_and_sorts_by_turn_index` | `src/ask_chatgpt/store.py:272` | `1 passed`, exit 0 | RED: expected `complete answer`, got stale partial content; `1 failed`, exit 1 | Y |
| Core-store raw mapping safety: auth/oai keys never persist | `tests/test_store_atomic_raw.py::test_write_raw_mapping_atomic_unwraps_header_wrapper_and_never_persists_auth_oai_keys` | `src/ask_chatgpt/store.py:589` | `1 passed`, exit 0 | RED: persisted metadata still contained an `oai-*` key; `1 failed`, exit 1 | Y |
| Menu fail-closed: absent model label must not select anything | `tests/test_menus.py::test_select_model_absent_label_fails_without_menu_selection_or_send` | `src/ask_chatgpt/menus.py:206` | `1 passed`, exit 0 | RED: `assert channel.menu_clicks == []` failed because mutation clicked `High`; `1 failed`, exit 1 | Y |

## Mutation details

1. `src/ask_chatgpt/store.py:290`: changed `return rendered.rstrip("\\n") + "\\n"` to apply `.replace("\\\\widehat", "\\\\hat")` before returning. Target went RED, then restored.
2. `src/ask_chatgpt/capture.py:732`: changed `return "".join(parts)` to replace literal `\\ne` with a rendered inequality glyph. Target went RED, then restored.
3. `src/ask_chatgpt/send.py:180`: changed the verified-submit condition from `newer and normalize_prompt(latest_user.text) == normalized` to unconditional success once a user turn was seen. Target went RED, then restored.
4. `src/ask_chatgpt/completion.py:151`: changed the explicit total-wait check to also fire at 600s when `max_total_wait_s is None`. Target went RED, then restored.
5. `src/ask_chatgpt/store.py:324`: forced salvaged partial records to `status="error"`. Target went RED, then restored.
6. `src/ask_chatgpt/store.py:378`: replaced the `_emit_stdout(...)` call with `pass`, suppressing stdout. Target went RED, then restored.
7. `src/ask_chatgpt/store.py:272`: changed last-writer-wins assignment to `setdefault(...)`, making first writer win. Target went RED, then restored.
8. `src/ask_chatgpt/store.py:589`: removed the `lowered.startswith("oai-")` sensitive-key clause. Target went RED, then restored.
9. `src/ask_chatgpt/menus.py:206`: changed requested-label equality to `and True`, allowing wrong labels through. Target went RED, then restored.

## Vacuous/green-by-triviality tests

None observed. Every mutation made its targeted test fail.

## Pristine tree proof

```text
$ git status --porcelain src/ tests/
```

```text
$ ls src/ask_chatgpt/*.m8bak 2>/dev/null || true
```

VERDICT: PASS
CONFIDENCE: high — All required gotchas and core invariants were exercised with targeted source mutations, each went RED, and src/tests plus backup files were clean afterward.
