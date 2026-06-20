# Mission M3 — Best-of-N detailed design for the ask-chatgpt v2 rewrite (DESIGN ONLY, non-editing)

You are a detached **Claude Opus MANAGER** for the `ask-chatgpt-dev` team, executing mission M3. **Load and obey** the `manager` skill and `.claude/skills/manager/references/agent-rigor.md` first. You inherit nothing but this contract, the files it names, and your appended charter. Repo: `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`.

## Mission
Produce the CONCRETE detailed design the implementation missions (M4 offline core, M5 capture/scrape/send) will follow. **DESIGN ONLY — no production source changes** (you write a design document, not code). Run it **best-of-N** per agent-rigor.

## Dispatch policy (HARD)
You are an Opus manager; **dispatch your design lenses as pi WORKERS** via `.claude/skills/manager/references/launchers/parent-claude/pi-watch.sh "<pointer to a contract file you write under team/contracts/>"`. **NEVER use the Claude Agent tool.** (If you needed a sub-manager you'd use `claude-watch.sh`, but design lenses are worker-sized.) Monitor with `--watch`. Note: multiple pi-watch launches in one message serialize — launch lenses across messages or budget time accordingly.

## Authoritative inputs — READ IN FULL FIRST
- `docs/REWRITE-SPEC.md` — the approved spec (architecture §2/§3, persistence §8, identity §9, concurrency §10, model/tools §11, CLI §4, gotcha fixes §5–§7, safety §13).
- `team/evidence/handoffs/M2-ground-truth-probe.md` — **AUTHORITATIVE live-site facts.** The design MUST honor these (do not re-derive or contradict):
  - **Backend-api capture works but cookies-only 404s** — it requires the web-app headers (`Authorization` bearer + `oai-client-build-number`/`-version` + `oai-device-id` + `oai-language` + `oai-session-id` + `x-openai-target-path` + `x-openai-target-route`). Design must obtain these from the page's OWN request (intercept the app's request/response on your own tab, or read them) and forward; **never persist/log the token**; fail-closed to copy-button/KaTeX-annotation/DOM.
  - **~17MB / ~5k mapping nodes**, no pagination — design for streaming/efficient handling, not gratuitous full-in-memory.
  - **DR/Pro turns**: no `deep_research` content_type; large `turn_exchange_id` groups (hidden `assistant:thoughts`/`code`/`reasoning_recap` + tool nodes `web.run`/`file_search`/`python`/`container.exec` + a final visible `assistant:text` report in `content.parts[0]`). Citations in `metadata.content_references`/`citations`/`search_result_groups`/`search_queries`.
  - **Attachments**: `metadata.attachments[]`, `content_references[type=file]`, `content.assets[].asset_pointer`, code `metadata.aggregate_result` (ids/pointers; no literal `/files/` URLs seen).
  - **Completion signals**: top-level `async_status`; `metadata.is_complete`/`is_finalizing`/`pro_progress`; node `status`; possibly `/backend-api/conversation/<id>/stream_status`.
  - **Selectors (observed live)**: composer `#prompt-textarea` (contenteditable div, role=textbox); tools `button[data-testid="composer-plus-btn"]`; copy `button[data-testid="copy-turn-action-button"]`; turns `[data-message-id][data-message-author-role]`; **model picker has NO stable test-id** → label-driven Radix enumeration. Clipboard `readText` exists but permission=`prompt` (grant-only).
- `team/charter.md` (your appended role) — domain constraints + safety invariants.

## Best-of-N design (distinct lenses → synthesis → independent verification)
Suggested lenses (each a pi worker, distinct angle):
1. **Library API + module structure** — concrete `Session` object API + atomic-CLI-verb composition + module layout (REWRITE-SPEC §2/§3).
2. **Persistence + schema** — per-conversation store, JSONL turn schema, message-tree → current-branch linearization + raw-mapping retention, attachment representation covering the M2 shapes, DR-turn grouping by `turn_exchange_id`.
3. **Capture + auth-header mechanism + completion** — THE load-bearing piece: exactly how to obtain/forward the web-app auth/OAI headers safely (prefer intercepting the page's own `/backend-api/conversation` request/response over reading the token), the fetch+parse pipeline, fail-closed fallback, completion detection via `async_status`/metadata.
4. **Concurrency** — tab pool (lazy-open, idle-evict, LRU) + adaptive send-rate (backoff + politeness floor); single-owner rate budget on the persistent `Session`.
5. **CLI/loop ergonomics** — verb surface (`ask`/`create`/`scrape`/`history`/`fetch`/`loop`/`status`), keep-pushing loop, stdout+`--out`, error taxonomy (+`PromptNotSubmittedError`), `status` contents.
Then a **synthesizer** (one coherent design) and an **independent verifier** (does it honor every M2 finding + every gotcha fix + every safety invariant? is it the simplest correct design — Occam?).

## Output
- Write the detailed design to `team/evidence/reports/M3-detailed-design.md`: implementable detail — module list + responsibilities + key signatures; the JSONL schema; the capture pipeline incl. auth-header handling + fail-closed fallback; completion detection; concurrency model; CLI verbs; and a recommended M4/M5 build-step sequence.
- Write a manager handoff at `team/evidence/handoffs/M3-design.md` (Status; what was verified; artifacts+trust; blockers; recommended next; complexity/paradigm signals).
- Do **NOT** modify production source (`src/`, `pyproject.toml`), do **NOT** run any real-site/browser leg (offline design only), do **NOT** push. Do **NOT** commit — leave the design doc + handoff for the team lead to review, commit, and fold into `docs/REWRITE-SPEC.md`.

## Acceptance bar
A concrete, implementable design that demonstrably honors **every** M2 ground-truth finding (especially the auth/OAI-header capture requirement and the fail-closed fallback), **every** gotcha fix (verified-send / raw-markdown-capture / no-hidden-ceiling / eager-write+partial-salvage / stdout+--out), and **every** safety invariant; produced by best-of-N (distinct lenses + synthesis + independent verification — not a single sample); simplest-correct. Report honestly; surface open questions for the lead rather than guessing.
