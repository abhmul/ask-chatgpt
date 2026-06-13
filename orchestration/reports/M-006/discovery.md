START_TIMESTAMP: 2026-06-12T19:54:54-05:00
ESTIMATE: T2 45m
MESSAGES_USED: 7
STATUS_DETAIL: DONE

## Safety/preflight
- CDP preflight: reachable via read-only loopback `/json/version`
- CDP topology: contexts=1; preexisting_tabs_recorded=1
- Browser handling: attached via `connect_over_cdp(http://127.0.0.1:9222)`, opened one CDP-owned tab at a time, never launched Chromium, never used stealth/evasion, never read cookies/storage/profile contents, and never called `browser.close()` or `context.close()`.
- Tab hygiene self-check: preexisting tabs still present=True in main and recovery checks; latest page_count_before_teardown=2; preexisting_count=1; only owned tabs were closed

## Prompt-send ledger
- Ledger: `tmp/real-audit-20260612T194143/messages.log`
- T2 lines appended by this run: 7
- 1. `completion` at `/`
- 2. `copy` at `/c/<redacted-uuid>`
- 3. `download` at `/c/<redacted-uuid>`
- 4. `artifact2` at `/c/<redacted-uuid>`
- 5. `upload` at `/c/<redacted-uuid>`
- 6. `pinning` at `/`
- 7. `pinning2` at `/`

## Enumerated asset/request hosts
- `cdn.auth0.com`
- `cdn.openai.com`
- `chatgpt.com`
- `sdmntprcentralus.oaiusercontent.com`

## Proposed selectors and attributes
- `selectors.ready_root` = `main:has(#prompt-textarea)` — Main app region containing the stable prompt composer indicates logged-in chat readiness.
- `selectors.chat_list` = `nav:has(a[href^="/c/"])` — Navigation landmark containing /c/ conversation links is stable and title-free.
- `selectors.chat_item` = `nav a[href^="/c/"]` — Conversation history items are stable links whose href path starts with /c/; titles are not read.
- `selectors.new_chat_button` = `a[aria-label="New chat"]` — Accessible New chat link label is stable and non-class based.
- `selectors.composer` = `#prompt-textarea` — Stable composer id used by ChatGPT for the prompt input.
- `selectors.send_button` = `button[data-testid="send-button"]` — Stable data-testid for the prompt submit control.
- `selectors.model_menu` = `` — No safe stable model-menu selector was found after bounded 0-message discovery; left empty fail-closed rather than risking account/profile controls.
- `selectors.model_option` = `` — Model picker was not safely opened; options left empty fail-closed.
- `selectors.model_option_disabled` = `` — No disabled model option was safely observed in the opened model picker.
- `selectors.assistant_message` = `[data-message-author-role="assistant"]` — Stable data attribute identifies assistant-authored message containers.
- `selectors.message_body` = `[data-message-author-role="assistant"] .markdown` — Assistant message Markdown body uses stable semantic markdown container.
- `selectors.streaming_marker` = `button[data-testid="stop-button"]` — Stable stop/streaming control observed only while generation was active.
- `selectors.completion_marker` = `button[data-testid="copy-turn-action-button"]` — Turn action/copy control appeared after streaming completed; pair with stop-button disappearance and stable wait.
- `selectors.copy_button` = `button[data-testid="copy-turn-action-button"]` — Stable data-testid for per-turn copy action.
- `selectors.download_artifact` = `button[aria-label*="Download"]` — Accessible Download-labelled button is a stable artifact affordance.
- `selectors.upload_input` = `input[type="file"]` — Native file input is a stable upload hook and can be hidden behind the attach control.
- `selectors.login_wall` = `` — Not verified because login/logout is never automated; URL/auth-wall heuristics are used instead.
- `selectors.conversation_not_found` = `` — Bogus /c/<redacted-uuid> navigation did not expose a stable not-found marker during bounded 0-message observation; left empty fail-closed.
- `selectors.truncation_marker` = `` — Not verified because giant/truncating generations are out of scope for this leg.
- `selectors.rate_limit_marker` = `` — Not verified because this leg never provokes rate limits.
- `attributes.conversation_ref` = `` — No stable DOM attribute carrying the conversation ref was verified; observed source is the URL path shape /c/<redacted-uuid>.
- `attributes.turn_id` = `data-message-id` — Stable per-assistant-turn id attribute was present; only the attribute name was recorded.

## Unknowns from `docs/runbooks/observe-chatgpt-unknowns.md`

### 1. Zip attachment upload size/type limits
- Fact observed: small synthetic zip accepted = yes; size `437` bytes; first rejected size not tested.
- Selector(s)/behavior: upload input `input[type="file"]`; file chip visible = yes; upload/send completion behavior = upload prompt sent after chip/acceptance.
- Anonymized evidence: disposable prompt at `/c/<redacted-uuid>`; synthetic filenames only; no private files uploaded.
- D-001 revisit signal: true max zip bytes/file-count limits remain unmeasured; only a tiny valid zip was tested.

