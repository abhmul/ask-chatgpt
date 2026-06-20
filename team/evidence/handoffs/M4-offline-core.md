STATUS: DONE

# M4 — Phase-1 offline core (TDD, mock-proven) — manager handoff

Mission M4 (the OFFLINE CORE of the ask-chatgpt v2 rewrite, TDD against the `mock` channel, to the M3 detailed design §10 steps 1–6) is **DONE and independently verified**. Offline only — no chatgpt.com/CDP/browser legs were run. Acceptance met: GREEN `uv run pytest` with falsifiable tests + inspected artifacts (never exit codes alone). Implemented on `rewrite-v2`; nothing pushed; `stable` untouched; no `uv tool`.

## What was verified (re-derived from ground truth by the manager — not worker self-reports)
**Acceptance command (manager re-ran):**
```
uv run pytest  ->  188 passed in ~0.4s   (full output: team/evidence/reports/M4-pytest-authoritative.txt was the 183-passed pre-fix authoritative run; post-fix HEAD is 188 passed)
```
Tests are **falsifiable, not green-by-triviality**:
- Independent 5-lens verification panel: V1 mutation lens flipped ~8 targeted mutations RED (no un-failable tests); V3 mapped every acceptance-bar point to a genuinely falsifiable test.
- Manager re-derived the gotcha-critical behaviors by calling the PUBLIC API directly with adversarial inputs (independent of the worker test files): allowlist suffix-confusion reject; identity DECISION-1 project round-trip; `TurnRecord` invariant; selector validation; pending-stub supersession + default-hide + on-disk preservation; torn-line warn-vs-raise; raw-mapping secret stripping; 5001-node linearization with hidden-exclusion; DR conjunction (positive→deep_research, 5 negatives→normal); 4 attachment shapes + citations-separate; math fidelity (`'alpha'+''+'beta'+'\n'+'gamma'`→`'alphabeta\ngamma'`, `\widehat`/`\ne`/`\frac` intact, no `≠`); no-op send→`PromptNotSubmittedError` + completion-not-reached; completion newer-id gating; max_total_wait=None past 1500s (no hidden 600s ceiling); timeout salvage; CLI stdout-AND-`--out` via real `main()`; status `--json --no-browser-probe` 8-field schema; error exit codes + redaction; D-C completion-id-absent→fails closed.

**Four gotcha fixes (all hold):** #1 math corruption (capture: `"".join`, no separator/unicode conversion); #2 silent no-op send (`PromptNotSubmittedError`, never returns stale — hardened by D-C guard); #3 truncation/hidden ceiling (no-activity timeout resets on progress, `max_total_wait=None` unbounded, partial salvage); #4 `--out` suppresses stdout (stdout-AND-`--out`, fixed on the REAL `Session` path in E7).

**Commits on `rewrite-v2` (implementation; each staged ONLY `src/ask_chatgpt`+`tests`):**
```
6742cc1 M4: fix verification-panel findings            (D-A/D-B/D-C/N1/N2 + tests)
66b5533 M4 step 6: cli verbs and status over mock
274e8bc M4 step 5: verified send + completion detection over mock
de96e20 / 3d30e2d / 379795a  M4 step 4c/4b/4a: capture parser + fallback + DECISION-13 seam fix
64a9f97 M4 step 3: MockChannel offline fixtures
b6d954c M4 step 2: store.py JSONL/atomic/pending-stub/render/payload
7c1cdf3 M4 step 1: scaffold (data model, errors, identity, allowlist, selectors, channel seam)
```
(Manager-record commits — `0d8051d 43c45bf 9c599d1 7db36f4 7d01351` + a final record — touch only `team/`.)
**Isolation verified:** `git rev-parse --short stable` = `779eb40` (UNMOVED); branch `rewrite-v2`; no implementation commit staged `issues/cdp-send-repro/controller.mjs`, `team/state/live-state.json`, or `human/`; no `uv tool` run; nothing pushed; no Playwright import reachable from `import ask_chatgpt` or any test; offline (no network/CDP) in all tested paths; no auth/OAI/cookie/prompt leakage; no fabricated `created_at`.

