STATUS: DONE
VERDICT: PASS

Verified `team/evidence/reports/M3-detailed-design.md` against M2 live-site ground truth, cross-checking `docs/REWRITE-SPEC.md`, `team/charter.md`, and `.claude/skills/manager/references/agent-rigor.md`. No browser/CDP/network leg was run. All eight M2 fidelity checklist items are honored; no load-bearing fidelity gap was found.

## Itemized findings

1. **Auth/OAI headers — HONORED**
   - M2 evidence: `team/evidence/handoffs/M2-ground-truth-probe.md §Backend-api verdict` says the minimal fetch returned "**404**" and that replaying with web-app headers including `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, and `x-openai-target-route` "returned **200**"; it concludes backend capture is faithful "**if the implementation can safely obtain and forward the web-app Authorization/OAI headers**" and that cookies-only is refuted.
   - Design handling: `team/evidence/reports/M3-detailed-design.md §2.3 capture.py` defines `REQUIRED_CAPTURE_HEADERS` with the required header names and says `HeaderBundle` values "must never appear in `repr`, logs, exceptions, `raw-mapping.json`, `transcript.jsonl`, status reports, or test fixtures." `§4.1 Header acquisition` says capture "registers request listeners before navigation/reload on the tool-owned page, waits for a matching `GET https://chatgpt.com/backend-api/conversation/<conversation_id>`, lower-cases headers, validates the required set" and rejects "JS globals, localStorage, sessionStorage, IndexedDB, cookies, or app internals." It also says missing headers raise `BackendAuthUnavailableError` and enter the fail-closed fallback chain.
   - Assessment: the design obtains the required auth/OAI headers from the page's own request, forbids persistence/logging, and fails closed if unavailable.

2. **Scale / streaming — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Backend-api verdict` reports a successful replay "returned **200**, JSON, about **17.1 MB** in one response. No pagination was observed" and "about **5.0k mapping nodes** and about **5.0k current-branch nodes**."
   - Design handling: `M3-detailed-design.md §4.2 In-page streaming fetch and raw persistence` says the response body is "streamed in chunks" to `raw-mapping.json.tmp.<pid>` and that the implementation must "stream body-to-disk first and avoid browser-side full JSON materialization or CDP-serializing the whole response." It cites "M2 measured one successful response at ~17.1 MB and ~5.0k mapping/current-branch nodes" and keeps `iter_current_branch_records(raw_path)` replaceable by an event parser. `§5 Completion detection` adds that completion polling must not rewrite the 17 MB raw file on every poll.
   - Assessment: the measured scale is used as measured, not reinvented; the capture path is streaming/efficient and avoids gratuitous browser/CDP whole-response materialization.

3. **Content extraction — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Backend-api verdict` says "Visible assistant report bodies are in `message.content.content_type == "text"` with `message.content.parts` as a list of strings. `assistant:code` uses `message.content.text`; `assistant:thoughts` uses `message.content.thoughts`; many tool/code/thought nodes have no `parts`."
   - Design handling: `M3-detailed-design.md §3.5 Current-branch linearization and visible-vs-hidden classification` emits only visible `user:text` and `assistant:text` records and treats `assistant:code`, `assistant:thoughts`, `assistant:reasoning_recap`, `assistant:model_editable_context`, all `tool:*`, and `system:text` as hidden/raw unless later evidence proves visibility. It states the exact `content.parts` rule: one string uses `parts[0]`; multiple strings concatenate without invented separators; non-string parts fail closed. `§4.3 Canonical extraction` repeats that visible markdown lives in `content.parts` and that code/thoughts use `content.text`/`content.thoughts` while hidden.
   - Assessment: extraction matches M2's per-node content locations and does not assume `parts` exists on hidden tool/code/thought nodes.

