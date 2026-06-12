# M-001 decision memo — assistant response and patch-bundle return channels

## 1. TL;DR / recommendation up front

Recommendation only — the team lead decides; the decision is NOT made.
Spec anchor: the new product must expose `ask_chatgpt(prompt, session_identifier, model_settings...) -> text`, preserve session continuity, attempt model settings, support bundle-out/patch-bundle-back filesystem use, and keep CLI/library-first/local-mock/operator-runbook/honest-failure constraints (README.md:9-27).
Plain text primary: copy-button/clipboard automation for the latest completed assistant turn, because it uses ChatGPT's own copied serialization and avoids custom Markdown/code DOM parsing.
Plain text fallback: bounded selector-map DOM extraction of only the latest completed assistant turn, guarded by completion/end-marker checks and actionable `RESPONSE_TRUNCATED`/selector failures.
Patch-bundle zip primary: Playwright file-download capture of a GPT-produced downloadable zip artifact, but only after an operator-gated runbook proves real-site downloads for the target account/model.
Patch-bundle fallback: a small checksummed fenced base64url zip payload returned through the text channel, validated by byte count/SHA-256/manifest before apply; fail honestly when too large/truncated.
Connector-style callback is not recommended for the initial default because this repo's conflict statement asks for return capture without the predecessor connector and README keeps the product library-first (README.md:24-26).

## 2. Archive Level B rationale, with evidence strength

- Actual Level B rule: the browser layer was UI-shell automation only — open/wake chats, select stable model/app controls, send seeds, record coarse health — while completion and structured outputs came from orchestrator events/tools, never assistant text parsing (control-plane/DESIGN.md:46,146; control-plane/docs/runbooks/phase3-chatgpt-browser.md:7-9). Evidence strength: strong as architecture/source/runbook contract; it deliberately does not satisfy the new `-> text` requirement.
- Closed driver surface: `ChatUIDriver` exposed exactly `open_or_focus`, `new_or_select_chat`, `select_model_if_available`, `enable_connector_if_available`, `send_seed_prompt`, `read_coarse_health`, `health`, and `close`; forbidden source tokens included assistant/response/transcript/text extraction names (control-plane/DESIGN.md:888-961; control-plane/src/control_plane/browser/driver.py:15-27,97-105). Evidence strength: strong structural proof that predecessor code made assistant reading unrepresentable.
- Canonical-state/audit risk: transcripts, browser DOM, stdout, and dashboard state were noncanonical; SQLite events plus stored report/patch metadata were authoritative, and manual runbooks verified completion from orchestrator state, never chat text (control-plane/DESIGN.md:46; control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:135-137; control-plane/docs/runbooks/mvp-demo.md:7-11,165-167). Evidence strength: strong for the predecessor's audit model; not a measurement that DOM reading is inherently unreliable for this smaller tool.
- Selector fragility/UI-drift risk: selector maps were operator-versioned data, automated runs were loopback/data by default, real `chatgpt.com` required explicit opt-in plus a selector map/profile, and stale selectors should stop with coarse health rather than broaden or guess (control-plane/DESIGN.md:1018-1044; control-plane/docs/runbooks/phase3-chatgpt-browser.md:77,126-131; control-plane/VERIFICATION.md:307-308). Evidence strength: medium-strong engineering mitigation and mock proof; real ChatGPT selector drift was anticipated, not empirically measured.
- Scraper complexity/attack-surface risk: the predecessor intentionally avoided generic scraper-shaped methods and tested only selector visibility, `data-conversation-ref`, composer fill/click, and event causality (control-plane/src/control_plane/browser/playwright_driver.py:41-78,184-203,418-426; orchestration/handoffs/MISSION-004-handoff.json:36-47). Evidence strength: strong for shipped complexity containment; no comparative implementation cost study of a reader.
- Assistant-DOM prompt-injection risk: the Phase-3 mock rendered booby-trapped assistant messages, while green artifacts had zero sentinel leaks; the archive explicitly treated assistant DOM as adversarial content the adapter must not copy (control-plane/DESIGN.md:1084-1086; control-plane/tests/fixtures/phase3_mock_chat.py:1-3,271-273; control-plane/VERIFICATION.md:121-122). Evidence strength: strong loopback adversarial proof; not a proof over live `chatgpt.com` responses.
- Credential/profile/account-safety risk: real runs used an operator-owned persistent profile; the adapter never automated login and credentials/cookies/session/profile contents were barred from prompts, events, logs, reports, and commits (control-plane/DESIGN.md:871,1084; control-plane/docs/runbooks/phase3-chatgpt-browser.md:13,43-45; control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:9-11). Evidence strength: strong safety policy plus artifact scans; no automated real-site credential handling by design.
- Account/ToS/detectability: I found no resolved archive claim that DOM extraction specifically causes bans, violates ToS, or is detectable by anti-bot systems; the archive supports adjacent constraints against bypassing auth/approval/usage controls, unsafe public tunnels, and non-operator credential handling (control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:66-76,207-217; control-plane/docs/runbooks/phase3-chatgpt-browser.md:13,45). Evidence strength: policy/runbook reasoning, not empirical ban/ToS evidence.
- Empirical scope: machine verification was loopback/mock/local and intentionally did not contact ChatGPT/OpenAI; OP-1/OP-3/OP-4 real ChatGPT connector/browser/MVP halves remained operator-gated (control-plane/VERIFICATION.md:5,126-130; control-plane/docs/runbooks/phase3-chatgpt-browser.md:134-136). Evidence strength: high for what was and was not proven; live DOM/copy/download extraction remains unknown.

