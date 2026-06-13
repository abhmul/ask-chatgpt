# MISSION-006 — Real-site enablement: opt-in real tier, selector discovery, UC1–3 real acceptance (D-002)

**Mission type:** implement (tier plumbing) + real-site discovery/acceptance (operator-consented per D-002) + best-of-N verification.
**Dispatched by:** ask-chatgpt team lead, 2026-06-12.
**Wall-clock estimate:** `ESTIMATE: M-006 150m` (flag 2× = 300 min).
**Real-message pacing (operator-corrected 2026-06-12): NO hard message cap.** The earlier "≤30 / T2≤12 / T3≤15" was a self-imposed fiction; removed. Interact human-paced and attended; NEVER programmatically spam chatgpt.com (no rapid-fire loops; small waits between sends). Log every real message (timestamp, purpose, conversation) to `tmp/real-audit-<ts>/messages.log` for transparency/debugging — it is NOT a rationing budget. Use as many messages as the work genuinely needs; never skip a diagnostic or continuity message to "save budget." Stop only on rate-limit/honest-failure signals or completion.

## Read FIRST

1. `docs/DECISIONS.md` — **D-002 is this mission's charter** (tiering, budget, headed, login-never-automated, domain allowlist); D-001 still governs channel layering.
2. `docs/runbooks/observe-chatgpt-unknowns.md` — the 10 unknowns T2 resolves (now agent-driven).
3. `docs/runbooks/real-site-acceptance.md` — the UC1–3 real proofs T3 executes (now agent-driven; keep the doc as the manual alternative — update it only if it contradicts what you actually did).
4. `orchestration/handoffs/MISSION-005-handoff.json` + `VERIFICATION.md` — current verified state.
5. `orchestration/state/M-006-state.json` — create, keep resume-ready.

## Environment facts (transcribe into worker contracts; verify, don't assume)

- Operator is signed into chatgpt.com in system **Chromium** (and Firefox — fallback lane ONLY, unused unless Chromium attach is impossible; report before switching). Likely profile: `~/.config/chromium` (Arch). NEVER read/copy/log profile CONTENTS — the path is opaque config passed to Playwright.
- **Profile lock:** a RUNNING Chromium holds `SingletonLock` in the profile dir — `launch_persistent_context` on it will fail. Preflight: detect the running-browser/lock condition (e.g. the launch error itself, or lock file existence as a hint) → raise the named actionable error ("Chromium appears to be running; close it and re-run") and STOP that leg. Do not kill the operator's browser. Do NOT delete lock files.
- **Version mismatch gotcha:** Playwright's bundled chromium may refuse/corrupt a NEWER system-Chromium profile. Prefer `executable_path=/usr/bin/chromium` (the system binary) with the system profile; the driver has channel/executable knobs (M-002). If the system binary + Playwright protocol mismatch blocks automation, REPORT (do not improvise with profile copies).
- **Headed only** on the real account (D-002). Human-paced interaction (no rapid-fire sends; small waits between actions).
- **Login is NEVER automated.** If the session is logged out → `LoginRequiredError` with actionable message, STOP the leg. Never touch login forms, never test logout, never sign out.
- Real-site legs SERIALIZE (one browser, one account — never two real workers concurrently). Mock-tier work may overlap them.

## Task plan

