# Observe real ChatGPT unknowns (operator-run, consent-gated)

## Purpose

This runbook is for an operator to manually observe the real `chatgpt.com` UI with their own browser profile and account, under explicit consent, and record empirical facts that automated loopback tests cannot prove. The automated tool and automated tests NEVER perform these steps against the real site; tests are loopback-only against a local mock ChatGPT. The observations here unblock M-003 by confirming or correcting the assumptions that the mock fixture encodes and by supplying data for the later real-site selector map and tool configuration.

## Safety preamble — required before any observation

- Use only your own ChatGPT account, browser profile, quota, and workspace, and proceed only with explicit consent for this real-site manual observation.
- Record ONLY UI selectors, labels, visible behaviors, capability flags, limits, and nonsecret error copy. NEVER record, paste, screenshot, store, or commit credentials, cookies, session tokens, auth headers, local storage, browser-profile contents, account-private content, or sensitive conversation data.
- Nothing in this runbook is automated against the real site. Do not run `ask-chatgpt`, Playwright, pytest, or any browser automation for this observation run; use your own visible browser by hand.
- The future tool takes a browser profile DIRECTORY PATH as configuration and never inspects the profile contents. Do not include profile contents in results; if a path must be configured locally, keep it local and out of shared reports unless the operator explicitly approves a redacted path.
- If using browser developer tools to identify selector candidates, inspect only visible page elements for the current UI controls. Do not inspect cookies, storage, network auth headers, request bodies, or profile files.
- Use disposable prompts, synthetic files, and non-sensitive conversations. Redact account names, email addresses, workspace names, and any private text from notes before sharing.

## General observation setup

Use a dedicated logged-in browser profile that the operator controls. Prefer a new disposable chat and synthetic data: small text files, dummy zips, and prompts that reveal no private repository or account information. For each observation, record the date, browser, account/workspace/model context only as far as the operator is comfortable sharing, and whether the result appears account-, workspace-, or model-dependent. Selector candidates should favor stable visible roles, accessible names, labels, and scoped relationships such as “download button inside latest assistant turn,” not broad transcript scraping.

## 1. Zip attachment upload size/type limits

### What to observe

Zip attachment upload size/type limits: observe accepted/rejected `.zip` sizes, file counts, MIME/extensions, rejection copy, and whether limits differ by account/workspace/model.

### How to observe it manually

In a disposable chat, use the visible attachment control or drag-and-drop target to upload synthetic `.zip` files of increasing size and file count. Try at least one clearly small valid zip, a larger valid zip near the operator's expected workflow size, and a deliberately unsupported or borderline case only if the operator is comfortable. Repeat under different model/workspace contexts only when those contexts are available and non-sensitive. Do not upload private source or credentials.

### What to record

Record accepted maximum observed zip size, first rejected size, file count behavior, accepted/rejected extensions and MIME-like behavior, exact nonsecret rejection copy, and any account/workspace/model differences. Record selector candidates for `composer`, `upload.attachment_button`, `upload.file_input`, `upload.drop_zone`, `upload.progress`, `upload.file_chip`, and `upload.failure_message` → `src/ask_chatgpt/selector_maps/real.json` later. Record config candidates `upload_supported`, `max_zip_bytes`, `max_zip_files`, `allowed_upload_extensions`, and any per-model/workspace overrides → tool config.

### Gotchas

Upload controls may be hidden until the composer is focused or a plus/attachment menu is opened. Some limits may be enforced after a scanning delay rather than immediately. File type may be checked by extension, MIME, or contents. Workspace policy and model capability can change the result. Uploading a file makes its contents available to the service/model; use only synthetic data.

## 2. Whether/when ChatGPT offers file downloads from responses

### What to observe

Whether/when ChatGPT offers file downloads from responses: observe if a prompted patch zip appears as an artifact/download, whether Playwright sees a normal `Download`, suggested filename/MIME, retention/scanning delays, and byte-for-byte zip integrity.

### How to observe it manually

In a disposable chat, ask ChatGPT to produce a tiny patch bundle as a downloadable zip containing only synthetic files and a manifest. Watch whether the response creates an artifact card, file preview, download link, or browser download. If the operator clicks a download, save it to a non-sensitive scratch location and inspect only the resulting filename, type, size, manifest, and whether the zip contents match the requested synthetic files. This runbook does not run Playwright; record whether the browser behavior looks like a normal user-initiated download that M-003 should later validate with Playwright under a separate consent-gated check.

### What to record