4. **Deep Research / Pro turns — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Deep Research representation` says "No single `content_type == "deep_research"` was observed"; DR/Pro turns are "large `turn_exchange_id` groups containing one user message, many hidden assistant/tool nodes, and one visible final `assistant:text` report" with citations/search metadata in `metadata.content_references`, `metadata.citations`, `metadata.search_result_groups`, and `metadata.search_queries`.
   - Design handling: `M3-detailed-design.md §3.6 Deep Research / Pro turns` says "There is no `content_type == "deep_research"`" and represents DR/Pro as a `turn_exchange_id` group with the visible user and final assistant report emitted, hidden internals retained raw, and ambiguous scrape-only cases left `kind="normal"`. `§3.7 Attachments and citations` stores `CitationRef` records from `metadata.citations`, visible `content_references`, and source groups, while retaining `search_queries` raw unless linked to a displayed source.
   - Assessment: the design groups/linearizes DR from M2's tree shape, captures citations/search metadata, and does not invent a `deep_research` content type or separate DR capture endpoint.

5. **Attachment shapes — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Attachments reference shape` lists all four observed shapes: `message.metadata.attachments[]`; `message.metadata.content_references[]` with `type: "file"`; tool `tether_browsing_display` `message.content.assets[]` with `asset_pointer`; and tool `execution_output` `message.metadata.aggregate_result`. It also says "No literal `/backend-api/files/...` URLs or `sandbox:`/`attachment:` URI strings were observed."
   - Design handling: `M3-detailed-design.md §2.1 Canonical public data model` defines `AttachmentRef.source_kind` values `user_upload`, `file_reference`, `generated_asset`, and `code_execution_output`. `§3.7 Attachments and citations` maps each M2 shape in a table, says `AttachmentRef` stores ids/pointers/raw paths and "does not invent endpoints," and explicitly separates attachments from citations: "Attachments are byte-downloadable or locally materializable artifacts; citations are web/source references and are never downloaded by `fetch`."
   - Assessment: all four M2 attachment/reference shapes are represented, literal file URL assumptions are avoided, and citations are kept separate from attachments.

6. **Completion signals — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Deep Research representation` notes async/progress fields including top-level `async_status` and metadata `async_source`, `is_complete`, `is_finalizing`, and `pro_progress`; `§Recommended design adjustments` says completion should consider `/stream_status`, `async_status`, node `status`, and metadata `is_complete`/`is_finalizing`.
   - Design handling: `M3-detailed-design.md §5 Completion detection` polls backend state and parses top-level `async_status`, `update_time`, `current_node`, node `status`, message metadata `async_source`, `is_complete`, `is_finalizing`, `pro_progress`, and new assistant text length/hash. It says exact vocabularies are unverified and conservative. It also states `GET /backend-api/conversation/<id>/stream_status` "remains a hypothesis from M2" and must not be relied on before M5 verification.
   - Assessment: the design uses the observed completion/progress signals and correctly treats `stream_status` as a hypothesis.

7. **Selectors / menus / clipboard — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Selectors` gives `composer: "#prompt-textarea"`, `tools_button: "button[data-testid=\"composer-plus-btn\"]"`, turn selectors, copy button selector, stop/send selectors, and a label-driven model picker with no stable test id. It also records Radix menu roles/options and `§Clipboard viability` says clipboard permission was `prompt`, so fallback is feasible only with explicit permission/user gesture.
   - Design handling: `M3-detailed-design.md §2.10 selectors/` includes the M2 selector map exactly, including `#prompt-textarea`, tools button, message/user/assistant turns, copy button, stop button, send-button-unverified key, `radix_portal`, and a model-picker heuristic with "no stable data-testid/aria-label." `§2.6 menus.py` uses label-driven Radix enumeration under `[data-radix-popper-content-wrapper]`; `§6 Send and action strategy` lists observed model/tool labels and forbids opening `Recent files`/`Projects` submenus. `§4.4 Fail-closed fallback chain` says copy fallback requires explicit attended clipboard permission/user gesture because M2 found permission `prompt`.
   - Assessment: live selectors, Radix portal/menu behavior, label-driven model picking, private-submenu avoidance, and clipboard non-dependence are encoded correctly.

8. **Projects — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Project notes` says project probing was deferred; the authorized conversation used plain `/c/<conversation_id>`, and `gizmo_id`/`gizmo_type` were null, so the probe "does not confirm `/g/g-p-<projid>/c/<chatid>` behavior."
   - Design handling: `M3-detailed-design.md §2.8 identity.py` supports both `https://chatgpt.com/c/<conversation_id>` and `https://chatgpt.com/g/g-p-<project_id>/c/<conversation_id>` and says "Project send/create is treated as a near-term assumption because M2 did not probe project URLs." `§6 Send and action strategy` repeats project create/send is "not live-verified by M2" and must fail closed if context cannot be verified. `§12 Open questions` asks whether M5 should prioritize project create/send because M2 did not verify it.
   - Assessment: the design parses/accounts for project URL shape and metadata while correctly marking project send/create as unverified near-term work, not an M2-proven fact.

## Count and final verdict

- HONORED: 8
- PARTIAL: 0
- VIOLATED: 0
- MISSING: 0
- Most serious fidelity gap: none found. Non-blocking cautions already acknowledged by the design are M5 measurement/confirmation items, not contradictions of M2 ground truth.

VERDICT: PASS