- **T1 tier plumbing (single editor, mock-only, TDD):** `real_site` pytest marker; default run deselects it (`addopts`-level `-m "not real_site"` or equivalent) AND real tests skip unless `ASK_CHATGPT_REAL=1` (double gate; both proven by tests: a guard test asserts the default run collects zero real_site tests). Socket guard stays autouse for the default tier; real tier instead installs a **browser-level domain allowlist** (Playwright route interception: chatgpt.com + asset/CDN domains discovered at T2; everything else aborted + logged). Profile preflight helpers (lock → named error; logged-out detection — URL/redirect heuristic, no credential reads). Full default suite stays green (clean `uv run pytest` unchanged: 121+ tests, zero real_site collected).
- **T2 real-site selector discovery (ONE worker, real, human-paced):** headed persistent context on the operator profile (preflight first). Resolve the observe-runbook unknowns empirically: selectors for composer / send / latest-assistant-turn / completion signal / copy affordance / model menu / upload input / download affordance; session pinning via conversation URL (open chat, note URL, reopen by URL); model-selection hooks; whether responses offer file downloads (ask GPT to produce a small downloadable file; observe artifact + Playwright Download event); zip upload acceptance (attach a tiny zip; observe). FILL `src/ask_chatgpt/selector_maps/real.json` (fail-closed schema; only verified selectors). Findings report with per-unknown answers + evidence (URLs anonymized to path-shape, no account identifiers) + asset-domain list for T1's allowlist → `orchestration/reports/M-006/discovery.md`. Log every message.
- **T3 real-site UC1–3 acceptance (ONE worker, real, human-paced, AFTER T1+T2):** with `ASK_CHATGPT_REAL=1`, run the real halves: UC1 — `ask_chatgpt()` twice on one session_identifier (continuity via URL pinning) + one `model_settings` call; UC2 — tiny bundle (2–3 small text files) out → ask GPT for a patch-bundle edit → retrieve (download-primary; fenced fallback if no download) → apply to a temp root → diff matches; UC3 — same via the `ask-chatgpt` CLI (one prompt + the --session continuity rerun). Honest-failure real checks LIMITED to safe ones: nonexistent-session id; (NO logout tests, NO rate-limit provocation). Raw artifacts (responses, results.json, the patch bundle, the audit log) → `tmp/real-accept-<ts>/`. Where a D-001 assumption meets reality, RECORD it (DOM read reliability vs copy; download availability) — do not redesign mid-leg.
- **T4 verification — best-of-N panel (N=3 + synthesis; non-producers):**
  - T4a evidence audit: T2/T3 artifacts internally consistent (message log ≤ budgets, counts match audit; continuity evidence real; diff evidence real; no credential/account-identifier leakage in ANY artifact or report — grep for cookie/token/email patterns); default-tier purity re-proven (clean `uv run pytest` → zero real_site collected, socket guard intact).
  - T4b D-001/D-002 conformance: real tier double-gate works; allowlist enforced (evidence of aborted off-domain requests or a deliberate probe); headed + serialized + login-never-automated honored per artifacts; selector map fail-closed schema preserved (unverified keys absent, not guessed).
  - T4c empirical-findings review: discovery answers vs the 10 unknowns (complete? evidence-backed?); D-001 revisit triggers evaluated (is DOM-primary still right on the real site? is download-primary real for bundles?) → explicit recommendation with evidence.
  - T4d synthesis → update **`VERIFICATION.md`** real-site scope section (mock-proven AND NOW real-proven items, with artifact pointers; remaining unknowns honest) + `orchestration/reports/M-006/verify.md` with final `VERDICT: PASS|FAIL`.
- Manager: handoff (telemetry as literal top-level JSON fields per D4-fixed convention + bare lines in final log), state DONE, closeout commit `M-006:`. If profile locked / logged out at T2: complete T1, handoff PARTIAL with the EXACT operator action ("close Chromium" / "sign in"), recommend immediate resume — do not idle-wait for the operator inside the mission.

## SAFETY BLOCK — transcribe VERBATIM into every worker contract (workers inherit nothing)

- Real-site contact is permitted ONLY in T2/T3 legs, human-paced and attended, every message logged to the audit artifact; NEVER programmatically spam chatgpt.com (no rapid-fire/unattended loops). NO hard message cap. Default-tier tests stay loopback-only; the socket guard for the default tier must never be weakened.
- HEADED browser only; human-paced; one real worker at a time; never headless on the real account; never two real sessions concurrently.
- NEVER automate, test, or touch login/logout; logged-out → named actionable error, STOP. NEVER read/copy/store/log credentials, cookies, session tokens, or browser-profile contents; the profile path is opaque config. No account identifiers (email, name, org) in any report, artifact, code, or commit.
- Do not kill the operator's browser; do not delete lock files; profile locked → named actionable error, STOP the leg.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive READ-ONLY. Never write `.claude/`/`.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. Ephemeral ports for the mock. NEVER `git push`. ESTIMATE BEFORE EXECUTE.
- End report with `T<ID>-STATUS: DONE|BLOCKED` last line.

## Telemetry + worker mechanics (unchanged)

- Workers: `START_TIMESTAMP:`/`END_TIMESTAMP:` (`date -Iseconds`) + `ESTIMATE: T<ID> <min>m`; manager derives ACTUAL from run-dir metadata (pi self-timing hallucinated). Real legs additionally report `MESSAGES_USED: <n>`.
- pi via `bash .claude/skills/orchestration/references/pi-worker-watch.sh --wait-seconds 480 "<pointer>"`; FOREGROUND `--wait-seconds 480 --watch` loops (Bash timeout 600000 ms; you die at turn end; NEVER background a watch). Worker contracts under `orchestration/tasks/M-006/`, self-contained, report cap ~250 lines.
- Headed-browser note: T2/T3 workers run on the operator's desktop session — `DISPLAY`/Wayland env must reach the spawned browser; if no display is reachable, that is a named BLOCKED (report it; do not fall back to headless).