Record whether downloads are offered, under what prompt/model/account conditions, whether a normal browser download occurs, suggested filename, MIME/type shown by browser or OS, scanning/retention delay, whether the zip opens successfully, and whether bytes/manifest/content match the requested synthetic bundle. Record selector candidates for `assistant_turn`, `artifact.card`, `artifact.filename`, `artifact.download_button`, `artifact.download_link`, `artifact.status`, and `artifact.error` → real-site selector map. Record config candidates `download_supported`, `download_requires_artifact_mode`, `download_scan_delay_seconds`, `download_retention_observed`, and `playwright_download_event_expected`/`playwright_download_event_unverified` → tool config and later M-003 validation.

### Gotchas

Some accounts or models may create text instructions but no downloadable artifact. Artifact generation, scanning, and availability may lag after the assistant text finishes. Browser “ask where to save” settings can obscure whether a normal download happened. Download links may expire or be tied to the current session. Do not treat manual browser download as proof that Playwright has observed a `Download`; it is only the selector/behavior input for M-003 unless a later approved instrumented run confirms it.

## 3. Session pinning via URL/conversation ref

### What to observe

Session pinning via URL/conversation ref: observe whether stored conversation URLs/refs reopen the intended session across process/browser restarts, deleted/renamed chats, archived chats, and simultaneous sessions.

### How to observe it manually

Create a disposable chat, give it a harmless recognizable title or first prompt, and note the URL/ref pattern without sharing the actual private ref outside local operator notes. Close and reopen the browser, restart the browser process if appropriate, and paste or navigate back to the stored URL. Test the same disposable chat after rename, archive, and deletion only if the operator accepts that the test chat may be lost. Open the same stored URL in two windows or tabs to observe simultaneous-session behavior.

### What to record

Record whether the stored URL/ref reopens the intended conversation after restart, whether rename changes the ref, what happens after archive/delete, whether simultaneous sessions stay synchronized or conflict, and what visible error appears for stale refs. Record selector candidates for `conversation.current_ref_source`, `conversation.list_item`, `conversation.title`, `conversation.not_found_message`, `new_chat_button`, and `chat_history.search_or_archive_entry` if visible → real-site selector map. Record config candidates `session_pinning_supported`, `session_ref_kind`, `session_ref_redaction_policy`, `deleted_session_behavior`, `archived_session_behavior`, and `simultaneous_session_policy` → session store/tool config.

### Gotchas

Conversation refs and URLs can be account-private even if they are not credentials; do not commit real refs. Deleted chats may be unrecoverable. Archived chats may disappear from the default list but still open by URL. Simultaneous tabs can race on the active draft, model selection, or streaming turn.

## 4. Model-selection UI hooks

### What to observe

Model-selection UI hooks: observe stable selectors/labels for the target model/settings, persistence across sessions, failure states when unavailable, and whether model selection must be manual.

### How to observe it manually

In a disposable chat, open the model picker/menu, note visible labels and selected-state indicators, and select the intended target model if the operator consents. Create a new chat, reload the page, and reopen an existing chat to see whether the selection persists. If a desired model is unavailable, observe the visible disabled/upgrade/capacity/error state without attempting to bypass it.

### What to record

Record exact model option labels, accessible names if visible, selected-state text, whether the model can be selected before/after upload, persistence across new/reopened sessions, and unavailable/failure copy. Record selector candidates for `model.menu_button`, `model.option`, `model.option_label`, `model.selected_label`, `model.disabled_option`, `model.unavailable_message`, and any setting toggles that must accompany the model → real-site selector map. Record config candidates `preferred_model_label`, `model_selection_supported`, `model_selection_manual_only`, `model_selection_persists`, and `model_unavailable_error_mapping` → tool config.

### Gotchas

Labels can vary by account plan, workspace, region, rollout, or A/B test. Menus may close on blur and may render options lazily. Some models are only available after changing workspace or starting a new chat. A model displayed in history may not be selectable for a new turn.

## 5. Copy-button/clipboard behavior

### What to observe

Copy-button/clipboard behavior: observe button availability, hidden-menu behavior, permission prompts, completeness for Markdown/code/citations, stale clipboard races, and any visible account/telemetry prompts; do not infer server invisibility from local tests.

### How to observe it manually

Ask for a response containing Markdown headings, a code block, a list, and citations or links if available. After the response completes, hover or keyboard-focus the latest assistant turn and locate the copy affordance or actions menu. Before clicking Copy, put a harmless sentinel string in a local scratch editor; after clicking, paste into the scratch editor and compare the pasted content with the visible latest response. Repeat once after another response to check stale clipboard behavior and wrong-turn targeting.

### What to record

