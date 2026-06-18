STATUS: DONE
Produced a detailed design for capture, safe web-app auth/OAI header harvesting, canonical markdown extraction, fail-closed fallbacks, and completion detection.
Key decision: harvest required headers by observing the tool-owned page's own `/backend-api/conversation/<id>` request, keep values in memory only, then perform a single in-page authenticated fetch; reject JS/session-store scraping.
No production source was modified; remaining blockers are live-site-only M5 confirmations of exact completion status values, stream-status availability, memory footprint, and fallback fidelity.

## 1. Auth/OAI-header acquisition — load-bearing mechanism

### Required header set and safety boundary

The capture endpoint is `GET https://chatgpt.com/backend-api/conversation/<conversation_id>` and M2 refuted cookies-only capture: accept-only in-page fetch returned `404`, while replay with the web app's own headers returned `200` and a faithful JSON payload (M2 handoff; REWRITE-SPEC §5). The required request headers are exactly lower-cased in the capture code as `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, and `x-openai-target-route` (M2 handoff). Header values are secrets or session identifiers: they must stay in an in-memory object with `repr=False`/redacted display, must never be written to `raw-mapping.json`, `transcript.jsonl`, logs, exceptions, telemetry, or test fixtures, and must be discarded after the single fetch/poll sequence (M2 handoff; M3 common constraints §2).

Proposed internal type signatures:

```python
REQUIRED_CAPTURE_HEADERS: tuple[str, ...] = (
    "authorization",
    "oai-client-build-number",
    "oai-client-version",
    "oai-device-id",
    "oai-language",
    "oai-session-id",
    "x-openai-target-path",
    "x-openai-target-route",
)

@dataclass(slots=True)
class AuthHeaderBundle:
    source: Literal["web_app_request"]
    conversation_id: str
    acquired_at_monotonic: float
    header_names: frozenset[str]
    _headers: dict[str, str] = field(repr=False)

    def for_single_fetch(self) -> dict[str, str]: ...  # returns a shallow copy, no logging
    def redacted_summary(self) -> dict[str, object]: ...  # names + booleans only, never values
```

Errors from this layer are sanitized: `AuthHeadersUnavailable(conversation_id: str, missing: tuple[str, ...], reason: str)`, `AuthHeaderLeakPrevented(reason: str)`, and `HumanActionNeeded(reason: Literal["login","cloudflare"])`; none may include token/header values.

### Candidate option A — observe the page's own request (recommended)

Algorithm: attach to the operator-launched Chromium only after CDP preflight, acquire a tool-owned tab from the tab pool, register network listeners before navigation, navigate that tool-owned tab to the allowlisted conversation URL, wait until the app itself issues `GET /backend-api/conversation/<id>`, harvest the request headers from that request, validate the required names, then perform capture with those exact header values (REWRITE-SPEC §2/§5; M2 handoff). This respects the action/read asymmetry: the tool does not forge login, does not inspect operator tabs, and does not read browser storage broadly.

Concrete Playwright/CDP sequence in `capture.py`:

```python
async def acquire_auth_headers_from_own_request(
    page: Page,
    conv: ConversationAddress,
    *,
    selectors: SelectorMap,
    timeout_s: float = 30.0,
) -> AuthHeaderBundle:
    ...
```

Steps: (1) `allowlist.assert_allowed_url(conv.web_url, purpose="capture.navigate")` where valid web URL shapes are `https://chatgpt.com/c/<chatid>` and `https://chatgpt.com/g/g-p-<projectid>/c/<chatid>` (REWRITE-SPEC §9; M2 project caveat); (2) install `page.on("request", on_request)` before `page.goto`; (3) in `on_request`, accept only method `GET`, origin `https://chatgpt.com`, path exactly `/backend-api/conversation/<conversation_id>`, and the current tool-owned `page`; (4) call `await request.all_headers()` and lower-case names; (5) if any required header is absent, use a same-page CDP fallback listener, not a storage scrape: `cdp = await context.new_cdp_session(page)`, `await cdp.send("Network.enable")`, correlate `Network.requestWillBeSent` URL by `requestId` with `Network.requestWillBeSentExtraInfo.headers`, and harvest only the matched conversation request; (6) validate `authorization` is present and syntactically non-empty, preferably `Bearer ...`, without logging the suffix; (7) set the future result to `AuthHeaderBundle`; (8) remove listeners immediately after success/failure.