## 3. Candidate channels weighed

### 3.1 DOM extraction via selector maps

- Mechanism: wait for the target conversation's latest assistant turn to complete, select the last assistant message subtree via selector-map keys, read rendered text, normalize, and return only that turn.
- Fit for `-> text`: good mechanically and simplest to mock, but it is the clearest departure from Level B and inherits selector/completion/turn-selection fragility.
- Fit for zip retrieval: poor for binary; acceptable only as the fallback protocol carrying a small base64url zip with explicit `BEGIN/END`, byte count, SHA-256, and manifest.
- Server-visible/account relevance: DOM reads are mostly client-local after the conversation is loaded; any scroll/expand needed to reveal content could become server-visible and must be operator-runbook unknown.
- UI drift/session/model: high drift risk in message markup and streaming markers; session continuity and model selection are orthogonal and must be solved by local `session_identifier -> conversation_ref/URL` mapping plus model selectors (README.md:9; control-plane/src/control_plane/browser/selectors.py:12-15,75-121).
- Predecessor reuse: selector-map schema, URL loopback/external policy, Playwright locator helpers, and conversation-ref reading can be reused; the reader itself conflicts with the predecessor's forbidden-token/8-method boundary (control-plane/src/control_plane/browser/driver.py:15-27,97-105; control-plane/src/control_plane/browser/playwright_driver.py:368-386,418-426).

### 3.2 Copy-button / clipboard automation

- Mechanism: target the latest completed assistant message, click its Copy affordance, and read clipboard text through browser-granted clipboard permissions or a controlled test clipboard.
- Fit for `-> text`: best default recommendation if operator proof passes, because the UI owns Markdown/code serialization and the tool avoids reconstructing message internals.
- Fit for zip retrieval: bad for real binary zips; usable only as one text transport for the small fenced base64 fallback, with strict checksum/truncation detection.
- Server-visible/account relevance: clipboard read is local, but the Copy click is a first-party UI event that may be client/server telemetry; the archive has no evidence either way, so account-risk claims must stay empirical-unknown.
- UI drift/session/model: moderate drift risk around hidden action menus, accessible names, and clipboard permissions; targeting must be scoped to the current session's latest turn after local session/model selection.
- Predecessor reuse: can reuse selector maps and Playwright click/wait patterns, but the archive has no clipboard/copy allowlist method; adding it is new architecture outside Level B (control-plane/src/control_plane/browser/driver.py:97-105; control-plane/src/control_plane/browser/playwright_driver.py:117-128,184-203).

### 3.3 File-download capture

- Mechanism: instruct the assistant/UI to provide a downloadable patch zip, locate the artifact/download affordance, and capture it with Playwright `accept_downloads`/`expect_download`, then validate filename, manifest, hash, and changed-files-only contents.
- Fit for `-> text`: weak; forcing every plain answer into `.txt`/`.md` artifacts is slow and unnatural.
- Fit for zip retrieval: strongest UI-native path for actual binary zips if ChatGPT reliably offers downloads for the account/model/workflow.
- Server-visible/account relevance: artifact generation and download HTTP requests are visible to ChatGPT/OpenAI in real runs; this is normal product use but not client-only.
- UI drift/session/model: medium drift at artifact-card discovery; once a browser download event fires, byte capture is robust. Artifact identity must be tied to the active `session_identifier` turn.
- Predecessor reuse: existing Playwright/persistent-profile/selector infrastructure helps, but the archive driver has no download, upload, or file-chooser method in its allowlist (control-plane/src/control_plane/browser/driver.py:97-105; control-plane/src/control_plane/browser/playwright_driver.py:184-203).

