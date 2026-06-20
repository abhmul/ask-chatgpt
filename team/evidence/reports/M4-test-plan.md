# M4 offline-core falsifiable behavior checklist

## M4 acceptance-bar coverage map

- [x] 404-without-headers is not canonical capture: covered by C2 and D1.
- [x] No-op send raises `PromptNotSubmittedError`: covered by C6 and E6.
- [x] Completion requires a NEWER assistant id: covered by C7, E8, and E9.
- [x] No-activity-timeout resets on progress and salvages partial: covered by C7, E10, and E12.
- [x] Payload is written to stdout AND `--out`: covered by B12, F3, and F4.
- [x] Pending-stub supersession: covered by B8, B9, E4, and E7.
- [x] Capture linearizer classifies visible vs hidden: covered by C3, D4, D5, and D6.
- [x] Capture linearizer handles DR/Pro `turn_exchange_id` group: covered by C4 and D7.
- [x] Capture linearizer normalizes all 4 attachment shapes: covered by C5 and D8.
- [x] Citations remain separate from attachments: covered by A2, C5, and D9.

Priority key: P0 = M4 acceptance-bar or safety-critical; P1 = core public-contract behavior needed for a reliable offline core; P2 = bounded stub/edge behavior that must not grow into M5/M7 scope.

## (A) Data model + identity + allowlist + selectors-schema

### A1 [P0] `TurnRecord` is the single persisted and returned turn seam
- Behavior — Public construction, API returns, capture output, and JSONL serialization use one `TurnRecord` shape containing the M3 §2.1/§3.3 fields: `conversation_id`, `conversation_url`, `project_id`, `message_id`, `parent_id`, `turn_index`, `role`, `content_markdown`, `model`, `active_tools`, `kind`, `created_at`, `attachments`, `citations`, `status`, `partial`, `user_message_id`, `turn_exchange_id`, `client_send_id`, `supersedes_message_id`, `capture_source`, `fidelity`, and `error`.
- Why / gotcha — Prevents drift between capture, store, `Session.ask`, CLI output, and pending/salvage persistence; this is the seam M3 §2.1 makes authoritative.
- Falsifiability — A wrong implementation that returns an assistant wrapper without attachments/citations/status, persists only `role/content/message_id`, or has a separate `AskResult` field set that cannot round-trip to JSONL must fail.
- Required mock/fixture/clock/setup — One complete assistant turn fixture with model, tools, attachment, citation, exchange id, null error, and fixed timestamps; one public API path that returns the same logical record after load.

### A2 [P0] `ModelRef`, `AttachmentRef`, and `CitationRef` round-trip without unsafe side effects
- Behavior — `ModelRef` preserves nullable `slug` and `display`; `AttachmentRef` preserves `source_kind`, `source_ref`, `raw_path`, filename, mime, bytes, sha256, local path, download state, and sanitized metadata; `CitationRef` preserves title, URL, source, type, offsets, citation format, raw path, and sanitized metadata; citations are not stored as attachments and neither attachments nor citations are fetched during serialization, load, or render.
- Why / gotcha — M3 §3.7 separates byte/materializable attachments from web/source citations, and M4 must be offline with no invented attachment routes or citation URL fetches.
- Falsifiability — A wrong implementation that drops nullable model fields, serializes only attachment filenames, converts citations into attachment refs, opens `local_path`, downloads citation URLs, or computes fake hashes must fail.
- Required mock/fixture/clock/setup — Turns containing `model=None`, partially populated `ModelRef` values, all four attachment source kinds, two citations including a non-allowlisted URL, and fake fetch/open hooks that raise if called.

### A3 [P0] Turn status, partial, immutability, and local-id invariants are enforced at public boundaries
- Behavior — `partial` is false iff `status == "complete"`; pending/error/partial records have `partial=true`; public dataclasses declared frozen are not mutated in place; `message_id` beginning `local:` is valid only for a pending user stub with `turn_index=None`, `created_at=None`, `status="partial"`, `partial=true`, and a `client_send_id`.
- Why / gotcha — Append-only recovery and pending-stub supersession rely on records being immutable and honestly marked; local ids must never masquerade as backend turns.
- Falsifiability — A wrong implementation that persists `status="complete", partial=true`, accepts `local:abc` on a complete assistant record, mutates a loaded record in place, or gives a pending stub a numeric turn index must fail.
- Required mock/fixture/clock/setup — Valid complete/partial/error records, invalid status/partial combinations, valid pending stub, invalid local-id variants, and mutation attempts against `TurnRecord`, `ModelRef`, `AttachmentRef`, and `CitationRef`.

### A4 [P0] Error taxonomy exposes exact public codes, exit codes, retry metadata, and redacted details
- Behavior — Every public error inherits `AskChatGPTError` and carries stable `code`, `exit_code`, `retryable`, `retry_action`, message, and sanitized details, including the M3 §9 mappings for CDP 20, human-action-needed 21, domain 22, conversation 23, selector 24, prompt-not-submitted 30, model/tool reflection 31/32, backend auth/shape/fail-closed 40/41/42, completion timeout 50, max-total-wait 51, attachment 60/61, tab-pool 62, store 70, and internal 99.
- Why / gotcha — CLI/status automation depends on stable machine-readable failures, and M3 §9 forbids leaking headers, cookies, prompt bodies, raw response headers, or private tab data.
- Falsifiability — A wrong implementation that raises generic `ValueError`, uses code typos, swaps exit codes, marks domain errors blindly retryable, or includes `Authorization`, cookie, OAI, prompt, or response canaries in `str`, `repr`, details, stderr, or JSON must fail.
- Required mock/fixture/clock/setup — Table of all subclasses instantiated with canary details and causes; no channel required, plus one CLI formatting path in section F.

### A5 [P0] Conversation identity parsing is stateless, canonical, and safe for both required URL shapes
- Behavior — `parse_conversation_address` accepts bare conversation ids, `https://chatgpt.com/c/<id>`, and `https://chatgpt.com/g/g-p-<project_id>/c/<chat_id>` with query/fragment ignored for ids; `conversation_url(ref)` round-trips the project URL shape when `project_id` is known; `backend_conversation_url(id)` uses only the chat id; malformed, foreign-host, empty, and traversal-like addresses fail closed.
- Why / gotcha — Lead decisions put both plain and project URL identity parsing in M4, while backend/store keys remain the conversation id per M3 §2.8/§3.1.
- Falsifiability — A wrong implementation that requires `index.json` for bare ids, includes `?model=...` in the id, treats the project id as the conversation id, canonicalizes known project chats to non-project `/c/<id>`, accepts `chatgpt.com.evil.example`, or accepts `/c/../../x` must fail.
- Required mock/fixture/clock/setup — Empty temp data dir; bare UUID-like id; plain URL with trailing slash/query/fragment; project chat URL; project root URL for `parse_project_address`; foreign and malformed URL table.

### A6 [P1] Alias/session resolution is layered after stateless parsing and unknown aliases fail predictably
- Behavior — `resolve_conv_or_alias` returns a passed `ConversationRef` unchanged, resolves bare ids and URLs without relying on index state, consults `index.json` only for non-address aliases/sessions, and raises `ConversationNotFoundError` for unknown non-address aliases.
- Why / gotcha — Aliases are convenience cache, not identity authority; silent alias creation would route prompts/history to the wrong conversation.
- Falsifiability — A wrong implementation that lets an alias named like a URL override the URL, cannot resolve a URL when `index.json` is corrupt, or fabricates `ConversationRef(conversation_id="missing")` for an unknown alias must fail.
- Required mock/fixture/clock/setup — Index with aliases and sessions, empty index, corrupt index text, one existing transcript directory, and a missing alias lookup.