Navigation/wait details: call `await page.goto(conv.web_url, wait_until="domcontentloaded", timeout=...)` after the listeners are active; then wait for the header future until `timeout_s`. If the app does not issue the request, call `await page.reload(wait_until="domcontentloaded")` once and wait again. If no matching request is observed after the retry, raise `AuthHeadersUnavailable(reason="app_request_not_observed")` and trigger the fail-closed fallback chain. If the page lands on login or Cloudflare challenge, stop with `HumanActionNeeded` and poll read-only; login is never automated (M3 common constraints §2; team charter shared-resource ceilings).

Trade-offs: this option obtains exactly the headers M2 proved necessary, avoids guessing token storage, avoids over-reading private browser state, and preserves the web-app request-signing boundary. Its main fragility is that the SPA might serve a cached conversation without issuing the request; the fresh tool-owned tab plus one reload is the simplest correct mitigation. If Playwright's `request.all_headers()` omits sensitive headers, the CDP `Network.*ExtraInfo` fallback remains within the same option and still observes only the matched request from the tool-owned tab.

### Candidate option B — read bearer/session data from page JS or storage (rejected)

Possible implementation would evaluate page JS, local/session storage, IndexedDB, or app globals looking for bearer/OAI values, then synthesize the backend request. This is rejected for M4/M5 because it is fragile across web-app builds, risks reading unrelated signed-in browser state, may miss non-token OAI routing headers, and contradicts the minimal-observation safety posture (M3 common constraints §2; M2 handoff). It should remain a documented non-goal unless option A becomes impossible and the operator explicitly approves a narrower live-site probe.

Recommendation: implement option A only. All capture/completion code that needs backend auth receives an `AuthHeaderBundle` produced by `acquire_auth_headers_from_own_request`; no module may expose a public API for reading tokens from JS/storage.

## 2. Capture pipeline happy path

Public entry point in `capture.py`:

```python
async def capture_conversation(
    session: Session,
    conv_ref: str | ConversationAddress,
    *,
    reason: Literal["scrape", "post_send", "completion_poll"] = "scrape",
    include_hidden: bool = False,
) -> CaptureResult:
    ...
```

Proposed result types:

```python
@dataclass(slots=True)
class CaptureResult:
    conversation_id: str
    project_id: str | None
    raw_mapping_path: Path
    source: Literal["backend_api", "copy_button", "katex_annotation", "dom_text"]
    fidelity: Literal["canonical", "ui_copy", "math_annotation_reconstructed", "lossy_dom_text"]
    top_level: ConversationTopLevel
    visible_turns: list[VisibleTurnRecord]
    hidden_summary: HiddenSummary
    attachments: list[AttachmentRef]
    citations: list[CitationRef]
    partial: bool
```

Happy-path algorithm: (1) parse `conv_ref` using `identity.py` into `ConversationAddress(conversation_id: str, project_id: str | None, web_url: str, backend_url: str)`; (2) run CDP preflight before any real-site leg, and stop cleanly with `CDP_UNREACHABLE` if `http://127.0.0.1:9222/json/version` is unavailable (M3 common constraints §2); (3) acquire a tool-owned tab from the lens-4 tab pool, never by iterating `context.pages`; (4) allowlist-check both the conversation URL and backend URL; (5) acquire `AuthHeaderBundle` by observing the page's own request as above; (6) issue `GET https://chatgpt.com/backend-api/conversation/<conversation_id>` as an in-page fetch using `page.evaluate` with `credentials: "include"`, `cache: "no-store"`, `accept: "application/json"`, and the harvested headers; (7) stream the response body to `<data-dir>/conversations/<conversation_id>/raw-mapping.json.tmp` and atomically replace `raw-mapping.json` only after HTTP status, JSON parse, and minimal shape checks pass; (8) parse top-level fields and `mapping`; (9) linearize the current branch and extract canonical markdown records; (10) hand records to `store.py` for idempotent upsert/append and to `history/export` for rendering (REWRITE-SPEC §5/§8; M2 handoff).

