ESTIMATE: T1c 20m
# T1c angle: spec-fit / simplicity lens

Scope: file-reading only; no network contact. Sources checked: repo `README.md`; SEED handoff grep/read for UX/runbook/library-first/mock/fixture; targeted archive greps for the loopback mock-chat/selector-map pattern.

## 1. Three use cases as testable obligations

### A. `ask_chatgpt(...) -> text`

Automated loopback acceptance must prove:

- Given `prompt`, `session_identifier`, and optional `model_settings`, the library opens/selects a chat in a local mock and submits the prompt.
- It returns exactly the latest assistant response text, not prior assistant text, booby-trap DOM text, prompt echo, or fixture control JSON.
- Calling again with the same `session_identifier` reuses the same conversation; a different identifier creates/selects a distinct conversation.
- Model settings are attempted where the UI/mock exposes them; unsupported settings produce an actionable failure/degraded warning, not silent success.
- Named failures are surfaced as stable reason codes/messages.

### B. Bundle out -> patch bundle back -> applied locally

Automated loopback acceptance must prove:

- The library zips requested files/directories plus an informational README/catalog for GPT.
- The mock receives/observes the uploaded bundle request without contacting any real service.
- The mock returns a patch bundle containing only changed files.
- The tool retrieves the patch bundle, validates integrity/manifest, applies it locally, and the resulting diff exactly matches the expected diff.
- Upload unsupported, return-channel unsupported, corrupt bundle, and truncated response each fail honestly before applying partial edits.

### C. CLI wrapping the function

Automated loopback acceptance must prove:

- A command such as `ask-chatgpt --session S --prompt "..." [--file/--dir ...]` calls the same library path as use case A/B.
- Plain text goes to stdout or `--output`; patch application is explicit (`--apply` or equivalent) and reports the diff/result.
- Exit code 0 means the library obligation completed; nonzero exits include the same actionable reason codes as the library.

## 2. Minimal design by moving parts

### Shared minimum

- Library-first core: `ask_chatgpt()` owns prompt submission, session mapping, response capture, and bundle helpers; CLI is a thin adapter.
- One browser automation layer is unavoidable for ChatGPT.com UI interaction; keep it small and data-driven with selector maps.
- Session state should be a simple local mapping from `session_identifier` to conversation URL/ref plus metadata; no daemon/registry unless later forced.
- Every response/bundle protocol should include an explicit end marker and checksum/size where applicable, so truncation is detectable.

### Plain text return channel

Minimal choice: DOM extraction via selector-map selectors for the latest assistant message.

Why: it reuses the browser and selector-map machinery already needed to submit prompts/select sessions; it adds one extraction selector and completion/end-marker logic, not a new OS primitive, callback server, or tunnel. It is cheap to mock with static/dynamic HTML and cheap to test against adversarial older messages.

Reject as primary:

- Clipboard/copy button: adds global clipboard state, permissions/headless quirks, copy-button selectors, cleanup, and harder faithful CI mocks.
- File download: overkill for ordinary text and depends on product behavior not required for simple `-> text`.
- Connector callback: proven prior art but too many moving parts for this repo's library-first, zero-dependency, 1-2-command UX.

### Patch-bundle retrieval

Occam-minimal path: reuse DOM extraction for a small, checksummed fenced payload containing a base64url zip patch bundle. This satisfies the README's "patch bundle" requirement without adding a second UI channel. It is adequate for the basic filesystem acceptance if the fixture uses small files and the protocol has `BEGIN/END`, byte count, SHA-256, and manifest checks.

Add a download channel only as an optional preferred path after operator-gated proof that chatgpt.com reliably offers downloadable files for the relevant model/workflow. If available, downloads reduce truncation/copy corruption risk for larger patch bundles; that benefit can justify the extra Playwright download-event handling. But making downloads mandatory before empirical proof would bake an unknown into the minimal product.

Do not add clipboard or connector fallback initially. A fallback pays for itself only if it uses machinery already present; DOM-fenced patch payload does, clipboard/connector do not.

## 3. Local mock-ChatGPT fixture requirements

Common fixture requirements:

