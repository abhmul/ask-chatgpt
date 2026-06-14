# ask-chatgpt — Design Spec: Web-UI-mirroring interface + persistence/cache layer

**Status:** SPEC (proposed; not yet built). Authoritative target for the *next* iteration of this tool. For future agents implementing it. Build incrementally, **keep the proven engine**, mock-prove offline, real-verify over CDP. This supersedes the ad-hoc shape of the current `ask_chatgpt()` god-function — but NOT the engine beneath it.

**Read alongside:** `VERIFICATION.md` (what is real-proven), `docs/DECISIONS.md` (D-001 channels, D-002 real-site/CDP), `docs/USAGE.md` (current surface), `issues/2026-06-14-response-truncated-drops-out-file-and-session.md` (the persistence bugs this spec fixes).

---

## 0. Why this redesign

Today `ask_chatgpt(prompt, session_identifier, model_settings, files, dirs, ...) -> text|AskChatGPTResult` is a single function that branches on `files=` (text vs bundle). The *engine* under it is real-proven and good; the *interface and persistence* are weak:

- It is a **god-function** that conflates plain Q&A with the bundle round-trip.
- Sessions are created **implicitly** (first use of a `session_identifier`); there is no explicit "open a chat → get an id."
- There is **no transcript persistence** — only the conversation ref is stored (`sessions.json`), so there is no history, no cache, and a truncated/failed call loses all output (the 2026-06-14 issue).
- **Attachments-out**, **project tagging**, and **add-on/tool selection** are not first-class.

The operator's framing — *mirror the way a human drives the Web UI* — is the right target. This spec defines that interface, the persistence/cache layer beneath it, and what to reuse vs reshape vs build.

## 1. Principles (design reasoning — honor these)

1. **Mirror the Web UI's primitives.** An agent should drive ChatGPT like a human: open a chat; send a prompt with optional files / model / add-ons / project; receive a reply plus any attachments. Expose those primitives, not a monolith.
2. **Library-first; the CLI is a thin wrapper.** (Unchanged from today.)
3. **Keep the proven engine.** `BrowserSession`/driver mechanics — CDP attach, send, `wait_for_completion`, bounded DOM read, model-tier selection, upload, download-capture — plus selector-maps-as-data, fail-closed, the session registry, tier-purity, and no-stealth are **real-proven** (`VERIFICATION.md`). Reuse them. This is NOT a ground-up rewrite.
4. **Persistence-first: lose nothing.** Every prompt→response is persisted **untruncated**, written **eagerly** (on conversation-open) and **on-error** (with salvaged partial text). This single store is the substrate for history, cache, and resilience, and it fixes the truncation data-loss bugs.
5. **No hidden magic limits.** Only clearly-stated defaults the caller fully controls. (See the 600s-ceiling incident, §7 — a hidden constant silently overrode `--timeout`. Never again. Defaults yes; secret caps no.)
6. **Bounded reading by default; full-scrape only on explicit request.** D-001's "latest completed turn only, no transcript-wide scraping" stays the default for `ask()`. Reading a whole conversation (`read_conversation`) is an explicit, operator-authorized exception, fail-closed.
7. **Falsifiable verification + honest scope.** Tests must be able to fail. "Cached == web UI" must be checked against the live DOM, not assumed. No overclaiming (the M-006/M-007 retraction lesson). Own-tab-only; never read non-owned tabs (the M-009/M-011 leak lesson).

## 2. Architecture (layers)

```
┌ Feature layers (consumers of the core) ───────────────────────────────┐
│   bundle round-trip (files→zip→patch)    Deep Research / tools    ...  │
├ Core interface (the Web-UI primitives) ───────────────────────────────┤
│   create_chat → ask(...) → Response(session_id, text, attachments)    │
│   get_history · read_conversation · the transcript/cache STORE        │
├ Engine (KEEP — real-proven) ──────────────────────────────────────────┤
│   BrowserSession/driver: CDP attach, send, wait_for_completion,       │
│   bounded read, model-tier select, upload, download-capture           │
│   session registry · selector-maps-as-data · fail-closed · no-stealth │
└───────────────────────────────────────────────────────────────────────┘
```

Bundles and Deep Research become **consumers of `ask()`**, not branches inside it.

## 3. The core interface (target API)