## Artifacts + trust
- `src/ask_chatgpt/` modules: `models, errors, identity, allowlist, selectors/, channels/{base,mock}, store, capture, send, completion, menus(fail-closed stub), session, cli` — **verified-independently** (188 green + manager re-derivations + 5-lens panel).
- `tests/` (24 test files + `mock_scenarios.py` substrate) — **verified-independently** (falsifiable; V1 mutation + E7 RED-on-revert).
- `team/evidence/reports/M4-test-plan.md` (TDD target), `M4-verification.md` (panel synthesis + final PASS), `M4-pytest-authoritative.txt`, `M4-verify-lens-{1..5}.md` — **manager-reviewed**.
- `team/contracts/M4-common.md` (worker preamble + **13 MANAGER DECISIONS**, incl. the DECISION-13 seam correction) + `M4-E{1..7}-*.md` per-step contracts — **manager-authored**.
- `team/state/M4-manager-state.json` — resume-ready live state.

## Key engineering decisions made during M4 (recorded in M4-common.md DECISIONS 1–13)
Project-id without `g-p-` + round-trip; prompt normalization (strip + CRLF→LF, no inner collapse); render format + `ask` raw-content stdout; empty `parts=[]`→`""`; DR conjunction (no numeric threshold); `download_state="pending"`; torn-line `StoreWarning` vs `StoreError`; sparse backend cadence; `StatusReport` exact fields; `--project` on `create` not `ask`; timeout split (`CompletionTimeoutError` vs `MaxTotalWaitExceededError`); validation via public behavior; **DECISION 13** (relax `created_at=None` invariant + stop `record_partial` fabricating `datetime.now` — caught when the over-strict invariant FORCED a "never agent self-report" violation downstream).

## Blockers
None.

## Recommended next — M5 (attended CDP capture/scrape + verified-send smoke)
Per M3 §10 M5: implement `CdpChannel` (preflight/attach/open_tab/detach behind LAZY Playwright import; `/json/version` gate; own-tabs-only; never quit Chromium); own-page request header acquisition + streaming backend fetch (cookies-only still 404; values never logged/persisted; atomic raw-mapping write; ~17MB stream-to-disk with measured RSS/tracemalloc); prove `scrape` on an operator-approved NON-target smoke conversation; fidelity harness (`\widehat`/`\ne`/`\frac` vs web-UI copy); verified UI send on a low-risk approved prompt; catalogue real completion status vocab. Real legs are **operator-attended** (CDP `:9222`, own-tab-only, no stealth, login/Cloudflare→`HUMAN-ACTION-NEEDED`).

### Open questions still needing M5 live data (NOT M4 gaps — design §12)
Completion status vocabulary + `stream_status` verification (incl. deferred N3 completion node-id fallback); attachment byte-download routes; send-rate defaults; ~17MB memory budget (whole-parse vs event parser); multi-part `content.parts` join live confirmation; safe profile verification. M4 implemented the conservative offline defaults for all of these; do NOT guess live values.

## Complexity / paradigm signals
- The single most valuable manager intervention was **probing the consumer**, not the test count: the over-strict E1 `created_at` invariant passed all tests but silently forced `record_partial` to fabricate a wall-clock timestamp (DECISION 13). Over-tight invariants push violations downstream.
- The verification panel earned its cost: 3 real defects (2 acceptance-relevant) survived a 183-green suite because every one hid behind a fake Session / a mock that raises — the adversarial path (failing `--out`, clipboard-would-succeed, completion-id-absent) was untested. A green suite proves tested paths; the panel asks what path the tests didn't take.
- No paradigm shift needed; the M3 design held up under implementation. Architecture stayed simple (no daemon; single-tab spine; minimal pool/budget stubs).
