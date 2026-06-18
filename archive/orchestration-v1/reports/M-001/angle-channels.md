ESTIMATE: T1b 25m

# T1b angle: return-channel engineering comparison

Scope/safety: file-reading research only; I did not contact chatgpt.com/OpenAI/tunnels and did not run Playwright. Archive facts used: `browser/driver.py` has a closed `ChatUIDriver` allowlist (`open_or_focus`, `new_or_select_chat`, model/connector selection, `send_seed_prompt`, `read_coarse_health`, `health`, `close`) and explicit forbidden reader tokens; `selectors.py` provides operator-versioned selector maps (`test_id`, `role`, `css`, templated CSS/role) with required shell keys only; `playwright_driver.py` uses sync Playwright persistent context, `page.goto`, locator wrappers, visibility waits, `fill`, `click`, `select_option`, `wait_for_function`, and coarse health only; no archive browser code mentions downloads or clipboard; `DESIGN.md`/runbooks make MCP events/tools authoritative and DOM extraction prohibited for the predecessor.

## 1. DOM extraction via selector maps

Mechanism: after prompt send, wait until the target conversation has a completed assistant turn, locate the last assistant message container, read rendered text from that subtree, normalize it, and return it. This extends the existing selector-map-as-data pattern from shell controls to message DOM, likely adding keys such as `assistant_message`, `assistant_message_by_turn`, `assistant_streaming_marker`, `assistant_complete_marker`, and maybe code-block selectors. It is a reversal of the predecessor design, which deliberately included forbidden reader tokens and DOM tripwires.

Playwright implementation sketch: reuse `PlaywrightChatUIDriver._ensure_page()`, `_locator_from_resolved()`, `_wait_visible()`, `_conversation_ref()`, and selector-map validation style. Add selector entries, then sketch: `page.locator(resolved_assistant_css).last.wait_for(state="visible", timeout=...)`; wait for completion by absence of a stop/streaming marker or by a stable text hash over N animation frames via `page.wait_for_function(...)`; read with `locator.inner_text()` or `locator.evaluate("node => node.innerText")`; for exact Markdown/code fidelity, maybe collect DOM segments and code blocks separately. This requires changing driver-contract tests and the forbidden-token audit in `driver.py`/`DESIGN.md`; it is not a drop-in extension under current archive invariants.

Failure modes: selector drift in message markup; wrong turn selected in a long/retried conversation; streaming not complete; virtualized history or collapsed older messages; hidden text from code blocks, math renderers, tool cards, citations, or localized labels; duplicated assistant messages after regenerate; truncation if the web UI itself truncates; prompt-injection text in the DOM being treated as state; accidental scraping of secrets if transcript contains them.

Server-visible vs client-side: mostly client-side after the conversation is loaded. Locator queries and DOM reads are local browser automation and should not themselves create a ChatGPT request. Confidence: high for pure `innerText`/DOM reads, but empirical unknown for any scroll/expand/click needed to reveal hidden content because the web app may lazy-load history or telemetry.

Robustness under UI drift: fragile. The existing selector map can localize repairs if drift is limited to CSS/role/test-id changes, but semantic drift in message structure/completion markers forces code changes. Blast radius is large because current tests and docs enforce no assistant-content reader; repair path is not just updating JSON selectors, it is a product-policy change plus new adversarial tests.

Fit for `-> text`: 3/5 engineering fit if policy permits: direct, local, no clipboard permission, good for plain rendered prose, but fragile and currently contradicted by archive design. Empirical unknown: exact ChatGPT DOM structure/completion signals for current UI.

Fit for patch-bundle zip retrieval: 1/5. DOM is text-oriented; binary zip retrieval would require base64-in-chat or link scraping, both brittle and size-limited.

Session continuity/model selection: no independent session/model mechanism. It depends on the existing controller to select `conversation_ref`/new chat and `preferred_model` before prompt send; output selectors must be scoped to the active conversation/turn to avoid mixing sessions.

## 2. Copy-button / clipboard automation

Mechanism: wait for the assistant turn to finish, reveal/click that message's Copy control, then read the clipboard text from the browser context or host clipboard. This delegates message serialization to ChatGPT's UI copy handler rather than reverse-engineering the full message DOM.

Playwright implementation sketch: add selector-map keys for `assistant_message`, `assistant_copy_button`, maybe `message_actions_button`, and a completion marker. With sync Playwright: focus target page; hover/locate last assistant message (`page.locator(...).last.hover()` if actions are hidden); click copy (`copy_button.click(timeout=...)`); read via `context.grant_permissions(["clipboard-read", "clipboard-write"], origin=...)` then `page.evaluate("navigator.clipboard.readText()")`. If browser permission fails, Chromium CDP permission grant or OS clipboard access is a possible fallback, but that is outside archive patterns. Existing driver launch would need clipboard permissions and possibly headed/focused behavior; no current code covers it.

