LENS: completeness-spec
START_TIMESTAMP: 2026-06-12T01:33:10-05:00
END_TIMESTAMP: 2026-06-12T01:33:40-05:00
ESTIMATE: T9V3 20m

## CHECK 1: FAIL — mission deliverables present

Implementation deliverables (MISSION-002 deliverables 1–5 as expanded by this T9 contract) are present:

- `pyproject.toml` → PASS: uv project with `playwright==1.60.0`, pytest dev group, src package wheel target.
- `src/ask_chatgpt/driver.py` → PASS: `BrowserSession` has `channel` mock/real knobs, loopback mock guard, `REAL_BASE_URL`, and persistent-context real path.
- `src/ask_chatgpt/selector_map.py` + `src/ask_chatgpt/selector_maps/{mock,real}.json` → PASS: JSON data selector maps; real map intentionally empty/fail-closed.
- `src/ask_chatgpt/driver.py` → PASS: `wait_for_completion()` polls streaming/completion/truncation markers.
- `src/ask_chatgpt/readers.py` → PASS: `ResponseReader`, `DomReader`, `CopyButtonReader`, configurable order; default DOM then copy.
- `src/ask_chatgpt/session_registry.py` → PASS: JSON `SessionRegistry`, explicit `store_path`, `ASK_CHATGPT_STATE_DIR` override.
- `src/ask_chatgpt/driver.py` + `src/ask_chatgpt/api.py` → PASS: `model_settings` passed to `select_model()` and persisted in registry.
- `src/ask_chatgpt/errors.py` → PASS: named actionable error classes present.
- `src/ask_chatgpt/api.py` and `src/ask_chatgpt/__init__.py` → PASS: public `ask_chatgpt()` exported.
- `tests/fixtures/mock_chatgpt/server.py` + `tests/test_fixture_*.py` → PASS: loopback mock fixture and tests present.
- `tests/conftest.py` + `tests/test_network_guard.py` → PASS: autouse socket guard plus browser route guard; verify-run says targeted guard demo `2 passed in 0.45s` and full suite `56 passed in 24.59s`.
- `scripts/accept_uc1.sh` + `scripts/accept_uc1.py` → PASS: ephemeral mock acceptance writes `tmp/accept-uc1-<ts>/` artifacts.
- `docs/runbooks/observe-chatgpt-unknowns.md` → PASS: observation runbook present.
- Full MISSION-002 closeout artifacts → FAIL: `orchestration/reports/M-002/verify.md` and `orchestration/handoffs/MISSION-002-handoff.json` were not present when inspected. If this V3 lens is intended to exclude later synthesis/handoff artifacts, the implementation subset above is PASS; against the literal mission deliverables list, this is a missing deliverable.

## CHECK 2: FAIL — memo §6 fixture affordances

