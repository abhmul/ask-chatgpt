# ask-chatgpt v2 — Web-UI-mirroring CLI rewrite (SPEC)

> **Status:** authoritative rewrite spec, approved by the operator 2026-06-18 via a grill-me intake session. Supersedes `docs/DESIGN-SPEC.md` (which described an *incremental* reshape of the v1 god-function and is now historical). This spec describes a **from-scratch rewrite**: the v1 library is archived and rebuilt; v1 code is consulted as *reference*, not copied.
>
> The load-bearing constraints below are mirrored into `team/charter.md` ("Rework spec"), which is fed verbatim into every manager/worker contract. This document is the full design record; the charter is the worker-facing distillation. **Universal rigor is not restated here** — it lives in `.claude/skills/manager/references/agent-rigor.md`.

## 1. Goal & primary consumer

`ask-chatgpt` is a Python tool that mirrors chatgpt.com's web-UI functionality from the command line, driving an operator-signed-in Chromium over CDP (Playwright). It does **not** use the OpenAI API.

- **Primary consumer:** autonomous agents (the tool is scripted, not primarily interactive).
- **Most-pressing deliverable:** scrape the long math conversation at `https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31` into a faithful local transcript the operator can process — *but not at the expense of hacky code*. The scrape is the first real consumer of the capture+transcript spine, so building that spine correctly **is** the path to the scrape.
- **Headline workflows:** (a) send "keep pushing!!" to a model (e.g. Pro Extended) in a loop on a hard problem; (b) scrape/continue existing conversations, including ones with Deep Research turns and load-bearing math.

## 2. Architecture

**Library-core + thin CLI + persistent session; no daemon** (decision C).