Failure modes: copy button selector/label drift; actions hidden until hover/focus; wrong message copied; streaming not complete; clipboard-read permission denied; insecure-origin/permission constraints; page not focused; OS clipboard race with user actions; copy handler may omit images/files/tool cards/citations or preserve unwanted formatting; locale/accessibility-name changes; enterprise/browser policy disabling clipboard; large response truncation in clipboard or UI copy handler.

Server-visible vs client-side: mixed. Reading clipboard is local. The click on ChatGPT's Copy button is a UI event that may be logged by client telemetry or sent to the server; the archive has no evidence either way. Confidence: medium-low for invisibility; mark as empirical unknown. Compared with DOM extraction, this is less purely local because it intentionally exercises a first-party UI control.

Robustness under UI drift: moderate. It is less sensitive to internal Markdown/code DOM because the UI owns serialization, but still sensitive to message action affordances, hover menus, and accessible names. Repair path can often be selector-map updates if copy controls remain conceptually stable; if the copy affordance moves into menus or requires permissions, code changes are needed.

Fit for `-> text`: 4/5 if empirical clipboard tests pass. It likely returns the assistant's canonical copied text and avoids custom parsing. It is not grounded in archive implementation and needs a completion detector plus clipboard permission strategy.

Fit for patch-bundle zip retrieval: 1.5/5. It can carry text patches or base64 only with high truncation/corruption risk; it is not a binary channel.

Session continuity/model selection: orthogonal. Existing session/model flow still opens/selects the conversation and model; copy must target the last assistant message in that selected session. It does not help continuity or model settings.

## 3. File-download capture

Mechanism: instruct GPT/ChatGPT UI to produce a downloadable artifact (zip, code file, or manifest), wait for the file/link/card in the assistant turn, click the download affordance, and capture the browser download to local storage. For the patch-bundle objective, this is the only candidate that naturally returns a binary zip from the UI.

Playwright implementation sketch: launch persistent context with downloads enabled, e.g. `chromium.launch_persistent_context(user_data_dir, accept_downloads=True, downloads_path=...)`; after prompt send and completion, locate the artifact/download button via selector-map keys (`artifact_card`, `download_button`, `download_link`); use sync API `with page.expect_download(timeout=...) as d: locator.click(); download = d.value; download.suggested_filename; download.save_as(target_path)`. Also attach `page.on("download", ...)` if multiple files are possible. Existing archive driver would need launch kwargs support for `accept_downloads`/`downloads_path` and new selectors; current code has no `expect_download` or download path handling.

Failure modes: ChatGPT may refuse or fail to create files; generated file may not be a real zip or may include unchanged/extra files; artifact UI selector drift; download button hidden behind menus; server-side virus/scanning/retention delay; browser download cancellation; filename collisions; size/quota limits; wrong artifact from an earlier turn; `accept_downloads` omitted; headless download behavior differences; locale labels; stale partial `.crdownload`; inability to validate changed-files-only without opening zip locally. Empirical unknown: current ChatGPT web artifact/download behavior for GPT-generated zip files was not grounded in the archive.

Server-visible vs client-side: server-visible. Prompting file creation, artifact generation, and the HTTP download request are visible to ChatGPT/OpenAI infrastructure; even if Playwright capture is local, the artifact fetch is network traffic in a real run. Confidence: high for a server-hosted artifact/download path, but exact telemetry/download implementation is empirical unknown.

Robustness under UI drift: moderate for binary capture once a download event fires; fragile at the UI-discovery layer. Repair path is selector-map updates for the artifact/download affordance if stable; code changes if ChatGPT changes artifact cards, uses sandboxed previews, or requires file APIs rather than normal downloads.

Fit for `-> text`: 2/5. It can force the assistant to emit a `.txt`/`.md` file, but that is awkward for normal `ask_chatgpt(prompt)->text`, adds latency, and makes every response an artifact workflow.

Fit for patch-bundle zip retrieval: 4/5 if real-site artifact generation is confirmed. It preserves binary bytes and avoids clipboard/DOM truncation. The score is capped because archive has no implementation evidence and no proof ChatGPT will reliably produce a changed-files-only zip.

Session continuity/model selection: orthogonal but artifact identity must be tied to the active `session_identifier`/turn. Existing controller handles conversation/model before prompt; download logic must disambiguate artifacts in that conversation.

## 4. Connector-style callback channel

Mechanism: browser sends a seed prompt telling the assistant to call local MCP/app tools; ChatGPT calls back through an approved connector/tunnel to the local daemon; the daemon records structured text/report/patch data in SQLite/events; `ask_chatgpt` reads local state and returns the submitted text/artifact reference. For text, this would require a dedicated answer-submission tool or reuse a report-like schema. For bundles, the assistant can submit `file_edits`/patch metadata and the local side can generate a zip of changed files, or a future tool can accept chunked/binary artifact data. The predecessor already proves the callback pattern for boot, task claim, report submission, manager integration, and `cp_propose_patch`.