### A7 [P0] URL allowlist accepts exact documented suffixes, rejects suffix confusion and unsafe schemes, and redacts safely
- Behavior — Default allowlist accepts apex and subdomains for `chatgpt.com`, `openai.com`, `oaiusercontent.com`, and `oaistatic.com`; rejects unrelated or suffix-confusion hosts; rejects empty, relative, `file:`, `javascript:`, `data:`, and non-http(s) targets; `require_allowed_url` raises `DomainNotAllowedError`; `sanitize_for_log` retains useful host context while redacting credentials, query strings, fragments, bearer-looking tokens, and cookies.
- Why / gotcha — Allowlist is the navigation/fetch safety boundary from M3 §2.11 and must fail closed before any channel side effect.
- Falsifiability — A wrong implementation using substring matching accepts `chatgpt.com.evil.example`; one accepting `javascript:https://chatgpt.com` or leaking `?access_token=secret` in an error must fail.
- Required mock/fixture/clock/setup — URL table for all allowed apex/subdomain cases, malicious host table, unsafe-scheme table, and rejected URL containing userinfo/query/fragment canaries.

### A8 [P0] Selector-map schema validation is strict for required M2/M3 keys
- Behavior — Loading the packaged selector map in strict mode requires non-empty string values for `composer`, `tools_button`, `message_turn`, `user_turn`, `assistant_turn`, `copy_button`, `stop_button`, `send_button_unverified_no_input`, `radix_portal`, and `model_picker_trigger_candidates`; missing or invalid required keys raise `SelectorNotFoundError`/`SELECTOR_NOT_FOUND`.
- Why / gotcha — M4 step 1 requires selector schema validation, including M2 additions for Radix portal and model-picker candidates, so selector drift fails before browser actions.
- Falsifiability — A wrong implementation that validates only `composer`, accepts whitespace/null/list values, fills missing keys with `""`, or ships a pre-M2 selector file missing `radix_portal` must fail.
- Required mock/fixture/clock/setup — Packaged `selectors/real.json`; table-generated selector maps omitting one required key at a time; representative maps with null, arrays, booleans, and whitespace strings.

### A9 [P1] Model-picker selector remains a candidate query, not a trusted single selector
- Behavior — The selector schema exposes `model_picker_trigger_candidates` exactly as the candidate-query key and does not rename it to a final `model_picker_trigger`; extra selector keys may be preserved/ignored but cannot compensate for missing exact required names.
- Why / gotcha — M2 found no stable model-picker test id/aria label; M3 §2.10/§6 requires enumeration and visible-label verification later, not trusting one selector.
- Falsifiability — A wrong implementation that drops the candidates key, accepts typo `model_picker_trigger_candidate`, or exposes only a trusted single `model_picker_trigger` must fail.
- Required mock/fixture/clock/setup — Packaged selector map plus a typo-key fixture and inspection of the public selector loader/type.

## (B) `store.py`

### B1 [P0] Data-dir resolution and conversation layout are exact and conversation-id keyed
- Behavior — Explicit `Store(data_dir=...)`/CLI `--data-dir` wins over `ASK_CHATGPT_DATA_DIR`, which wins over `~/.local/state/ask-chatgpt/`; `ensure_conversation(ref)` creates `<data-dir>/conversations/<conversation-id>/transcript.jsonl`, `raw-mapping.json` parent, `attachments/`, and `.gitignore` containing `attachments/`, without deleting existing files; project conversations are still keyed by chat id, not project id or alias.
- Why / gotcha — M3 §3.1 fixes the data layout and backend key; isolated temp stores are required for offline TDD.
- Falsifiability — A wrong implementation that always uses the env var, stores project chats under `conversations/<projectid>/`, writes files directly under the data dir, omits `.gitignore`, or overwrites a sentinel transcript must fail.
- Required mock/fixture/clock/setup — Temp explicit dir, env var dir, env-empty home/suffix case, preexisting sentinel file, plain ref, project ref, and alias pointing to project ref.

### B2 [P1] `index.json` patching preserves state and never invents backend timestamps
- Behavior — `put_conversation_ref` creates/patches `index.json` with `schema_version: 1`, `aliases`, `sessions`, and `conversations`; updating one conversation preserves unrelated aliases/sessions/refs; stored `last_updated` comes from `ConversationRef.updated_at` or remains null/absent when unavailable, never from agent wall clock.
- Why / gotcha — M3 §3.2 treats the index as rebuildable convenience metadata, not a source of invented history.
- Falsifiability — A wrong implementation that rewrites the index to only the latest conversation, drops aliases, or sets `last_updated=datetime.now()` under a frozen-clock/sentinel assertion must fail.
- Required mock/fixture/clock/setup — Preloaded index with two conversations plus alias/session; refs with `updated_at=None` and a fixed aware datetime; fake/frozen wall clock if available.

### B3 [P0] JSONL append and round-trip are stable, complete, and immutable at load
- Behavior — `upsert_turn` appends exactly one newline-terminated compact UTF-8 JSON object per record with all field names including null values; datetimes serialize as RFC3339 and load semantically equal; tuple/list fields serialize as arrays and load into public immutable tuple/dataclass shapes.
- Why / gotcha — Append-only crash recovery and schema stability depend on one complete object per line and predictable loading per M3 §3.3/§3.4.
- Falsifiability — A wrong implementation that pretty-prints multi-line JSON, omits null fields, rewrites instead of appending, writes `repr(datetime)`, epoch floats, comma-separated tools, or raw dict attachments must fail.
- Required mock/fixture/clock/setup — Temp store; complete turn with null optional fields, fixed UTC timestamp, multiple tools, attachments, and citations; direct file inspection and loaded object inspection.

### B4 [P0] Transcript reads implement last-writer-wins, pending visibility, supersession hiding, and stable ordering
- Behavior — `load_transcript(..., include_pending=False)` groups valid records by `message_id`, keeps the last record for each id, hides all local pending stubs with `message_id` starting `local:` and `turn_index is null` whether superseded or not, shows canonical superseding records, and sorts by `(turn_index is null, turn_index, created_at or "", message_id)`; `include_pending=True` surfaces pending stubs without promoting them.
- Why / gotcha — This implements the accepted pending-stub design and idempotent re-scrape behavior from M3 §3.3 and §3.4.
- Falsifiability — A wrong implementation that keeps first duplicate, shows unsuperseded local stubs in default history, drops the canonical superseding user, physically deletes the stub, converts pending stubs into indexed turns, or preserves append order after replacements must fail.
- Required mock/fixture/clock/setup — Transcript with out-of-order turns, a partial assistant followed by complete replacement with same id, unsuperseded local stub, superseded stub plus canonical user, and loads with both `include_pending` values.

### B5 [P1] Readers tolerate only one torn trailing JSONL line and fail on real corruption
- Behavior — A transcript ending with one invalid partial JSON line loads prior valid records with an observable warning/diagnostic; invalid JSON in the middle or more than one invalid trailing line raises `StoreError` or the documented store read error.
- Why / gotcha — M3 §3.3/§3.4 permits crash recovery from a torn append without silently masking corruption.
- Falsifiability — A wrong implementation that crashes on one torn final line, silently ignores a corrupt middle line, or ignores two trailing corrupt lines must fail.
- Required mock/fixture/clock/setup — Hand-written JSONL files for one trailing tear, middle corrupt line, and two trailing corrupt lines; selected warnings/logging capture once the warning interface is chosen.