Concrete in-page streaming fetch shape:

```javascript
async ({ url, headers, bindingName }) => {
  const res = await fetch(url, { method: "GET", credentials: "include", cache: "no-store", headers: { ...headers, accept: "application/json" } });
  const meta = { status: res.status, ok: res.ok, contentType: res.headers.get("content-type") || "" };
  if (!res.ok) return { ...meta, streamed: false };
  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let seq = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    if (text) await window[bindingName](seq++, text);
  }
  const tail = decoder.decode();
  if (tail) await window[bindingName](seq++, tail);
  return { ...meta, streamed: true };
}
```

The Python side exposes a unique per-capture binding such as `__askcgpt_capture_chunk_<uuid>` that writes chunks to the temp file and tracks byte count. The `headers` argument is the only place the secret values cross back into the page; it is not logged, not embedded in the returned metadata, and the bundle is deleted after use. If `res.status` is `403`, `404`, or `401`, or if content type/JSON shape is not recognized, raise a sanitized backend error and enter the fallback chain rather than emitting a possibly corrupt transcript (M2 handoff; M3 common constraints §4).

Minimal backend JSON shape checks before canonicalization: top-level object; `conversation_id: str` equal to the requested id; `mapping: dict[str, MappingNode]`; `current_node: str | null`; each mapping node has at least `id` or key id, `parent: str | null`, `children: list[str]`, and optional `message`; top-level keys such as `title`, `create_time`, `update_time`, `default_model_slug`, `async_status`, `moderation_results`, `safe_urls`, `blocked_urls`, `context_scopes`, `disabled_tool_ids`, `is_archived`, `is_temporary_chat`, `owner`, and `voice` are retained in raw and normalized only when needed (M2 handoff). Unknown extra top-level keys are preserved in raw and ignored by the transcript path.

## 3. Memory and streaming strategy

M2 measured a successful capture at about 17.1 MB in one response, with about 5.0k mapping nodes and no pagination observed; counts can vary while a conversation is updating (M2 handoff). A naive `page.evaluate(... await res.json())` or `await res.text()` design would hold at least one browser-side copy, one CDP serialization copy, one Python string/bytes copy, and then a Python object graph; that is avoidable. A provisional expectation is that a 17.1 MB JSON can expand to roughly tens to low hundreds of MB as Python dict/list/string objects, but this is an estimate only and must be measured in M5 with `tracemalloc` and process RSS on the real sample before treating whole-file parse as acceptable (agent-rigor: measure complexity empirically).

Recommended strategy: always stream the HTTP body to `raw-mapping.json.tmp` first with O(chunk) transfer memory, then parse from disk. This means a crash after download still has no partially named `raw-mapping.json`, and a crash after atomic replace still leaves the last complete backend capture. Do not enumerate all turns into memory and then decide what to persist; persist the raw response first, then emit transcript records incrementally.

Parser strategy is two-tiered for Occam plus rigor: implement the parser behind `iter_current_branch_records(raw_path: Path) -> Iterator[LinearizedRecord]`. In M4/mock and M5 initial real capture, whole-file `json.load` is acceptable only if measured peak memory is within an explicit engineering budget; otherwise switch the same interface to `ijson` or equivalent. The incremental plan is: pass 1 reads top-level `current_node` and `mapping` key/value pairs to build a compact `node_index: dict[str, NodeIndexEntry(parent: str | None, children: tuple[str, ...], has_message: bool, role: str | None, content_type: str | None, turn_exchange_id: str | None)]`; derive the current branch by following `parent` from `current_node` to root; pass 2 emits only current-branch visible records plus hidden summaries and attachment/citation refs. This keeps peak transcript memory proportional to branch output plus compact node metadata rather than full hidden tool/code/thought bodies.

Completion polling should not write a new 17 MB `raw-mapping.json` every few seconds unless it is the final or a salvage snapshot. For polling, reuse the same streaming machinery to a temp file, parse only progress signals/current-branch tail, and discard the temp on non-final polls unless it is needed for partial salvage. Poll cadence belongs to completion policy, not to the streaming primitive.

## 4. `mapping` to canonical markdown extraction