### 3.4 Connector-style callback channel

- Mechanism: seed ChatGPT to call a local MCP/app tool such as `submit_answer`/`propose_patch`, then read structured local state rather than UI text.
- Fit for `-> text`: robust and auditable but semantically changes the product from “read the chat response” to “assistant must call a return tool.”
- Fit for zip retrieval: strong if local side generates the zip from structured edits or accepts chunked uploads; this was the predecessor's proven pattern for structured reports/patches.
- Server-visible/account relevance: deliberately server-visible through ChatGPT app/connector/tool calls, tunnel/auth, and possible approval dialogs.
- UI drift/session/model: most robust after connector attachment because output transfer is schema/protocol-based; setup UI and approvals remain operator-runbook risk.
- Predecessor reuse: strongest reuse — MCP runbook, server, event model, invitations, watcher, and patch tools — but the new task explicitly frames this as heavyweight and “without that connector,” and README says no daemons/registries unless forced (README.md:24-26; control-plane/docs/runbooks/phase2-chatgpt-acceptance.md:5-11,66-76).

### 3.5 Fenced base64 zip over a text channel

- Mechanism: a protocol layer over copy/DOM text: assistant emits a fenced payload with manifest, byte count, SHA-256, and base64url zip; the tool validates before applying.
- Fit for `-> text`: not a separate text answer channel; it consumes the chosen text channel.
- Fit for zip retrieval: useful fallback for small patch bundles and local mock acceptance; unsuitable as the only real path because UI response length/truncation limits are unknown.
- Server-visible/account relevance: same as the underlying text channel; no artifact download request, but generated binary-as-text remains in the chat transcript.
- UI drift/session/model: inherits copy/DOM targeting risks; integrity checks make truncation/corruption actionable.
- Predecessor reuse: none beyond local patch/audit ideas; predecessor patch bundles were local artifacts/events, not ChatGPT UI downloads (control-plane/docs/runbooks/mvp-demo.md:111-142,144-167).

## 4. Recommended layering and reconciliation

- Reconciled rule: preserve Level B safety disciplines where they still fit — no credentials, operator-owned profile, loopback automated tests, selector maps, fail-closed selectors, explicit runbooks, no broad transcript scraping — but deliberately depart from “never extract assistant output” because README makes returned text and patch-bundle retrieval core acceptance obligations (README.md:9-20,24-26; control-plane/DESIGN.md:46,888-961).
- Text primary: implement copy-button/clipboard first, with a selector-map-scoped latest-turn target and a completion detector. This keeps custom DOM parsing minimal and yields the UI's own copied text if the affordance and permissions are stable.
- Text fallback: implement DOM extraction as a bounded fallback, not a generic scraper: latest assistant turn only, no history sweep, no credential/profile reads, explicit completion marker/stable-text wait, and truncation/end-marker failure. This is the necessary escape hatch when copy is absent or clipboard permissions fail.
- Bundle primary: implement download capture as the preferred real zip path, but gate any claim of real-site support on an operator runbook that observes a real downloadable zip, normal Playwright download event, and post-download integrity validation.
- Bundle fallback: implement fenced base64 zip over the text channel for small bundles and for deterministic local acceptance. It should be a fallback because it is more truncation-prone than downloads, but it prevents the whole design from depending on an unproven ChatGPT download affordance.
- Connector position: do not ship connector callback as the initial default; keep it as a later “structured/audited mode” if direct UI return channels cannot meet reliability or account constraints. This keeps the new repo smaller and honors the no-connector conflict while acknowledging the archive's strongest proven transfer path.
- Evidence reconciliation: the archive's anti-DOM evidence is strongest for “the predecessor did not leak mock adversarial DOM and used events as canonical state,” not for “a small, bounded reader is impossible or a ToS ban risk.” Therefore the departure is justified only because the product's definition changed, and it must be bounded, tested against adversarial fixtures, and operator-gated on the real site.

## 5. Rejected options

- Pure predecessor Level B with no response reader: rejected because it cannot implement `ask_chatgpt(...) -> text` or retrieve a patch bundle (README.md:9-20,24).
- DOM extraction as the primary text channel: rejected because it maximizes selector/message-structure fragility and most directly reintroduces the predecessor's adversarial-DOM risk.
- Clipboard/copy for binary patch bundles: rejected because it is text-only and vulnerable to truncation/corruption for zips.
- File download for ordinary text answers: rejected because it makes simple calls artifact-heavy and depends on unproven UI behavior.
- Connector callback as default: rejected because it is heavy, server-visible, approval/tunnel-dependent, and contrary to the initial “without connector” direction, despite strong archive proof.
- Base64 fenced zip as the only bundle path: rejected because real response length/truncation limits are unknown and binary downloads, if proven, are cleaner.

