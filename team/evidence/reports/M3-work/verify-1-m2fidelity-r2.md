STATUS: DONE
VERDICT: PASS

Re-verified the current `team/evidence/reports/M3-detailed-design.md` against authoritative M2 live-site facts in `team/evidence/handoffs/M2-ground-truth-probe.md`, cross-checking `docs/REWRITE-SPEC.md`, `team/charter.md`, and `.claude/skills/manager/references/agent-rigor.md`. No browser/CDP/network leg was run. I did not rely on the design's self-description or revision log for correctness.

## Itemized findings

1. **Auth/OAI headers — HONORED**
   - M2 evidence: `team/evidence/handoffs/M2-ground-truth-probe.md §Backend-api verdict` says the minimal in-page fetch returned **404** with only `detail`, while replay with `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, and `x-openai-target-route` returned **200**; it concludes cookies-only is refuted and headers must be safely obtained/forwarded.
   - Design quote/evidence: `team/evidence/reports/M3-detailed-design.md §2.3 capture.py` defines `REQUIRED_CAPTURE_HEADERS` with exactly those names and says values "must never appear in `repr`, logs, exceptions, `raw-mapping.json`, `transcript.jsonl`, status reports, fixtures, or any file on disk." `§4.1 Header acquisition` says capture "registers request listeners before navigation/reload on the tool-owned page, waits for a matching `GET https://chatgpt.com/backend-api/conversation/<conversation_id>`" and validates the required set; it rejects JS/storage/cookie scraping and raises `BackendAuthUnavailableError`/falls back fail-closed if missing.
   - Assessment: obtains headers from the page's own request, never persists/logs the token/OAI values, and fails closed if unavailable.

2. **Scale / streaming — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Backend-api verdict` reports about **17.1 MB** in one response, **no pagination**, and about **5.0k mapping/current-branch nodes**, with counts varying during updates.
   - Design quote/evidence: `M3-detailed-design.md §4.2 In-page streaming fetch and raw persistence` says the body is "streamed in chunks" to `raw-mapping.json.tmp.<pid>`, values are never returned/logged, and the implementation must "stream body-to-disk first and avoid browser-side full JSON materialization or CDP-serializing the whole response." It explicitly cites "M2 measured one successful response at ~17.1 MB and ~5.0k mapping/current-branch nodes" and keeps `iter_current_branch_records(raw_path)` replaceable by an event parser. `§5 Completion detection` says not to full-fetch/rewrite ~17 MB on every short poll.
   - Assessment: measured scale is used as measured, and the design avoids gratuitous full-response materialization in the browser/CDP path.

3. **Content extraction — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Backend-api verdict` says visible assistant report bodies are `message.content.content_type == "text"` with `message.content.parts` as string lists; `assistant:code` uses `content.text`; `assistant:thoughts` uses `content.thoughts`; many tool/code/thought nodes have no `parts`.
   - Design quote/evidence: `M3-detailed-design.md §3.5 Current-branch linearization and visible-vs-hidden classification` says only `user:text` and `assistant:text` are emitted as visible records; `assistant:code`, `assistant:thoughts`, `assistant:reasoning_recap`, `assistant:model_editable_context`, all `tool:*`, and `system:text` stay hidden/raw unless later evidence proves visibility. It specifies: "if the list has one string, use `parts[0]`; if multiple strings, concatenate the strings without inserting separators" and non-string parts fail closed. `§4.3 Canonical extraction` repeats the `content.parts` rule and notes code/thoughts use `content.text`/`content.thoughts` while hidden.
   - Assessment: per-node extraction matches M2 and does not assume hidden nodes have `parts`.

4. **DR/Pro turns — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Deep Research representation` says there is no `content_type == "deep_research"`; DR/Pro turns are large `turn_exchange_id` groups with one user message, many hidden assistant/tool/code/thought nodes and tool authors (`web.run`, `file_search`, `python`, `container.exec`), plus one visible final `assistant:text` report in `parts[0]`; citations/search metadata lives in `metadata.content_references`, `metadata.citations`, `metadata.search_result_groups`, and `metadata.search_queries`.
   - Design quote/evidence: `M3-detailed-design.md §3.6 Deep Research / Pro turns` says "There is no `content_type == "deep_research"`" and represents DR/Pro as a `turn_exchange_id` group with visible user/final assistant emitted, hidden internals raw, and ambiguous scrape-only cases kept `kind="normal"`. `§3.7 Attachments and citations` records `CitationRef` from `metadata.citations`, visible `content_references` such as `grouped_webpages`/`sources_footnote`, and source groups, while retaining `search_queries` raw unless linked to a displayed source.
   - Assessment: groups/linearizes DR according to M2 without inventing a DR content type or separate bespoke capture path; citations/search metadata are preserved or promoted only with evidence.

5. **Attachment shapes — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Attachments reference shape` lists four observed shapes: `message.metadata.attachments[]`, `metadata.content_references[]` with `type: "file"`, tool `tether_browsing_display` `message.content.assets[]` with `asset_pointer`, and tool `execution_output` `message.metadata.aggregate_result`; it also says no literal `/backend-api/files/...`, `sandbox:`, or `attachment:` URL strings were observed.
   - Design quote/evidence: `M3-detailed-design.md §2.1 Canonical public data model` defines `AttachmentRef.source_kind` values `user_upload`, `file_reference`, `generated_asset`, and `code_execution_output`. `§3.7 Attachments and citations` maps all four M2 shapes, states "M2 observed no literal `/backend-api/files/...`, `sandbox:`, or `attachment:` URLs" and therefore does not invent endpoints, and separates concepts: "Attachments are byte-downloadable or locally materializable artifacts; citations are web/source references and are never downloaded by `fetch`."
   - Assessment: schema represents all four observed shapes, stores ids/pointers/raw paths rather than fabricated URLs, and keeps citations separate from attachments.