Canonical extraction consumes the backend `mapping` message tree; the transcript linearizes only the current branch while retaining the full raw tree in `raw-mapping.json` (REWRITE-SPEC §8; M2 handoff). Current-branch algorithm: start from top-level `current_node`, follow each node's `parent` to root, reverse the list, and process those nodes in order. Nodes outside the current branch remain in raw only; branch-aware history is deferred (REWRITE-SPEC §15).

Per-node extraction rule:

```python
def classify_and_extract(node_id: str, node: MappingNode) -> LinearizedRecord | HiddenNodeSummary | None:
    message = node.get("message")
    role = message.get("author", {}).get("role") if message else None
    content = message.get("content", {}) if message else {}
    content_type = content.get("content_type")
    key = (role, content_type)
```

Rules keyed by `(author_role, content_type)`: `("user", "text")` is visible user markdown from `message.content.parts` when it is a list of strings; concatenate with `"".join(parts)` to avoid inventing separators, and mark a shape error if any part is non-string. `("assistant", "text")` is visible assistant markdown from `message.content.parts` using the same exact concatenation; this is where visible assistant report bodies live, including DR/Pro final reports (M2 handoff). `("assistant", "code")` extracts `message.content.text` but classifies it as hidden internal unless M5 finds a UI-visible counterexample; it is retained in raw and may contribute to hidden summaries. `("assistant", "thoughts")` extracts `message.content.thoughts` only for hidden summary counts and never emits it into the linear transcript. `("assistant", "reasoning_recap")`, `("assistant", "model_editable_context")`, `("tool", *)`, and `("system", *)` are hidden in the linear transcript; retain their existence, role, content type, author name, status, and attachment refs in summaries but not hidden text bodies unless an explicit debug/export mode is later approved (M2 handoff).

Visible turn JSONL fields handed to the store match the rewrite spec and add source/fidelity fields needed by this lens:

```json
{
  "conversation_id": "string",
  "message_id": "string",
  "parent_id": "string|null",
  "turn_index": "integer",
  "role": "user|assistant",
  "content_markdown": "string",
  "model": {"slug": "string|null", "display": "string|null"},
  "active_tools": ["string"],
  "kind": "normal|deep_research|image|unknown",
  "created_at": "number|string|null",
  "attachments": ["AttachmentRef"],
  "citations": ["CitationRef"],
  "status": "complete|partial|error",
  "partial": "boolean",
  "capture_source": "backend_api|copy_button|katex_annotation|dom_text",
  "fidelity": "canonical|ui_copy|math_annotation_reconstructed|lossy_dom_text"
}
```

DR/Pro handling: there is no `content_type == "deep_research"`; a DR/Pro turn is a `turn_exchange_id` group with one user message, many hidden assistant/tool nodes, and one visible final `assistant:text` report whose body is `message.content.parts[0]` in observed samples (M2 handoff). The linearizer should group hidden nodes by `turn_exchange_id`, set `kind="deep_research"` when the group has DR/pro/search metadata or substantial hidden tool/reasoning activity, and attach citations/search metadata from the visible assistant message's `message.metadata.content_references`, `message.metadata.citations`, `message.metadata.search_result_groups`, and `message.metadata.search_queries`. Citation entries preserve offsets `start_ix`, `end_ix`, `citation_format_type`, and nested `metadata`; web citations are not downloaded (M2 handoff; REWRITE-SPEC §8).

Attachment refs cover all M2 shapes: user-uploaded `message.metadata.attachments[]` with `id`, `size`, `name`, `file_token_size`, `source`, `is_big_paste`; file citations in `message.metadata.content_references[]` where `type == "file"` with keys including `id`, `name`, `source`, `snippet`, `cloud_doc_url`, `library_file_id`, `library_artifact_type`, `page_range_start`, `page_range_end`, `input_pointer`, `fff_metadata`, and `connector_id`; generated/image assets in tool `tether_browsing_display` `message.content.assets[]` with `content_type`, `asset_pointer`, `size_bytes`, `width`, `height`, `fovea`, `metadata`; and code-exec outputs in tool `execution_output` `message.metadata.aggregate_result` with `code`, `messages`, `jupyter_messages`, `final_expression_output`, `run_id`, `status`, timing, and exception fields (M2 handoff). Downloading bytes is a later lazy `fetch` step, not part of capture canonicalization.

