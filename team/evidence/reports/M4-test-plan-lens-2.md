# M4 offline-core capture slice — Lens 2 falsifiable behavior checklist

Scope: this checklist is for TDD of the offline capture parser/linearizer/classifier and attachment/citation normalization against raw fixture files only. No test in this slice should reach chatgpt.com, CDP, Playwright, a browser, the clipboard, or citation/attachment URLs. A “raw fixture shape” below may include a backend JSON body file, a small sidecar with fake fetch/header metadata, and optional offline UI fallback fixtures such as copied text or DOM/KaTeX HTML.

## Fixture conventions

- Use fake sentinel secrets such as `SECRET_AUTH_SENTINEL` and `SECRET_OAI_DEVICE_SENTINEL` only in in-memory/sidecar header fixtures created to test redaction. They must not appear in expected outputs.
- Required backend header names for positive authorized fixtures are exactly `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, and `x-openai-target-route`; tests should assert names may be reported/redacted but values never leak.
- Backend body fixtures should be raw ChatGPT-style JSON with top-level `conversation_id`, `mapping`, `current_node`, optional `async_status`, `default_model_slug`, and unknown extra top-level keys retained in the raw file.
- Fallback fixtures must be explicit offline artifacts; do not use real `navigator.clipboard`, DOM automation, or network fetches.

## Backend response handling and raw persistence

### B01 — 404 without required headers is not a canonical capture

1. Behavior: A backend response fixture with HTTP status 404 and a JSON body such as `{"detail": ...}` from an accept-only/no-required-headers request must fail closed and enter the fallback path; it must not emit an empty transcript or canonical backend records.
2. Why/gotcha: M2 proved accept-only fetch returned 404 while the same endpoint with web-app auth/OAI headers returned 200. M4 acceptance explicitly requires 404-without-headers coverage.
3. Falsifiability: Catch an implementation that treats any JSON response as valid, treats 404 `detail` as a zero-turn conversation, or silently marks `capture_source="backend_api"` after a missing-header response.
4. Required raw fixture shape: Sidecar `status=404`, `content_type="application/json"`, request header names missing at least `authorization` and one OAI header, body file with only top-level `detail` and no `mapping`/`current_node`.

### B02 — 200 with the required header set is accepted as canonical backend input

1. Behavior: A 200 JSON fixture whose sidecar proves all required header names were present must be validated and parsed as canonical backend data, producing `capture_source="backend_api"`, `fidelity="canonical"`, `status="complete"`, and `partial=false` for emitted records.
2. Why/gotcha: Backend capture is primary only when the web-app auth/OAI header set is safely acquired; M2 observed a 17.1 MB successful JSON body with those headers.
3. Falsifiability: Catch an implementation that still rejects authorized 200 fixtures because it expects cookies-only behavior, ignores the header requirement entirely, or marks canonical backend records as lossy/partial.
4. Required raw fixture shape: Sidecar `status=200`, JSON content type, all required header names present with fake secret values in a non-persisted header bundle, body with matching `conversation_id`, valid `mapping`, and valid `current_node`.

### B03 — Non-2xx, non-JSON, parse failure, id mismatch, and missing top-level shape all fail closed

1. Behavior: Backend fixtures must be rejected before transcript emission when status is non-2xx, content type is not JSON, JSON parsing fails, top-level `conversation_id` mismatches the expected conversation, `mapping` is absent/not an object, or `current_node` is absent/invalid.
2. Why/gotcha: §4.2 and §4.4 require fail-closed behavior for these cases because emitting ambiguous markdown/math is worse than stopping.
3. Falsifiability: Catch an implementation that partially parses malformed JSON, accepts a fixture for a different conversation, guesses a leaf when `current_node` is missing, or emits DOM/text fallback as canonical without marking degradation.
4. Required raw fixture shape: A small matrix of raw files: malformed JSON, wrong `conversation_id`, no `mapping`, `current_node` not in `mapping`, and non-JSON sidecar content type.

### B04 — Successful validation promotes one raw mapping; failed validation discards temp output

1. Behavior: A successful backend capture should leave exactly one promoted raw mapping artifact for the conversation and point the transcript at it; a failed backend validation should not promote a corrupt/partial raw mapping as the canonical raw artifact.
2. Why/gotcha: §4.2 requires streaming to a temp file first and discarding temp files on invalid status/shape; raw persistence is part of the lose-nothing contract only after shape validation.
3. Falsifiability: Catch an implementation that writes a 404 body to `raw-mapping.json`, leaves a malformed temp file referenced by `Transcript.raw_mapping_path`, or overwrites a good raw file with a failed retry.
4. Required raw fixture shape: One valid 200 raw fixture and one invalid 404 or malformed fixture processed through the offline capture harness with temporary/promoted output paths under a temp conversation directory.

### B05 — Unknown top-level keys are retained raw but not normalized into invented transcript fields

1. Behavior: Unknown top-level backend keys must remain present in the raw JSON artifact and may be listed in `raw_top_level_keys`, but they must not create invented `TurnRecord` fields or change visible transcript text.
2. Why/gotcha: §4.3 says shape checks retain unknown top-level keys in raw and normalize only known transcript fields.
3. Falsifiability: Catch an implementation that drops unknown keys from raw persistence, crashes on harmless extra keys, or maps unknown telemetry into citations/attachments/kind.
4. Required raw fixture shape: Valid 200 body with extra top-level keys such as `safe_urls`, `blocked_urls`, `owner`, and one synthetic `future_key`, plus ordinary visible turns.

### B06 — Large current branches are handled iteratively and deterministically

1. Behavior: A synthetic raw fixture with about 5k mapping nodes on the current branch must linearize deterministically without recursion-limit failures, key-order dependence, or quadratic behavior visible at test scale.
2. Why/gotcha: M2 observed about 5k mapping/current-branch nodes, and M4 mock fixtures are expected to include a ~5k-node mapping.
3. Falsifiability: Catch an implementation that recursively walks parents until `RecursionError`, sorts mapping keys instead of following parents, or times out/hangs on a long but simple chain.
4. Required raw fixture shape: Valid 200 body with a 5k-node parent chain ending at `current_node`, sparse visible `user:text`/`assistant:text` messages, many hidden nodes, and side branches not on the current branch.

## Current-branch linearization and record identity

### L01 — Linearization follows `current_node` parent links to root, then reverses

1. Behavior: Transcript order must be the reversed parent chain from `current_node` to root, not insertion order, mapping-key lexical order, create-time order, or all tree nodes.
2. Why/gotcha: §3.5 gives the algorithm and M2 confirms backend `mapping` is a message tree with `current_node` selecting the UI branch.
3. Falsifiability: Catch an implementation that emits side branches, emits root-to-leaf incorrectly, or orders nodes by UUID/key/time rather than the parent chain.
4. Required raw fixture shape: Mapping keys deliberately out of chronological/lexicographic order, with one abandoned side branch containing plausible visible text and a `current_node` on a different branch.

### L02 — Side branches and hidden internals are retained in raw but not emitted as transcript turns

1. Behavior: The raw mapping artifact must still contain side-branch nodes and hidden current-branch nodes, while the transcript emits only visible records from the selected current branch.
2. Why/gotcha: §3.5 says raw mapping retains side branches and hidden internals; user-facing history should match the UI branch.
3. Falsifiability: Catch an implementation that prunes raw to only visible nodes, emits all mapping nodes as transcript turns, or loses hidden nodes needed for attachment/citation grouping.
4. Required raw fixture shape: Current branch with hidden reasoning/tool nodes and a non-current side branch with visible-looking user/assistant messages.

### L03 — Cycles in the parent chain are a backend shape error

1. Behavior: If following `parent` links from `current_node` revisits a node id, linearization must raise a backend-shape/fail-closed error and emit no canonical transcript.
2. Why/gotcha: §3.5 includes explicit cycle detection raising `BackendShapeUnrecognizedError("cycle in mapping parent chain")`.
3. Falsifiability: Catch an implementation that infinite-loops, silently truncates at the repeated node, or emits a partial transcript as complete.
4. Required raw fixture shape: Valid-looking `mapping` with `current_node=C`, `C.parent=B`, `B.parent=A`, and `A.parent=C`.

### L04 — Broken parent references and invalid `current_node` fail closed

1. Behavior: If `current_node` is not a mapping key or a parent link points to a missing node before root, parsing must fail closed rather than guessing a root or skipping the broken segment.
2. Why/gotcha: §4.2 rejects missing/invalid `current_node`; the parent-chain algorithm assumes every traversed node is in `mapping`.
3. Falsifiability: Catch an implementation that emits only the suffix after the missing parent, treats unknown parents as root, or substitutes mapping insertion order.
4. Required raw fixture shape: One fixture with `current_node="missing"`; another with a leaf whose parent is `missing_parent`.

### L05 — `message_id`, `parent_id`, `turn_index`, and timestamps come from backend shape, not agent guesses

1. Behavior: For backend-derived visible records, `message_id` must be `message.id` when present, otherwise the mapping node id; `parent_id` must be the raw mapping parent id even if it points to a hidden node; `turn_index` is the visible-order index; `created_at` uses backend timestamp when available and is not filled with agent wall-clock time.
2. Why/gotcha: §2.1 defines canonical id/timestamp behavior and allows visible parent ids to point to hidden nodes.
3. Falsifiability: Catch an implementation that always uses node ids despite different `message.id`, rewrites `parent_id` to the previous visible record, numbers hidden nodes in `turn_index`, or inserts `datetime.now()` for missing backend timestamps.
4. Required raw fixture shape: Visible assistant node whose raw parent is a hidden tool node, message ids differing from node ids, mixed present/missing `create_time` values, and at least two visible turns separated by hidden nodes.

## Visible-vs-hidden classification and `content.parts`

### C01 — `user:text` is visible and extracts only string `content.parts`

1. Behavior: A current-branch node with `message.author.role="user"` and `message.content.content_type="text"` is emitted as a user `TurnRecord` whose markdown is derived by the `content.parts` rule.
2. Why/gotcha: §3.5 says `user:text` is visible; this is one of only two visible classes.
3. Falsifiability: Catch an implementation that drops user turns, reads user text from some unrelated field, or includes user attachments as transcript text.
4. Required raw fixture shape: User message with `content.parts=["user prompt"]`, plus metadata attachments to ensure attachment refs do not contaminate `content_markdown`.

### C02 — `assistant:text` is visible and extracts only string `content.parts`

1. Behavior: A current-branch node with `message.author.role="assistant"` and `message.content.content_type="text"` is emitted as an assistant `TurnRecord` whose markdown is derived by the `content.parts` rule.
2. Why/gotcha: §3.5 and M2 identify visible assistant report bodies in `message.content.parts` for `assistant:text`.
3. Falsifiability: Catch an implementation that drops final assistant reports, prefers `message.content.text` over `parts`, or emits assistant text from hidden code/thought nodes.
4. Required raw fixture shape: Assistant text message with `parts=["final report"]`, plus neighboring hidden `assistant:code` and `assistant:thoughts` nodes with tempting text fields.

### C03 — Assistant code/thought/reasoning/model-editable-context nodes are hidden

1. Behavior: `assistant:code`, `assistant:thoughts`, `assistant:reasoning_recap`, and `assistant:model_editable_context` nodes on the current branch must not produce standalone transcript text, though their raw data and extractable refs/status may be retained.
2. Why/gotcha: M2 observed these roles/content types as hidden internals, and §3.5 explicitly classifies them hidden unless future live evidence proves otherwise.
3. Falsifiability: Catch an implementation that emits code cells, thought summaries, reasoning recaps, or model-editable-context as visible assistant turns.
4. Required raw fixture shape: Current branch containing all four assistant hidden content types, with non-empty `content.text` or `content.thoughts` fields that would be obvious if leaked.

### C04 — All `tool:*` and `system:text` nodes are hidden

1. Behavior: Every tool-authored node, regardless of `content_type`, and every `system:text` node must be hidden from transcript text.
2. Why/gotcha: §3.5 explicitly says all `tool:*` and `system:text` are hidden while raw retains them.
3. Falsifiability: Catch an implementation that emits `tool:execution_output`, `tool:tether_browsing_display`, `tool:multimodal_text`, or system messages as user/assistant transcript turns.
4. Required raw fixture shape: Tool nodes with visible-looking text/output and a system text node on the current branch before a final visible assistant message.

### C05 — Hidden nodes can contribute refs and grouping, but not transcript prose

1. Behavior: Hidden nodes may contribute attachment refs, citation refs, progress/status, `turn_exchange_id` grouping, and DR/Pro classification evidence, but their text fields must not be concatenated into visible markdown.
2. Why/gotcha: §3.5 and §3.6 separate hidden internals from user-facing history while preserving metadata needed for final reports.
3. Falsifiability: Catch an implementation that either discards all hidden metadata and misses generated assets/citations, or includes hidden reasoning/tool text inside `content_markdown`.
4. Required raw fixture shape: Same `turn_exchange_id` group with hidden tool asset, hidden code execution aggregate, hidden thoughts, citation metadata, and one visible final assistant report.

### C06 — Single-string `content.parts` uses exactly `parts[0]`

1. Behavior: If visible `content.parts` contains exactly one string, `content_markdown` must be that exact string with no trimming, HTML conversion, delimiter rewriting, or normalization.
2. Why/gotcha: §3.5 defines the single-part rule; M2 found backend markdown/math is canonical.
3. Falsifiability: Catch an implementation that strips leading/trailing newlines, converts markdown to plain text/HTML, changes math delimiters, or reads another field.
4. Required raw fixture shape: Visible user and assistant messages with one string part containing leading/trailing whitespace, markdown table pipes, and LaTeX tokens.

### C07 — Multiple string `content.parts` concatenate with no inserted separator

1. Behavior: If visible `content.parts` contains multiple strings, `content_markdown` must be the direct concatenation in array order with no inserted newline, blank line, space, or delimiter; the original boundaries remain only in raw.
2. Why/gotcha: §3.5 chooses the no-invented-separator rule and explicitly rejects blank-line join assumptions.
3. Falsifiability: Catch an implementation that joins with `"\n\n"`, spaces, commas, Markdown separators, or sorted/deduplicated parts.
4. Required raw fixture shape: Assistant `parts=["alpha", "", "beta", "\n", "gamma"]` where any inserted separator changes the expected exact output.

### C08 — Non-string or malformed visible `content.parts` fail closed

1. Behavior: For visible `user:text` or `assistant:text`, `content.parts` must be a list of strings; non-string elements, absent `parts`, or non-list `parts` trigger backend-shape/fail-closed fallback and produce no canonical backend record for that capture.
2. Why/gotcha: §3.5 says non-string parts are a backend shape error; §4.4 lists visible `content.parts` shape mismatch as a fallback trigger.
3. Falsifiability: Catch an implementation that stringifies dict/list parts, drops non-string parts and emits the rest, or emits a partial record marked canonical.
4. Required raw fixture shape: Visible assistant messages with `parts=["ok", {"type":"image"}]`, `parts="not a list"`, and missing `parts`.

### C09 — Empty `content.parts` is ambiguous and must be made explicit before tests lock behavior

1. Behavior: The design specifies one string, multiple strings, and non-string failure, but does not explicitly state whether an empty list is valid empty markdown or a backend-shape error.
2. Why/gotcha: This is a real ambiguity in §3.5; tests should not accidentally bless an arbitrary behavior without lead decision.
3. Falsifiability: Once decided, include a fixture that catches the opposite behavior: either emitting `""` when it should fail closed, or failing closed when empty visible messages should be allowed.
4. Required raw fixture shape: Visible `assistant:text` with `content.parts=[]` and no other text fields.

### C10 — Backend markdown math tokens round-trip without corruption

1. Behavior: Backend visible markdown containing `\widehat`, `\ne` or `\neq`, and `\frac{}{}` must appear in `content_markdown` exactly as in the raw JSON string after JSON decoding; no Unicode substitution, extra escaping, delimiter deletion, or HTML/plain-text conversion is allowed.
2. Why/gotcha: M2 found these tokens in canonical backend markdown and §4.4 makes math fidelity acceptance falsifiable.
3. Falsifiability: Catch an implementation that converts `\ne` to `≠`, double-escapes backslashes in the in-memory record, strips `\(` or `\[` delimiters, or rewrites `\frac{a}{b}` to `a/b`.
4. Required raw fixture shape: Assistant `content.parts` string such as `"\\(\\widehat{x} \\ne y, \\frac{a}{b}\\) and \\[z \\neq 0\\]"` plus markdown table syntax.

### C11 — Unknown roles/content types must not become visible transcript text by accident

1. Behavior: Anything outside the explicitly visible `user:text` and `assistant:text` classes must not be emitted as visible transcript text unless a future design update names it visible.
2. Why/gotcha: §3.5 deliberately keeps classification small and evidence-based.
3. Falsifiability: Catch an implementation with a broad fallback such as “any node with `content.parts` is visible” or “any assistant content is transcript text.”
4. Required raw fixture shape: Nodes with roles/content types such as `assistant:multimodal_text`, `tool:text`, and `system:text`, each containing tempting `parts` strings.

Ambiguity: The design names observed hidden classes but does not fully specify whether unknown non-visible classes should be silently hidden or raise a backend-shape error. The minimum falsifiable requirement for this slice is that unknown classes do not produce visible transcript text or canonical markdown claims.

## Deep Research / Pro classification

### D01 — Positive DR/Pro classification requires the full evidence pattern in scrape-only mode

1. Behavior: In offline scrape-only fixtures, an assistant final report is classified with `kind="deep_research"` and `active_tools` including `deep_research` only when the same `turn_exchange_id` contains a visible user message, a large hidden reasoning/tool/code group, citation/search metadata, and a visible final `assistant:text` report.
2. Why/gotcha: §3.6 and M2 show no `content_type="deep_research"`; DR/Pro is represented by a turn-exchange group, not a single type.
3. Falsifiability: Catch an implementation that classifies any long assistant answer, any citation-bearing answer, or any hidden-tool answer as DR without the full evidence pattern.
4. Required raw fixture shape: One `turn_exchange_id` group with user `text`, many hidden `assistant:thoughts`/`assistant:code`/`tool:*` nodes, `metadata.citations` or search metadata, and one final visible assistant `text` report.

### D02 — Missing any major DR evidence keeps `kind="normal"`

1. Behavior: If the group lacks shared `turn_exchange_id`, lacks the hidden reasoning/tool group, lacks citation/search metadata, or lacks a visible final `assistant:text`, the visible assistant record must remain `kind="normal"` in scrape-only mode.
2. Why/gotcha: §3.6 says ambiguous scrape-only cases remain normal rather than overclaiming.
3. Falsifiability: Catch an implementation with an overbroad heuristic such as “has citations => deep_research” or “has tool nodes nearby => deep_research.”
4. Required raw fixture shape: Negative fixture set varying one missing evidence element at a time: citations-only normal answer, hidden-tools-without-citations answer, same-exchange hidden group without final visible assistant, and final assistant with hidden nodes but different `turn_exchange_id` values.

### D03 — `content_type="deep_research"` must not be required or trusted as the primary signal

1. Behavior: Positive DR fixtures without any `content_type="deep_research"` must still classify from the evidence pattern, and a synthetic node with `content_type="deep_research"` but lacking the pattern must not by itself force `kind="deep_research"`.
2. Why/gotcha: M2 observed no single `deep_research` content type.
3. Falsifiability: Catch an implementation that looks only for a nonexistent content type, or one that trusts a lone content-type string over the group evidence.
4. Required raw fixture shape: Positive evidence-pattern fixture with only observed content types, plus a negative fixture containing one artificial `assistant:deep_research`-like node without hidden group/citations/final report.

### D04 — Hidden same-exchange refs attach to the visible final DR/Pro report

1. Behavior: Attachment and citation refs found on hidden nodes in the same DR/Pro `turn_exchange_id` should attach to the visible final assistant report, while hidden text remains raw-only.
2. Why/gotcha: §3.6 states hidden same-exchange attachment refs attach to the visible final report.
3. Falsifiability: Catch an implementation that drops hidden generated assets/code outputs, creates hidden transcript records to hold them, or attaches them to the wrong visible turn.
4. Required raw fixture shape: DR evidence group with hidden `tether_browsing_display` asset and hidden `execution_output` aggregate before the final assistant report.

### D05 — “Large hidden group” threshold is ambiguous; use fixtures far from the boundary

1. Behavior: Tests should include a clearly positive large hidden group and clearly negative tiny groups, but should avoid encoding an arbitrary exact threshold unless the lead decides one.
2. Why/gotcha: §3.6 says “large hidden reasoning/tool group” without a numeric cutoff.
3. Falsifiability: Catch threshold-insensitive implementations by using a positive fixture with dozens of hidden nodes and negatives with zero/one hidden node; do not fail an implementation solely for choosing threshold 10 vs 20 unless specified.
4. Required raw fixture shape: Positive group with 30+ hidden reasoning/tool nodes; negative group with one hidden tool node and otherwise similar visible text.

## Attachment normalization

### A01 — User-upload metadata attachments normalize to `source_kind="user_upload"`

1. Behavior: `message.metadata.attachments[]` on a visible user message must create `AttachmentRef` entries with `source_kind="user_upload"`, `source_ref=id`, `filename=name`, `bytes=size`, a correct JSON-pointer `raw_path`, sanitized metadata including `source`, `file_token_size`, and `is_big_paste`, and no transcript text pollution.
2. Why/gotcha: §3.7 table lists this as the user-upload shape observed by M2.
3. Falsifiability: Catch an implementation that ignores user uploads, treats them as citations, inserts filenames into `content_markdown`, or invents a download URL/local path.
4. Required raw fixture shape: Visible `user:text` node with `metadata.attachments=[{"id":"file_123","size":42,"name":"data.csv","file_token_size":7,"source":"local","is_big_paste":false}]`.

### A02 — `content_references[type=file]` normalizes to `source_kind="file_reference"`, not a web citation

1. Behavior: `message.metadata.content_references[]` entries where `type == "file"` must create `AttachmentRef(source_kind="file_reference")` with `source_ref=id`, `filename=name`, listed metadata sanitized, and `raw_path`; they must not be mixed into `CitationRef` merely because they live under `content_references`.
2. Why/gotcha: §3.7 separates file content references from citations and lists their observed fields.
3. Falsifiability: Catch an implementation that treats all `content_references` as citations, drops file refs, truncates raw snippets in the raw artifact, or tries to fetch `cloud_doc_url`.
4. Required raw fixture shape: Assistant or same-exchange hidden node with `metadata.content_references=[{"type":"file","id":"file_ref_1","name":"paper.pdf","source":"uploaded","snippet":"...","cloud_doc_url":"https://example.invalid/doc","library_file_id":"lib_1","input_pointer":{"file_index":0,"line_start":1,"line_end":2}}]`.

### A03 — Tool `content.assets[]` normalizes to `source_kind="generated_asset"`

1. Behavior: `message.content.assets[]` on hidden tool `tether_browsing_display` messages must create generated-asset attachment refs on the associated visible report, with `source_ref=asset_pointer`, `mime=content_type`, `bytes=size_bytes`, dimensions/fovea/metadata preserved in sanitized metadata, and hidden tool text not emitted.
2. Why/gotcha: §3.7 table lists generated/image-like assets from tool display messages.
3. Falsifiability: Catch an implementation that drops assets because the tool node is hidden, emits the tool node as transcript text, or stores `asset_pointer` as a citation URL.
4. Required raw fixture shape: Hidden `tool:tether_browsing_display` node with `content.assets=[{"content_type":"image/png","asset_pointer":"asset_abc","size_bytes":1234,"width":640,"height":480,"fovea":null,"metadata":{"prompt":"fake"}}]` and a later visible assistant report in the same exchange.

### A04 — Tool `metadata.aggregate_result` normalizes code execution output when associated with a visible report

1. Behavior: Hidden tool `execution_output` messages with `metadata.aggregate_result` and `run_id` must retain the full aggregate raw and, when associated with a visible final report, create a `code_execution_output` attachment ref with `source_ref=run_id`, `filename="run_<run_id>_aggregate.json"`, and `mime="application/json"`; code/output text must not be transcript prose.
2. Why/gotcha: §3.7 table identifies code execution output as a materializable artifact shape, not visible assistant text.
3. Falsifiability: Catch an implementation that discards aggregates, emits Jupyter output as assistant markdown, or creates an attachment without the run id/raw path.
4. Required raw fixture shape: Hidden `tool:execution_output` node with `metadata.aggregate_result={"run_id":"run_789","status":"success","code":"print(1)","messages":[],"jupyter_messages":[],"final_expression_output":"1"}` in the same exchange as a visible assistant report.

### A05 — Attachment refs do not imply byte fetching or invented endpoints in M4

1. Behavior: Offline capture must normalize stable ids/pointers/raw paths without downloading bytes, inventing `/backend-api/files/...`, following `sandbox:`/`attachment:` URLs, setting fake `local_path`, or computing fake `sha256`.
2. Why/gotcha: M2 observed no literal file URLs and §3.7 says refs are stored for later lazy fetch without inventing endpoints.
3. Falsifiability: Catch an implementation that attempts network/file fetches during parsing, marks attachments `downloaded`, or fabricates local files/paths from ids.
4. Required raw fixture shape: All four attachment shapes with ids/pointers but no fetchable byte URL; include a fake URL that would be invalid if fetched.

Ambiguity: §2.1 requires a `download_state`, but §3.7 does not mandate the exact non-downloaded value for each source in M4. Tests should at minimum assert `local_path is None`, `sha256 is None`, no network/fetch occurs, and `download_state != "downloaded"`; a lead decision can tighten this to `pending` or `unsupported` per source.

### A06 — Attachment metadata is sanitized and bounded without destroying raw evidence

1. Behavior: AttachmentRef metadata must exclude auth/OAI header values and other sensitive transport data, while the raw mapping preserves the original backend attachment fields; display-oriented truncation must not truncate the raw fixture.
2. Why/gotcha: §2.1 says attachment metadata is sanitized with no auth/OAI headers; §3.7 allows transcript metadata to truncate display snippets while raw stays full.
3. Falsifiability: Catch an implementation that leaks sentinel header values into attachment metadata, mutates raw snippets, or copies entire unrelated message metadata into every attachment.
4. Required raw fixture shape: File-reference attachment with a long `snippet`, ordinary listed metadata, and a deliberately injected fake header-like metadata key/value to verify sanitization policy.

## Citation handling

### R01 — `metadata.citations[]` become `CitationRef`, not attachments

1. Behavior: Assistant `message.metadata.citations[]` entries must create citation refs preserving title/url when present, offsets `start_ix`/`end_ix`, `citation_format_type`, nested sanitized metadata, source `"citations"`, and `raw_path`; they must not create attachment refs or trigger fetching.
2. Why/gotcha: §3.7 says citations are web/source references and are never downloaded by `fetch`.
3. Falsifiability: Catch an implementation that treats citation URLs as downloadable attachments, drops offsets, or fetches citation URLs for titles/snippets.
4. Required raw fixture shape: Visible assistant message with `metadata.citations=[{"start_ix":10,"end_ix":20,"citation_format_type":"tldr","metadata":{"title":"Source","url":"https://example.invalid/source"}}]`.

### R02 — Web/source `content_references` become citations, while file refs remain attachments

1. Behavior: `content_references` such as `grouped_webpages` and `sources_footnote` should produce `CitationRef(source="content_references")`; `content_references[type=file]` should produce `AttachmentRef(source_kind="file_reference")` instead.
2. Why/gotcha: §3.7 separates file references from citation/source references despite sharing the `content_references` container.
3. Falsifiability: Catch an implementation that buckets all content references together, double-counts file refs as both citation and attachment, or ignores grouped webpage sources.
4. Required raw fixture shape: One assistant message with three content references: `type="grouped_webpages"`, `type="sources_footnote"`, and `type="file"`.

### R03 — `search_result_groups` can promote displayed sources; raw `search_queries` alone do not

1. Behavior: Search result groups marked/linked as displayed sources may become citations, but `search_queries` alone are retained raw and not promoted to citations unless linked to a displayed source.
2. Why/gotcha: §3.7 says `search_queries` are retained raw and promoted only when linked to a displayed source, avoiding internal telemetry as citations.
3. Falsifiability: Catch an implementation that turns every search query string into a citation, or ignores displayed search result groups entirely.
4. Required raw fixture shape: Assistant metadata with `search_queries=["private query text"]` and `search_result_groups` containing one displayed result with title/url plus one non-displayed/internal result.

### R04 — Citations stay separate from attachments and are never fetched

1. Behavior: A record may have both `attachments` and `citations`, but citation refs must not have attachment fields such as `download_state`/`local_path`, attachment refs must not have citation offsets, and neither citation URLs nor attachment ids are fetched in this offline slice.
2. Why/gotcha: §3.7 and REWRITE-SPEC gotcha #8 separate byte artifacts from web/source references.
3. Falsifiability: Catch an implementation that merges citations into attachments for convenience, tries to download citation URLs, or stores citation URLs as attachment `source_ref`.
4. Required raw fixture shape: One visible assistant report with a file reference, a web citation, a grouped webpage source, and a generated asset in the same exchange.

## Fail-closed fallback and fidelity marking

### F01 — Successful backend records are canonical, complete, and not partial

1. Behavior: For a valid backend fixture, every emitted record must have `capture_source="backend_api"`, `fidelity="canonical"`, `status="complete"`, and `partial=false`.
2. Why/gotcha: §4.3 defines successful backend extraction as canonical; §2.1 says `partial` is false iff status is complete.
3. Falsifiability: Catch an implementation that marks backend math as lossy, leaves `partial=true` on complete records, or mixes fallback fidelity into a successful backend parse.
4. Required raw fixture shape: Valid 200 backend body with visible user/assistant messages and no fallback fixture needed.

### F02 — Fallback order is exactly backend_api → copy_button → katex_annotation → dom_text

1. Behavior: When backend validation fails, the offline fallback harness must attempt fallback sources in the specified order and stop at the first allowed/successful source, preserving the selected source and fidelity.
2. Why/gotcha: §4.4 mandates the order and warns not to silently emit DOM text as canonical.
3. Falsifiability: Catch an implementation that jumps directly to DOM text, uses KaTeX before copy, or continues to a lower-fidelity source after a copy-button fixture succeeded.
4. Required raw fixture shape: Invalid backend fixture plus three fallback fixtures all available, each containing distinguishable text so the chosen output proves the order.

### F03 — Copy-button fallback requires explicit permission/fixture and marks `ui_copy`

1. Behavior: Copy-button fallback may produce records with `capture_source="copy_button"` and `fidelity="ui_copy"` only when the offline test explicitly supplies an allowed copy fixture; without permission/fixture it must raise/continue according to configured degraded-salvage policy rather than read real clipboard.
2. Why/gotcha: M2 found clipboard permission state `prompt`; M4 lead decision is fail-closed by default and never auto-read clipboard.
3. Falsifiability: Catch an implementation that calls `navigator.clipboard.readText`, reads the operator clipboard, treats copy fallback as canonical backend, or uses copy without explicit opt-in.
4. Required raw fixture shape: Backend failure fixture plus sidecar `allow_clipboard=false` and no copy text for the negative case; separate positive offline copy fixture with exact assistant markdown.

### F04 — KaTeX annotation fallback is degraded and partial

1. Behavior: KaTeX fallback must reconstruct only from `<annotation encoding="application/x-tex">` in document order and mark `capture_source="katex_annotation"`, `fidelity="math_annotation_reconstructed"`, and `partial=true`.
2. Why/gotcha: §4.4 defines KaTeX as a degraded salvage path, not a full-fidelity transcript.
3. Falsifiability: Catch an implementation that marks KaTeX reconstruction complete/canonical, ignores annotation order, or mixes DOM prose into math annotations without marking partial.
4. Required raw fixture shape: Offline HTML fixture with two KaTeX annotation elements containing `\widehat{x}` and `\frac{a}{b}`, plus surrounding DOM text that should not be misrepresented as canonical markdown.

### F05 — DOM `textContent` is last-resort lossy salvage only

1. Behavior: DOM text fallback must be used only after backend/copy/KaTeX fail or are unavailable, and records must be marked `capture_source="dom_text"`, `fidelity="lossy_dom_text"`, and `partial=true`; it is acceptable only for salvage/status, not a fidelity pass.
2. Why/gotcha: §4.4 says DOM text is last resort and lossy.
3. Falsifiability: Catch an implementation that uses DOM text while a copy fixture exists, marks DOM text complete/canonical, or claims math round-trip fidelity from textContent.
4. Required raw fixture shape: Invalid backend fixture, no copy fixture/permission, no KaTeX annotations, and a DOM text fixture with visibly degraded math such as `x ≠ y` instead of `\ne`.

### F06 — No faithful fallback means loud fail-closed behavior

1. Behavior: If backend fails and no allowed faithful/degraded fallback fixture is available under the caller's policy, capture must raise a human-action/fail-closed error such as `HUMAN-ACTION-NEEDED` and emit no fake complete transcript.
2. Why/gotcha: M4 lead decision says clipboard fallback is fail-closed by default and no faithful fallback should stop rather than silently degrade.
3. Falsifiability: Catch an implementation that returns an empty successful transcript, fabricates assistant text, or auto-enables clipboard/DOM fallback without caller permission.
4. Required raw fixture shape: 404/malformed backend fixture with no copy fixture, no KaTeX fixture, no DOM fixture, and `allow_clipboard=false`/degraded salvage disabled.

### F07 — `partial` and `status` remain honest across all sources

1. Behavior: `partial=false` iff `status="complete"`; backend and successful full copy can be complete, while KaTeX/DOM degraded salvage must be partial, and backend shape errors must not yield complete records.
2. Why/gotcha: §2.1 defines the invariant and §4.4 requires honest degraded marking.
3. Falsifiability: Catch an implementation with `status="complete", partial=true`, `status="partial", partial=false`, or DOM/KaTeX records marked complete.
4. Required raw fixture shape: One valid backend fixture, one copy fallback fixture, one KaTeX fallback fixture, and one DOM text fallback fixture.

## Secret/header redaction and output hygiene

### S01 — Header bundle repr/redaction never exposes values

1. Behavior: Header containers may expose required header names through a redacted view, but `repr`, `str`, exceptions, and diagnostic objects must not include bearer/OAI header values.
2. Why/gotcha: §2.3 makes `HeaderBundle` `repr=False` and says values must never appear in repr/logs/exceptions/status/fixtures/files.
3. Falsifiability: Catch an implementation whose dataclass repr includes `_headers`, whose error message says `authorization=SECRET_AUTH_SENTINEL`, or whose redacted view returns raw values.
4. Required raw fixture shape: In-memory/sidecar header bundle with sentinel values for every required header; force a failure path after header acquisition to inspect repr/error text.

### S02 — Secret values never appear in transcript, raw mapping, status, logs, or normalized metadata

1. Behavior: Sentinel auth/OAI values must be absent from every produced file and object representation in this slice: `raw-mapping.json`, `transcript.jsonl` if store is involved, `CaptureResult`, `TurnRecord`, `AttachmentRef.metadata`, `CitationRef.metadata`, errors, and logs.
2. Why/gotcha: M2 required forwarding sensitive headers, and §2.3 makes non-persistence/non-logging a safety invariant.
3. Falsifiability: Catch an implementation that writes request headers into raw JSON sidecars, copies whole request metadata into attachment/citation metadata, logs fetch arguments, or includes header values in assertion-friendly error messages.
4. Required raw fixture shape: Valid 200 body plus header sidecar with sentinel values and one raw message metadata field containing a fake header-like value to verify metadata sanitization.

### S03 — Header values are one-request inputs, not long-lived capture state

1. Behavior: Offline tests should model headers as consumed for a single backend fetch/check and discarded afterward; persisted capture state should contain only redacted progress data such as ids, lengths, hashes, statuses, and timing.
2. Why/gotcha: §2.3 says `for_single_fetch()` is for exactly one capture fetch or sparse completion check and no long-lived header reference is held.
3. Falsifiability: Catch an implementation that stores the header mapping on `CaptureResult`, `Transcript`, store metadata, or a reusable long-lived object after capture.
4. Required raw fixture shape: Authorized 200 fixture whose fake header bundle is inspected after capture through all returned/persisted objects for absence of sentinel values.

## Explicit out-of-scope for this lens

- No live header acquisition, browser request listeners, CDP, Playwright import behavior, real clipboard reads, real attachment byte downloads, or citation URL fetches.
- No send/completion polling behavior except where `send_context` or `turn_exchange_id` affects classification in raw capture fixtures.
- No CLI/store rendering tests except incidental inspection needed to prove capture outputs do not leak headers or corrupt markdown.