- The core is a Python **library**; the CLI is a thin wrapper over it.
- **Atomic operations** (single `ask`, `scrape`, `status`) attach over CDP → act → detach. Stateless and crash-proof; ideal for one-shot agent calls and the read-only scrape.
- **Loops and multi-tab concurrency** use a **persistent `Session`** the consuming process holds: attach once, reuse across turns/tabs. This is the only correct home for the account **rate budget** and the **tab pool** (one owner across all concurrent consumers — the shared-resource-ceiling rule). The `.mjs` controller's persistent-loop model, in Python.
- **No separate daemon/IPC service.** Durable truth lives in the browser + the on-disk transcript, so crash-recovery is trivial; a stateful service would be redundant complexity (rejected per Occam and the operator's "no hacky code").

### Capture/action asymmetry (load-bearing)

- **Actions** (send a prompt, create a chat, pick a model, toggle a tool, upload a file) go through the **real UI** — we never forge requests (replicating request-signing is fragile and risks bot-detection).
- **Reads/capture** go through the page's **own authenticated backend endpoint** (see §7), with UI affordances as a fail-closed fallback.

### Module layout (indicative; finalized in design mission M3)

- `session.py` — persistent `Session` (CDP attach/detach, tab pool, rate budget, lifecycle).
- `capture.py` — backend-api capture (canonical markdown, DR, attachment refs) + UI/annotation fallback.
- `send.py` — UI send with new-turn verification, idle-reload, wait-for-composer.
- `completion.py` — completion detection (backend-api poll primary; DOM-consensus fallback).
- `menus.py` — general label-driven Radix-menu interaction (model picker + tools menu).
- `store.py` — per-conversation transcript store (JSONL), index, attachments.
- `identity.py` — URL/id/alias parsing, project handling.
- `channels/` — `mock` (deterministic tests) and `cdp` (attended real).
- `selectors/` — fail-closed selector maps (`mock.json`, `real.json`).
- `errors.py` — named, actionable error taxonomy.
- `allowlist.py` — domain allowlist (safety).
- `cli.py` — thin CLI.

## 3. Public library API (indicative)

```python
session = Session(cdp_endpoint="http://127.0.0.1:9222", data_dir=...)  # persistent; owns tab pool + rate budget
conv = session.create(project=None)                 # explicit new conversation (optionally in a project)
result = session.ask(conv_or_url, prompt, *, model=None, tools=(), attach=(), timeout=...)  # send → verify → wait → capture → persist
transcript = session.scrape(conv_or_url, *, with_attachments=False)   # populate store from backend-api
history = session.history(conv_or_url)               # browser-free read from local JSONL
path = session.fetch(conv_or_url, attachment_ref)    # lazy attachment download
status = session.status(conv_or_url=None)            # diagnostics
```

Atomic CLI verbs construct a short-lived `Session` internally; `loop` and concurrent use hold one open.

## 4. CLI surface

| Verb | Behaviour | Browser |
|---|---|---|
| `ask <conv?> "<prompt>"` | send → verify new turn → wait → capture → append transcript → print to **stdout** (and also `--out` if given). Flags: `--model LABEL`, `--tool LABEL` (repeatable), `--attach FILE` (repeatable), `--project ID`, `--timeout S` (no-activity window), `--out FILE`, `--data-dir`. | yes |
| `create` | start a conversation (optionally `--project ID`); print its URL/id. | yes |
| `scrape <conv>` | populate JSONL store + render a single markdown export; `--with-attachments`, `--out`, `--data-dir`. Read-only. | yes (read) |
| `history <conv>` / `export <conv>` | render local transcript to markdown — **no browser**. | no |
| `fetch <conv> <attachment>` | lazily download a referenced attachment. | maybe |
| `loop <conv> --message "keep pushing!!" [--max-iterations N]` | single invocation holding one persistent session: attach once → idle-reload → send → verify-new-turn → wait → append → repeat. Convenience over the agent-driven primary. | yes |
| `status [<conv>]` | tool/conversation diagnostics (§12). | preflight |

**Output rule (fixes the v1 "`--out` suppresses stdout" gotcha):** `ask`/`scrape` **always** print to stdout *and additionally* write `--out` when given — so stdout is always a usable fallback.

**Keep-pushing primary form:** because addressing is stateless-by-URL and `ask` appends to the transcript, an agent simply calls `ask <url> "keep pushing!!"` repeatedly and judges each reply (the agent supplies the "is it solved?" judgment). `loop` is the fire-and-forget convenience.

## 5. Capture strategy (§ resolves gotcha: rendered-DOM corrupts math)

**Primary: the page's own authenticated backend endpoint.** chatgpt.com's web app loads a conversation by calling an internal endpoint (hypothesis: `GET /backend-api/conversation/<id>`) from the signed-in page, returning structured JSON with **canonical markdown** content per turn. We issue that *same* `fetch` from inside the attached page via `page.evaluate`, in the operator's session. This is the most faithful "mirror" (the data the UI renders, fetched the way the UI fetches it), and it is:

- **side-effect-free** — never touches the operator's clipboard or view;
- **uniform** — all turns at once, math/LaTeX intact, **Deep Research reports + citations come through as structured data** (no bespoke DR path);
- **robust** — no per-turn DOM fragility.

**Fail-closed fallback** (only if the backend JSON shape is unrecognised): the per-turn **copy button** → clipboard (raw markdown), then KaTeX `<annotation encoding="application/x-tex">` reconstruction, then DOM `textContent` (last resort, known-lossy).

**Caveats:** the backend endpoint is undocumented and may change shape (hence fail-closed fallback). The exact endpoint/response shape is a **strong hypothesis, unverified against the live site** — it is the first thing the M2 ground-truth probe confirms. It is **not** the public OpenAI API (no key, no separate billing).

**Fidelity bar:** no serious formatting issues that produce ambiguous math. Acceptance = re-capture a sample (including a DR turn and a heavy-math turn) and confirm `\widehat`, `\ne`, and `\frac{}{}` round-trip vs the web-UI **copy** output as ground truth. Verified, never assumed-by-construction.

## 6. Send & action strategy (§ resolves gotcha: silent no-op send returns stale response)

Send goes through the real composer, but **a send is not "done" until a new turn is verified to exist**:

1. Before sending, capture the latest user-turn `data-message-id` (and/or user-turn count) as a **baseline**.
2. Fill `#prompt-textarea` (with `insertText` fallback for the rich editor) and submit (send button, Enter fallback).
3. **Poll briefly for a *new* user turn** carrying the prompt; if none appears within a short window, raise `PromptNotSubmittedError` (loud + retryable) instead of returning.
4. The composer transiently un-mounts during turn transitions — **wait/retry for the composer rather than treating absence as fatal**, and **reload the conversation when idle between turns** to clear accumulated SPA staleness.
5. `wait_for_completion` is passed the baseline and requires the returned assistant turn to be **newer** than baseline (different `message_id`) — never returns a pre-existing completed turn.

Model/tool selection is likewise **verified**: after selecting, confirm the UI reflects the requested state before sending; fail-closed otherwise.

## 7. Completion detection (§ resolves gotcha: hidden 600s ceiling)

- **Primary:** poll the backend-api conversation state until the new turn is **complete** (not generating). Handles long-running Pro/Deep-Research turns naturally (DR ≈ minutes).
- **Fallback (DOM consensus, ported from v1 as reference):** streaming-marker seen → stop-button absent ≥ stable window → text stable ≥ window → (saw-streaming OR non-empty body), gated on the new-turn baseline.
- **No hidden ceiling.** `timeout` is a **no-activity window** (resets on progress), not a hard cap. An optional explicit `max_total_wait` exists (default unbounded). Long Pro/DR runs must never be silently killed.

## 8. Persistence: layout & schema (§ resolves gotcha: truncation drops --out + session)

**Per-conversation store** under a configurable data root (`--data-dir` / `ASK_CHATGPT_DATA_DIR`, default `~/.local/state/ask-chatgpt/`):

```
<data-dir>/
  index.json                                  # alias/session-id → conversation_id, model, project, title, last-updated
  conversations/<conversation-id>/
    transcript.jsonl                           # append-only, one record per turn
    raw-mapping.json                           # retained backend-api message tree (lossless)
    attachments/                               # gitignored; lazily downloaded artifacts
    .gitignore                                 # ignores attachments/
```

**Per-turn JSONL record (append-only; reads do last-writer-wins per `message_id`):**

```jsonc
{
  "conversation_id": "...",
  "message_id": "...",          // canonical; idempotency key AND the send-verification baseline
  "parent_id": "...",
  "turn_index": 0,
  "role": "user|assistant",
  "content_markdown": "...",    // canonical, untruncated
  "model": {"slug": "...", "display": "Pro Extended"},   // independent of tools
  "active_tools": ["deep_research"],                      // tools are orthogonal to model
  "kind": "normal|deep_research|image|...",
  "created_at": "...",          // from backend-api timestamp — authoritative, never an agent self-report
  "attachments": [{"filename": "...", "mime": "...", "bytes": 0, "sha256": "...", "source_ref": "...", "local_path": null}],
  "citations": [{"title": "...", "url": "..."}],          // DR web sources; NOT downloaded
  "status": "complete|partial|error",
  "partial": false
}
```

**Write discipline (lose nothing):** eager-write the turn record (prompt + conversation ref) at/just-before send; update with the full response on completion; on error/timeout **salvage** whatever partial text is visible with `status` + `partial=true`. The conversation ref is persisted **before** send, so a truncated/failed call is always resumable.

**Attachments vs citations:** *attachments* = downloadable files (generated images, code-interpreter sandbox files, the "Download all plots/CSVs" artifact) — metadata recorded at capture, **bytes downloaded lazily** into `attachments/`. *citations* = DR web-source URLs — stored as a list, never downloaded.

**Conversation tree:** backend-api conversations are message *trees* (edits/regenerations branch). The transcript linearizes the **current branch** (what the UI shows); the full mapping is retained in `raw-mapping.json` so nothing is lost. Branch-aware history is a deferred, not-yet-first-class feature.

## 9. Identity & addressing

- **Canonical key = the conversation id** (`<id>` in `/c/<id>`, also `<chatid>` in `/g/g-p-<projid>/c/<chatid>`); backend-api is keyed by it.
- **Primary selector = URL or bare conversation id — stateless** (no prior registry entry needed to address a known chat; this is why URL is more robust than v1's registry-dependent `--session`).
- **Alias / session-id = optional convenience** in `index.json`.
- **Project id captured as metadata** (`project_id`, nullable). **Projects are near-term:** addressing, scraping, **sending into**, and **creating chats within** a project are all in early scope. Both URL shapes are parsed. (Probe confirms composer/send mechanics are identical under a project URL and captures the new-chat-in-project URL on creation.)

## 10. Concurrency: tab pool + adaptive rate

Maximize concurrency, but treat **tabs as a cache, not state**:

- **Managed tab pool:** lazy-open on demand, **idle-evict** (close tabs not in use), LRU-reclaim at a configurable generous ceiling. Stateless addressing makes re-opening an evicted conversation cheap.
- **Adaptive send-rate** (not an artificial low cap): ramp up to "as many as we can manage," **back off on rate-limit/Cloudflare signals**, with a small **politeness floor** between sends. These safety nets are non-negotiable — they protect the single operator account from being flagged (the no-spamming rule) — but impose no arbitrary low ceiling. Reads (scrape/backend-api) run parallel; sends are rate-governed. The persistent `Session` is the single owner of both pool and budget.

## 11. Model & tools (general label-driven abstraction)

One general mechanism for both menus: **open the Radix menu → enumerate options in the portal (`[data-radix-popper-content-wrapper]`) → select by display label**, fail-closed if absent. Model tiers are `menuitemradio`; model families are a `menuitem` submenu; the "+"/More menu holds modes, toggles, and app connectors.

- **Deep Research is a tool, orthogonal to the model** — recorded as a separate `active_tools` entry, composable with any model. No DR special-casing.
- **Near-term validated set:** model = Pro Extended (+ the scrape conversation's model); tool = Deep Research.
- DR completion via backend-api poll (long-running); report + citations captured via §5.

## 12. `status` (detailed status of tool)

- **Global:** version; CDP endpoint reachable (preflight `curl -s --max-time 5 http://127.0.0.1:9222/json/version`); browser attached + profile; **signed-in vs login-wall**; selector-map channel + validity; data-dir + #conversations + total turns + pending attachment downloads; concurrency/rate state; last error.
- **Per-conversation (`status <conv>`):** model, active tools, #turns, last-turn time/role, pending attachments, branch info.

## 13. Safety invariants (from charter — non-negotiable for every node)

CDP-attach only; **no Playwright-launched browser** (Cloudflare blocks it); **no stealth/anti-detection ever**; domain allowlist (chatgpt.com / openai.com / auth domains / oaiusercontent etc.); **inspect only tabs the tool itself opens** (never operator/other tabs — leak risk); **never quit the browser** (detach only); preflight CDP before any real leg; **login/Cloudflare challenge → STOP, log `HUMAN-ACTION-NEEDED`, poll read-only**; login is **never** automated; real-site legs are **operator-attended** (never CI/cron/unattended). Never `git push`; never move/commit `stable`; never `uv tool install/upgrade/reinstall`.

## 14. Channels

- **`mock`** — deterministic, offline; the default acceptance substrate (`uv run pytest`).
- **`cdp`** — attended real (operator-launched signed-in Chromium at `:9222`).
- **Dropped:** the v1 Playwright-*launched* persistent-profile `real` channel — launched browsers are Cloudflare-blocked, so it added no real capability.

## 15. Out of scope / deferred

- **Dropped (over-engineered, per operator):** the v1 bundle/patch/apply round-trip (`bundle.py` + `patch.py`, ~2,000 lines). Replaced by **general attachments in/out**. "Apply a returned patch" may return later as an optional consumer layer.
- **Deferred:** branch-aware history as a first-class feature (raw tree is retained meanwhile).

## 16. Ground-truth probe checklist (mission M2 — attended, de-risks the design)

The design rests on assumptions that must be verified against the live site before heavy build:

1. **Backend-api capture:** confirm the conversation endpoint, its response shape, that `content.parts` carries canonical markdown, and that it is reachable via in-page `fetch` in the operator's session.
2. **Deep Research representation** in that JSON (report body, citations, search metadata) — and the attachment/file reference shape.
3. **Project send/create:** composer/send identical under `/g/g-p-…/c/…`; how a new chat in a project is created and its resulting URL.
4. **Live selectors:** composer, send button, model menu + options (incl. family submenu), tools menu, copy button, new-user-turn detection, login-wall/Cloudflare markers.
5. **Clipboard fallback viability** over CDP against real Chrome.
6. **Empirical rate behaviour** (what backoff signals look like).

Probe discipline: inspect **only** tool-opened tabs; never read operator tabs (leak risk); preflight CDP; precise-match if any verbatim read is unavoidable.

## 17. Gotcha → fix traceability (the four filed issues)

| Issue | Fix in this spec |
|---|---|
| `capture-renders-dom-not-raw-markdown` (silent math corruption) | §5 backend-api canonical markdown primary; annotation fallback; fidelity acceptance. |
| `cdp-send-noop-returns-stale-response` (silent no-op send) | §6 new-turn baseline + `PromptNotSubmittedError` + idle-reload + wait-for-composer. |
| `response-truncated-drops-out-file-and-session` (+ 600s ceiling) | §7 no hidden ceiling + backend-api poll; §8 eager-write + partial-salvage. |
| `out-suppresses-stdout` | §4 stdout **and** `--out`. |

## 18. Testing & acceptance

- **Mock-first:** every offline-provable behaviour proven against the `mock` channel; `uv run pytest` is the acceptance command (inspect artifacts, not exit codes).
- **Falsifiable tests:** a test that cannot fail proves nothing; capture/cache/completion correctness must be checkable against an authoritative signal, not self-reported. Real-site vs mock-only claims kept strictly separate.
- **Adversarially review every GPT-facing prompt** before sending — wording predetermines outcomes (past bugs: a base64 directive killed the download path; a recall prompt contained its own answer). Want a file → ask for a file.
- **`VERIFICATION.md` re-issued** honestly for the new library with a falsifiability + prompt-quality lens — not a green exit. The old `VERIFICATION.md` verifies the v1 library and goes stale on rewrite.
- **Real legs operator-attended**, never unattended.

## 19. Mission sequence

`M1` archive old library + scaffold (preserve dirty `driver.py` via stash, non-destructive) → `M2` **attended ground-truth probe** (§16) → `M3` best-of-N detailed design (informed by M2) → `M4` Phase-1 offline core (library API, store, mock, completion, eager-write/salvage, stdout+out) TDD → `M5` backend-api capture + `scrape` + verified send over cdp → `M6` **run the scrape of `/c/6a316aa8…` + verify fidelity** (the pressing deliverable) → `M7` model/tools + keep-pushing loop + tab-pool/rate → `M8` independent best-of-N verification + re-issue `VERIFICATION.md`.