Record whether a copy button exists, whether it is hidden behind hover or a menu, any browser or site permission prompt, whether Markdown/code/citations are complete, whether the latest turn or a stale/older turn was copied, whether the OS clipboard was overwritten, and any visible account/telemetry disclosure or prompt. Record selector candidates for `assistant_turn`, `assistant_turn_body`, `assistant_turn_actions`, `copy.button`, `copy.menu_item`, `copy.success_toast`, and `copy.permission_prompt` → real-site selector map. Record config candidates `copy_supported`, `copy_requires_hover`, `copy_requires_permission`, `copy_markdown_fidelity`, `copy_citation_fidelity`, and `clipboard_side_effect_warning` → tool config.

### Gotchas

Copying clobbers the operator's OS clipboard. Hidden action menus can target the wrong turn if the cursor is over an older message. Clipboard permissions differ by browser and profile. Some citation content may require expansion. Local clipboard success does not prove anything about server visibility or telemetry; do not infer invisibility from a local paste test.

## 6. Assistant completion signal

### What to observe

Assistant completion signal: observe reliable end-of-turn markers, streaming stop behavior, regenerate/retry effects, and whether long responses are virtualized or lazily loaded.

### How to observe it manually

Prompt for a short response and then a long structured response. Watch the UI during streaming: stop button, send button enabled/disabled state, spinner, “thinking” text, action buttons, and any final marker. After completion, try visible regenerate/retry controls only on disposable content and observe whether the old turn is replaced or a new turn appears. Scroll through a long answer to see whether older portions are lazily loaded or virtualized.

### What to record

Record the most reliable completion indicators and the order in which they appear/disappear, whether the send button becomes enabled before the response is truly complete, how stop/regenerate/retry change turn identity, and whether long responses remain present in the DOM/visible page. Record selector candidates for `assistant_turn`, `assistant_turn_body`, `assistant_turn_streaming_marker`, `assistant_turn_complete_marker`, `stop_generating_button`, `send_button`, `regenerate_button`, `retry_button`, and `continue_generating_button` → real-site selector map. Record config candidates `completion_signal_strategy`, `completion_stable_wait_ms`, `long_response_virtualized`, `regenerate_replaces_turn`, and `retry_failure_mapping` → tool config.

### Gotchas

Action buttons may appear before attachments, citations, or code blocks finish loading. A “continue generating” control may mean the response is incomplete even after streaming stops. Long responses can be virtualized, making naive DOM reads partial. Regenerate/retry may invalidate stored turn references.

## 7. File upload UI hooks

### What to observe

File upload UI hooks: observe stable selectors for attachment input/drop, upload progress/failure messages, and whether bundle README/catalog files are visible to the model.

### How to observe it manually

Prepare a synthetic bundle with a README/catalog file and one or two tiny dummy files. In a disposable chat, upload the bundle through the visible attachment control and, separately if available, drag-and-drop. Watch progress, attached-file chips, scanning, and failure states. Ask the model a non-sensitive question such as “List the files you can see in the uploaded bundle and summarize the README/catalog” to observe whether the README/catalog is visible to the model.

### What to record

Record selector candidates and labels for attachment control, file input, drop target, progress indicator, attached-file chip, remove-file action, and failure message. Record whether the README/catalog is visible to the model, whether nested paths/file counts are preserved, and whether upload must complete before sending. Feed selector candidates to `composer`, `upload.attachment_button`, `upload.file_input`, `upload.drop_zone`, `upload.progress`, `upload.file_chip`, `upload.remove_file_button`, and `upload.failure_message` → real-site selector map. Feed `bundle_readme_visible_to_model`, `upload_requires_send_after_complete`, `upload_progress_states`, and `upload_failure_error_mapping` → tool config.

### Gotchas

A model may acknowledge a file chip without actually reading every file. Large or nested bundles may be partially indexed. Upload parsing can lag behind UI progress. Some modes support attachments but not archives. Removing an uploaded file before send may leave stale UI state.

## 8. Text-channel size/truncation limits

### What to observe

Text-channel size/truncation limits: observe maximum safe fenced payload size, truncation symptoms, and whether checksums/end markers catch all partial outputs.

### How to observe it manually

In a disposable chat, ask for synthetic fenced payloads of increasing size using explicit `BEGIN`, `END`, byte/character count, and checksum/end-marker text. Keep the payload harmless and avoid private data. Compare visible output and copied output, if copy is being evaluated, to see whether the final marker and declared length/checksum survive. Stop before the browser or account becomes stressed.

### What to record

