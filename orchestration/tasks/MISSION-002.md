# MISSION-002 — Core build: scaffold, mock-ChatGPT fixture, browser layer, `ask_chatgpt() -> text`, UC1 acceptance

**Mission type:** implement (TDD/RED-first; single-editor for source-mutating legs; best-of-N design is ALREADY DONE — M-001).
**Dispatched by:** ask-chatgpt team lead, 2026-06-11.
**Wall-clock estimate:** `ESTIMATE: M-002 120m` (flag threshold 2× = 240 min).

## Read these files FIRST (in order)

1. `docs/DECISIONS.md` — **D-001 is the recorded design decision; it is binding.** Text: DOM-primary bounded reader + copy-button fallback behind one `ResponseReader` interface. Bundles (M-003 scope, but the fixture must support them): download-capture primary + checksummed fenced-base64url fallback. Level B survivals: loopback-only tests, selector maps as data, fail-closed selectors, adversarial fixtures, no credential reads, no history sweep.
2. `orchestration/reports/M-001/decision-memo.md` — **§6 is the mock-fixture requirements spec (binding); §7 is the runbook unknowns list.**
3. `README.md` — the product spec (use case 1 + acceptance shape + honest failure modes are this mission's scope).
4. `orchestration/state/M-002-state.json` — create and maintain it (resume-ready at all times; the previous mission was recovered solely because of this file).

## Objective

A `uv` Python project in this repo where `ask_chatgpt(prompt, session_identifier=..., model_settings=...) -> str` works end-to-end against a local loopback mock-ChatGPT fixture, with automated acceptance green and ZERO chatgpt.com contact. Real-site code paths (channel="real": operator profile attach, chatgpt.com URLs) are built but NEVER exercised by tests — they are proven later via operator runbooks.

## Deliverables (all committed, prefix `M-002:`)

1. `pyproject.toml` + `src/ask_chatgpt/` package: browser session controller (mock-vs-real channel knobs), selector-map loader (maps are JSON data under `src/ask_chatgpt/selector_maps/` or similar), completion detector, `ResponseReader` interface with `DomReader` (primary) + `CopyButtonReader` (fallback), session registry (`session_identifier -> conversation ref/URL`, JSON store, path overridable for tests), `model_settings` selection where the UI allows, named error types (login required, session not found, model unavailable, response truncated, selector unavailable, upload/download unsupported — actionable messages), and the public `ask_chatgpt()` function.
2. `tests/` — unit + E2E vs the fixture; `tests/fixtures/<mock fixture>` implementing memo §6 (loopback bind only; adversarial/booby-trap assistant DOM; stable AND virtualized selector variants; copy button writing the browser clipboard; download artifact card serving a real zip with Content-Disposition; fenced-base64 variants; `<input type=file>` upload affordance; honest-failure states incl. login-required, session-not-found, model-unavailable, truncated, rate-limited). Fixture supports bundle affordances NOW (M-003 consumes them).
3. A network guard in the test suite: automated tests must be provably unable to reach non-loopback hosts (e.g. a pytest fixture that blocks/asserts socket connections to non-127.0.0.1, plus Playwright route interception in fixture-driven tests). The verify leg must demonstrate the guard trips on a deliberate violation.
4. `scripts/accept_uc1.sh` — scripted use-case-1 acceptance: spins the fixture on an EPHEMERAL port, calls `ask_chatgpt()` (same session id twice to prove continuity; a model_settings call; at least one honest-failure case), writes raw artifacts (stdout, JSON results, exit codes) to `tmp/accept-uc1-<ts>/`, exits non-zero on any failure.
5. `docs/runbooks/observe-chatgpt-unknowns.md` — operator OBSERVATION runbook generated from memo §7 verbatim items (manual, consent-gated, no tool required; lets the operator resolve empirical unknowns in parallel with M-003).
6. `orchestration/reports/M-002/verify.md` (independent, see Verification) + `orchestration/handoffs/MISSION-002-handoff.json`.

## Suggested task slicing (manager refines; EDITING LEGS SERIALIZE — one editor at a time in this shared tree)

- T1 scaffold: `uv init`-style pyproject (package `ask_chatgpt`, `src/` layout), dev group: pytest + playwright; `uv sync --all-groups`; Playwright browser: CHECK `~/.cache/ms-playwright` first (predecessor likely cached chromium); if absent, ESTIMATE then `uv run playwright install chromium` (~150 MB download — state it). Smoke test green.
- T2 fixture core: loopback HTTP server (ephemeral port), conversations keyed by stable refs, composer/send, latest-assistant-turn rendering + completion marker, reset/inspection endpoints, selector-map JSON for the mock. TDD.
- T3 fixture adversarial + failure + file affordances: memo §6 booby-traps, virtualized variant, copy button + clipboard write, download artifact (real zip bytes), fenced-base64 payload variants, upload input, all honest-failure states, per-test scriptable assistant behavior. TDD.
- T4 driver core: Playwright session controller (channel="mock" loopback URL vs channel="real" chatgpt.com + persistent operator profile path — real path never tested), selector-map loader (fail-closed: missing/stale selector -> named error, never guess), completion detector, open-or-create conversation, model selection. TDD vs fixture.
- T5 readers: `ResponseReader` interface; `DomReader` (latest completed turn only, truncation/end-marker detection) primary; `CopyButtonReader` fallback; order configurable, D-001 default. Must pass adversarial fixtures (booby-trap text never returned). TDD.
- T6 session registry + errors module (pure python, can interleave with T2/T3 if a second worker is idle — but NEVER two editors in the tree concurrently; prefer strict serialization).
- T7 `ask_chatgpt()` integration + UC1 E2E tests + `scripts/accept_uc1.sh` + network-guard wiring.
- T8 observation runbook doc (NON-EDITING of source; may run parallel to any single editor leg).
- T9 INDEPENDENT verification (non-producer worker): fresh `uv sync --all-groups`; full `uv run pytest` (serialized, ephemeral ports) + `scripts/accept_uc1.sh`; inspect produced artifacts (not exit codes alone); confirm network guard trips on deliberate violation; confirm D-001 conformance (DOM-primary default, fail-closed selectors, no credential reads, booby-trap never returned); per-check verdicts + final `VERDICT: PASS|FAIL` + `T9-STATUS:` last line → `orchestration/reports/M-002/verify.md`. On FAIL: manager revives the offending leg (REWORK-CAUSE coded), re-verifies.

## SAFETY BLOCK — transcribe VERBATIM into every worker contract (workers inherit nothing)

- Automated tests and ALL mission work NEVER contact chatgpt.com/openai or any external network service; the mock fixture binds loopback (127.0.0.1) ONLY, on EPHEMERAL ports (never assume a fixed port is free — the operator runs long-lived daemons). The ONLY permitted external download is Playwright chromium via `uv run playwright install chromium` IF not already cached (check `~/.cache/ms-playwright` first; estimate before executing).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents; none appear in code, tests, logs, commits, or reports. The real-channel code path takes a profile DIRECTORY PATH as config; it never inspects profile contents.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ its `tmp/`). The archive `/home/abhmul/Documents/weak-simplex-conjecture` is READ-ONLY prior art (never its `archive/` or `human/` dirs). Never write `.claude/` or `.agents/`. Never touch the shared agent venv (`~/.local/share/agent-python/.venv`) — this repo's deps live in its own uv project.
- `uv sync --all-groups` ALWAYS (bare `uv sync` silently uninstalls non-default groups → phantom ModuleNotFoundError). Serialize pytest runs in this tree. Kill only processes your own run started.
- NEVER `git push`. ESTIMATE BEFORE EXECUTE (state expected wall-clock + output volume before any major command; detach anything >2 min).
- End your report with `T<ID>-STATUS: DONE|BLOCKED` as the LAST line.