- Bind loopback only, preferably ephemeral `127.0.0.1` port; expose control endpoints for tests to reset state, set failure modes, and inspect submitted prompts/uploads.
- Serve an HTML page matching a selector map: ready root, login marker, chat list/item by conversation ref, new chat, composer, send, model menu/option, upload input/drop area, latest assistant message, completion marker, optional copy/download controls.
- Track conversations so session-continuity tests can prove reuse vs new chat.
- Include adversarial prior assistant messages and prompt echoes so extraction tests prove they read only the intended latest response.
- Simulate failure states: login wall, missing session, upload rejection, no download, truncation/missing end marker, corrupt checksum.

Candidate-channel support:

- DOM extraction: cheap to mock. Serve assistant HTML whose `data-testid`/CSS selectors match the selector map; include older booby-trap messages and a final marker/checksum. This is the strongest simplicity signal.
- Clipboard/copy button: partly cheap, faithfully hard. A mock can render a copy button and call `navigator.clipboard.writeText`, but CI/headless permissions and global clipboard isolation are extra moving parts; a fake in-page variable would not exercise the real channel.
- Downloads: cheap to mock faithfully. Serve a real zip at a link/button with `Content-Disposition: attachment`; tests listen for a real browser download event and validate bytes/hash. Also simulate absent link, delayed link, corrupt/truncated file.
- Connector callback: possible but heavy. A loopback callback server can prove schema/protocol locally, but it reintroduces server lifecycle, connector semantics, and possibly tunnel-shaped UX; it is not a simplicity fit for this repo unless all direct channels fail.

Archive grounding: the prior mock pattern already used loopback-only `MockChatServer`, selector-map JSON, `data-testid` selectors, `/__mock/*` control endpoints, prompt history, and explicit failure states such as login wall/rate limit/missing app. Reuse the pattern, not the predecessor's full control-plane apparatus.

## 4. Honest failure-mode taxonomy

- `LOGIN_REQUIRED`: easiest by DOM marker (`login_required_marker`) before sending; all return channels are secondary. Action: ask operator to log in in the configured browser profile and rerun.
- `SESSION_NOT_FOUND`: easiest by local session map plus chat-list/URL validation. Action: create a new session for this identifier or clear/remap the stored conversation ref.
- `UPLOAD_UNSUPPORTED`: easiest by upload selector/error DOM after attempting file attach. Action: run without files, reduce/rename bundle, or wait for operator-gated proof of accepted zip type/size.
- `DOWNLOAD_UNSUPPORTED`: easiest with download channel because no link/event appears within a bounded wait; if DOM-fenced bundle fallback exists, report fallback used. Action: switch to text bundle fallback or operator-runbook verification.
- `RESPONSE_TRUNCATED`: easiest for DOM/text when required end marker/checksum/byte count is missing or mismatched; also easy for downloads via size/hash mismatch. Action: retry with smaller prompt/bundle or request downloadable bundle if proven available.

Channel comparison: DOM makes login/session/truncation observable with the fewest parts; download makes bundle integrity easiest once available; clipboard makes failures least clean because missing copy button, clipboard permission, stale clipboard, and truncated content can look similar; connector can schema-detect many failures but at high UX/dependency cost.

## 5. Operator-gated only: empirical unknowns not assumed in tests

Automated tests must never claim these for real chatgpt.com:

- Zip attachment upload size/type limits and rejection messages.
- Whether/when chatgpt.com offers downloadable files from assistant responses for the relevant models/settings.
- Whether session pinning via URL is stable enough for `session_identifier` mapping.
- Model-selection UI hooks, labels, and persistence.

If clipboard/copy is reconsidered, real copy-button availability and browser clipboard permission behavior should also be operator-gated, not assumed from loopback.

## Minimal-design recommendation from this lens only

Spec-fit/simplicity view, input to synthesis: implement a small library-first Playwright/selector-map path with DOM extraction as the required return channel for assistant text and for the initial small patch-bundle protocol via a checksummed fenced base64 zip; keep the CLI thin; build a loopback mock that exercises selectors, sessions, uploads, DOM extraction, optional real downloads, and named failures. Add file-download capture as an optional preferred patch path only after an operator-gated runbook proves real ChatGPT download behavior. Do not import the predecessor's connector/tunnel architecture or clipboard channel for the initial product.

ACTUAL: T1c 20m
END: 2026-06-11T22:46:41-05:00
T1c-STATUS: DONE