## 5. Fail-closed fallback chain for capture fidelity

Fallback triggers are explicit: auth headers unobtainable or missing required names; app request not observed after fresh tool-owned navigation plus one reload; login/Cloudflare challenge (`HumanActionNeeded`, no automation); backend fetch `401`, `403`, or `404`; content type not JSON; JSON parse failure; top-level shape missing `conversation_id`, `mapping`, or a compatible `current_node`; conversation id mismatch; visible assistant `content.parts` shape not a list of strings; or any unknown backend status that would make math/markdown ambiguous (M2 handoff; M3 common constraints §4). These failures must be loud: return `CaptureResult(source != "backend_api", fidelity != "canonical", partial=True as appropriate)` and/or raise `CaptureFidelityDegraded`; never silently emit DOM text as canonical markdown.

Fallback chain: (1) primary backend-api canonical markdown; (2) per-turn copy button; (3) clipboard raw markdown, only with explicit attended permission/user gesture because M2 saw clipboard permission state `prompt`; (4) KaTeX `<annotation encoding="application/x-tex">` reconstruction for math; (5) DOM `textContent` last resort, known lossy (M2 handoff; REWRITE-SPEC §5). Selector strings used by the fallback live in `selectors/real.json` and must fail closed: `message_turn = "[data-message-id][data-message-author-role]"`, `assistant_turn = "[data-message-author-role=\"assistant\"][data-message-id]"`, `user_turn = "[data-message-author-role=\"user\"][data-message-id]"`, and `copy_button = "button[data-testid=\"copy-turn-action-button\"]"` (M2 handoff). The code must hover the specific assistant turn before looking for the copy button because M2 observed the button after hover.

Copy-button fallback is attended and side-effectful because it can touch the operator clipboard; it is not an unattended fallback. Proposed signature: `async def capture_turn_via_copy(page: Page, turn_message_id: str, *, require_operator_clipboard_grant: bool) -> FallbackTurn`. If clipboard permission is not already explicitly granted for the tool-owned page, raise `HumanActionNeeded(reason="clipboard_permission")` rather than triggering a permission prompt or reading arbitrary clipboard contents. If copy succeeds and `navigator.clipboard.readText()` returns text after the user-approved gesture, set `fidelity="ui_copy"`; this is the best fallback ground truth for markdown/math.

KaTeX fallback reconstructs only math spans from `annotation[encoding="application/x-tex"]` under the target assistant turn, combined with surrounding DOM text in document order. It must set `fidelity="math_annotation_reconstructed"`, `partial=True`, and include `loss_notes=["surrounding_markdown_from_dom", "math_delimiters_reconstructed"]` because markdown structure and delimiters can be ambiguous. DOM `textContent` fallback sets `fidelity="lossy_dom_text"`, `partial=True`, and should normally raise unless the caller explicitly asked to salvage partial output on timeout/error.

Fidelity acceptance is falsifiable in M5/M6: for a sample containing a DR turn and a heavy-math turn, compare backend/copy/fallback output against the web-UI copy output and require `\widehat`, `\ne` or `\neq`, and `\frac{}{}` to round-trip without ambiguous corruption; backend JSON already contained `\widehat`, `\frac`, `\ne`/`\neq`, `\(`, `\[`, and markdown table pipes in M2, but no full copy-output comparison was performed, so this remains a live acceptance check (M2 handoff; REWRITE-SPEC §5/§18).

## 6. Completion detection with no hidden ceiling

Public completion entry point in `completion.py`:

```python
async def wait_for_completion(
    session: Session,
    page: Page,
    conv: ConversationAddress,
    baseline: TurnBaseline,
    *,
    auth: AuthHeaderBundle | None = None,
    timeout: float | None = 300.0,          # no-activity window, not total cap
    max_total_wait: float | None = None,    # default unbounded
    poll_interval_s: float = 5.0,
    stable_window_s: float = 8.0,
) -> CompletionResult:
    ...
```