## 6. Local mock-ChatGPT fixture requirements

- Common: bind loopback only; expose reset/failure/inspection endpoints; maintain multiple conversations keyed by stable conversation refs; support `session_identifier` reuse vs new-session creation; serve a selector-map-compatible ready root, chat list/items, new-chat button, composer, send button, model menu/options, and upload controls (README.md:18-20; control-plane/tests/fixtures/phase3_mock_chat.py:22-23,300-327,501-518).
- Adversarial content: include older assistant messages, prompt echoes, and booby-trap strings so tests prove the tool returns only the intended latest assistant turn, not prior DOM or injected control text; the archive mock already rendered assistant sentinels and withheld assistant text from control endpoints (control-plane/tests/fixtures/phase3_mock_chat.py:1-3,262-273,435-492).
- Copy channel: render a latest-message Copy button, optionally hidden until hover/focus; write exactly the expected assistant text to `navigator.clipboard`; tests must grant/read real browser clipboard permissions where possible, simulate permission denial, stale clipboard, wrong-message copy, missing button, and truncated copied text.
- DOM fallback: expose explicit selector keys for assistant message, turn id, streaming marker, completion marker, and message body; provide stable and unstable/virtualized variants; include required end markers/checksums for truncation detection.
- Download channel: after a mock assistant turn, render an artifact card/link/button that serves a real zip with `Content-Disposition: attachment`; tests must capture a real Playwright download event, validate bytes/SHA/manifest, and cover missing link, delayed link, wrong older artifact, corrupt zip, truncated zip, filename collision, and download unsupported.
- Fenced base64 fallback: generate a small patch zip payload in a fenced block with `BEGIN/END`, manifest, byte count, SHA-256, and base64url; also serve variants with missing end marker, mismatched hash, changed+unchanged files, and oversized payload.
- Upload/file input: accept the caller's outgoing bundle through an `<input type=file>`/drop affordance in the mock, record metadata without real network, and simulate upload unsupported, size/type rejection, and corrupted upload.
- Honest failures: fixture states must cover login required, session not found/stale conversation, model option unavailable, upload unsupported, download unsupported, response truncated, rate limit/backoff, and selector unavailable; the archive mock already had login/missing-app/rate-limit/load-failure patterns to reuse conceptually (control-plane/tests/fixtures/phase3_mock_chat.py:238-251; control-plane/tests/fixtures/phase3_mock_selector_map.json:1-77).

## 7. Empirical unknowns resolvable only by operator-gated runbooks

- Zip attachment upload size/type limits: observe accepted/rejected `.zip` sizes, file counts, MIME/extensions, rejection copy, and whether limits differ by account/workspace/model.
- Whether/when ChatGPT offers file downloads from responses: observe if a prompted patch zip appears as an artifact/download, whether Playwright sees a normal `Download`, suggested filename/MIME, retention/scanning delays, and byte-for-byte zip integrity.
- Session pinning via URL/conversation ref: observe whether stored conversation URLs/refs reopen the intended session across process/browser restarts, deleted/renamed chats, archived chats, and simultaneous sessions.
- Model-selection UI hooks: observe stable selectors/labels for the target model/settings, persistence across sessions, failure states when unavailable, and whether model selection must be manual.
- Copy-button/clipboard behavior: observe button availability, hidden-menu behavior, permission prompts, completeness for Markdown/code/citations, stale clipboard races, and any visible account/telemetry prompts; do not infer server invisibility from local tests.
- Assistant completion signal: observe reliable end-of-turn markers, streaming stop behavior, regenerate/retry effects, and whether long responses are virtualized or lazily loaded.
- File upload UI hooks: observe stable selectors for attachment input/drop, upload progress/failure messages, and whether bundle README/catalog files are visible to the model.
- Text-channel size/truncation limits: observe maximum safe fenced payload size, truncation symptoms, and whether checksums/end markers catch all partial outputs.
- Artifact identity and wrong-turn risk: observe how response files are associated with a specific assistant turn when older artifacts exist in the same conversation.
- Operator UX/failure messaging: observe whether login, session-not-found, upload/download unsupported, and model-unavailable errors can be detected without reading credentials or account-private data.

## 8. Telemetry footer

ESTIMATE: T2 45m
ACTUAL: T2 44m
END_TIMESTAMP: 2026-06-11T22:57:49-05:00
T2-STATUS: DONE
