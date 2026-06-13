# MISSION-008b — Real-site corrected verification over CDP (the real half of M-008)

**Status:** DISPATCHED 2026-06-13. **Manager:** headless Opus `claude -p` under `claude-orchestrator-watch.sh`. **Editor:** pi (GPT-5.5 xhigh), single editor.

**ESTIMATE:** 120m (flag at 240m). REAL-SITE mission — wall-clock includes human-paced real sends.

## Why this mission

M-008a fixed the GPT-facing prompts (downloadable `.zip`, zero base64; non-circular continuity; non-vacuous truncation) and hardened completion detection — all MOCK-proven and independently gate-PASSED (`VERIFICATION.md` → "M-008a INDEPENDENT GATE"). This mission proves the corrected behavior **on the real site** over CDP, and resolves the two completion concerns the gate flagged. This REPLACES the retracted M-006/M-007 real-site claims with honest, falsifiable real evidence.

## HARD CONSTRAINTS — REAL SITE (D-002; read `docs/DECISIONS.md` D-002 + the charter before any real send)

- **CDP attach ONLY.** Preflight `curl -s http://127.0.0.1:9222/json/version` FIRST. If it is down, STOP immediately with `CDP_UNREACHABLE` in the handoff — do NOT launch a browser yourself (Cloudflare blocks Playwright-launched browsers; M-006 finding). `connect_over_cdp` to the operator's signed-in Chromium.
- **No stealth / anti-detection ever** (independent grep must stay clean). No UA/fingerprint spoofing.
- **Login NEVER automated.** If logged out / profile-locked / any Cloudflare or human-verification challenge appears → STOP, write `HUMAN-ACTION-NEEDED` with the exact state, poll READ-ONLY (no sends) every ~10 min, and surface it. Never click through a challenge.
- **Tab hygiene:** work ONLY in tabs the tool opens; NEVER touch/close the operator's tabs; `close()` = detach, NEVER quit the browser.
- **Human-paced, NO message cap** (operator-corrected): spend the messages the work genuinely needs; small waits between sends; never programmatic spamming/rapid-fire loops. Keep a lightweight per-message audit log (transparency, not rationing).
- **Never read/store/log** credentials, cookies, session tokens, or profile contents. NO account identifiers or literal `/c/<id>` in artifacts, commits, logs, or reports (redact refs).
- Default test tier stays loopback-mock-only; real tests run behind the `real_site` marker + `ASK_CHATGPT_REAL=1` double-gate. `uv sync --all-groups`. Commit working slices; **NEVER `git push`**.
- **Telemetry v2:** real START/END timestamps (`date -Iseconds`); pi self-reported minutes are HALLUCINATED — derive ACTUAL from run-dir mtimes. `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE:` lines in the handoff.

## Read first
`VERIFICATION.md` (CORRECTION + the M-008a INDEPENDENT GATE section); `orchestration/NEXT-SESSION-compacted.md`; `docs/DECISIONS.md` (D-001, D-002); `orchestration/reports/M-008a/PROMPTS-FOR-REVIEW.md` (the prompts you will fire); `src/ask_chatgpt/driver.py:wait_for_completion`; `src/ask_chatgpt/selector_maps/real.json`; this file; the charter.

---

## T1 — Completion robustness follow-up (offline; do FIRST, before real legs)

From the M-008a gate (driver.py:wait_for_completion, real/cdp branch ~352-371):
1. **Add an absolute wall-clock ceiling.** Today the progress-aware deadline extends on every text change with no hard cap → a pathologically growing/oscillating body could wait unbounded. Add an absolute ceiling (a max total wait from first poll, independent of progress) after which it fails closed with `ResponseTruncatedError`. Pick a sane default (e.g. a few minutes; justify it), keep it configurable. RED-first.
2. **Remove the now-dead `_REAL_COMPLETION_STABLE_S` (driver.py:45)** — nothing reads it after M-008a; leaving it implies a stability window still governs completion. (If T2 reintroduces a stability fallback, reintroduce a clearly-named constant for THAT.)
3. Keep the mock path + the full suite green (`uv run pytest` = 206+ passed, 1 deselected, 0 real_site).

## T2 — Validate completion_marker reliability on the REAL site (GATING — the truncation fix depends on it)