### B6 [P1] Append/replace operations preserve old durable data under failure and concurrent access
- Behavior — Appends flush/fsync complete lines under a per-conversation lock so prior lines remain readable after a simulated append failure and concurrent store instances never byte-interleave JSON objects.
- Why / gotcha — M3 §3.4 makes transcript loss one of the core gotchas and calls for per-conversation advisory locking.
- Falsifiability — A wrong implementation that rewrites the whole file and leaves it empty/half-written on failure, or allows `{"a"...{"b"...}` byte interleaving, must fail.
- Required mock/fixture/clock/setup — Existing transcript with one record, failure injection in the write/flush path for the next append, and either a controllable fake lock or two parallel store instances appending small records.

### B7 [P0] Raw mapping and index replacement are atomic, validated, and header-free
- Behavior — `write_raw_mapping_atomic(conversation_id, raw_tmp)` parses/validates candidate raw JSON before `os.replace`; valid input atomically replaces the old raw file, invalid input leaves the old file intact; raw mapping persistence contains backend JSON only and rejects/strips accidental request-header wrappers; index replacement also leaves the old complete index readable if temp write/rename fails.
- Why / gotcha — M3 §3.4 and §4.2 require raw artifacts to be old-complete or new-complete and never persist auth/OAI headers.
- Falsifiability — A wrong implementation that renames invalid JSON over the old raw file, writes `authorization`, `cookie`, or `oai-device-id` keys from a wrapper into `raw-mapping.json`, or truncates `index.json` to `{"schema` on failure must fail.
- Required mock/fixture/clock/setup — Existing raw mapping and index; valid tmp with top-level `mapping`/`current_node`; invalid tmp; candidate with obvious header wrapper/sensitive keys; failure injection during index temp write/rename.

### B8 [P0] `begin_send` durably creates a unique hidden pending user stub before risky UI work
- Behavior — `begin_send(ref, prompt, model, active_tools)` persists the conversation/index entry and appends a unique `client_send_id` user stub with `message_id="local:<client_send_id>"`, prompt text, requested model/tools, `turn_index=None`, `created_at=None`, `status="partial"`, and `partial=true`.
- Why / gotcha — Lead decision accepts pending eager-write stubs so a crash or no-op send does not lose the prompt.
- Falsifiability — A wrong implementation that returns an in-memory stub only, reuses a constant id, omits the prompt, marks it complete, or fails to create the index/conversation before the stub must fail.
- Required mock/fixture/clock/setup — Temp store, fixed `ConversationRef`, two `begin_send` calls with different prompts/tools, immediate index/transcript inspection, and default vs pending transcript reads.

### B9 [P0] `commit_send` appends a canonical user record that supersedes but does not mutate/delete the pending stub
- Behavior — Committing a verified send appends a canonical user `TurnRecord` with the backend/DOM user id and `supersedes_message_id="local:<client_send_id>"`; default reads show one confirmed user prompt and direct JSONL inspection still shows the original pending line.
- Why / gotcha — M3 §2.1/§3.3 reconciles canonical backend ids with the lose-nothing local stub by append-only supersession, not a separate outbox.
- Falsifiability — A wrong implementation that edits the stub in place, deletes the stub line, leaves both records visible by default, never records the canonical id, or depends on an independent outbox file as the source of truth must fail.
- Required mock/fixture/clock/setup — Begin-send stub, canonical user fixture, direct JSONL line count/content inspection, default and `include_pending=True` loads, and artifact/layout check that no outbox is required.

### B10 [P0] `record_partial` persists honest redacted salvage records
- Behavior — Partial salvage appends an assistant record with supplied partial markdown, `status="partial"` or `"error"` as appropriate, `partial=true`, known `client_send_id`/user/new-assistant linkage when available, actual `capture_source`/`fidelity`, and redacted stable error details.
- Why / gotcha — M3 §5/§6 require timeout/error salvage without pretending partial output is complete or leaking secrets.
- Falsifiability — A wrong implementation that only logs salvage, marks it complete/canonical, omits linkage, lies about source, or stores raw exception repr with bearer/cookie/prompt canaries must fail.
- Required mock/fixture/clock/setup — Fake `CompletionTimeoutError` and backend/capture exceptions containing canaries, partial markdown, known client/user/assistant ids, temp store, and artifact redaction scan.

### B11 [P1] Markdown rendering is deterministic, visible-only, literal, and offline
- Behavior — `render_markdown(load_transcript(...))` renders only default-visible canonical records in stable order; pending local stubs, hidden/internal raw mapping text, and superseded records are absent; `content_markdown` bodies are preserved literally except deterministic role/turn separators; rendering is byte-identical for the same transcript and never fetches attachments/citations.
- Why / gotcha — M3 §3.3/§3.5 and the rewrite gotchas require faithful local history/export without browser or network access.
- Falsifiability — A wrong implementation that renders every JSONL line, leaks hidden raw text, strips code fences, corrupts `\widehat`, `\ne`, or `\frac{}{}`, adds `Rendered at <now>`, or downloads a citation/attachment must fail.
- Required mock/fixture/clock/setup — Transcript with canonical user/assistant turns, local stub, replacement record, raw mapping containing hidden sentinel text, math/table/code/Unicode content, pending attachment and citation URL, and fetch/open hooks that raise.

### B12 [P0] Payload helper writes stdout and `--out` independently with identical payload bytes
- Behavior — The public helper used by `ask`, `scrape`, `history`, and `export` emits the payload to stdout every time and additionally writes the same payload to `--out` when provided; if out-file writing fails, stdout still contains the payload; string and byte payloads are written exactly through atomic same-directory temp/rename.
- Why / gotcha — This directly fixes the v1 `--out` suppresses stdout gotcha and is an M4 step 2/6 acceptance point.
- Falsifiability — A wrong implementation that chooses stdout OR file, writes a summary to stdout and full payload to file, writes `str(bytes)` for bytes, normalizes newlines, truncates NUL bytes, or writes the out file first and returns before printing on file error must fail.
- Required mock/fixture/clock/setup — Stdout capture, temp out path, known Unicode markdown payload, byte payload with NUL, preexisting out file, and failure injection before rename.

### B13 [P1] Attachment cache paths are deterministic and confined
- Behavior — `attachment_path(conversation_id, ref)` returns a deterministic path under `conversations/<id>/attachments/` and sanitizes filenames/refs against absolute paths, duplicates, and traversal.
- Why / gotcha — M3 §3.4/§3.7 makes attachment bytes lazy and local-cache-only; path traversal would scatter or overwrite user files.
- Falsifiability — A wrong implementation that joins raw filename `../../secret`, returns an absolute path outside the conversation, or produces nondeterministic paths for the same ref must fail.
- Required mock/fixture/clock/setup — Attachment refs with normal, duplicate, absolute, traversal-like filenames and sha/source ids; temp data dir path assertions.

## (C) `MockChannel` fixtures

### C1 [P0] Mock channel is a deterministic offline `BrowserChannel` seam
- Behavior — `MockChannel` implements the protocol needed by M4 through channel-bound `TabLease` objects, records call order/counters, supports fake monotonic clock/sleeper injection for waits, raises on unknown browser/page attributes, and never imports Playwright, opens a browser, touches CDP, or performs network I/O.
- Why / gotcha — M4 is offline core only, and the channel seam is the only way send/completion/capture code should touch browser-like behavior.
- Falsifiability — A wrong implementation that imports Playwright at module import time, attempts `/json/version`, uses `context.pages`, performs a real fetch, or lets lower modules access browser internals must fail under the mock.
- Required mock/fixture/clock/setup — No CDP endpoint; Playwright-unavailable/default import guard if practical; `TabLease(tab_id, url, channel=mock)` exposing only protocol methods; call log and fake clock.