## Telemetry v2 (lesson from M-001: pi minute self-reports are HALLUCINATED — ~15× off)

- Worker contracts REQUIRE: run `date -Iseconds` at start and end and write literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines in the report. Workers still emit `ESTIMATE: T<ID> <min>m` (their estimate is meaningful) but the manager derives `ACTUAL` from `.pi-workers/<run>/metadata.txt` `started_at` + report `END_TIMESTAMP` / file mtimes — NEVER from worker minute self-reports.
- Manager handoff: `ESTIMATE: M-002 120m`, derived `ACTUAL: M-002 <min>m`, end timestamp, `REWORK-CAUSE:` per rework leg.

## Worker mechanics

- pi (GPT 5.5 xhigh) via `bash .claude/skills/orchestration/references/pi-worker-watch.sh "<pointer to task file>"` from repo root; FOREGROUND blocking watches per your charter's detached-session discipline (you die at turn end — never end your turn with children running).
- Worker contracts: one file per task under `orchestration/tasks/M-002/`, fully self-contained (exact deliverable paths, the files to read — `docs/DECISIONS.md`, memo §6, this contract's relevant section — the SAFETY BLOCK verbatim, telemetry v2 lines, report-length cap ~200 lines).
- Max 3 pi workers concurrent (team cap), but editing legs serialize; the operator's pi account is SHARED with other programs — if pi launches throttle or fail oddly, drop to 1 concurrent and note it in the handoff.

## Handoff requirements (`orchestration/handoffs/MISSION-002-handoff.json`)

Rigor protocol: `STATUS` token near top; what was verified + evidence (verdicts, artifact paths, the authoritative pytest/acceptance output location); artifacts + trust levels; blockers (exact action); recommended next missions (M-003 readiness: which fixture affordances M-003 consumes); complexity/paradigm signals. State plainly which code paths are mock-proven vs real-site-unproven (operator runbook pending).