The M-008a fix completes on `not streaming_visible AND completion_visible`, where real `completion_marker` = the copy-turn-action button. The gate flagged: if that button is delayed/hover-gated/virtualized at end-of-turn, a COMPLETE turn becomes a false `ResponseTruncatedError`. **Validate from ground truth:**
1. Over CDP, send several real prompts (short and long) and observe, at genuine end-of-turn: does `completion_marker` reliably MATCH, and does `streaming_marker` (stop button) reliably disappear? Record hit/miss per turn in the audit log. Inspect the real DOM (the tab the tool opened) to confirm the affordance is present-and-stable at completion, not hover-only.
2. **If reliable:** keep the affordance-only completion; document the evidence.
3. **If UNRELIABLE:** implement a **hardened stability fallback** — complete on `streaming_marker seen-then-sustainedly-absent` AND body text stable for a LONGER sustained window (robust to the >2s micro-pause that caused the original clip), as an OR with the affordance; or map a more reliable completion affordance into `real.json`. Re-verify it does not reintroduce the micro-pause clip (re-run the T1/M-008a driver micro-pause test) and does not fail-open. RED-first for any logic change.

## T3 — Real truncation / completeness for `ask_chatgpt() -> text` (UC1 CORE)

Flip the M-008a truncation-elicitation harness to `channel="cdp"`. Send the deterministic long-response prompt (180 ordered `LINE-<k> <token>` lines + `__ELICIT_COMPLETE__` sentinel); assert the returned text is COMPLETE (exact ordered lines + terminal sentinel + length ≥ 4096). This is the real proof that `->text` no longer clips (the M-007 `…1F3845_` failure mode). If it clips, the completion design is wrong → iterate with T2. Capture the real response artifact (redacted of any identifiers).

## T4 — Real UC2 downloadable-file round-trip over CDP

1. **Discover + populate `real.json:download_artifact`** (currently empty/fail-closed): drive the rewritten bundle prompt so ChatGPT produces an actual downloadable `.zip`; inspect the real DOM for the download-link affordance; populate the verified selector (selectors-as-data; no guessing — fail-closed if not found).
2. With the rewritten prompt + an uploaded bundle, elicit a **real downloadable file**, capture it via the existing download path (`patch.py` `_scan_download_artifacts`/`_download_candidate_bytes`), validate (structural zip + zip-slip matrix + caps — the full source-agnostic gauntlet) and apply → diff-match. Confirm **changed-files-only**.
3. **Honest failure is a valid outcome:** if the real ChatGPT surface cannot produce a downloadable file (no code/file tool available in that conversation), the correct result is a named `DownloadUnsupportedError`, NOT a base64 text blob — record it honestly and note it as input to Workstream B (tool enablement). Do NOT fall back to claiming success via inline text.

## T5 — Real falsifiable continuity over CDP

Flip the M-008a continuity harness to `channel="cdp"`: turn-1 plants a full-length nonce (only in turn 1); turn-2 (same `session_identifier`, **nonce ABSENT**) asks to recall it → assert the exact nonce returns. **CONTROL:** the identical turn-2 against a FRESH conversation must FAIL to produce the nonce (proves the test can fail). **CROSS-PROCESS:** turn-1 via one CLI process, turn-2 via a separate process (registry-carried continuity). Redact `/c/<id>` refs in artifacts.

## T6 — Honest verification + verdict (producer-side; team lead runs the independent panel)

Best-of-N over the real evidence (via pi workers / your own ground-truth analysis — you lack the Agent/Task tool; do NOT attempt `claude` subagents). MANDATORY lenses: (A) correctness/real-reproduction; (B) **prompt-quality + falsifiability** (each real test could have failed — controls/sentinels present; no prompt predetermined its result); (C) safety/conformance (no stealth; CDP detach-not-quit; login never automated; no leakage; tier purity preserved). Write `orchestration/reports/M-008b/verify.md` (VERDICT) and a real-message audit log. Then issue an HONEST update to `VERIFICATION.md`: for each of UC1-truncation, UC2-real-file, continuity — state real-PROVEN vs mock-only vs UNPROVEN, with evidence. No overclaiming; scope precisely (e.g. modified-single-file vs full matrix).

## Deliverables & handoff
- Code: T1 ceiling + dead-constant removal; T2 completion validation (+ hardened fallback if needed); `real.json:download_artifact` populated (if discovered); real-channel continuity/truncation harnesses.
- `orchestration/reports/M-008b/verify.md` + real audit log; honest `VERIFICATION.md` update.
- `orchestration/handoffs/MISSION-008b-handoff.json` — STATUS DONE / PARTIAL / BLOCKED(+`CDP_UNREACHABLE`/`HUMAN-ACTION-NEEDED`) with exact resume state, telemetry, commit shas (no push), and a per-leg real-PROVEN/mock-only/UNPROVEN table.
- On any challenge/logout: STOP, `HUMAN-ACTION-NEEDED`, poll read-only, surface — do not push through.