### C2 [P0] Backend header fixtures cover 404-without-headers and 200-with-required-headers
- Behavior — Mock backend fixtures include a 404 JSON `detail` response for accept-only/no-required-headers requests and a 200 JSON response only when the required header names are present: `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, and `x-openai-target-route`; header values are canaries that must never persist.
- Why / gotcha — M2 proved accept-only returned 404 while web-app auth/OAI headers returned 200; this is an explicit M4 acceptance point.
- Falsifiability — A wrong mock or implementation that treats any JSON body as valid, ignores the header requirement, logs header values, or marks 404 `detail` as an empty canonical transcript must fail.
- Required mock/fixture/clock/setup — Sidecars for status/content type/header-name presence, 404 body with no mapping/current_node, 200 body with matching `conversation_id`, valid `mapping`, valid `current_node`, and fake secret header values.

### C3 [P0] Raw mapping fixtures cover large current branches, side branches, hidden nodes, malformed trees, content parts, and math tokens
- Behavior — Mock raw fixtures include a deterministic ~5k-node parent chain ending at `current_node`, side branches not on the current branch, hidden current-branch internals, cycles, broken parent links, invalid `current_node`, visible `content.parts` cases, and backend markdown containing `\widehat`, `\ne`/`\neq`, `\frac{}{}`, markdown tables, code fences, whitespace, and Unicode.
- Why / gotcha — M3 §3.5 and M4 step 3 require testing the real mapping/tree shape and math fidelity at offline scale.
- Falsifiability — A parser that recurses until `RecursionError`, sorts mapping keys, emits side branches, accepts cycles, stringifies non-string parts, inserts separators, or corrupts math must fail against these fixtures.
- Required mock/fixture/clock/setup — Raw JSON body generator or static files with deliberately out-of-order mapping keys, sparse visible user/assistant text, many hidden nodes, malformed variants, and exact expected decoded markdown strings.

### C4 [P0] DR/Pro fixtures include positive and negative `turn_exchange_id` evidence groups
- Behavior — Mock fixtures include a clearly positive same-`turn_exchange_id` group with a visible user message, large hidden reasoning/tool/code group, citation/search metadata, generated/code assets, and final visible `assistant:text`; negative fixtures omit one major evidence element at a time and include a synthetic `content_type="deep_research"` without the evidence pattern.
- Why / gotcha — M3 §3.6 says DR/Pro is a grouped evidence pattern, not a single content type, and ambiguous scrape-only cases stay normal.
- Falsifiability — A classifier that labels any long/cited/tool-bearing answer as deep research, requires a nonexistent `deep_research` content type, or ignores hidden same-exchange refs must fail.
- Required mock/fixture/clock/setup — Positive group with 30+ hidden nodes; negatives for citations-only, hidden-tools-without-citations, no final visible assistant, mismatched exchange ids, and synthetic lone deep-research-like node.

### C5 [P0] Attachment and citation fixtures cover all required source shapes without byte/network fetches
- Behavior — Mock fixtures include `metadata.attachments[]` user uploads, `metadata.content_references[type=file]` file references, tool `content.assets[]` generated assets, tool `metadata.aggregate_result` code execution output, assistant `metadata.citations[]`, web/source `content_references`, and displayed `search_result_groups` with raw paths and sanitized metadata canaries.
- Why / gotcha — M4 acceptance requires all four attachment shapes and citations separate; M3 §3.7 forbids invented endpoints and citation downloads.
- Falsifiability — A normalizer that ignores hidden tool assets, treats all content references as citations, double-counts file refs, fetches fake URLs, sets fake `local_path`/`sha256`, or leaks header-like metadata values must fail.
- Required mock/fixture/clock/setup — One mixed conversation fixture with all attachment/citation shapes in visible and hidden same-exchange nodes, fake invalid URLs that raise if fetched, long snippets, and sensitive metadata canaries.

### C6 [P0] Send/UI fixtures cover selector drift, composer unmount/remount, no-op submit, prompt mismatch, and safe submit controls
- Behavior — Mock send scenarios include required-selector missing, composer absent-then-visible, composer never visible, fill ignored/truncated, disabled send button, global Enter misuse, existing generation requiring idle/reload, no-op submit with unchanged user turns, new wrong user turn, and successful new user turn.
- Why / gotcha — M3 §6 and M4 step 5 target silent no-op sends, composer staleness, and unsafe UI actions.
- Falsifiability — Send code that submits without composer verification, presses Enter globally, ignores disabled controls, accepts any new user turn, or proceeds to completion after no-op must fail.
- Required mock/fixture/clock/setup — Selector visibility sequences, composer text snapshots, focus state, enabled/disabled button states, stop-button/idle timeline, baseline user/assistant ids, completion sentinel that raises if called on failed send, and call log order checks.

### C7 [P0] Completion fixtures cover newer-assistant gating, active statuses, progress resets, long progress, cadence, and salvage
- Behavior — Mock completion timelines include old assistant stable text, new assistant empty then growing, active/finalizing/unknown-active statuses, each progress token changing independently, same-length text-hash changes, continuous progress beyond 600s, explicit total cap, no-progress timeout with partial text, backend shape error after partial, DOM stable-window fallback, and sparse backend-vs-cheap-DOM counters.
- Why / gotcha — M3 §5 requires a newer assistant id, no hidden 600s ceiling, no-activity timeout reset by progress, sparse backend checks, and salvage on timeout/error.
- Falsifiability — Completion code that accepts stale assistant text, treats unknown active statuses as complete, tracks only length, has a hard 600s cap, fetches full backend every DOM tick, or raises without persisted partial must fail.
- Required mock/fixture/clock/setup — Fake monotonic clock/sleeper; timelines for backend and DOM snapshots; counters for DOM polls, header acquisitions, lightweight backend checks, and full raw captures; partial/salvage sources with canaries.

### C8 [P1] Safety/redaction fixtures cover clipboard prompt, login/challenge, allowlist failure, and private-tab canaries
- Behavior — Mock fixtures include clipboard permission `prompt`, explicitly allowed offline copy text, login wall, Cloudflare/challenge, disallowed URLs before navigation/fetch, foreign/private page canaries, one-use header canaries, and status reports with unchecked selector `present=null`.
- Why / gotcha — M3 safety invariants and lead decision require fail-closed clipboard behavior, no private-tab enumeration, and redacted diagnostics.
- Falsifiability — Code that auto-reads clipboard, keeps sending through login wall, navigates before allowlist check, enumerates operator pages, reuses headers, or leaks private tab/header/prompt canaries must fail.
- Required mock/fixture/clock/setup — Mock methods raising on clipboard auto-read, page enumeration, foreign close, disallowed navigation/fetch, and reused header; status fixture with redacted `last_error`.

## (D) Capture parser/linearizer

### D1 [P0] 404 without required headers and other invalid backend responses fail closed before canonical transcript emission
- Behavior — A backend response fixture with HTTP 404 and no required auth/OAI headers enters the fallback/fail-closed path and does not emit an empty transcript or canonical backend records; non-2xx, non-JSON, JSON parse failure, conversation id mismatch, missing/non-object `mapping`, and absent/invalid `current_node` are likewise rejected before transcript emission.
- Why / gotcha — M2's accept-only 404 is an explicit M4 acceptance point, and M3 §4.2/§4.4 says ambiguous backend capture is worse than a loud stop.
- Falsifiability — A wrong parser that treats 404 `detail` as zero-turn success, partially parses malformed JSON, guesses a leaf, accepts a different conversation id, or labels fallback content `backend_api/canonical` must fail.
- Required mock/fixture/clock/setup — C2 404 fixture; malformed JSON, wrong id, no mapping, invalid current_node, and non-JSON content-type fixtures; optional fallback policy disabled to assert `CaptureFailedClosedError`/human-action-needed path.

### D2 [P0] Authorized 200 backend fixtures produce canonical complete records and promote exactly one validated raw artifact
- Behavior — A 200 JSON fixture with all required header names validates as backend input, preserves unknown top-level keys in `raw-mapping.json`, promotes the raw file only after shape validation, and emits records with `capture_source="backend_api"`, `fidelity="canonical"`, `status="complete"`, and `partial=false`.
- Why / gotcha — M3 §4.2/§4.3 define backend JSON as canonical only after safe header acquisition and shape validation.
- Falsifiability — A wrong implementation that rejects authorized 200s, drops unknown top-level keys from raw, maps unknown telemetry into transcript fields, leaves a malformed temp referenced by `Transcript.raw_mapping_path`, or marks backend records partial/lossy must fail.
- Required mock/fixture/clock/setup — C2 authorized 200 fixture with extra top-level keys (`safe_urls`, `blocked_urls`, `owner`, `future_key`), ordinary visible turns, old raw file, and invalid retry fixture proving old raw remains.

### D3 [P1] Backend header values are one-request inputs and never persist in capture artifacts or diagnostics
- Behavior — Header containers may expose required names through a redacted view, but values are consumed for one backend fetch/check and absent from `repr`, `str`, exceptions, `CaptureResult`, `Transcript`, `TurnRecord`, normalized metadata, raw mapping, JSONL, logs, and status.
- Why / gotcha — M3 §2.3/§4.1/§5 make non-persistence and non-logging of auth/OAI headers a safety invariant.
- Falsifiability — A wrong implementation whose dataclass repr includes `_headers`, writes a request-header wrapper to raw JSON, stores a header map on a result object, or includes `SECRET_AUTH_SENTINEL` in an error/status/log must fail.
- Required mock/fixture/clock/setup — Authorized fixture with unique canary values for every required header and forced failure after header acquisition; artifact/object/string redaction scan.

### D4 [P0] Current-branch linearization follows parent links iteratively, retains raw side branches, and fails on broken trees
- Behavior — Linearization follows `current_node` parent links to root, detects cycles/missing parents/invalid current_node, reverses the path for transcript order, emits only visible records from that selected branch, handles ~5k nodes without recursion-limit failure, and leaves side branches/hidden internals intact in raw.
- Why / gotcha — M3 §3.5 defines the backend mapping as a tree with `current_node` selecting the UI branch.
- Falsifiability — A wrong implementation that emits mapping insertion order, lexicographic id order, all tree nodes, side branches, infinite-loops on cycles, treats unknown parent as root, or prunes raw to visible nodes must fail.
- Required mock/fixture/clock/setup — C3 large/out-of-order fixture, side branch with tempting visible messages, cycle fixture, missing-parent fixture, invalid-current-node fixture, and raw artifact inspection.

### D5 [P1] Backend-derived record identity and timestamps come from raw backend shape, not agent guesses
- Behavior — Visible record `message_id` is backend `message.id` when present otherwise mapping node id; `parent_id` is the raw mapping parent id even when hidden; `turn_index` counts visible records only; `created_at` uses backend timestamp when available and remains null when missing rather than using agent wall clock.
- Why / gotcha — M3 §2.1/§3.5 allows visible parent ids to point to hidden nodes and rejects invented timestamps.
- Falsifiability — A wrong implementation that always uses node ids despite different message ids, rewrites parent to the previous visible turn, numbers hidden nodes into `turn_index`, or inserts `datetime.now()` for missing create time must fail.
- Required mock/fixture/clock/setup — Visible assistant whose raw parent is hidden, message ids differing from node ids, mixed present/missing `create_time`, and visible turns separated by hidden nodes under a frozen-clock/sentinel assertion.

### D6 [P0] Visible-vs-hidden classification and `content.parts` extraction are exact and math-preserving
- Behavior — Only `user:text` and `assistant:text` on the current branch emit transcript turns; `assistant:code`, `assistant:thoughts`, `assistant:reasoning_recap`, `assistant:model_editable_context`, all `tool:*`, `system:text`, and unknown non-visible classes do not emit transcript prose; visible `content.parts` must be a list of strings, one string uses exactly `parts[0]`, multiple strings concatenate in order with no inserted separator, non-string/missing/non-list parts fail closed, and decoded markdown/math is preserved exactly.
- Why / gotcha — M3 §3.5 is the tiebreaker: it chooses no invented separator and fail-closed non-string parts; this covers the explicit visible-vs-hidden acceptance point and math gotcha.
- Falsifiability — A wrong implementation that emits hidden code/thought/tool/system text, uses `content.text` instead of `parts`, trims whitespace, joins parts with blank lines/spaces, stringifies dict parts, accepts any node with `parts`, converts `\ne` to `≠`, double-escapes backslashes, or strips math delimiters must fail.
- Required mock/fixture/clock/setup — C3 fixture with visible user/assistant parts, all hidden observed classes with tempting text, unknown role/content types, multiple-string parts like `['alpha', '', 'beta', '\n', 'gamma']`, non-string parts, and exact math/table/code expected strings.

### D7 [P0] DR/Pro classification requires the full same-exchange evidence pattern and attaches hidden refs to the final report
- Behavior — In scrape-only capture, an assistant final report becomes `kind="deep_research"` with `active_tools` including `deep_research` only when the same `turn_exchange_id` contains the full M3 §3.6 evidence pattern: visible user message, large hidden reasoning/tool/code group, citation/search metadata, and visible final `assistant:text`; ambiguous cases remain `kind="normal"`; hidden same-exchange attachment/citation refs attach to the visible final assistant report without hidden prose.
- Why / gotcha — M2 observed DR/Pro as a turn-exchange group and no `content_type="deep_research"`; overclaiming DR is misleading.
- Falsifiability — A wrong implementation that classifies any long answer, any cited answer, any hidden-tool answer, or a lone synthetic deep-research content type as DR, or drops hidden same-exchange generated/code assets, must fail.
- Required mock/fixture/clock/setup — C4 positive and negative fixture matrix with final visible assistant, hidden tool/asset/citation metadata, mismatched exchange ids, and synthetic deep-research-like node.

### D8 [P0] All four attachment shapes normalize to `AttachmentRef` without byte fetching or invented routes
- Behavior — User `metadata.attachments[]` normalize to `source_kind="user_upload"`; `content_references[type=file]` normalize to `source_kind="file_reference"`; tool `content.assets[]` normalize to `source_kind="generated_asset"`; tool `metadata.aggregate_result` associated with a visible report normalizes to `source_kind="code_execution_output"` with `source_ref=run_id`, `filename="run_<run_id>_aggregate.json"`, and `mime="application/json"`; all preserve raw paths/sanitized metadata, do not pollute transcript markdown, do not fetch bytes, and do not invent local paths, hashes, or endpoints.
- Why / gotcha — This is an explicit M4 acceptance point from M3 §3.7 and the mission contract.
- Falsifiability — A wrong implementation that ignores user uploads, treats file refs as citations, drops hidden tool assets, emits code/Jupyter output as assistant prose, follows `cloud_doc_url`, fabricates `/backend-api/files/...`, sets `download_state="downloaded"`, or copies auth/OAI metadata into refs must fail.
- Required mock/fixture/clock/setup — C5 fixtures for all four shapes with raw paths, ids/pointers, sizes, dimensions, aggregate result, long snippets, fake invalid URLs, metadata canaries, and fetch/open hooks that raise.

### D9 [P0] Citations normalize to `CitationRef`, remain separate from attachments, and are never fetched
- Behavior — Assistant `metadata.citations[]`, web/source `content_references` such as `grouped_webpages`/`sources_footnote`, and displayed `search_result_groups` produce `CitationRef` values with title/URL/source/type/offsets/citation format/raw path/sanitized metadata; `content_references[type=file]` remain attachments; `search_queries` alone stay raw and are not promoted; citation URLs are never fetched.
- Why / gotcha — M3 §3.7 and the acceptance bar explicitly require citations separate from byte artifacts.
- Falsifiability — A wrong implementation that stores citation URLs as attachment `source_ref`, gives citations `download_state`/`local_path`, treats every search query as a citation, double-counts file refs as citation and attachment, drops offsets, or downloads citation URLs must fail.
- Required mock/fixture/clock/setup — C5 mixed assistant report with file reference, web citation, grouped webpage source, displayed and non-displayed search result groups, search query string, generated asset in same exchange, and URL fetch hooks that raise.

### D10 [P1] Capture fallback order and fidelity marking are honest and fail-closed by default
- Behavior — When backend validation fails, fallback attempts are ordered backend API → copy button → KaTeX annotation → DOM text; copy requires explicit offline fixture/permission and never reads the real clipboard by default; KaTeX and DOM salvage mark degraded fidelity and `partial=true`; no allowed fallback raises `HumanActionNeededError` or `CaptureFailedClosedError` rather than fabricating a complete transcript.
- Why / gotcha — M3 §4.4 plus lead decision make clipboard fail-closed by default and forbid silently emitting DOM text as canonical.
- Falsifiability — A wrong implementation that jumps directly to DOM, uses KaTeX before copy, auto-reads clipboard on permission prompt, marks DOM/KaTeX complete/canonical, continues to lower fidelity after copy succeeds, or returns an empty successful transcript must fail.
- Required mock/fixture/clock/setup — Invalid backend fixture plus distinguishable copy/KaTeX/DOM fixtures, negative clipboard-prompt/no-fixture case, allowed offline copy fixture, KaTeX HTML annotations in document order, DOM text with visibly degraded math, and policy toggles.

## (E) Send + completion

### E1 [P0] Send/completion lower modules operate only through `TabLease.channel`
- Behavior — `send.py` and `completion.py` accept a channel-bound `TabLease` and call only `BrowserChannel` protocol methods; they do not create sessions, connect CDP, enumerate pages, own a tab pool, own a rate limiter, or import Playwright.
- Why / gotcha — M3 §2.2/§2.9 define the channel seam as the offline-test boundary and own-tab safety line.
- Falsifiability — A wrong implementation that constructs `CdpChannel`, calls `context.pages`, touches browser APIs directly, or bypasses `MockChannel.query_turns` must fail when the mock exposes no such objects and expected protocol calls are absent.
- Required mock/fixture/clock/setup — Minimal `TabLease(tab_id, url, channel=mock)` with strict protocol-only mock raising on unknown attributes and recording calls.

### E2 [P1] Requested model/tool changes fail closed in M4 unless already a no-op
- Behavior — With no requested model/tools, send does not touch menus; with requested model/tool changes in M4, the stub/fail-closed menu path raises `ModelSelectionNotReflectedError` or `ToolSelectionNotReflectedError` before prompt submission unless reflected state is already verified, and no canonical user turn is committed.
- Why / gotcha — Full Radix menu selection is M7; M3 §6 requires no prompt be sent under unverified model/tool state.
- Falsifiability — A wrong implementation that silently ignores `--model`/`--tool` and sends anyway, clicks ambiguous menus and then sends, or commits a canonical user after reflection failure must fail.
- Required mock/fixture/clock/setup — Mock menu state with absent/ambiguous reflected labels, prompt submission counter, and temp store verifying no canonical user; if a pending stub exists due to implementation ordering, default reads must still hide it.

### E3 [P0] Send establishes an idle/reloaded baseline before any composer mutation and preserves assistant baseline
- Behavior — Before fill/submit, send waits for existing generation to be idle, performs the between-turn reload needed to clear SPA staleness, reads latest user id/count and latest assistant id/count from the current DOM, and passes the pre-send assistant baseline unchanged to completion.
- Why / gotcha — M3 §6 and gotcha #2 prevent stale assistant returns and no-op submissions caused by SPA staleness.
- Falsifiability — A wrong implementation that reads baseline after submit, tracks only user count, overwrites `latest_assistant_id` after the new user appears, or submits while `stop_visible=True` must fail.
- Required mock/fixture/clock/setup — Mock initial snapshot with `u1/a1`, active generation then idle, submit only succeeds after reload, call log asserting `query_turns` precedes fill/click, and completion fixture with attractive old assistant `a1`.

### E4 [P0] `Session.ask` eagerly persists the pending stub before risky UI submission and failures preserve it hidden
- Behavior — After baseline and before composer/submit can fail, `Session.ask` calls `Store.begin_send`; if composer never appears or submit no-ops, the transcript contains the pending local stub only when `include_pending=True` and default reads/history omit it.
- Why / gotcha — Lead decision and M3 §6 require lose-nothing prompt capture without presenting unsubmitted prompts as real history.
- Falsifiability — A wrong implementation that writes only after verified submit loses the prompt on composer failure; one that exposes `local:<client_send_id>` in default history or drops it entirely must fail.
- Required mock/fixture/clock/setup — Temp store; mock composer permanently absent and no-op submit cases; compare default and `include_pending=True` transcript loads after failure.

### E5 [P1] Composer handling verifies content and submits only through safe focused controls
- Behavior — `wait_for_composer` tolerates transient missing/unmounted composer until timeout; fill uses editor APIs and verifies normalized composer text before submit; submit clicks an enabled send control after input, or uses Enter fallback only while composer is focused; permanent absence raises `SelectorNotFoundError` and does not call completion.
- Why / gotcha — M3 §6 names composer unmount/staleness and blind Enter as send hazards.
- Falsifiability — A wrong implementation that fails on first transient absence, spins without fake-clock timeout, submits after ignored/truncated fill, presses Enter globally, clicks a disabled button and reports success, or starts completion without a composer must fail.
- Required mock/fixture/clock/setup — Composer absent/absent/visible sequence, composer-never-visible sequence, fake clock, fill ignored/truncated case, prompts with whitespace/newlines, enabled/disabled send controls, focus state, and completion sentinel.

### E6 [P0] Verified send requires a new user turn carrying the normalized prompt; no-op raises `PromptNotSubmittedError`
- Behavior — `verify_prompt_submitted` succeeds only when a user turn newer than baseline appears by different latest user id or increased user count and that turn text matches the normalized prompt; no new matching user within timeout raises `PromptNotSubmittedError`/`PROMPT_NOT_SUBMITTED` and completion is not called.
- Why / gotcha — This is the explicit no-op-send acceptance point and fixes v1 returning stale responses.
- Falsifiability — A wrong implementation that accepts an old turn with matching text, any new user turn with wrong text, a count-only/id-only signal, a stale DOM snapshot, or returns previous assistant `a-old` must fail.
- Required mock/fixture/clock/setup — Parameterized snapshots for new id+prompt success, increased count+prompt success, new id wrong text failure, old id/count matching prompt failure, unchanged no-op fixture with existing assistant, fake clock for `send_verify_timeout_s`, and completion mock raising if called on failure.

### E7 [P0] Successful ask commits canonical user supersession and returns the new assistant turn only
- Behavior — After verified submission, `Store.commit_send` appends the canonical user record superseding the local stub; completion/capture then persists and returns the captured assistant `TurnRecord` whose assistant id is newer than baseline and whose `user_message_id` links to the submitted user.
- Why / gotcha — M3 §6 public semantics are send → verify → wait → capture → persist → return assistant, with pending-stub supersession.
- Falsifiability — A wrong implementation that returns the submitted user, the pending stub, a `CompletionState`, pre-existing assistant `a-old`, or leaves both local and canonical user visible by default must fail.
- Required mock/fixture/clock/setup — Successful mock send with old assistant `a-old`, new user `u2`, new assistant `a2`, final backend capture containing distinct `a2` markdown, and transcript loads/default visibility checks.

### E8 [P0] Completion starts only after verified send and requires an assistant id newer than baseline
- Behavior — `wait_for_completion` is invoked only after `verify_prompt_submitted` returns `SubmittedTurn`; a completion state is never successful unless it contains an assistant id different from and newer than `baseline.latest_assistant_id`.
- Why / gotcha — M3 §2.5/§5 require newer-assistant gating and prevent no-op sends from returning stale assistant text.
- Falsifiability — A wrong implementation that always calls completion after clicking submit, treats old stable assistant `a1` as complete, or returns non-empty baseline text must fail.
- Required mock/fixture/clock/setup — No-op send fixture with completion sentinel; baseline `a1`; backend/DOM snapshots exposing stable complete-looking `a1`; fake clock to prove polling/timeout rather than success.

### E9 [P1] Completion success waits for conservative complete signals and baseline-gated DOM consensus
- Behavior — A new assistant id alone is insufficient while text is empty without explicit empty-complete signal or while any relevant `async_status`, node status, `async_source`, `is_complete=False`, `is_finalizing`, or `pro_progress` is active/in-progress/finalizing/unknown-active; DOM fallback requires a new assistant id, stop button absent for a stable window, text hash/length stable for that window, and `saw_streaming` or non-empty body.
- Why / gotcha — M3 §5 defers exact live vocabularies and chooses conservative offline defaults.
- Falsifiability — A wrong implementation that returns success on first new id, first token while finalizing, unknown active status, old stable DOM text, stop-visible DOM text, or before stable-window duration must fail.
- Required mock/fixture/clock/setup — Backend timelines with empty/new text/active/final states, unknown-active status cases, DOM snapshots old stable/new stop visible/new changing/new stable absent-stop, and fake clock.

### E10 [P0] No-activity timeout is reset by every progress token, text hash changes, and no hidden total ceiling exists by default
- Behavior — `activity_timeout_s` measures time since last progress, not wait start; progress resets include `update_time`, `current_node`, new node id, new assistant id, assistant text hash, assistant text length, `async_status`, node status, `pro_progress`, and `is_finalizing`; same-length different text counts; `max_total_wait_s=None` runs beyond 600s under progress; an explicit `max_total_wait_s` raises `MaxTotalWaitExceededError` when exceeded.
- Why / gotcha — This is the explicit no-activity-timeout acceptance point from M3 §5 and fixes long Pro/DR premature timeout.
- Falsifiability — A wrong implementation using `start + activity_timeout_s`, tracking only text length, ignoring `pro_progress`/`update_time`, timing out at a hard-coded 600s, or ignoring an explicit total cap must fail.
- Required mock/fixture/clock/setup — Fake clock; parameterized timelines where exactly one listed token changes per activity window; same-length text change `abc`→`abd`; continuous progress to 1200s then completion; explicit small total cap with continuing progress.

### E11 [P1] Completion backend cadence is sparse and uses fresh one-use headers without full fetch per progress tick
- Behavior — Cheap DOM progress polls run at `progress_poll_interval_s`; backend checks run at explicit `backend_check_interval_s` or channel/mock default when `None`, never collapsing to DOM cadence; each backend check acquires a fresh one-use header bundle and discards it; full backend conversation capture is reserved for final capture and explicit salvage snapshots, not every progress tick.
- Why / gotcha — M3 §5/§4.2 forbids full heavy backend fetches every short progress tick and makes header lifetime one-request only.
- Falsifiability — A wrong implementation that performs backend checks every 2s when backend interval is 30s, reuses headers, stores headers across iterations, or full-fetches a 5k-node mapping every DOM poll must fail.
- Required mock/fixture/clock/setup — Fake clock with `progress_poll_interval_s=2` and `backend_check_interval_s=30`, mock counters for DOM polls/header acquisitions/lightweight backend/full raw fetches, unique one-use canary headers rejected on reuse, and large mapping fixture.

### E12 [P0] Timeout and capture errors salvage the best available partial honestly and redacted
- Behavior — On no-activity timeout or non-timeout backend/capture errors after a partial exists, orchestration persists a partial assistant record; salvage order is latest backend partial for the new turn, then copy/clipboard output only with explicit attended permission, then DOM text of the new assistant; default clipboard prompt fails closed as `HumanActionNeededError`; persisted partial records have honest status/source/fidelity and redacted error details.
- Why / gotcha — M3 §5/§6 require lose-nothing partial salvage and lead decision forbids auto-reading clipboard.
- Falsifiability — A wrong implementation that raises without store partial, returns partial as complete success, prefers DOM over backend partial, reads clipboard by default, marks clipboard prompt success, salvages old assistant text, or writes header/prompt canaries to JSONL must fail.
- Required mock/fixture/clock/setup — Fake-clock no-progress timeline with new assistant partial, backend/capture shape error after partial, backend partial vs DOM disagreement, clipboard prompt case, explicitly allowed copy case, DOM-only case, temp store, and canary redaction scan.

## (F) CLI + session

### F1 [P0] Offline mock/session paths do not require real CDP/browser and history/export are store-only
- Behavior — Importing CLI/session and running M4 tests with `channel="mock"` never imports Playwright, preflights CDP, opens a browser, or performs network; `Session.history`/CLI `history` and `export` resolve local ids/URLs/aliases, load the store, render markdown, and never attach/preflight/probe browser.
- Why / gotcha — M4 is offline-only, and M3 §2.2/§8 mark history/export browser column as no.
- Falsifiability — A wrong implementation that calls `CdpChannel.preflight`, `/json/version`, `attach`, network fetch, or a shared CLI setup path before local history/export must fail.
- Required mock/fixture/clock/setup — Local temp store transcript for bare id/plain URL/project URL/alias; fake channel/CDP/browser methods that raise if touched; Playwright-unavailable import guard if practical.

### F2 [P1] CLI verbs dispatch to the documented `Session` methods and forward public flags faithfully
- Behavior — `ask`, `create`, `scrape`, `history`, `export`, `fetch`, and `status` call respectively `Session.ask`, `Session.create`, `Session.scrape`, `Session.history`, `Session.history`, `Session.fetch`, and `Session.status`; `ask` forwards optional conversation, prompt, `--model`, repeated `--tool`, repeated `--attach`, `--timeout`, `--max-total-wait` with omitted value as `None`, `--out`, and `--data-dir`; other verbs forward documented `--project`, `--json`, `--with-attachments`, `--no-browser-probe`, and output/data-dir flags as applicable.
- Why / gotcha — M3 §8 makes the CLI a thin parser/output layer over `Session`, with no business logic or hidden defaults such as a 600s max total.
- Falsifiability — A wrong parser that swaps conv/prompt, drops repeated tools/attachments, treats omitted conv as prompt, coerces omitted max-total to 600, maps `export` to scrape, ignores `--project`, or leaves a scaffold `not implemented` path must fail.
- Required mock/fixture/clock/setup — CLI harness injecting a fake `Session` call recorder; cases with no conv, bare id, URL conv, two tools, two attachments, explicit/omitted timeouts, create project/draft returns, scrape with attachments, fetch, and status JSON/no-browser-probe.

### F3 [P0] CLI payload output is stdout-first, `--out` additional, deterministic, and stream-separated
- Behavior — Successful `ask` prints assistant markdown to stdout with exactly one trailing newline and also writes the same payload to `--out`; `scrape`, `history`, and `export` print rendered markdown to stdout and additionally write `--out`; payloads and status JSON go to stdout, while diagnostics/progress/errors go to stderr.
- Why / gotcha — This is the explicit stdout-and-`--out` acceptance point and preserves machine-usable stdout per M3 §8.
- Falsifiability — A wrong implementation that suppresses stdout when `--out` is passed, writes different payloads to file and stdout, prints diagnostics mixed into markdown/JSON stdout, strips meaningful internal content, or emits two final newlines for content already ending in newline must fail.
- Required mock/fixture/clock/setup — Fake `Session.ask` and scrape/history/export payloads containing multiple lines and final-newline variants, temp out paths, stdout/stderr capture, and deterministic expected payload bytes.

### F4 [P0] CLI `ask` emits salvaged partial markdown on completion timeout before nonzero exit
- Behavior — If `Session.ask` times out but persists or carries a salvaged partial, CLI `ask` writes the salvaged markdown to stdout and to `--out` if provided, then exits with the completion error code and writes the redacted error to stderr.
- Why / gotcha — M3 §5/§8/§9 require stdout to still receive useful partial output on timeout while error status remains machine-visible.
- Falsifiability — A wrong implementation that suppresses stdout on nonzero exit, prints only `ERROR`, prints stale complete text, writes only `--out`, or exits 0 after partial timeout must fail.
- Required mock/fixture/clock/setup — Fake `Session.ask` raising `CompletionTimeoutError` with/storing a partial record; temp out path; captured stdout/stderr/exit code.

### F5 [P1] `status` reports schema semantics, honors `--no-browser-probe`, and can exit nonzero while printing report
- Behavior — CLI `status [conv]` calls `Session.status(conv_or_url, probe_browser=not --no-browser-probe)`; JSON status includes store counts, CDP preflight result when probed, attached/signed-in/login-wall/challenge state from a tool-owned diagnostic tab when safe, selector-map validity with per-selector `present=null` when unchecked, tab-pool and budget snapshots, last redacted error, and optional per-conversation model/tools/turn counts/last turn/attachments/branch/paths; blocking conditions may exit nonzero while stdout still contains the report.
- Why / gotcha — M3 §8 defines status as a diagnostic report, not merely an error, and forbids probing when disabled.
- Falsifiability — A wrong implementation that probes with `--no-browser-probe`, omits `last_error`, uses false instead of null for unchecked selectors, includes raw canaries/private tab data, prints only `ERROR` with no report on login wall, or exits 0 on blocking CDP/login state must fail.
- Required mock/fixture/clock/setup — Fake `StatusReport`/session recorder with healthy, CDP unreachable, login wall, Cloudflare, unchecked selector, redacted last error, and conversation details; stdout/exit capture.

### F6 [P0] CLI errors use stable stderr format, JSON error mode, exit codes, and redaction
- Behavior — Non-JSON errors write first stderr line `ERROR <CODE>: <message>`; JSON-mode commands emit redacted error JSON on stderr without corrupting stdout; CLI exits with the `AskChatGPTError.exit_code` and wraps unexpected exceptions as internal exit 99 after redaction.
- Why / gotcha — M3 §9 is the public automation contract for agents.
- Falsifiability — A wrong implementation that prints tracebacks by default, lower-case codes, error JSON on stdout, generic exit 1/2 for all runtime errors, prompt bodies in `PromptNotSubmittedError`, or header/cookie canaries in stderr must fail.
- Required mock/fixture/clock/setup — Fake `Session` methods raising representative errors for prompt-not-submitted 30, completion-timeout 50, max-total-wait 51, human-action-needed 21, selector-not-found 24, store-error 70, and unexpected exception 99; plain and JSON-mode CLI captures.

### F7 [P1] `Session` owns minimal M4 pool/budget stubs and lower modules never own shared-resource state
- Behavior — A persistent `Session` owns one `TabPool` stub and one `AdaptiveSendBudget` stub; lower modules receive leases only; budget gates prompt submission but not completion waiting; no hard message cap exists; pool stubs open/close/reuse only tool-created tabs and `detach(close_managed_tabs=True)` closes managed tabs and detaches without quitting Chromium or closing foreign tabs.
- Why / gotcha — M3 §7 places lifecycle/resource ownership in `Session` and keeps full pool/rate behavior out of M4 except safety-preserving stubs.
- Falsifiability — A wrong implementation that constructs a new pool/budget per send, holds the budget through long completion, fails the N+1th send due to a hidden cap, enumerates operator pages, calls browser quit, or closes a foreign tab must fail.
- Required mock/fixture/clock/setup — Injected pool/budget stubs with identity/call counters, two sequential asks in one `Session`, long completion fixture with fake clock, repeated successful mock sends beyond suspicious cap, owned and foreign tab sentinels, and channel guards for page enumeration/quit/foreign close.

### F8 [P2] M4 stubs for create/fetch/loop remain bounded and do not assert live M5/M7 behavior
- Behavior — `create` may return a normal or draft `ConversationRef` over mock and forwards `--project`; `fetch` checks local cached refs and does not attach when cached; `loop`, if exposed in M4, is an explicit minimal/stub or bounded mock-only dispatch and must not run an unbounded real browser loop, full TabPool orchestration, rate adaptation, or project UI behavior.
- Why / gotcha — M3 §10 keeps full `loop`, menus, TabPool, AdaptiveSendBudget, and project send/create beyond the offline M4 core except minimal stubs.
- Falsifiability — A wrong implementation that requires a server id for draft create, ignores `--project` before forwarding, always attaches before checking cached fetch, silently starts an unbounded loop, hides a message cap, or touches real CDP/browser under mock must fail.
- Required mock/fixture/clock/setup — Fake `Session.create` returning normal and draft refs, fake cached `Session.fetch` returning a temp path/JSON metadata, optional CLI loop invocation under mock asserting documented stub/bounded behavior.

## OPEN AMBIGUITIES / GAPS FOR THE MANAGER

- Project id normalization needs one exact convention before tests pin strings: M3 examples imply `ConversationRef.project_id` may be the value after `g-p-` while URLs contain `/g/g-p-<project_id>/c/<chat_id>`; tests should require round-trip consistency after the manager pins whether stored `project_id` includes `g-p-`.
- Prompt normalization for composer verification and submitted-user comparison is required by M3 §6 but not specified; tests must pin the chosen public normalization with adversarial whitespace/newline cases rather than call the implementation helper as its own oracle.
- Markdown render exact role separators, attachment/citation display format, and final newline policy beyond CLI `ask` are underspecified; tests should assert visible content fidelity and deterministic output while the manager pins any exact render format needed for snapshots.
- Empty visible `content.parts=[]` is not resolved by M3 §3.5; once decided, include a fixture that catches the opposite behavior.
- DR/Pro “large hidden group” threshold is qualitative; use fixtures far from the boundary unless the manager chooses a numeric threshold.
- Attachment `download_state` exact non-downloaded value per source is not pinned; current tests should require no fetch, `local_path is None`, `sha256 is None`, and not `downloaded` until the manager chooses `pending`/`unsupported`/`not_downloadable` defaults.
- Torn-line warning/diagnostic interface is unspecified; choose warnings, logging, or store diagnostics before asserting the observable warning mechanism.
- `backend_check_interval_s=None` default is intentionally deferred to channel/mock defaults; exact cadence tests should use explicit intervals, and a separate test should only assert `None` does not collapse to DOM cadence.
- `StatusReport` exact top-level field names depend on the final dataclass; tests should pin the final names once implemented while preserving the schema semantics listed above.
- CLI `--project` for `ask` appears in the M3 CLI table but `Session.ask` has no `project` parameter and project send/create is out of M4; manager should decide whether M4 only parses/forwards/fails closed or removes/defers the flag for ask.
- M3 §5 and §9 both discuss timeout classes, with §5/lens consensus distinguishing no-activity `CompletionTimeoutError` from explicit `MaxTotalWaitExceededError`; manager should confirm this exact split before writing taxonomy tests.
- Selector validation entry point and data-model validation location are not specified; tests should target public behavior (invalid selector maps fail startup/config; invalid turn records cannot be durably persisted/loaded as valid) rather than private constructor details.