`TurnBaseline` is produced by the send cluster before submitting: `latest_user_message_id: str | None`, `user_turn_count: int`, `latest_assistant_message_id: str | None`, `assistant_turn_count: int`, `conversation_update_time: float | None`, and optionally the new submitted user `message_id` after send verification. Completion must never return an assistant turn whose `message_id` equals `baseline.latest_assistant_message_id`; it must find a new assistant on the current branch after the verified new user turn (REWRITE-SPEC §6/§7; gotcha #2/#3). If the send cluster cannot verify a new user turn, it raises `PromptNotSubmittedError` before completion is called.

Primary backend completion loop: acquire or reuse `AuthHeaderBundle`, then poll the authenticated conversation endpoint with the same in-page fetch mechanism. Each poll parses progress signals from top-level `async_status`, top-level `update_time/current_node`, node `status`, message metadata `async_source`, `is_complete`, `is_finalizing`, and `pro_progress`, and the new assistant visible text length/hash (M2 handoff). The exact status value vocabulary is live-site data to catalog in M5; until then the conservative rule is: incomplete if any relevant current-branch/new-turn signal is active/in-progress/finalizing or `metadata.is_complete is False`; complete only when a new visible assistant `assistant:text` exists after baseline, its text is non-empty or an explicitly empty completed answer is signaled, no relevant node is active, `is_finalizing` is not true, and top-level async state is absent or known complete. Unknown active-looking values keep polling; unknown impossible shapes raise `CompletionStateUnknown` and trigger DOM fallback/salvage rather than declaring success.

No hidden ceiling: `timeout` is a no-activity window and resets whenever any authoritative progress changes, including `update_time`, `current_node`, new node id, new assistant text length/hash, `async_status`, node `status`, `pro_progress`, or `is_finalizing` transitions (REWRITE-SPEC §7; M3 common constraints §4). `max_total_wait` defaults to `None` and only applies if the caller explicitly opts in. Long Pro/DR turns that show periodic progress can run for minutes or longer and must not be killed by a fixed 600s cap. If the no-activity window expires, return/raise `CompletionNoActivityTimeout` with `partial=True` after salvaging any visible new assistant text and current backend partial if available.

`GET /backend-api/conversation/<id>/stream_status` is a hypothesis from M2 and must not be relied on until M5 verifies it. Design hook: `async def poll_stream_status_if_verified(...) -> StreamStatus | None`; if M5 proves it exists and has a smaller authoritative payload, use it to reduce repeated 17 MB polls, but keep conversation endpoint polling as the primary proven path until then (M2 handoff).

DOM consensus fallback is the controller.mjs behavior ported into selectors and gated on baseline. Use selectors `assistant_turn = "[data-message-author-role=\"assistant\"][data-message-id]"`, `stop_button = "button[data-testid=\"stop-button\"], #composer-submit-button[aria-label*=\"Stop\" i]"`, and `composer = "#prompt-textarea"` from M2. Loop state tracks `saw_streaming = stop button visible or new assistant text/id changed`, `stop_absent_since`, `text_stable_since`, `latest_new_assistant_id`, `latest_new_assistant_text_len`, and `latest_new_assistant_text_hash`. DOM fallback declares complete only when a new assistant id different from baseline exists, the stop button has been absent for `stable_window_s`, the new assistant text hash/length has been stable for `stable_window_s`, and `(saw_streaming or non_empty_body)` is true. DOM text is a progress/completion signal, not canonical output; after DOM consensus, run backend capture again for canonical markdown, and if backend still fails use the fail-closed fallback chain with degraded fidelity.

On timeout/error, salvage is mandatory (REWRITE-SPEC §8; M3 common constraints §4). Salvage order: latest backend partial `assistant:text` for the new turn if available; else copy-button fallback if attended permission exists; else DOM textContent of the new assistant turn. Store an assistant record with `status="partial"`, `partial=true`, `capture_source` set to the salvage source, and `fidelity` set honestly. The eager user record and conversation ref are written by send at or just before submit, so a failed/truncated completion remains resumable.

## Cross-cluster interfaces & dependencies

Exposes to lens 2 / linearizer: `iter_current_branch_records(raw_path: Path) -> Iterator[LinearizedRecord]`, `classify_and_extract(node_id, node)`, visible-vs-hidden classification, `HiddenSummary` grouped by `turn_exchange_id`, attachment refs for all M2 shapes, and citation/search metadata fields `content_references`, `citations`, `search_result_groups`, and `search_queries`. Lens 2 should not re-fetch or reinterpret auth; it consumes raw JSON plus normalized records.

Exposes to store: `CaptureResult` and per-turn JSONL records with `conversation_id`, `message_id`, `parent_id`, `turn_index`, `role`, `content_markdown`, `model`, `active_tools`, `kind`, `created_at`, `attachments`, `citations`, `status`, `partial`, `capture_source`, and `fidelity`. Store owns atomic `raw-mapping.json` placement, append/upsert semantics keyed by `message_id`, eager user-turn write before send, and partial-salvage updates (REWRITE-SPEC §8).

Needed from identity/addressing: parse URL or bare id into `ConversationAddress(conversation_id, project_id, web_url, backend_url)`, supporting both `/c/<id>` and `/g/g-p-<projid>/c/<chatid>`; project send/create behavior is near-term but not M2-verified (REWRITE-SPEC §9; M2 project notes).

Needed from session/tab pool/rate cluster: a tool-owned `PageLease` created by the session without iterating `context.pages`, CDP preflight enforcement, detach-not-quit lifecycle, modest shared concurrency around three tabs, and read concurrency policy. Capture reads may run in parallel, but send rate remains governed by the single persistent `Session` owner (M3 common constraints §2; REWRITE-SPEC §10).

Needed from send/action cluster: `TurnBaseline` before send, verified new user turn id/count after send, `PromptNotSubmittedError` if no new user appears, and model/tool verification before submit. `wait_for_completion` is invoked only after send verification and must require a new assistant turn newer than the baseline (REWRITE-SPEC §6/§7).

Needed from selectors/menu cluster: fail-closed `selectors/real.json` containing M2-observed selectors for `composer`, `message_turn`, `user_turn`, `assistant_turn`, `copy_button`, `stop_button`, `tools_button`, `send_button_unverified_no_input`, and model picker heuristic. Fallback and DOM completion must not invent broad selectors outside this map unless M5 updates it with evidence.

Needed from safety/error modules: `allowlist.py` for chatgpt.com/openai/auth/oaiusercontent domains, sanitized error taxonomy, no Playwright-launched browsers, no stealth/anti-detection, login/Cloudflare `HUMAN-ACTION-NEEDED`, and no persistence/logging of Authorization/OAI header values (M3 common constraints §2; team charter).

## Open questions / assumptions

M5 must verify exact `async_status`, node `status`, `metadata.is_complete`, `metadata.is_finalizing`, and `metadata.pro_progress` value vocabularies; this design intentionally treats unknown values conservatively rather than guessing completion.

M5 must verify whether `/backend-api/conversation/<id>/stream_status` exists, what auth headers it needs, and whether it can reduce repeated full conversation polls; until verified, it is only a hook.

M5 must measure real peak memory for a 17.1 MB/~5k-node capture with streaming download plus whole-file parse, using process RSS/tracemalloc; the provisional tens-to-low-hundreds-of-MB estimate is not an acceptance fact.

Assumption: `request.all_headers()` or CDP `Network.requestWillBeSentExtraInfo` exposes the web-app `authorization` and OAI headers for the tool-owned page's own request; if both omit them, option A needs a new attended probe and option B still requires explicit operator approval.

Assumption: `"".join(message.content.parts)` preserves canonical markdown better than inserting separators; M5 copy-output comparison should confirm this for multi-part messages and adjust if the live shape proves otherwise.

Project URLs are parsed and metadata is preserved, but M2 did not probe `/g/g-p-<projid>/c/<chatid>` behavior; M5 must verify project capture/send/create before claiming support beyond addressing/scrape assumptions.

Clipboard/copy fallback requires explicit attended permission and may overwrite/read clipboard; M2 saw permission state `prompt`, so unattended fallback must fail closed rather than depend on clipboard access.

It is unknown whether auth/OAI headers remain valid throughout very long Pro/DR runs; if a completion poll gets auth failure mid-run, reacquire only if it can be done on the tool-owned page without disrupting generation, otherwise fall back to DOM consensus and capture canonically after completion.
