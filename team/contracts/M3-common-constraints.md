# M3 common constraints — READ IN FULL (every M3 design worker)

> You are a **pi worker** for the `ask-chatgpt-dev` team, executing part of **mission M3: best-of-N detailed design** for the ask-chatgpt v2 rewrite. You inherit **nothing** but your task pointer and the files named here. This file carries the constraints, safety rules, live-site ground-truth facts, and gotcha fixes that **every** M3 worker must honor. Your lens/role-specific contract (named in your launch prompt) carries your scope + deliverable. Read **both** this file and your role contract in full before acting. Repo root = your cwd = `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`.

## 0. What M3 is (and is NOT)
- M3 produces a **design document only**. The implementation happens later (M4 offline core, M5 capture/scrape/send). Your job is to design, not to build.
- **DESIGN ONLY — HARD:** Do **NOT** modify any production source: `src/`, `pyproject.toml`, `tests/`, `README.md`, `VERIFICATION.md`. Do **NOT** run any real-site / browser / CDP / network leg against chatgpt.com or openai.com (this is offline design). Do **NOT** `git add/commit/push`, do **NOT** run `git checkout`/branch ops, do **NOT** run `uv tool install/upgrade/reinstall`. Do **NOT** touch the `stable` branch in any way.
- **Write ONLY your single output markdown file** at the path your role contract specifies (under `team/evidence/reports/M3-work/` for lenses/verifiers, or `team/evidence/reports/M3-detailed-design.md` for the synthesizer). Creating that one file (and using `bash` read-only to inspect inputs / your own output) is the only filesystem mutation you may make.

## 1. Required reading — read these IN FULL, FIRST (they are ground truth; prose-about-them is stale until re-derived)
1. `docs/REWRITE-SPEC.md` — the approved spec (architecture §2/§3; capture §5; send §6; completion §7; persistence §8; identity §9; concurrency §10; model/tools §11; status §12; safety §13; channels §14; gotcha traceability §17; testing §18; mission sequence §19).
2. `team/evidence/handoffs/M2-ground-truth-probe.md` — **AUTHORITATIVE live-site facts.** The design MUST honor these; do not re-derive or contradict them (you cannot — this is offline; M2 was the attended probe).
3. `team/charter.md` — the team's domain charter + safety invariants (the "Rework spec" section is the worker-facing distillation of the spec).
4. `.claude/skills/manager/references/agent-rigor.md` — the universal rigor every node obeys (independent verification, best-of-N, verify-from-ground-truth, Occam, handoff protocol). Obey it.
- **Optional reference (read-only, NEVER copy):** `issues/cdp-send-repro/controller.mjs` — the real-proven CDP send+verify controller (the `.mjs` model the Python `Session` mirrors). Consult only if your role needs send/completion mechanics.
- **Do NOT read** `archive/`, `human/`, `tmp/`, or `prompt-buffer.md` (forbidden / out of scope). Do NOT read or touch any browser tab or live conversation (offline).

## 2. Safety invariants (non-negotiable — transcribed verbatim; the design must encode every one)
- **CDP-attach ONLY; no Playwright-*launched* browser** (a launched browser is Cloudflare-blocked → infeasible). Attach to the operator's already-running signed-in Chromium over CDP at `http://127.0.0.1:9222`.
- **No stealth / anti-detection, ever.**
- **Domain allowlist** (safety): only chatgpt.com / openai.com / their auth domains / `oaiusercontent` etc. The design includes an `allowlist.py` enforcing this.
- **Inspect ONLY tabs the tool itself opens.** Never read or touch operator/other tabs (leak risk — the operator and/or another agent may be using the same browser concurrently). **Never iterate `context.pages`** to find tabs.
- **Never quit the browser** (detach only).
- **Preflight CDP** before any real leg: `curl -s --max-time 5 http://127.0.0.1:9222/json/version`; if down → stop cleanly (`CDP_UNREACHABLE`) and escalate to the operator.
- **Login / Cloudflare challenge → STOP, log `HUMAN-ACTION-NEEDED`, poll read-only.** Login is **never** automated.
- **Real-site legs are operator-attended CDP runs**, never CI/cron/unattended.
- **ChatGPT account** is single + operator-owned: **human-paced; no programmatic spamming; NO hard message cap** (the old "max N messages" was retracted fiction — an audit log is transparency, not rationing). Safety nets (backoff, politeness floor) protect the account; they impose no arbitrary low ceiling.
- **The web-app `Authorization` bearer token and OAI headers must NEVER be persisted or logged** — obtain them transiently from the page's own request, forward them for the single fetch, and discard. Not in transcripts, not in logs, not in `raw-mapping.json`, not in error messages.
- Concurrency is **modest (~3-way)** against the shared browser.

