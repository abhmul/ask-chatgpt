# MISSION-009 — Harden `ask-chatgpt` for agent use: real UC2 closeout + real model-selection + short-response completion + consumer usage guide. REAL SITE (+ offline guide).

**Status:** DISPATCHED 2026-06-13. **Manager:** headless Opus under `claude-orchestrator-watch.sh`. **Editor:** pi, single editor. **ESTIMATE:** 135m (flag 270m); real-site human-paced.

## Why
Workstream A is complete + verified (`VERIFICATION.md` M-008b gate). The operator asked "is this ready to be used by other agents?" and chose **harden for agent use** over building Deep Research (deferred). Close the gaps that block another agent from relying on the tool against real ChatGPT: real UC2 round-trip, real model-selection, the short-response completion edge, and a consumer usage guide. (Deep Research / general add-ons = a later mission.)

## HARD CONSTRAINTS — REAL SITE (read `docs/DECISIONS.md` D-002 + the charter)
- CDP attach ONLY; preflight `curl -s http://127.0.0.1:9222/json/version` FIRST → STOP `CDP_UNREACHABLE` if down (never launch a browser).
- NO stealth; login NEVER automated; ANY challenge/logout → STOP + `HUMAN-ACTION-NEEDED` + poll READ-ONLY ~10min, never click through.
- Tab hygiene: own tabs only; never touch operator tabs; `close()` = detach, never quit.
- Human-paced, NO message cap, no spamming; per-message audit log. Never read/store/log credentials/cookies/tokens/profile; NO account identifiers or literal `/c/<id>` in artifacts (redact).
- Default tier stays loopback-mock-only (`real_site`+`ASK_CHATGPT_REAL=1` double-gate); `uv sync --all-groups`; NEVER `git push`; telemetry v2 (real `date -Iseconds`; pi minutes hallucinated). RED-first for behavior changes; keep the suite green.

## Read first
`VERIFICATION.md` (M-008b gate + 5 follow-ups); `orchestration/reports/M-008b/` (`verify.md`, `T4-download-capture.json` = recorded download selector, `real-audit-log.md`); `scripts/m008b_real_probe.py` (probe pattern); `src/ask_chatgpt/selector_maps/real.json`; `src/ask_chatgpt/{api,cli,driver,patch,bundle,readers}.py`; `docs/DECISIONS.md`; the charter.

---

## T1 — Real UC2 full round-trip closeout (real)
1. **Populate `real.json:download_artifact`** with the verified selector recorded in M-008b (the "Download the patch bundle" affordance; find it in `orchestration/reports/M-008b/`). Selectors-as-data, fail-closed: if not reproducible now, leave empty + report.
2. **Real UC2 round-trip via the PRODUCTION path** over CDP: upload a small bundle → elicit a real downloadable `.zip` (the M-008a prompt) → capture via the production download path → validate + **APPLY** + diff + verify **content-correctness** on the REAL bytes (e.g. `favorite_color` red→blue, siblings unchanged). Closes "UC2 real apply+diff not run." Honest `DownloadUnsupportedError` if no file affordance.

## T2 — Short-response completion edge (real; UC1 core for everyday use)
Send several SHORT real prompts (one-word / one-line answers — e.g. "Reply with just the word: ping"). Confirm `ask_chatgpt()->text` returns each WITHOUT a spurious `ResponseTruncatedError` (the M-008b fail-closed edge: stop button visible < one 0.1s poll → `streaming_seen` never set → spurious truncation). Record hit/miss per prompt. **If it bites on normal short responses, fix it** — RED-first. Candidate fix: allow completion when `completion_marker` present AND text stable ≥3s even if `streaming_seen` was never observed (the never-saw-streaming case ONLY), WITHOUT reopening the micro-pause clip — prove via the existing `_MicroPauseCompletionState` + `_PrematureGlobalMarkerState` tests still passing PLUS a new short-response test. Consider also a faster initial poll. Keep all 209 mock tests green.

## T3 — Real model-selection wiring (B-2; makes `model_settings` work live)
1. Discover the model picker in the composer/header over CDP; capture VERIFIED selectors for the model menu trigger + per-model option entries. Populate `real.json` `model_menu` / `model_option` (currently empty/fail-closed). Selectors-as-data; fail-closed if not mappable.
2. Wire `model_settings` so a requested model is actually selected on real before sending (the code path exists, mock-proven; make it real). **Prove the selection took effect via UI STATE** (the picker/header reflects the chosen model) — NOT by asking the model what it is (unreliable). If the requested model is absent from the menu, raise a named actionable error (fail-closed), do NOT silently send on the wrong model.
3. Honest scope: which models are available depends on the operator's plan; document what was observed.

## T4 — Consumer usage guide (offline; AFTER T1–T3 so it reflects real state)
Write `docs/USAGE.md` — a concise guide for ANOTHER AGENT consuming this tool. Include: the library call (`from ask_chatgpt import ask_chatgpt`) + the `ask-chatgpt` CLI invocation; the **CDP-browser prerequisite** (operator launches `chromium --profile-directory='Profile 1' --remote-debugging-port=9222` signed into chatgpt.com; the tool attaches via `--channel cdp --cdp-endpoint http://127.0.0.1:9222`); `--session`/`session_identifier` continuity; bundles (`--files/--dirs/--out/--apply/--dry-run/--root`); `model_settings`; and the NAMED ERROR MODES (`LoginRequiredError`, `ChallengePresentError`, `DownloadUnsupportedError`, `ResponseTruncatedError`, `SessionNotFoundError`, etc. — read `src/ask_chatgpt/errors.py` for the actual set) with what each means + the operator action. Be HONEST about caveats: attended/human-browser-required, consumes the operator's quota, real model-selection/UC2 scope as actually proven in T1–T3, the short-response behavior, and that default tier is mock-only. Tie claims to `VERIFICATION.md`.

## T5 — Verify (producer-side) + handoff
Honest `verify.md`: per-item real status (UC2 real round-trip PASS/honest-fail with evidence; short-response sample + any fix; model-selection real PASS/fail-closed; usage guide accuracy vs ground truth). Real audit log. `orchestration/handoffs/MISSION-009-handoff.json` with per-item status, commit shas (no push), any `CDP_UNREACHABLE`/`HUMAN-ACTION-NEEDED`, and `GATE: AWAITING-TEAM-LEAD-SPOTCHECK`. Verify lenses via pi / own analysis (no `claude` subagents — you lack Agent/Task). The MANDATORY lens: does the usage guide overclaim relative to what is real-proven?

## Deliverables
`real.json` `download_artifact` + `model_menu`/`model_option` populated (if reproducible); real UC2 round-trip + model-selection + short-response evidence (+ any completion fix, RED-first); `docs/USAGE.md`; `orchestration/reports/M-009/{discovery.md,verify.md}` + audit log; handoff. **Deep Research / general add-ons are OUT of scope (a later mission).**
