Status: DONE

## Preflight

- `curl -s --max-time 5 http://127.0.0.1:9222/json/version` succeeded.
- Browser: Chrome/149.0.7827.53; CDP protocol 1.3; websocket endpoint present.
- Safety: used CDP attach only, created own pages, did not call/iterate `context.pages`, did not read/touch pre-existing tabs, performed no sends, did not quit the browser. Completed probe tabs were closed; browser was left running.

## Backend-api verdict

**Verdict: CONFIRMED with a required design adjustment.** The endpoint is viable and returns faithful canonical markdown including math, but the contract's minimal `fetch('/backend-api/conversation/<id>', {headers:{accept:'application/json'}})` is **not sufficient** on the live site.

- Minimal in-page fetch from a fresh chatgpt.com page: `GET /backend-api/conversation/6a316aa8-5dc8-83ea-9014-b8ea38dabc31` returned **404**, JSON, top-level keys `detail` only.
- Observed own-tab web-app request for the authorized conversation used the same path plus request headers including `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, and `x-openai-target-route`.
- Replaying the same endpoint in-page with those web-app headers, including `authorization` (value not logged/persisted), returned **200**, JSON, about **17.1 MB** in one response. No pagination was observed.
- Working endpoint: `GET https://chatgpt.com/backend-api/conversation/6a316aa8-5dc8-83ea-9014-b8ea38dabc31` with the page/web-app auth headers above.

Observed response shape:

- Top-level keys include `conversation_id`, `title`, `create_time`, `update_time`, `mapping`, `current_node`, `default_model_slug`, `async_status`, `moderation_results`, `safe_urls`, `blocked_urls`, `context_scopes`, `disabled_tool_ids`, `is_archived`, `is_temporary_chat`, `owner`, `voice`, etc.
- `mapping` is a message tree keyed by node id; each node has parent/children plus optional `message`.
- Successful captures saw about **5.0k mapping nodes** and about **5.0k current-branch nodes**; counts changed slightly while the conversation was still updating/in progress.
- Roles/content types observed: `user:text`, `assistant:text`, `assistant:thoughts`, `assistant:code`, `assistant:reasoning_recap`, `assistant:model_editable_context`, `tool:text`, `tool:tether_browsing_display`, `tool:execution_output`, `tool:multimodal_text`, `system:text`.
- Visible assistant report bodies are in `message.content.content_type == "text"` with `message.content.parts` as a list of strings. `assistant:code` uses `message.content.text`; `assistant:thoughts` uses `message.content.thoughts`; many tool/code/thought nodes have no `parts`.

Math/markdown faithfulness booleans for assistant `content.parts` strings:

- `contains \widehat`: true
- `contains \frac`: true
- `contains \ne` or `\neq`: true
- `contains $` delimiter: false
- `contains \(` delimiter: true
- `contains \[` delimiter: true
- Markdown table pipe present: true

Conclusion: backend JSON is a faithful canonical capture source for visible assistant markdown/math **if the implementation can safely obtain and forward the web-app Authorization/OAI headers**. The cookies-only/accept-only assumption is refuted.

## Deep Research representation

- No single `content_type == "deep_research"` was observed.
- Deep Research/Pro-style turns appear as large `turn_exchange_id` groups containing one user message, many hidden assistant/tool nodes, and one visible final `assistant:text` report.
- Large turn groups observed contained dozens to 100+ nodes each, with hidden `assistant:thoughts`, `assistant:code`, `assistant:reasoning_recap`, tool `execution_output`, `tether_browsing_display`, and tool authors such as `web.run`, `file_search`, `python`, and `container.exec`.
- Final report body lives in `message.content.parts[0]` on a visible `assistant:text` message; sampled report bodies were roughly 7k–16k chars each.
- Citation/search metadata lives on assistant messages, mainly in `message.metadata.content_references`, `message.metadata.citations`, `message.metadata.search_result_groups`, and `message.metadata.search_queries`.
- `content_references` types observed include `grouped_webpages`, `sources_footnote`, and `file`. `citations` entries use offsets (`start_ix`, `end_ix`) plus `citation_format_type` and nested `metadata`.
- Async/progress fields observed include top-level `async_status` and metadata keys such as `async_source`, `is_complete`, `is_finalizing`, and `pro_progress`.

## Attachments reference shape

- User-uploaded attachments: `message.metadata.attachments[]` with keys shaped like `id` (`file_...`-like id), `size`, `name`, `file_token_size`, `source`, `is_big_paste`.
- File citations/references: `message.metadata.content_references[]` entries with `type: "file"`; keys include `id`, `name`, `source`, `snippet`, `cloud_doc_url`, `library_file_id`, `library_artifact_type`, `medical_file_reference`, `drug_file_reference`, `page_range_start`, `page_range_end`, `input_pointer`, `fff_metadata`, `connector_id`. `input_pointer` has `file_index`, line range, message id, and message index.
- Generated/image-like assets: tool `tether_browsing_display` messages can have `message.content.assets[]` with `content_type`, `asset_pointer`, `size_bytes`, `width`, `height`, `fovea`, `metadata`.
- Code execution outputs: tool `execution_output` messages use `message.metadata.aggregate_result` with keys such as `code`, `messages`, `jupyter_messages`, `final_expression_output`, `run_id`, `status`, timing fields, and exception fields.
- No literal `/backend-api/files/...` URLs or `sandbox:`/`attachment:` URI strings were observed in the captured JSON; references were by ids, asset pointers, and metadata shapes above.