| Memo §6 affordance | Status | Evidence |
|---|---:|---|
| Loopback-only bind, ephemeral port | PRESENT | `server.py:23`, `server.py:1207-1235`; `test_mock_chatgpt_binds_loopback_ephemeral_nonfixed_port`. |
| Reset/inspection/failure scripting endpoints | PRESENT | `/__reset__`, `/__inspect__`, `/__script__` in `server.py`; `test_mock_chatgpt_control_plane`. |
| Conversations keyed by stable refs | PRESENT | `Conversation.conversation_ref`, `/c/<ref>`, `data-conversation-ref`; `test_uc1_continuity_same_identifier_reuses_conversation_and_different_identifier_creates_new`. |
| Session reuse vs new session | PRESENT | `SessionRegistry` + UC1 test asserts same id reuses ref and different id creates new. |
| Selector-map-compatible ready root/chat list/items/new chat/composer/send/model/upload | PRESENT | `mock.json` keys `ready_root`, `chat_list`, `chat_item`, `new_chat_button`, `composer`, `send_button`, `model_*`, `upload_input`; `test_mock_chatgpt_browser_happy_path_uses_selector_map`, upload test. |
| Adversarial older turns, prompt echoes, booby traps, latest-turn-only | PRESENT | `test_adversarial_boobytrap_latest_completed_turn_is_unique`; `test_dom_reader_is_bounded_to_latest_turn_under_adversarial_layouts`; `test_default_read_response_dom_primary_resists_booby_trapped_copy`. |
| Copy button and real clipboard write/read | PRESENT | `server.py:821`, `server.py:1030-1034`; `test_copy_button_clipboard_modes_on_loopback_context`; `test_copy_button_reader_happy_path_returns_clipboard_text`. |
| Copy stale/wrong/missing/truncated variants | PRESENT | `_COPY_MODES={ok,missing,wrong,stale,truncated}` at `server.py:37`; tests at `test_fixture_adversarial.py:252` and `:293`, plus reader missing-button test. |
| Copy permission-denied variant | MISSING | No `permission_denied`/`denied` copy mode in `_COPY_MODES`; grep found no fixture/test simulating clipboard permission denial. This is a silent memo §6 gap. |
| DOM selector keys for assistant, turn id, streaming, completion, body | PRESENT | `mock.json` keys `assistant_message`, `message_body`, `streaming_marker`, `completion_marker`, attr `turn_id`; fixture renders markers at `server.py:807`. |
| DOM stable and virtualized variants | PRESENT | `_LAYOUT_VARIANTS={stable,virtualized}`; `test_virtualized_unstable_variant_hides_older_traps_but_keeps_latest_targetable`; reader parametrized stable/virtualized tests. |
| DOM completion/end and truncation markers | PRESENT | `assistant-turn-complete`, `assistant-truncated`; `test_streaming_turn_flips_to_complete_after_scripted_reads`; `test_response_truncated_failure_renders_truncation_without_completion`. |
| Download artifact card/link/button, real zip, Content-Disposition | PRESENT | `server.py:852`, `server.py:1109`; `test_download_artifact_ok_serves_real_zip_with_attachment_header` captures Playwright download and validates zip/SHA/manifest/header. |
| Download missing/delayed/wrong/corrupt/truncated/collision/unsupported variants | PRESENT | `_DOWNLOAD_MODES={ok,missing,delayed,wrong_older,corrupt,truncated,collision,unsupported}`; `test_download_artifact_variants_are_scriptable_and_detectable`. |
| Fenced base64 BEGIN/END + manifest + bytecount + SHA256 | PRESENT | `build_mock_fenced_patch_bundle()` emits `BEGIN_PATCH_BUNDLE`, `MANIFEST_JSON`, `ZIP_BYTE_COUNT`, `ZIP_SHA256`, `BASE64URL`, `END_PATCH_BUNDLE`; `test_fenced_base64url_patch_bundle_ok_and_variants`. |
| Fenced missing-end/bad-hash/changed+unchanged/oversized variants | PRESENT | `_FENCED_MODES={ok,missing_end,bad_hash,changed_and_unchanged,oversized}`; same fenced test covers each. |
| Upload `<input type=file>` and metadata recording | PRESENT | `server.py:923`, `/__upload__`, `record_upload()`; `test_upload_input_records_tmp_path_file_metadata_and_variants`. |
| Upload unsupported/size-type-reject/corrupt variants | PRESENT | `_UPLOAD_MODES={ok,unsupported,reject_size_type,corrupt}`; upload test covers `unsupported`, `reject_size_type`, `corrupt`. |
| Honest failure: login required | PRESENT | `_FAILURE_MODES` includes `login_required`; `test_login_required_maps_to_named_error`, `test_page_level_honest_failure_markers`. |
| Honest failure: session not found/stale conversation | PRESENT | `_FAILURE_MODES` includes `session_not_found`; `/c/<ref>` returns not-found marker; `test_session_not_found_maps_to_named_error`. |
| Honest failure: model unavailable | PRESENT | `_FAILURE_MODES` includes `model_unavailable`; disabled option render; `test_model_unavailable_maps_to_named_error`. |
| Honest failure: upload unsupported | PRESENT | `_FAILURE_MODES` includes `upload_unsupported` and maps upload mode to unsupported; upload test verifies unsupported UI. |
| Honest failure: download unsupported | PRESENT | `_FAILURE_MODES` includes `download_unsupported`; download unsupported marker/variant tested in `test_download_artifact_variants_are_scriptable_and_detectable`. |
| Honest failure: response truncated | PRESENT | `_FAILURE_MODES` includes `response_truncated`; truncation marker; driver/readers tests raise `ResponseTruncatedError`. |
| Honest failure: rate limit/backoff | PRESENT | `_FAILURE_MODES` includes `rate_limited`; `data-retry-after-seconds=60`; `test_rate_limited_maps_to_named_error`, `test_rate_limited_send_renders_backoff_marker`. |
| Honest failure: selector unavailable | PRESENT | `_FAILURE_MODES` includes `selector_unavailable`; composer absent/marker rendered; `test_selector_unavailable_fixture_mode_maps_to_named_error`. |

## CHECK 3: PASS — named error taxonomy complete

`src/ask_chatgpt/errors.py` defines `LoginRequiredError`, `SessionNotFoundError`, `ModelUnavailableError`, `ResponseTruncatedError`, `SelectorUnavailableError`, `UploadUnsupportedError`, `DownloadUnsupportedError`, and `RateLimitedError`, all subclassing `AskChatGPTError` with operator-action default messages. `tests/test_errors.py` checks subclassing, nonempty/actionable messages, optional details, and absence of credential-like strings.

## CHECK 4: PASS — acceptance proves README UC1 shape

`orchestration/reports/M-002/verify-run.md` and `tmp/accept-uc1-20260612-012754/results.json` show `overall: pass`. Continuity is proven by `same-session-call-1` and `same-session-call-2-continuity` both using `conversation_ref: conv-1`, with `user_prompts: ["accept UC1 prompt one", "accept UC1 prompt two"]`. Model settings are proven by `model-settings-available` with `model_settings: {"model":"mock-default"}` and response `accept UC1 model-settings answer`. Honest failure is proven by `honest-failure-login-required` raising `LoginRequiredError` with an actionable sign-in/no-credentials message.

## CHECK 5: PASS — observation runbook covers all 10 memo §7 unknowns

`docs/runbooks/observe-chatgpt-unknowns.md` has numbered sections 1–10 matching memo §7: zip upload limits; downloads; session pinning; model-selection hooks; copy/clipboard; completion signal; upload hooks; text-channel truncation; artifact↔turn identity; operator UX/failure messaging. The preamble is operator-run/consent-gated, forbids automation and credential/cookie/token/profile capture, requires synthetic/redacted data, and includes an M-003-consumable YAML results template with selector candidates, capabilities, limits, session/model/completion/copy/upload/download/artifact/error fields.

## CHECK 6: FAIL — honest gaps / intended incompleteness

INTENDED incompleteness: `src/ask_chatgpt/selector_maps/real.json` is all empty by design and `tests/test_driver.py::test_real_selector_template_is_all_empty_and_fails_closed` confirms fail-closed behavior; real-site support remains operator-runbook-gated. INTENDED incompleteness: M-003 owns actual bundle retrieval/apply code, while M-002 fixture affordances for download, fenced base64, and upload are present. ACCIDENTAL gap: memo §6 copy permission-denied fixture/test affordance is missing. ACCIDENTAL/pending deliverable gap if applying the literal full mission checklist: `verify.md` and `MISSION-002-handoff.json` are absent.

V3-VERDICT: FAIL
V3-STATUS: DONE
