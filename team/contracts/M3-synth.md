# M3 Synthesizer — one coherent detailed design (DESIGN ONLY)

**Read first, in full:** `team/contracts/M3-common-constraints.md`, then the **five lens outputs** `team/evidence/reports/M3-work/lens-1-api.md`, `lens-2-persistence.md`, `lens-3-capture.md`, `lens-4-concurrency.md`, `lens-5-cli.md`, then the sources `docs/REWRITE-SPEC.md`, `team/evidence/handoffs/M2-ground-truth-probe.md`, `team/charter.md`, `.claude/skills/manager/references/agent-rigor.md`.

**Your job (best-of-N synthesis):** produce **ONE coherent, implementable detailed design** from the five lenses. Keep the strongest elements; **reconcile conflicts** (especially at the seams — see below); justify non-obvious selections; cut accreted complexity (Occam). Where lenses disagree or leave a gap, **decide and state why**, or record it as an explicit open question for the lead. Do not merely concatenate the lenses — integrate them.

**Write your deliverable to:** `team/evidence/reports/M3-detailed-design.md` (this is THE M3 deliverable; begin with the `STATUS:` line, then a 1-paragraph overview).

## Seams you MUST reconcile (cross-cluster coherence)
- The **`Session` API result object** (lens 1) must expose exactly the fields the **JSONL record** (lens 2) stores and the **capture pipeline** (lens 3) extracts — one consistent field set (`message_id`, `parent_id`, `content_markdown`, `model{slug,display}`, `active_tools`, `kind`, `created_at`, `attachments`, `citations`, `status`, `partial`).
- The **visible-vs-hidden node classification** (lens 3) must match the **linearization** (lens 2) that consumes it.
- The **tab pool + rate budget** (lens 4) must be owned by the persistent `Session` (lens 1); reads parallel, sends governed.
- The **CLI verbs** (lens 5) must map 1:1 to `Session` methods (lens 1); the **error taxonomy** (lens 5) must cover the failure modes every other lens raises (auth-headers-unobtainable, capture-fail-closed, completion-timeout-with-salvage, prompt-not-submitted, cdp-unreachable, login-wall, allowlist).

## Required sections (the M3 contract's output spec — all must be present and concrete)
1. **Architecture overview** — library-core + thin CLI + persistent `Session`, no daemon; capture/action asymmetry; atomic-op vs persistent-Session.
2. **Module list + responsibilities + key signatures** — every module (`session`, `capture`, `send`, `completion`, `menus`, `store`, `identity`, `channels/{base,mock,cdp}`, `selectors/`, `errors`, `allowlist`, `cli`), with typed public signatures. Include the **channel abstraction** (the browser seam enabling the offline mock).
3. **The JSONL transcript schema** (every field + type + semantics) + data-dir layout + index.json + the tree→current-branch linearization + DR-turn-by-`turn_exchange_id` handling + unified attachment representation covering all M2 shapes + citations-separate-from-attachments + eager-write/partial-salvage write discipline + atomic-write mechanics.
4. **The capture pipeline** — auth/OAI-header acquisition (intercept the page's OWN `/backend-api/conversation` request; **never persist/log the token**; fail-closed if unobtainable), in-page fetch, ~17MB/~5k-node stream-then-persist handling, `mapping`→canonical-markdown extraction, and the **fail-closed fallback chain** (copy-button → KaTeX annotation → DOM textContent) with exact triggers.
5. **Completion detection** — backend-api poll primary (`async_status`/`is_complete`/`is_finalizing`/`pro_progress`/node `status`; consider `/stream_status`) + DOM-consensus fallback gated on new-turn baseline; **no hidden ceiling** (`timeout` = no-activity window; `max_total_wait` default unbounded); salvage on timeout.
6. **Send & action strategy** — verified-send (baseline `message_id` → new-turn poll → `PromptNotSubmittedError` → wait-for-composer → idle-reload); verified model/tool selection via label-driven Radix enumeration.
7. **Concurrency model** — tab pool (lazy-open/idle-evict/LRU) + adaptive send-rate (ramp/backoff/politeness-floor) + single-owner budget (shared-resource-ceiling) + ~3-way modest concurrency; safety (own-tabs-only, never-quit).
8. **CLI verbs** — the full table (`ask`/`create`/`scrape`/`history`/`export`/`fetch`/`loop`/`status`) with flags, behavior, stdout+`--out`, machine-readable `status`.
9. **Error taxonomy** — the named hierarchy + retryability + exit codes.
10. **Recommended M4/M5 build-step sequence** — concrete ordered steps (M4 = offline core TDD against mock; M5 = backend-api capture + scrape + verified send over cdp), naming which modules/tests each step delivers and the falsifiable acceptance for each.
11. **Design decisions & rationale** + **Open questions for the lead** (anything needing live-site confirmation in M5, or an operator decision).

Honor EVERY M2 ground-truth fact, EVERY gotcha fix, EVERY safety invariant (common §2–§4). Be the **simplest correct** design — flag and cut any over-engineering you find in the lenses. End by listing which lens each major decision came from (traceability for the verifiers).