### Library
```python
create_chat(*, session_identifier=None, channel="cdp", cdp_endpoint=None) -> Session
    # Registers a session and returns it with a provisional id. The real /c/<id> ref is
    # bound lazily on the first ask() (the Web UI also has no URL until the first send).

ask(session, prompt, *,
    files=None, dirs=None,          # attachments-in (bundle layer may wrap this)
    model=None,                     # reasoning tier today; model-family when wired (M-010 scope)
    tools=None,                     # add-ons: ["deep_research", "web_search", ...] (M-011/M-012)
    project=None,                   # project/workspace tag (NEW; needs discovery)
    cache="fallback",               # "off" | "fallback" | "prefer"  (§4)
    timeout=30.0,                   # NO-ACTIVITY window, resets on progress; NO hidden cap (§7)
    max_total_wait=None,            # OPTIONAL explicit absolute cap; default None = unbounded
) -> Response

Response(
    session_id: str,                # same as input unless a new chat was created
    text: str,                      # the assistant reply (untruncated)
    attachments: list[Attachment],  # files the assistant produced (downloads); [] if none
    status: "complete"|"truncated"|"error",
    conversation_ref: str,          # settled /c/<id>
    turn_index: int,
    from_cache: bool,
)

get_history(session_identifier) -> list[Turn]
    # The tool's own recorded prompt→response sequence for the session (from the local store).
    # Browser-free. Honest scope: records turns the TOOL made, not operator-typed turns.

read_conversation(conversation_ref_or_session_id) -> list[Turn]
    # SCRAPE all turns from a known conversation. Operator-authorized exception to D-001's
    # no-full-scrape rule; for the operator's own conversations. Needs the browser; fail-closed.
```

### CLI
```
ask-chatgpt new-chat [--session ID]                                  # create_chat
ask-chatgpt --session ID "PROMPT" [--files … --model … --tools … --project … --no-cache --out …]   # ask
ask-chatgpt history --session ID [--json]                            # get_history
ask-chatgpt scrape (--session ID | --ref /c/<id>) [--json]           # read_conversation
```
`--no-cache` == `cache="off"` + overwrite the stored entry (= "invalidate this call").

### Backward compatibility
Keep the current `ask_chatgpt()` and CLI working as a **thin wrapper over `ask()`** during migration; do not break existing callers (the WSC agent, `docs/PARALLEL-GPT-RECIPE.md`). Deprecate, don't delete.

## 4. Persistence: the transcript / cache store (the load-bearing new piece)

One store per `ASK_CHATGPT_STATE_DIR`, alongside `sessions.json`. Append-only JSONL (`transcript.jsonl`) — one record per turn:
```json
{ "session_id": "...", "turn_index": 0, "conversation_ref": "/c/<id>",
  "prompt": "...", "prompt_sha256": "...", "model_settings": {...},
  "response_text": "<UNTRUNCATED>", "attachments": [...],
  "status": "complete|truncated|error", "partial": false, "created_at": "<iso8601>" }
```

**Write points (these also fix the 2026-06-14 issue):**
1. **Eagerly** — persist the conversation_ref to the registry the moment `open_or_create_conversation` returns, *before* send. (Issue Bug 2: ref currently saved only on success → lost on truncation.)
2. **On completion** — the full response + attachments.
3. **On error/truncation** — salvage whatever partial text is in the latest turn and record it with `status` + `partial=true`; the CLI writes it to `--out` and warns. (Issue Bug 1: `--out` currently never written on error.)

**Cache (reads from the same store):**
- **Key:** `sha256(session_id-or-"none" || normalized_prompt || model_settings)`.
- **Modes** (caller-controlled; default RECOMMENDED `fallback`):
  - `off` — never read cache (always hit GPT); still writes.
  - `fallback` (default) — hit GPT; only if GPT is unreachable/fails, serve the cached response. Resilience without changing healthy behavior. *Matches "if something happens to the operator."*
  - `prefer` — if a cache hit exists, return it WITHOUT calling GPT. **Stateless calls only**; for `--session` (continued) calls, `prefer` is refused/downgraded to live, because serving cache without sending the turn would **diverge** the live conversation from the local view.
- `--no-cache` — bypass the read AND overwrite the stored entry with the fresh result.
- `Response.from_cache` flags cache-served results.
- **Untruncated invariant:** never store a truncated read as `complete`. A cache hit only counts when `status == complete`.

**Tests for the cache (operator requirement — "cached == web UI"):**
- Mock: cached text == the response the mock served. (offline)
- **Real (over CDP): cached text == the live DOM of that turn.** This doubles as a guard that the read did not truncate — it ties the cache's correctness to the completion logic. (needs a run window)

## 5. Scraping prior conversations — `read_conversation`