6. **Completion signals — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Deep Research representation` and `§Recommended design adjustments` identify top-level `async_status`, metadata `async_source`, `is_complete`, `is_finalizing`, `pro_progress`, node `status`, and possible `/backend-api/conversation/<id>/stream_status` as a hypothesis.
   - Design quote/evidence: `M3-detailed-design.md §5 Completion detection` says backend checks parse `async_status`, `update_time`, `current_node`, node `status`, metadata `async_source`, `is_complete`, `is_finalizing`, `pro_progress`, and new assistant text length/hash. It says exact vocabularies are unverified/conservative and that `GET /backend-api/conversation/<id>/stream_status` "remains a hypothesis from M2" and must not be relied on before M5 verification.
   - Assessment: uses the observed completion/progress signals and treats `stream_status` as unverified.

7. **Selectors / menus / clipboard — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Selectors` gives `#prompt-textarea`, `button[data-testid="composer-plus-btn"]`, `[data-message-id][data-message-author-role]`, user/assistant turn selectors, `button[data-testid="copy-turn-action-button"]`, stop/send selectors, and a label-driven model picker because no stable test id/aria label was observed; Radix menus use `[data-radix-popper-content-wrapper]`, `menuitemradio` tiers and submenu radio families. `§Clipboard viability` says permission state was `prompt`, so clipboard read is not an unattended fallback.
   - Design quote/evidence: `M3-detailed-design.md §2.10 selectors/` includes the concrete selector map with `#prompt-textarea`, tools, turn, copy, stop, send, `radix_portal`, and `model_picker_trigger_candidates: "composer-footer button[aria-haspopup=\"menu\"]"`; it says model picking enumerates candidates, matches visible text, uses only `radix_portal`, and fails closed. `§2.6 menus.py` and `§6 Send and action strategy` require label-driven Radix enumeration, exact `menuitemradio`/submenu selection, reflected-label verification, and no opening `Recent files`/`Projects` submenus. `§4.4 Fail-closed fallback chain` says copy fallback requires explicit attended clipboard permission/user gesture because permission was `prompt`.
   - Assessment: live selectors, model/menu behavior, private-submenu avoidance, and clipboard non-dependence are encoded correctly. Minor wording note only: `§6`'s compact observed-tools list omits `Recent files`/`Projects` from the comma-separated label list, but the same paragraph explicitly names them as submenus not to open, so this is not a load-bearing selector/fidelity gap.

8. **Projects — HONORED**
   - M2 evidence: `M2-ground-truth-probe.md §Project notes` says project probing was deferred; the authorized target was plain `/c/<conversation_id>`, `gizmo_id`/`gizmo_type` were null, and `/g/g-p-<projid>/c/<chatid>` behavior was not confirmed.
   - Design quote/evidence: `M3-detailed-design.md §2.8 identity.py` supports both `https://chatgpt.com/c/<conversation_id>` and `https://chatgpt.com/g/g-p-<project_id>/c/<conversation_id>` but says "Project send/create is treated as a near-term assumption because M2 did not probe project URLs." `§6 Send and action strategy` repeats project create/send is "not live-verified by M2" and must fail closed if project context cannot be verified. `§12 Open questions` asks whether M5 should prioritize project create/send.
   - Assessment: current design accounts for project URL/metadata while correctly marking project send/create as unverified, not M2-proven.

## Regression check

No M2-fidelity regression found in the revised current design. Independently re-checking the current sections touched or implicated by the revision (`§2.3`, `§2.5`, `§2.6`, `§2.9`, `§2.10`, `§4.1`, `§4.2`, `§5`, `§6`, `§7`, `§10`) shows the load-bearing M2 facts are still present: own-request auth/OAI header capture with redaction/fail-closed behavior, measured 17.1 MB/~5k streaming handling, sparse completion checks with `stream_status` still hypothetical, executable label-driven model/menu selection, and projects still marked unverified.

## Count and final verdict

- HONORED: 8
- PARTIAL: 0
- VIOLATED: 0
- MISSING: 0
- Most serious fidelity gap: none. The only note is non-blocking wording around the compact tools label list; the safety/fidelity behavior remains encoded.

VERDICT: PASS