Record the largest payload size that reliably includes all markers, symptoms of truncation, whether the UI asks to continue, whether copy and visible text differ, and whether declared byte count/checksum/end markers catch every partial result observed. Record selector candidates for `assistant_turn_body`, `copy.button` if used, `continue_generating_button`, and truncation/error banners → real-site selector map. Record config candidates `max_safe_fenced_payload_chars`, `max_safe_fenced_payload_bytes`, `truncation_detection_required_markers`, `text_zip_fallback_max_bytes`, and `response_truncated_error_mapping` → tool config.

### Gotchas

Model output limits and UI rendering limits are different. “Continue” can produce a second turn or altered payload that fails checksum. Copy and DOM-visible text may have different truncation/fidelity behavior. Long responses may be virtualized, so visible absence is not always actual absence, but missing end markers must be treated as failure.

## 9. Artifact↔turn identity and wrong-turn risk

### What to observe

Artifact identity and wrong-turn risk: observe how response files are associated with a specific assistant turn when older artifacts exist in the same conversation.

### How to observe it manually

In one disposable conversation, ask for one downloadable synthetic artifact, then later ask for a second artifact with a clearly different filename and contents. Scroll between turns and observe where artifact cards, filenames, previews, and download controls appear. Download or open only the synthetic artifacts if needed to confirm identity. Repeat with duplicate or similar filenames only if the operator wants to measure collision behavior.

### What to record

Record whether each artifact is visually nested inside its assistant turn, appears in a global side panel, or remains sticky after scrolling; how filenames, timestamps, previews, or card positions distinguish old vs latest artifacts; and whether clicking the latest visible download ever retrieves an older file. Record selector candidates for `assistant_turn`, `assistant_turn_id`, `artifact.card_within_turn`, `artifact.filename`, `artifact.timestamp`, `artifact.preview`, and `artifact.download_button_within_turn` → real-site selector map. Record config candidates `artifact_scoped_to_turn`, `artifact_latest_selection_rule`, `duplicate_filename_behavior`, and `wrong_turn_risk_level` → tool config.

### Gotchas

Artifact side panels may detach files from the originating turn. Duplicate filenames can be auto-renamed by the browser, not by ChatGPT. Lazy loading can hide older or newer cards until scrolled. A preview pane may keep showing an older artifact while the transcript focus moves to a newer turn.

## 10. Operator UX/failure messaging

### What to observe

Operator UX/failure messaging: observe whether login, session-not-found, upload/download unsupported, and model-unavailable errors can be detected without reading credentials or account-private data.

### How to observe it manually

Use only controlled, non-sensitive scenarios. In a separate disposable profile or logged-out window, observe the login-required state without entering credentials. Navigate to a known-bad or redacted disposable conversation URL to observe session-not-found behavior. Observe model-unavailable, upload-unsupported, and download-unsupported states only when they arise naturally or through harmless synthetic tests; do not attempt to bypass account or workspace controls.

### What to record

Record exact nonsecret visible copy for login required, session not found, upload unsupported, download unsupported, and model unavailable; whether the message can be detected without account-private data; and what user remediation should be shown. Record selector candidates for `login_required_marker`, `session_not_found_message`, `upload.unsupported_message`, `download.unsupported_message`, `model.unavailable_message`, `rate_limit_banner`, and `operator_blocking_modal` → real-site selector map. Record error mappings `LOGIN_REQUIRED`, `SESSION_NOT_FOUND`, `UPLOAD_UNSUPPORTED`, `DOWNLOAD_UNSUPPORTED`, `MODEL_UNAVAILABLE`, `RATE_LIMITED`, and `SELECTOR_UNAVAILABLE` → tool config/errors.

### Gotchas

Failure pages and modals can include account email, workspace name, plan details, or private conversation titles; redact before sharing. Logged-out tests should not record credentials or login flow details. Some errors are transient or localized. A missing selector must fail closed rather than broaden into reading private transcript content.

## Results template for M-003

Copy this template into a local observation note and fill only nonsecret facts. Use `unknown` when not observed. Do not paste credentials, cookies, tokens, profile contents, private conversation text, or unredacted conversation refs.