## Selectors

Machine-usable selectors observed on the live site:

```json
{
  "composer": "#prompt-textarea",
  "tools_button": "button[data-testid=\"composer-plus-btn\"]",
  "message_turn": "[data-message-id][data-message-author-role]",
  "user_turn": "[data-message-author-role=\"user\"][data-message-id]",
  "assistant_turn": "[data-message-author-role=\"assistant\"][data-message-id]",
  "copy_button": "button[data-testid=\"copy-turn-action-button\"]",
  "stop_button": "button[data-testid=\"stop-button\"], #composer-submit-button[aria-label*=\"Stop\" i]",
  "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button",
  "model_picker_heuristic": "button[aria-haspopup=\"menu\"] with visible current-model label in the composer footer; no stable data-testid/aria-label observed"
}
```

Selector notes:

- Composer is a visible contenteditable `div#prompt-textarea` with `role="textbox"` and aria label `Chat with ChatGPT`; `[data-testid="prompt-textarea"]` was absent.
- Empty fresh chat did not mount a visible send button under the read-only/no-input constraint. On an in-progress authorized conversation, the submit control was `button#composer-submit-button[data-testid="stop-button"][aria-label="Stop answering"]`.
- Authorized conversation DOM exposed 3 visible user turns and 3 visible assistant turns at probe time with `[data-message-id][data-message-author-role]`.
- Per-turn copy buttons were visible after hovering an assistant turn: `button[data-testid="copy-turn-action-button"][aria-label="Copy message"]`.

Model picker:

- The model picker was the composer-footer button showing current label `Pro Extended`; no stable test id was present.
- Top-level `menuitemradio` labels: `Instant`, `Medium`, `High`, `Extra High`, `Pro Extended` (checked).
- Family submenu: `GPT-5.5`; submenu radio labels observed: `5.5`, `5.4`, `5.3`, `4.5 Leaving on June 26`, `o3`.

Tools/+ menu:

- Top-level labels: `Add photos & files Ctrl U`, `Recent files`, `Create image`, `Deep research`, `Web search`, `More`, `Projects`.
- `More` submenu labels observed: `Agent mode`, `Create task`, `Figma`, `Finances`, `GitHub`, `OpenAI Platform`.
- I did not open `Recent files` or `Projects` submenus because they may expose private operator names unrelated to the authorized scrape target.

## Clipboard viability

- `navigator.clipboard` exists and `navigator.clipboard.readText` exists.
- Permission state was `prompt`; no final read was attempted and no permission grant was applied, to avoid a user-visible prompt or reading operator clipboard contents.
- Clipboard fallback is feasible only with explicit permission/user gesture; do not depend on it as an unattended fallback.

## Project notes

Deferred. No operator-provided project URL was supplied, and I did not inspect existing tabs. The authorized conversation was probed via plain `/c/<conversation_id>`; latest captured top-level `gizmo_id`/`gizmo_type` were null, so this probe does not confirm `/g/g-p-<projid>/c/<chatid>` behavior.

## Blockers / caveats

- The accept-only backend fetch specified in the design returned 404; working capture requires the page/web-app `authorization` and OAI headers.
- The conversation was actively/incrementally updating during the probe (`in_progress` nodes and visible stop button), so exact node counts varied by capture.
- Send button selector could not be directly observed without entering text; I did not type or send.
- Model picker lacks a stable observed data-testid/aria selector; current practical strategy is label-driven enumeration from the composer-footer model button.
- No full clipboard/copy-output comparison was performed; math fidelity conclusion is from backend canonical markdown tokens and structure, not clipboard text.

## Recommended design adjustments

1. Update §5: backend capture remains primary, but not cookies-only. First acquire the same auth/OAI header set the web app uses for `GET /backend-api/conversation/<id>`; never persist or log header values.
2. Treat failure to obtain `authorization` as fail-closed and fall back to copy/annotation paths.
3. Update completion polling to use the authenticated conversation endpoint and consider `/backend-api/conversation/<id>/stream_status`, `async_status`, node `status`, and metadata `is_complete`/`is_finalizing`.
4. Linearize only the current branch for transcript, but retain the raw mapping. Group hidden DR/Pro internals by `turn_exchange_id`; visible report bodies are `assistant:text` `content.parts`.
5. Expand attachment schema to cover `metadata.attachments`, `content.assets.asset_pointer`, `metadata.content_references[type=file]`, and code `metadata.aggregate_result`.
6. Update selector map with the selectors above; keep model/tool selection label-driven via Radix portal enumeration.
