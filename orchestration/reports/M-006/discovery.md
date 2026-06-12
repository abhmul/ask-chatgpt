START_TIMESTAMP: 2026-06-12T10:36:28-05:00
ESTIMATE: T2 1m
MESSAGES_USED: 0
STATUS: BLOCKED — logged out
RESUME_ACTION: sign into chatgpt.com in the browser, then resume M-006 T2

## Safety/preflight result

- Display: `DISPLAY=:0` observed before browser launch.
- Profile lock: `~/.config/chromium/SingletonLock` did not exist by `os.path.lexists`; no current-user `chromium` processes were present before launch.
- Browser launch: headed persistent Chromium launched with `executable_path=/usr/bin/chromium`, `user_data_dir=/home/abhmul/.config/chromium`, and `--profile-directory=Default`; no Playwright/Chromium protocol mismatch occurred.
- Login check: navigation to `https://chatgpt.com` landed on host `chatgpt.com` with a visible login/auth wall. Per contract, I stopped immediately, did not type into or submit any login form, and did not automate sign-in.
- Source files: `src/ask_chatgpt/selector_maps/real.json` was read only for schema shape and was not edited.

## Prompt-send ledger

- Ledger: `tmp/real-audit-20260612T100518/messages.log`.
- T2 lines appended: 0.
- Per-send purposes: none; blocked before discovery and before any disposable prompt could be sent.

## Enumerated asset/request hosts

These are hostnames only, captured before the logged-out stop condition; no full URLs, queries, tokens, cookies, storage, or profile contents were read or recorded.

- `accounts.google.com`
- `api.oaistatsig.com`
- `cdn.openai.com`
- `chatgpt.com`

## Selector proposal summary

`orchestration/reports/M-006/real-selectors-proposed.json` contains the full selector/attribute schema with every value empty fail-closed. No logged-in UI selector was verified. `login_wall` is also left empty per contract; the preflight uses URL/login-wall heuristics rather than installing a selector found from a logged-out state.

## Unknowns from `docs/runbooks/observe-chatgpt-unknowns.md`

### 1. Zip attachment upload size/type limits

- Fact: Not observed; blocked at logged-out preflight before attachment controls were reachable.
- Selector(s)/behavior: `upload_input` unverified and empty.
- Evidence: Login/auth wall was visible on `chatgpt.com`; no logged-in composer was reached.
- D-001 revisit signal: Upload capability, zip acceptance, size/file-count limits, and model visibility remain unknown.

### 2. Whether/when ChatGPT offers file downloads from responses

- Fact: Not observed; zero prompt sends.
- Selector(s)/behavior: `download_artifact` unverified and empty.
- Evidence: No synthetic download prompt was sent; no artifact or browser `Download` event was tested.
- D-001 revisit signal: Download-primary for bundles remains unproven; fenced/text fallback assumptions cannot be corrected from this blocked run.

### 3. Session pinning via URL/conversation ref

- Fact: Not observed; no disposable conversation was created.
- Selector(s)/behavior: `conversation_ref` attribute remains empty; no `/c/<redacted-uuid>` was created or reopened.
- Evidence: Only preflight URL shape `/` was observed before stop.
- D-001 revisit signal: URL pinning and reopen-after-restart behavior remain unknown.

### 4. Model-selection UI hooks

- Fact: Not observed; model picker was not reachable while logged out.
- Selector(s)/behavior: `model_menu`, `model_option`, and `model_option_disabled` unverified and empty.
- Evidence: Discovery stopped before opening any logged-in model menu.
- D-001 revisit signal: Model selection hooks, disabled-state selectors, labels, and persistence remain unknown.

### 5. Copy-button/clipboard behavior

- Fact: Not observed; no assistant response existed.
- Selector(s)/behavior: `copy_button` unverified and empty.
- Evidence: Zero prompts sent; no clipboard interaction attempted.
- D-001 revisit signal: DOM-read reliability vs copy, copy fidelity, hover/menu behavior, and clipboard permission behavior remain unknown.

### 6. Assistant completion signal

- Fact: Not observed; no generation was started.
- Selector(s)/behavior: `assistant_message`, `message_body`, `streaming_marker`, and `completion_marker` unverified and empty.
- Evidence: Zero prompt sends; no stop-button/copy-button transition observed.
- D-001 revisit signal: Completion strategy and stable wait remain unknown.

### 7. File upload UI hooks

- Fact: Not observed; no logged-in composer or file input was reached.
- Selector(s)/behavior: `upload_input` unverified and empty.
- Evidence: Stopped at login wall before opening attach controls or uploading the synthetic zip.
- D-001 revisit signal: Attachment input/chip/progress selectors and bundle README/catalog visibility remain unknown.

### 8. Text-channel size/truncation limits

- Fact: Not observed and intentionally not provoked.
- Selector(s)/behavior: `truncation_marker` empty by contract.
- Evidence: No large synthetic generation was requested.
- D-001 revisit signal: Text-channel truncation limits and end-marker reliability remain unknown.

### 9. Artifact↔turn identity and wrong-turn risk

- Fact: Not observed; no artifacts or assistant turns existed.
- Selector(s)/behavior: `turn_id` attribute and `download_artifact` selector unverified and empty.
- Evidence: Blocked before any synthetic artifact-generating prompts.
- D-001 revisit signal: Artifact scoping to turns, duplicate filename behavior, and wrong-turn risk remain unknown.

### 10. Operator UX/failure messaging

- Fact: Login-required condition is detectable without reading private account data; exact login-copy/selectors were not installed because this leg must stop when logged out and leave `login_wall` empty.
- Selector(s)/behavior: Preflight detected a visible login/auth wall on `chatgpt.com` and stopped. `conversation_not_found`, upload/download unsupported, model unavailable, and rate-limit markers were not observed.
- Evidence: URL shape `/`, host `chatgpt.com`, `wall_visible=true`; no credentials, account identifiers, storage, cookies, tokens, screenshots, or profile contents were read or stored.
- D-001 revisit signal: Continue only after operator signs into `chatgpt.com` in the browser; then rerun T2 from preflight.

## Output files

- `orchestration/reports/M-006/real-selectors-proposed.json`
- `orchestration/reports/M-006/discovery.md`

END_TIMESTAMP: 2026-06-12T10:37:33-05:00
T2-STATUS: BLOCKED
MESSAGES_USED: 0