Playwright implementation sketch: this mostly reuses existing driver/controller rather than adding a reader. `BrowserSessionController` creates server-side invitations, opens/selects chat, selects model, enables connector, sends `worker_boot`/manager seeds, and waits on events. Existing Playwright calls are `page.goto`, `page.get_by_test_id`/`get_by_role`/`locator`, `fill`, `click`, waits, and persistent profile launch. The return path is not Playwright extraction; it is MCP `ToolRouter` handling `cp_boot`, `cp_claim_task`, `cp_submit_report`, `cp_mark_report_integrated`, and `cp_propose_patch`, then local API/DB reads. For an `ask_chatgpt` product, add a minimal `cp_submit_answer(session_identifier, text, idempotency_key)` and optionally `cp_submit_patch_bundle_manifest`/chunk upload, or generate zip locally from `cp_propose_patch(file_edits)`.

Failure modes: heavyweight first-time setup; plan/workspace Developer Mode/app availability; tunnel/auth failures; approval prompts; connector not attached to the conversation; tool-call policy/confirmation friction; ChatGPT chooses not to call the tool or calls with invalid schema; tool count/visibility issues; public tunnel risk if auth is weak; local daemon/session registry lifetime; idempotency/session mismatch; current MCP route rejects non-`file_edits` patch proposals and `bundle` apply is deferred, so zip-bundle support needs new local code.

Server-visible vs client-side: deliberately server-visible. ChatGPT/OpenAI sees connector/app use and tool calls enough to route them through the MCP/app path; tunnel requests hit the local daemon; approval decisions may be part of ChatGPT UI state. Confidence: high, grounded in Phase-2/3 runbooks and MCP server design.

Robustness under UI drift: strongest after connector attachment. The UI automation remains shell-level and already modeled by selector maps (`connector_button`, `connector_option`, `prompt_textbox`, model selectors), while output transfer is protocol/schema-based. Drift in ChatGPT app/connector setup is operator-runbook risk; output parsing does not break on message DOM redesign.

Fit for `-> text`: 3.5/5. It is robust and auditable for structured answer submission, but it changes the semantics from "read the assistant's chat response" to "require the assistant to call a return tool" and is overkill for one-off plain text. Good when exact audit/state matters more than generic chat compatibility.

Fit for patch-bundle zip retrieval: 4.5/5 engineering fit if the team accepts local zip generation or adds a bundle-upload tool. It is the only proven predecessor path for structured patch transfer, avoids UI binary/download fragility, and keeps validation local. Caveat: existing archive supports MCP `file_edits` proposals; `bundle` exists as a format but apply/reconciliation is deferred and MCP currently rejects non-`file_edits` proposals.

Session continuity/model selection: best integrated with continuity because `cp_boot`, `browser_session_ref`, endpoint identity, run_id, and events already model sessions/reconnects. Model selection remains a browser-shell concern (`preferred_model` and selector map) before seed send; connector output itself is model-agnostic.

## Rankings

Text retrieval ranking: 1) copy-button/clipboard, because it likely yields ChatGPT's own copied text serialization without custom message parsing; empirical unknowns are clipboard permission and copy telemetry. 2) DOM selector extraction, because it is direct and mostly client-side, but fragile and contrary to the archive's deliberate no-reader contract. 3) connector callback, because it is robust/proven but not generic "read the chat response" unless prompts/tools force answer submission. 4) file-download, because turning every text response into an artifact is slow and unnatural.

Bundle retrieval ranking: 1) connector callback, if local generation of the changed-files zip from submitted structured edits is acceptable; it is the proven, auditable, least-UI-fragile transfer path. 2) file-download capture, if the non-negotiable requirement is a literal ChatGPT UI-produced zip; Playwright download capture is clean, but real ChatGPT artifact behavior is ungrounded here. 3) clipboard, only viable for small textual patch payloads, not binary zips. 4) DOM extraction, unsuitable for binary bundles.

Natural layering: for text, use copy-button as primary with DOM extraction as a diagnostic/fallback only if policy allows a reader surface; connector return-tool mode is a separate "structured/audited ask" mode, not a transparent fallback. For bundles, use connector/local zip generation as primary for reliability and validation, with Playwright `expect_download()` as a UI-artifact fallback or compatibility mode after operator-gated real-site testing. Do not use DOM/clipboard for zip bundles except emergency small-text diagnostics.

## Empirical unknowns requiring operator-gated runbooks

- Current ChatGPT selectors and stable completion signal for assistant turns.
- Whether Copy returns complete Markdown/code text, includes citations/tool cards, and works under Playwright clipboard permissions in the chosen browser/profile.
- Whether clicking Copy produces server-side telemetry/account-risk signals.
- Whether ChatGPT reliably creates downloadable zip artifacts containing only changed files, what size limits apply, and whether downloads are normal Playwright `Download` events.
- Whether file artifacts are retained, scanned, renamed, or blocked in the target workspace/model.
- Exact model-selector and connector UI behavior in the target Pro/workspace account.
- Whether a connector answer-submission/bundle-upload tool is acceptable product semantics for `ask_chatgpt(prompt)->text`.

ACTUAL: T1b 34m
END_TIMESTAMP: 2026-06-11T22:47:24-05:00
T1b-STATUS: DONE
