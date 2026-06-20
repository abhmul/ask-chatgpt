# M4 offline core — independent verification (synthesized)

**VERDICT: PASS** (after one fix cycle). The M4 offline core is implemented to the M3 design, `uv run pytest` is GREEN with **188 falsifiable tests**, the four gotcha fixes hold (including on the real `Session` path for gotcha #4), and all safety/isolation invariants are intact. Final implementation HEAD: `6742cc1`.

## Method
Single-editor pi implementation across 6 TDD steps (E1–E6) + a seam fix (DECISION 13) + one panel-driven fix cycle (E7), each independently re-derived from ground truth by the manager (not trusting exit codes or worker self-reports). Terminal verification = an independent **5-lens pi panel** (distinct dimensions) over one authoritative `uv run pytest` output, all reasoning offline.

## Panel result (5 lenses over commit 66b5533, 183 passed)
| Lens | Dimension | Verdict |
|---|---|---|
| V1 | Falsifiability / mutation (isolated copy; ~8 mutations flip RED) | PASS |
| V2 | Correctness vs M3 design (§2/§3/§5/§6/§9) | FAIL (2 load-bearing) |
| V3 | Acceptance-bar / anti-circular mapping | PASS |
| V4 | Adversarial: gotcha-regression + safety + secret-leak + no-fabrication | FAIL (2) |
| V5 | Reproduction / isolation / offline | PASS (notes non-issues) |

V1 confirmed the suite's tests genuinely fail under wrong implementations (no un-failable tests). V3 mapped every acceptance-bar point to a falsifiable test. V5 reproduced 183 passed, offline, `stable=779eb40` unmoved, all implementation commits scoped to `src/ask_chatgpt`+`tests`, no `uv tool`, no push.

## Manager adjudication of the two FAILs (re-derived from code)
Three REAL defects (cross-confirmed / re-derived), two cheap correctness notes, one false positive:
- **D-A [gotcha #4]** `Session.ask/scrape` wrote `--out` internally (with a null stdout) before the CLI printed stdout → an out-write failure suppressed stdout + success double-wrote. (V2.2 + V4.1.)
- **D-B [Q6 clipboard fail-closed]** `salvage_partial` auto-called `read_clipboard` with no opt-in (masked only because the mock raises). (V2.1.)
- **D-C [gotcha #2 hardening]** `_select_new_assistant` fell back to `assistants[-1]` when the verified completion id was absent from capture → could return stale. (V4.2.)
- **N1** `poll_backend_completion` defaulted to the unverified `stream_status` endpoint (M3 §5 says hypothesis-only). **N2** capture ignored per-message `metadata.model_slug` (M3 §3.3).
- **FALSE POSITIVE:** V4's "hardcoded 600s" flag is the by-design `activity_timeout_s=600.0` **no-activity window** (M3 `Session` signature), NOT the gotcha-#3 *total* ceiling (which is `max_total_wait_s=None`). No action.

PASS-confirmed by the panel and unchanged: gotcha #1 math fidelity (`"".join`, no separator/unicode conversion), no `datetime.now` fabrication of `created_at`, no Playwright reachable, `HeaderBundle(repr=False)` + raw-mapping strips auth/OAI/cookie keys, offline-only, no module-level browser launch.

## Fix cycle (E7, commit 6742cc1) — each with a NEW falsifiable test for the uncovered adversarial path
- D-A: removed Session-level `--out` writes; CLI is the single stdout-first→out owner. Test: real `Session.ask(channel=mock)` via CLI with a failing `--out` write still prints stdout. (Manager re-derived: no `emit_payload`/`_NullStdout` remains in `session.py`.)
- D-B: `salvage_partial(allow_clipboard=False)` defaults backend→DOM; clipboard only behind the explicit (un-wired in M4) opt-in. (Manager re-derived: `read_clipboard` now under `if allow_clipboard:`.)
- D-C: `_select_new_assistant` raises `InternalError` when the verified id is absent (fallback only for the `None` case). (Manager direct probe: absent→fails closed `INTERNAL_ERROR`; present→returns it.)
- N1: `prefer_lightweight=False` default (stream_status opt-in). N2: per-message `metadata.model_slug` preferred over top-level default.
- N3 (completion node-id fallback): DEFERRED to M5 (completion live-vocab work).

## Final independently-verified state (HEAD 6742cc1)
- `uv run pytest` = **188 passed** (manager re-ran). Tests are falsifiable (V1 mutation panel + E7 RED-on-revert + manager re-derivations), not green-by-triviality.
- Gotcha fixes all hold: #1 math (capture probe), #2 no-op→`PromptNotSubmittedError` + no stale return (incl. D-C guard), #3 no hidden ceiling + salvage (fake-clock to 1500s), #4 stdout AND `--out` on the REAL Session path (D-A fix).
- Safety: `stable` 779eb40 unmoved; branch `rewrite-v2`; every implementation commit staged only `src/ask_chatgpt`+`tests` (never `controller.mjs`/`live-state.json`/`human/`); no `uv tool`; nothing pushed; offline (no Playwright/CDP/network in any tested path); no auth/OAI/cookie/prompt leakage; no fabricated timestamps.

## Deferred to M5 (need live data — NOT M4 failures)
Completion status vocabulary + `stream_status` verification (N3 included); attachment byte-download routes; send-rate defaults; ~17MB memory budget; multi-part-join live confirmation; profile verification; real `CdpChannel` + header acquisition + real send/scrape smoke. All are explicitly M5/M7 per the M3 design §10 and the lead decisions.