## 3. M2 ground-truth facts (AUTHORITATIVE — the design must be consistent with ALL of these)
**Backend-api capture — CONFIRMED with a required adjustment:**
- The capture endpoint is `GET https://chatgpt.com/backend-api/conversation/<conversation_id>`. A minimal in-page `fetch` with only cookies + `accept: application/json` returns **404** (top-level key `detail`). The cookies-only assumption is **refuted**.
- It returns **200** only when the **web-app request headers** are forwarded: `authorization` (bearer), `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, `x-openai-target-route`. The design must **obtain these from the page's OWN request** (intercept the app's own `/backend-api/conversation` request/response on your own attached tab, or read them from that request) and forward them for the single capture fetch. **Never persist/log the token.** It is **NOT** the public OpenAI API (no key, no separate billing).
- A successful capture returned **~17.1 MB in one response, no pagination**, ~**5.0k mapping nodes** (~5.0k current-branch nodes); counts vary while a conversation is still updating. → Design for **streaming / memory-efficient handling**, not a gratuitous full-in-memory parse-everything-then-process.
- Response top-level keys include: `conversation_id`, `title`, `create_time`, `update_time`, `mapping`, `current_node`, `default_model_slug`, `async_status`, `moderation_results`, `safe_urls`, `blocked_urls`, `context_scopes`, `disabled_tool_ids`, `is_archived`, `is_temporary_chat`, `owner`, `voice`.
- `mapping` is a **message tree** keyed by node id; each node has parent/children plus an optional `message`.
- Roles/content types observed: `user:text`, `assistant:text`, `assistant:thoughts`, `assistant:code`, `assistant:reasoning_recap`, `assistant:model_editable_context`, `tool:text`, `tool:tether_browsing_display`, `tool:execution_output`, `tool:multimodal_text`, `system:text`.
- **Where the visible markdown lives:** visible assistant report bodies are in `message.content.content_type == "text"` with `message.content.parts` as a **list of strings**. `assistant:code` uses `message.content.text`; `assistant:thoughts` uses `message.content.thoughts`; many tool/code/thought nodes have **no** `parts`.
- **Math/markdown faithfulness (measured booleans on assistant `content.parts`):** contains `\widehat` = true; `\frac` = true; `\ne`/`\neq` = true; `$` delimiter = false; `\(` delimiter = true; `\[` delimiter = true; markdown table pipe = true. → Backend JSON is a **faithful canonical capture** of visible assistant markdown/math **IF** the auth/OAI headers are obtained safely.

**Deep Research / Pro turns:**
- There is **no** `content_type == "deep_research"`. DR/Pro turns appear as **large `turn_exchange_id` groups**: one user message + many hidden assistant/tool nodes + one **visible final `assistant:text` report** whose body is `message.content.parts[0]` (sampled report bodies ~7k–16k chars).
- Large turn groups had dozens to 100+ nodes, with hidden `assistant:thoughts`, `assistant:code`, `assistant:reasoning_recap`, tool `execution_output`, `tether_browsing_display`, and tool authors `web.run`, `file_search`, `python`, `container.exec`.
- **Citation/search metadata** lives on assistant messages, mainly in `message.metadata.content_references`, `message.metadata.citations`, `message.metadata.search_result_groups`, `message.metadata.search_queries`. `content_references` types observed: `grouped_webpages`, `sources_footnote`, `file`. `citations` entries use offsets (`start_ix`, `end_ix`) + `citation_format_type` + nested `metadata`.

**Attachments reference shapes (cover ALL of these):**
- User-uploaded: `message.metadata.attachments[]` (keys: `id` like `file_...`, `size`, `name`, `file_token_size`, `source`, `is_big_paste`).
- File citations/refs: `message.metadata.content_references[]` with `type: "file"` (keys: `id`, `name`, `source`, `snippet`, `cloud_doc_url`, `library_file_id`, `library_artifact_type`, `medical_file_reference`, `drug_file_reference`, `page_range_start`, `page_range_end`, `input_pointer` {file_index, line range, message id, message index}, `fff_metadata`, `connector_id`).
- Generated/image assets: tool `tether_browsing_display` messages may have `message.content.assets[]` (keys: `content_type`, `asset_pointer`, `size_bytes`, `width`, `height`, `fovea`, `metadata`).
- Code-exec outputs: tool `execution_output` messages use `message.metadata.aggregate_result` (keys: `code`, `messages`, `jupyter_messages`, `final_expression_output`, `run_id`, `status`, timing, exception fields).
- **No literal `/backend-api/files/...` URLs or `sandbox:`/`attachment:` URIs were observed** — references are by ids, asset pointers, and the metadata shapes above. Downloading bytes (lazy `fetch`) is a separate, later step.

**Completion signals:** top-level `async_status`; metadata `async_source`, `is_complete`, `is_finalizing`, `pro_progress`; node `status`. Consider `GET /backend-api/conversation/<id>/stream_status` (hypothesis — verify in M5, not now).

**Live selectors (observed; the selector map should use these; keep them in `selectors/real.json`, fail-closed):**
```json
{
  "composer": "#prompt-textarea",                                            // contenteditable div, role=textbox, aria 'Chat with ChatGPT'; [data-testid=prompt-textarea] ABSENT
  "tools_button": "button[data-testid=\"composer-plus-btn\"]",
  "message_turn": "[data-message-id][data-message-author-role]",
  "user_turn": "[data-message-author-role=\"user\"][data-message-id]",
  "assistant_turn": "[data-message-author-role=\"assistant\"][data-message-id]",
  "copy_button": "button[data-testid=\"copy-turn-action-button\"]",          // visible after hovering an assistant turn; aria 'Copy message'
  "stop_button": "button[data-testid=\"stop-button\"], #composer-submit-button[aria-label*=\"Stop\" i]",
  "send_button_unverified_no_input": "button[data-testid=\"send-button\"], #composer-submit-button",  // empty fresh chat did NOT mount a send button; on an in-progress chat the submit control was #composer-submit-button[data-testid=stop-button]
  "model_picker_heuristic": "composer-footer button[aria-haspopup=\"menu\"] showing the current-model label; NO stable data-testid/aria-label — use label-driven Radix enumeration"
}
```
- **Menus are Radix portals:** open the trigger first, then enumerate options in `[data-radix-popper-content-wrapper]`. Model tiers are `menuitemradio`; model families are a `menuitem` submenu. Observed model tiers: `Instant`, `Medium`, `High`, `Extra High`, `Pro Extended` (checked); family submenu `GPT-5.5` radios: `5.5`, `5.4`, `5.3`, `4.5 Leaving on June 26`, `o3`. Tools/`+` menu top-level: `Add photos & files`, `Recent files`, `Create image`, `Deep research`, `Web search`, `More`, `Projects`; `More` submenu: `Agent mode`, `Create task`, `Figma`, `Finances`, `GitHub`, `OpenAI Platform`. (Do NOT open `Recent files`/`Projects` submenus — private-name leak risk.)
- **Clipboard fallback:** `navigator.clipboard.readText` exists but permission state was `prompt` (grant-only). Feasible only with explicit permission/user gesture → **do NOT depend on it as an unattended fallback.**
- **Projects:** deferred in M2 (no project URL probed; `gizmo_id`/`gizmo_type` were null on the plain `/c/<id>` target). The design should still account for both URL shapes (`/c/<id>` and `/g/g-p-<projid>/c/<chatid>`) and `project_id` metadata, but treat project send/create behavior as a **near-term, not-yet-live-verified** assumption to be confirmed in M5.

## 4. The four gotcha fixes (each MUST be honored by the design — these are why the rewrite exists)
1. **`capture-renders-dom-not-raw-markdown` (silent math corruption):** capture from the backend-api **canonical markdown** (primary); fail-closed fallback chain copy-button → KaTeX `<annotation encoding="application/x-tex">` → DOM `textContent` (known-lossy, last resort). Fidelity bar: `\widehat`, `\ne`, `\frac{}{}` round-trip vs the web-UI **copy** output as ground truth — **verified, never assumed-by-construction**.
2. **`cdp-send-noop-returns-stale-response` (silent no-op send):** a send is **not "done" until a new turn is verified**. Capture latest user-turn `message_id` (and/or user-turn count) as a **baseline** before send → fill `#prompt-textarea` (insertText fallback) → submit → **poll briefly for a NEW user turn carrying the prompt**; if none within a short window → raise **`PromptNotSubmittedError`** (loud + retryable), never return a stale reply. The composer transiently un-mounts during turn transitions → **wait/retry for the composer, don't treat absence as fatal**; **reload the conversation when idle between turns** to clear SPA staleness. `wait_for_completion` requires the returned assistant turn to be **newer** than baseline (different `message_id`). Model/tool selection is likewise verified (confirm the UI reflects the requested state before sending; fail-closed otherwise).
3. **`response-truncated-drops-out-file-and-session` (+ hidden 600s ceiling):** **No hidden completion ceiling.** `timeout` is a **no-activity window** (resets on progress), not a hard cap; an optional explicit `max_total_wait` defaults to **unbounded**. Long Pro/DR runs (minutes) must **never be silently killed**. Completion primary = backend-api poll; fallback = DOM consensus gated on the new-turn baseline.
4. **`out-suppresses-stdout`:** `ask`/`scrape` **always** print to **stdout** *and additionally* write `--out` when given — stdout is always a usable fallback.
- **Lose nothing (write discipline):** **eager-write** the turn record (prompt + conversation ref) at/just-before send; update with the full response on completion; on error/timeout **salvage** whatever partial text is visible with `status` + `partial=true`. The conversation ref is persisted **before** send so a truncated/failed call is always resumable.

## 5. Rigor you must apply (summarized; the full text is in `.claude/skills/manager/references/agent-rigor.md`)
- **Re-derive every claim from ground truth — including claims in this contract and in the spec.** A claim's being in your contract does not make it true; check it against `docs/REWRITE-SPEC.md` and `team/evidence/handoffs/M2-ground-truth-probe.md`.
- **Measure complexity empirically — never hand-guess** time/space/memory/request-count/scale. The ~17 MB / ~5k-node figure is **measured** (M2) — use it; do not invent different numbers. Prefer **O(batch) / stream-then-persist** designs whose peak footprint is independent of total scale over "enumerate-everything-first" designs.
- **Occam:** prefer the **simplest correct design**; continually cut accreted complexity; a significant paradigm shift only if it dramatically improves the design without sacrificing correctness.
- **Falsifiability:** any test/acceptance you propose must be able to **fail** — a capture/completion check must be verifiable against an authoritative signal, not self-reported. Want a file → ask for a file (adversarially review any GPT-facing prompt the design implies).
- **Honesty:** surface open questions and uncertainties for the synthesizer/lead rather than guessing. Mark every assumption as an assumption.

## 6. Output discipline (every M3 worker)
- Write your deliverable to the **exact path** your role contract names. Create no other files; mutate no production source.
- **Begin your output file with a single status line** so shipment can be verified by a single-token extract:
  `STATUS: DONE` (or `PARTIAL` / `BLOCKED`) — then 2–4 lines: what you produced, key decisions, any blocker.
- Be **concrete and implementable**: name modules, functions with signatures, JSON field names + types, selector strings, algorithm steps — not vague prose. A reader implementing M4/M5 should not have to re-design.
- Every lens must end with two sections: **"Cross-cluster interfaces & dependencies"** (what your cluster exposes to other clusters, and what it needs from them — so the synthesizer can reconcile the seams) and **"Open questions / assumptions"**.
- Cite the source of each non-obvious claim (`REWRITE-SPEC §N`, `M2 handoff`, or "assumption").
