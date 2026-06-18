# MISSION-007 — UC2 real-green (fenced-format alignment) + GAP-15 conversation_ref persistence

**Mission type:** implement (single-editor, TDD/RED-first) + real-site acceptance over CDP (D-002) + best-of-N verification.
**Dispatched by:** ask-chatgpt team lead, 2026-06-12 (operator chose "fenced-format alignment").
**Wall-clock estimate:** `ESTIMATE: M-007 120m` (flag 2× = 240 min).
**Real-message pacing: NO cap** (the earlier ≤30 was a removed self-imposed fiction). Human-paced, attended, NEVER programmatically spam chatgpt.com; log every real message to `tmp/real-audit-<ts>/messages.log` for transparency only; spend what proving UC2 genuinely needs.

## Read FIRST (in order)

1. `docs/DECISIONS.md` — D-001 (fenced-base64url is the bundle fallback and, per M-006, the REAL bundle path since the real site fires no Playwright Download event) + D-002 (CDP attach; human-paced; no stealth; login never automated).
2. `orchestration/reports/M-006/T3-uc2char.md` — **the real-format evidence**: ChatGPT DID emit a valid fenced base64-zip (144-byte zip, matching SHA-256) AND a clean unified diff over the real `.markdown` DOM. This is the ground truth the alignment targets.
3. `orchestration/reports/M-006/verify.md` + `VERIFICATION.md` §M-006 — UC2 PARTIAL rationale, GAP-15 description.
4. `orchestration/state/M-007-state.json` — create, keep resume-ready.

## Operator environment (verify; don't assume)

- The operator's Chromium ('agent' profile = dir `Profile 1`, signed into chatgpt.com) is RUNNING with `--remote-debugging-port=9222` (team lead verified reachable at dispatch). Real legs attach via `connect_over_cdp("http://127.0.0.1:9222")`. If the endpoint is unreachable at preflight: write handoff PARTIAL with `CDP_UNREACHABLE` + the launch command and exit cleanly (team lead re-coordinates) — do NOT idle more than one watch cycle.
- ABSOLUTE real-leg rules (D-002): work ONLY in tabs the tool opens; NEVER touch/navigate/close the operator's tabs; NEVER quit the browser (detach only); login/logout NEVER automated; any Cloudflare/human-verification UI → STOP actions, log `HUMAN-ACTION-NEEDED`, poll read-only up to 10 min, else PARTIAL; NO stealth/anti-detection ever.

## Objective

UC2 (bundle round-trip) GREEN on the real site over CDP — bundle out → ask GPT for a fenced patch bundle → retrieve via the fenced base64url path → apply locally → diff matches — AND the same round-trip still green on the mock. Plus GAP-15 fixed so session continuity uses a properly-persisted `conversation_ref`.

## Task plan (best-of-N is the default for non-editing legs; editing legs serialize)

- **T1 (single editor, MOCK-TIER, RED-first) — fenced-format alignment.** The three things that must agree: (a) `generate_prompt_instructions` / catalogue text in `src/ask_chatgpt/bundle.py` (what GPT is told to emit); (b) `_parse_fenced_patch_bundle` in `src/ask_chatgpt/patch.py` (what we parse); (c) how a fenced block actually renders inside the real assistant `.markdown` turn (per T3-uc2char.md — e.g. code-fence language tags, whitespace/newline normalization, the BEGIN/END markers, manifest + `ZIP_BYTE_COUNT` + `ZIP_SHA256` lines as the real DOM exposes them). RED FIRST: add a mock-fixture variant + test that reproduces the REAL rendered fenced format from T3-uc2char.md evidence and watch the current parser fail; then align prompt+parser (prefer making the parser robust to the real rendering — tolerate the markdown normalization GPT/!the DOM actually produce — over demanding GPT emit something brittle). Update the mock fixture so its fenced payload matches the real rendering, so this stays regression-caught. Full default suite green.
- **T2 (single editor) — GAP-15 conversation_ref persistence.** Real new-chat `conversation_ref` is empty when sampled before the URL settles to `/c/<id>`. Fix: refresh the ref AFTER completion (re-read the settled conversation URL) before the session registry `set()`. RED-first with a mock that simulates empty-then-settled URL; assert the registry stores the settled ref and continuity resolves to the same conversation. Keep fail-closed behavior intact.
- **T3 (real, over CDP, human-paced, AFTER T1+T2) — UC2 + continuity real acceptance.** Preflight CDP. Tiny bundle (2–3 small text files) out → instruct GPT (aligned prompt) to return a fenced patch bundle → retrieve (fenced path) → apply to a temp root → assert diff matches expectation (`UC2_DIFF_OK`). Then a continuity re-check proving GAP-15 (same `session_identifier` resolves to the same real conversation via the persisted ref). Raw artifacts → `tmp/real-accept-m007-<ts>/`; log every message. If GPT's emission still misaligns, capture the exact rendered text and iterate the parser (this is the whole point — spend the messages).
- **T4 — best-of-N verification panel (N=3 + synthesis; non-producers).** One evidence runner: fresh `uv sync --all-groups`; full `uv run pytest` (UC1/UC2/UC3 mock regression — must stay green, incl. the 169 default-tier count or higher); confirm default tier still collects ZERO `real_site` tests; capture the T3 real artifacts. Three parallel lenses over that evidence: (a) correctness/repro (UC2 mock round-trip + real round-trip diff-match real; GAP-15 continuity real); (b) spec-conformance (UC2 obligation green on real + mock; fenced path is the documented real bundle mechanism); (c) safety (no stealth grep-confirmed ABSENT; fail-closed selectors intact; no credential/profile reads; CDP tab-hygiene; login never automated; human-paced audit log present). Synthesis → update `VERIFICATION.md` (UC2 → real-PASS; GAP-15 → fixed) + `orchestration/reports/M-007/verify.md` with final `VERDICT: PASS|FAIL`. On FAIL: revive the offending editing leg (REWORK-CAUSE coded), re-run evidence + failed lens.
- Update `docs/runbooks/real-site-acceptance.md` UC2 section to the aligned fenced format if it drifted. Handoff `orchestration/handoffs/MISSION-007-handoff.json` (STATUS; per-UC verdicts; telemetry literal JSON fields + bare `ESTIMATE:`/`ACTUAL:` lines). Closeout commit `M-007:`. NEVER push.