For conversations already driven by agents whose local transcripts were not captured. Reads ALL turns from a known conversation (by `conversation_ref` or via the registry's `session_id → ref`). **Explicit, operator-authorized exception to D-001** (which forbade transcript-wide scraping for selector-fragility / adversarial-DOM reasons — those caveats still apply, so: bounded to one conversation, fail-closed on stale selectors, own-tab-only, redact `/c/<id>` in any logs). Populates the transcript store so subsequent `get_history` is browser-free. Browser-dependent.

## 6. What is built vs reshape vs build

| Piece | Current state | Action |
|---|---|---|
| Engine: CDP attach, send, `wait_for_completion` (cap fixed), bounded read, upload, download-capture | real-proven | **KEEP** |
| Model selection | reasoning-tier real-proven (M-010); family submenu not wired | KEEP + extend (family = later) |
| Session registry (`session_id → ref`) | works | KEEP; extend write to be eager (§4.1) |
| `ask_chatgpt()` god-function | works, conflated | **RESHAPE** into `ask()` + keep a compat wrapper |
| `create_chat()` explicit | none | **BUILD** (thin) |
| Transcript/cache store + `get_history` | none | **BUILD** (§4) — the keystone |
| Cache modes + `--no-cache` | none | **BUILD** (§4) |
| Partial-salvage + eager ref save (issue fixes) | absent | **BUILD** (§4 write points) |
| Attachments-out as first-class `Response.attachments` | bundle-only | **BUILD** (generalize download-capture) |
| `read_conversation` (scrape) | forbidden by D-001 | **BUILD** as an authorized exception (§5) |
| `tools=` add-ons (Deep Research) | discovered, not wired (M-011) | **BUILD** as a feature layer (M-012) |
| `project=` tagging | none, undiscovered | **BUILD** after UI discovery |
| Bundle round-trip | works inside `ask_chatgpt` | **RE-LAYER** as a consumer of `ask()` |

## 7. The "no hidden magic limits" rule (incident-derived)

`_REAL_COMPLETION_CEILING_S = 600` was a hard cap applied to every real/cdp `wait_for_completion` regardless of the caller's `--timeout` (fixed in `779eb40`). It silently killed 10–45 min Pro Extended / Deep Research replies. **Rule for all future code:** no constant may bound a user-facing operation in a way the caller cannot see or override. Defaults are fine and must be documented; absolute caps must be opt-in (`max_total_wait` default `None`). `timeout` is a *no-activity* window that resets on progress, not a wall-clock guillotine.

## 8. Verification & safety requirements (non-negotiable)

- **Tier purity:** the default test suite stays loopback-mock-only; real tests double-gated (`real_site` + `ASK_CHATGPT_REAL=1`).
- **Falsifiable tests:** every real-site test must be able to fail (controls / sentinels). Cache tests must compare against the live DOM, not self-report.
- **No stealth / no-anti-detection; CDP detach-not-quit; login never automated; challenge → stop.**
- **Own-tab-only by page identity** (never substring tab-matching — the M-011 leak). Never read account/profile UI. No `/c/<id>`, credentials, or identifiers in artifacts/commits.
- **Honest scope** in `VERIFICATION.md`: state real-proven vs mock-only vs unproven per feature; no overclaiming.

## 9. Build sequencing (most of this is OFFLINE — no browser needed)

- **Phase 1 — offline core (no browser):** transcript store + `get_history`; cache (`off`/`fallback`/`prefer` + `--no-cache`); `create_chat`; reshape `ask()` (engine underneath) + compat wrapper; the issue's eager-save + partial-salvage; full mock test coverage including a mock "cached == served" test. Buildable while the browser is busy.
- **Phase 2 — browser-dependent verification:** real "cached == live DOM" test; `read_conversation` (scrape); attachments-out capture (generalize download); real truncation/long-run validation of the cap fix.
- **Phase 3 — feature layers:** `tools=` / Deep Research (continues M-011/M-012); `project=` after UI discovery; re-layer bundles as a consumer.

## 10. Open decisions (operator — defaults proposed, confirm or override)

1. **Cache default mode:** `fallback` (recommended) vs `prefer` vs `off`.
2. **Cache key scope:** per-session (recommended) only, or also a cross-session "same question" mode?
3. **`prefer` on `--session` calls:** refuse/downgrade to live (recommended) vs serve cache anyway?
4. **Attachment representation:** path on disk + metadata (recommended) vs bytes in `Response`?
5. **Backward-compat horizon:** how long to keep `ask_chatgpt()` before deprecation?

---
*This spec is a target, not a contract. Implement in phases, mock-prove each, real-verify over CDP, and keep `VERIFICATION.md` honest about what is actually proven.*