```yaml
observation_run:
  date:
  operator_consent_confirmed: true
  browser:
  account_context_redacted:
  workspace_context_redacted:
  models_observed: []
  notes_redacted:

safety_confirmation:
  used_operator_owned_account: true
  recorded_only_ui_labels_selectors_behaviors: true
  omitted_credentials_cookies_tokens_profile_contents: true
  no_real_site_automation_used: true

selector_candidates:
  composer:
  assistant_turn:
  assistant_turn_id:
  assistant_turn_body:
  assistant_turn_streaming_marker:
  assistant_turn_complete_marker:
  send_button:
  stop_generating_button:
  regenerate_button:
  retry_button:
  continue_generating_button:
  copy_button:
  copy_menu_item:
  copy_success_toast:
  model_menu_button:
  model_option:
  model_selected_label:
  model_unavailable_message:
  upload_attachment_button:
  upload_file_input:
  upload_drop_zone:
  upload_progress:
  upload_file_chip:
  upload_remove_file_button:
  upload_failure_message:
  artifact_card:
  artifact_card_within_turn:
  artifact_filename:
  artifact_timestamp:
  artifact_download_button:
  artifact_download_link:
  artifact_status_or_error:
  conversation_ref_source:
  conversation_list_item:
  conversation_title:
  conversation_not_found_message:
  login_required_marker:
  upload_unsupported_message:
  download_unsupported_message:
  rate_limit_banner:
  operator_blocking_modal:

capabilities:
  upload_supported: unknown
  download_supported: unknown
  normal_browser_download_observed: unknown
  playwright_download_event_observed: not_observed_by_this_manual_runbook
  copy_supported: unknown
  model_selection_supported: unknown
  model_selection_manual_only: unknown
  session_pinning_supported: unknown
  bundle_readme_visible_to_model: unknown
  long_response_virtualized_or_lazy_loaded: unknown

limits:
  zip_upload_max_accepted_bytes:
  zip_upload_first_rejected_bytes:
  zip_upload_max_file_count:
  zip_upload_allowed_extensions: []
  zip_upload_rejection_copy_redacted:
  text_channel_max_safe_fenced_payload_chars:
  text_channel_max_safe_fenced_payload_bytes:
  text_channel_truncation_symptoms: []
  text_channel_required_end_markers: []
  text_zip_fallback_max_bytes:

session_pinning:
  ref_kind_observed:
  reopen_after_browser_restart:
  reopen_after_process_restart:
  behavior_after_rename:
  behavior_after_archive:
  behavior_after_delete:
  simultaneous_tabs_behavior:
  redaction_policy_for_refs:

model_selection:
  preferred_model_label:
  option_labels_observed: []
  selected_state_indicator:
  persists_new_chat:
  persists_reopened_chat:
  unavailable_state_copy_redacted:
  failure_error_mapping:

completion_signal:
  primary_completion_indicator:
  secondary_completion_indicator:
  send_button_enabled_semantics:
  stop_button_disappears_on_complete:
  regenerate_replaces_turn:
  retry_behavior:
  recommended_stable_wait_ms:

copy_clipboard:
  requires_hover_or_menu:
  browser_permission_prompt:
  markdown_complete:
  code_blocks_complete:
  citations_complete:
  stale_clipboard_race_observed:
  clipboard_side_effect_warning:
  visible_telemetry_or_account_prompt_redacted:

upload_behavior:
  progress_states: []
  failure_states_redacted: []
  upload_requires_completion_before_send:
  readme_catalog_visible_to_model:
  account_workspace_model_differences:

download_behavior:
  prompts_that_produced_download_redacted: []
  artifact_or_download_conditions:
  suggested_filename:
  mime_or_type_observed:
  scan_or_retention_delay_seconds:
  zip_integrity_verified:
  manifest_matches_requested_synthetic_files:
  m003_playwright_validation_needed: true

artifact_turn_identity:
  artifacts_nested_within_turn:
  global_or_sticky_artifact_panel:
  duplicate_filename_behavior:
  latest_artifact_selection_rule:
  wrong_turn_risk_level:

operator_ux_errors:
  login_required_detectable_without_private_data:
  session_not_found_detectable_without_private_data:
  upload_unsupported_detectable_without_private_data:
  download_unsupported_detectable_without_private_data:
  model_unavailable_detectable_without_private_data:
  recommended_actionable_messages: []

deviations_or_unobserved_items: []
```

## Cross-references and handoff

The local mock fixture requirements in `orchestration/reports/M-001/decision-memo.md` §6 encode assumed answers for copy, DOM fallback, downloads, fenced base64 fallback, uploads, session handling, and honest failures. This runbook's job is to confirm or correct those assumptions on the real site, using only operator-consented manual observation. The filled results feed the later real-site selector map template at `src/ask_chatgpt/selector_maps/real.json` and tool configuration for model selection, session pinning, upload/download support, text-channel limits, completion detection, and actionable failure mapping. The README acceptance shape requires this operator-gated real-site half in addition to loopback mock acceptance; green mock tests alone are not real-site proof.