## SAFETY BLOCK — transcribe VERBATIM into every worker contract (workers inherit nothing)

- Real-site contact ONLY in T3, ONLY via CDP attach to the operator's already-running signed-in Chromium (127.0.0.1:9222); human-paced and attended; every message logged to the audit artifact; NO hard message cap; NEVER programmatically spam chatgpt.com (no rapid-fire/unattended loops). Default-tier tests stay loopback-only; the autouse socket guard must never be weakened; `ASK_CHATGPT_REAL=1` + `real_site` marker double-gate real tests.
- Work ONLY in tabs the tool opens; NEVER touch/navigate/close the operator's tabs; NEVER quit the attached browser (detach only). Login/logout NEVER automated; logged-out/challenge → named actionable stop + `HUMAN-ACTION-NEEDED`. NO stealth/anti-detection of any kind (grep must stay clean).
- PATCH APPLY SAFETY (unchanged): validate the ENTIRE bundle (manifest, SHA-256, byte count, path safety) BEFORE mutating ANY file; reject absolute paths, `..`, symlink escapes; write only within the caller-specified root (+ `tmp/` in tests).
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents; no account identifiers (email/name/org/real conversation ids) in any report, artifact, code, or commit.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive `/home/abhmul/Documents/weak-simplex-conjecture` READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. Ephemeral ports for the mock. Kill only your own processes. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- Hook gotcha: the repo destructive-guard substring-scans command text and false-positives on phrases like `git checkout -- `; use `git stash push -u` for any revert. End every report with `T<ID>-STATUS: DONE|BLOCKED` as the LAST line.

## Singleton discipline (triple-launch recurred 3× in M-006)

- On startup, acquire an atomic singleton lock `tmp/M-007-manager.lock` (record your pid; if a live sibling pid holds it via `kill -0`, write a standdown note and exit cleanly). This prevents duplicate managers from double-driving the real browser.

## Telemetry + worker mechanics

- Workers: `START_TIMESTAMP:`/`END_TIMESTAMP:` (`date -Iseconds`) + `ESTIMATE: T<ID> <min>m` + (real legs) `MESSAGES_USED: <n>`; manager derives ACTUAL from `.pi-workers/<run>/metadata.txt started_at` + report END_TIMESTAMP (pi minute self-reports are hallucinated). Manager handoff carries `ESTIMATE: M-007 120m`, derived `ACTUAL`, end timestamp, `REWORK-CAUSE:` per rework leg, as literal top-level JSON fields + bare lines in the final log.
- pi via `bash .claude/skills/orchestration/references/pi-worker-watch.sh --wait-seconds 480 "<pointer>"`; FOREGROUND `--wait-seconds 480 --watch` loops (Bash timeout 600000 ms; you die at turn end; NEVER background a watch; write your handoff before ending your turn). Worker contracts under `orchestration/tasks/M-007/`, self-contained, report cap ~200 lines.