### 2. Whether/when ChatGPT offers file downloads from responses
- Fact observed: download affordance offered = yes; Playwright `Download` event = no; suggested filename = `not observed`; MIME/type = `not observed`.
- Selector(s)/behavior: download selector `button[aria-label*="Download"]`; integrity = not verified.
- Anonymized evidence: synthetic download prompts at shapes ['/c/<redacted-uuid>', '/c/<redacted-uuid>']; no real data requested.
- D-001 revisit signal: if no normal `Download` event was observed, keep fenced/base64 bundle fallback as primary or require later validation.

### 3. Session pinning via URL/conversation ref
- Fact observed: active conversation URL shape `/c/<redacted-uuid>`; reopen-by-URL within the running session = yes on a synthetic pinning prompt; restart persistence not tested.
- Selector(s)/behavior: conversation ref source = URL path /c/<redacted-uuid>; no DOM ref attribute verified; conversation-not-found selector ``.
- Anonymized evidence: bogus URL shape `/c/<redacted-uuid>` produced no stable not-found marker; pinning confirmation used only synthetic `PINNING-OK-2` content; real ids were not written.
- D-001 revisit signal: driver should support URL-derived conversation refs if no DOM ref attribute is installed; cross-restart persistence remains operator-observable, not tested here.

### 4. Model-selection UI hooks
- Fact observed: model picker opened = no after bounded safe discovery; option count observed = 0; disabled option observed = no; selection persistence not changed or tested.
- Selector(s)/behavior: menu ``; option ``; disabled ``.
- Anonymized evidence: model labels/account plan details were not recorded; only selector structure and counts were retained.
- D-001 revisit signal: preferred-model label and unavailable copy remain account/rollout dependent and should be configurable.

### 5. Copy-button/clipboard behavior
- Fact observed: copy button visible = yes; clicked latest synthetic turn = yes; success feedback = no; clipboard content was not read to avoid possible preexisting clipboard leakage.
- Selector(s)/behavior: copy selector `button[data-testid="copy-turn-action-button"]`; requires hover/menu = not required or not determined.
- Anonymized evidence: synthetic Markdown/code response at `/c/<redacted-uuid>`; no private transcript copied or stored.
- D-001 revisit signal: Markdown/code/citation fidelity via clipboard remains unverified unless a later operator-approved clipboard test uses a known sentinel.

### 6. Assistant completion signal
- Fact observed: streaming marker observed = yes; completion marker observed = yes; recommended stable wait = `2000` ms.
- Selector(s)/behavior: assistant `[data-message-author-role="assistant"]`; body `[data-message-author-role="assistant"] .markdown`; streaming `button[data-testid="stop-button"]`; completion `button[data-testid="copy-turn-action-button"]`.
- Anonymized evidence: latest assistant body was read only for synthetic prompts; URL shape `/c/<redacted-uuid>`.
- D-001 revisit signal: use stop-button-gone plus copy/action-button-appears plus a stable wait; do not rely solely on send-button enabled state.

### 7. File upload UI hooks
- Fact observed: attachment input found = yes; zip accepted = yes; README/catalog visible to model = yes; nested path visibility = yes.
- Selector(s)/behavior: file input `input[type="file"]`; chip selector/evidence = `text="m006_t2_bundle.zip"`; upload progress/error copy not forced.
- Anonymized evidence: uploaded only `m006_t2_bundle.zip` with README/alpha/bravo dummy files.
- D-001 revisit signal: upload failures, large bundles, and archive parsing lag need later bounded tests before setting high limits.

### 8. Text-channel size/truncation limits
- Fact observed: no giant generation was forced; truncation marker observed = no; short/medium synthetic responses completed normally = yes.
- Selector(s)/behavior: truncation selector `` left empty fail-closed; completion strategy above is still required for normal outputs.
- Anonymized evidence: only tiny/medium synthetic prompts were used; no stress payload was generated.
- D-001 revisit signal: max fenced payload size and checksum/end-marker policy remain to be measured without stressing quota/browser.

### 9. Artifact↔turn identity and wrong-turn risk
- Fact observed: artifact nested/scoped to assistant turn = selector scope not conclusively verified; multiple artifacts observed = yes; latest selection rule = use latest matching download affordance and synthetic filename when available.
- Selector(s)/behavior: assistant turn `[data-message-author-role="assistant"]` plus artifact/download selector `button[aria-label*="Download"]` when present.
- Anonymized evidence: synthetic filenames only; no real artifacts or filenames were recorded.
- D-001 revisit signal: if artifact selector is global rather than turn-scoped, downstream must scope to the latest assistant turn or require filename matching.

### 10. Operator UX/failure messaging
- Fact observed: login wall not triggered by design; session-not-found detectable = no; rate limit not triggered = yes; model unavailable/upload/download unsupported only observed if naturally present.
- Selector(s)/behavior: login selector ``; not-found selector ``; rate-limit selector ``.
- Anonymized evidence: not-found copy shape `not observed`; no account identifiers or real conversation ids recorded.
- D-001 revisit signal: preserve actionable operator errors: `CDP_UNREACHABLE`, `logged out`, `CHALLENGE_NOT_CLEARED`, `SESSION_NOT_FOUND`, `SELECTOR_UNAVAILABLE`, and fail-closed upload/download unsupported handling.

## D-001 revisit signals
- None beyond the explicitly unverified fail-closed keys above.

END_TIMESTAMP: 2026-06-12T20:06:32-05:00
T2-STATUS: DONE
