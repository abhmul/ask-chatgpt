# M-009 verify.md — producer-side honest verification

Mission: harden `ask-chatgpt` for agent use — real UC2 closeout + real model-selection + short-response
completion edge + consumer usage guide. REAL SITE over CDP. Manager: headless Opus. CDP preflight PASS
(`127.0.0.1:9222`, Chrome/149; attach-only, never launched). No `CDP_UNREACHABLE`, no
`HUMAN-ACTION-NEEDED` (no challenge/logout encountered). Never pushed.

Every result below was re-derived from inspected artifacts and re-run suites — not from worker claims or
exit codes alone. The independent USAGE overclaim pass is `T5-usage-overclaim-verify.md` (a non-producer
pi verifier; its one concern was fixed — see T4).

## Per-item status

### T1 — Real UC2 full round-trip closeout — **real-PROVEN (PASS)**
Closes the M-008b disclosed follow-up #1 ("UC2 real apply+diff + content-correctness not yet run";
`VERIFICATION.md:172,198`). Evidence `orchestration/reports/M-009/T1-uc2-roundtrip.json` (SHIPPED config,
`download_selector_injected=null`): `retrieve_outcome=retrieved`, `bundle_source=download`,
`bundle_bytes=161`; applied to a fresh tree → `favorite_color = "blue"` (was red) with
`favorite_food = "pizza"` unchanged; `content_correct=true`; clean `DiffSummary` (example.txt modified,
+1/−1 line). Falsifiable: `content_correct` would be false on wrong/unmodified content.

Two real, mock-shaped production gaps were found and fixed (RED-first, single pi editor; independently
re-verified by the manager):
1. **Double-wait truncation (keystone, also T2).** `retrieve_patch_bundle` calls `wait_for_completion` a
   second time on the already-finished turn; on real/cdp `streaming_seen` could never be re-established →
   spurious `ResponseTruncatedError`. CONFIRMED real (first probe: `retrieve_outcome=ResponseTruncatedError`)
   then fixed; re-probe reached the scan. (`driver.py`, commit `eb26c9a`.)
2. **Opaque-real download.** Production `_scan_download_artifacts` required `data-source-turn-id` /
   `data-byte-count` / `data-sha256` that the real bare `<button>Download the patch bundle</button>` does
   not carry (mock-shaped). CONFIRMED real (`PatchMalformedError: missing data-source-turn-id`), then added
   an opaque-real path: no integrity metadata → capture + validate the zip STRUCTURALLY; mock/strict path
   unchanged (partial metadata still fails closed). `real.json:download_artifact` populated with the
   verified selector. (`patch.py`, `real.json`, commit `e386bc4`.)

### T2 — Short-response completion edge — **fixed (RED-first) + real-confirmed (PASS)**
Addresses M-008b follow-up #3 (`VERIFICATION.md:200`). The never-saw-streaming completion path
(`driver.py:wait_for_completion`) returns an already-finished turn when the stop control was never caught
by a 0.1s poll, gated on completion-marker-present + stop-absent ≥3s + non-empty latest-turn text-stable
≥3s. Dormant in every pre-existing test (all have streaming at the first poll), so it cannot reopen the
micro-pause / premature-global-marker guards — both `_MicroPauseCompletionState` and
`_PrematureGlobalMarkerState` tests stay green; +2 new never-saw-streaming unit tests (RED proven first).
Real-confirmed via PRODUCTION `ask_chatgpt()->text`: 4/4 short prompts returned (`PING`/`hi`/`7`/`OK`),
`spurious_truncations=[]` (`T2-short-response.json`). Honest nuance: these normal short replies still
showed the stop button ~7s (M-008b parity), so the fix's value is proven by the UC2 double-wait (where
streaming was genuinely never re-seen) + the unit tests, not by these replies biting.

### T3 — Real model-selection wiring — **honest FAIL-CLOSED (partial, documented)**
Read-only CDP enumeration of the current UI found NO targetable model switcher (full 37-testid inventory;
no model/switcher testid; only a non-clickable `<span>ChatGPT</span>` + a reasoning-effort "Extra High"
control). Per selectors-as-data/fail-closed, `model_menu`/`model_option` stay EMPTY (no real.json change).
VERIFIED end-to-end: `ask_chatgpt(..., model_settings={'model':...}, channel='cdp')` →
`SelectorUnavailableError("selector 'model_menu' unavailable")` BEFORE any send — never silently sends on
the wrong model (the mission's hard requirement). Default no-model path works (T1/T2 probes).
`T3-model-findings.md` documents the evidence + a follow-up recommendation (the real picker is a
render-on-open dropdown, so a future `select_model` must open the menu before enumerating options).

### T4 — Consumer usage guide `docs/USAGE.md` — **written + independently overclaim-checked (PASS after one fix)**
Reflects the real-proven state above (no overclaim). An INDEPENDENT non-producer pi verifier
(`T5-usage-overclaim-verify.md`) checked all 8 dimensions: UC2 real-proven (OK), short-response (OK),
model fail-closed (OK), download-path honesty (OK), error table (1 CONCERN), test-tier 212/4 — independently
re-run (OK), channel honesty (OK), no-leak (OK). The single concern — the error table implied each error
maps to a "distinct" exit code, but `CDPUnreachableError`/`ChallengePresentError`/`ProfileLockedError`
fall through to generic exit `1` and bundle errors share `11` — was FIXED (intro reworded; the three rows
now show `(1)`). Mandatory lens result: **no residual overclaim.**

### T5 — Verify + handoff — this file + `MISSION-009-handoff.json` (GATE: AWAITING-TEAM-LEAD-SPOTCHECK).

## Suite + conformance (independently re-derived)
- **Default suite GREEN:** `uv run pytest -q` → **212 passed, 4 deselected** (manager-run AND independently
  re-run by the pi verifier). Baseline was 209; +2 never-saw-streaming tests +1 opaque-UC2 test = 212; the
  fail-closed-empty download test was updated in place (not added) to assert the new opaque invariant.
- **Tier purity:** default suite loopback-mock-only; real-site tests double-gated (`real_site` marker +
  `ASK_CHATGPT_REAL=1`); 0 real_site in the default run.
- **No stealth; CDP attach-only; detach-not-quit** (owned-tab `close()` only); **login never automated**;
  challenge/logout would fail closed.
- **No leakage:** account identifiers were detected mid-discovery (profile button text) and IMMEDIATELY
  scrubbed — the leaked report was deleted and the probe hardened (account/profile excluded; only
  model-name text emitted). Final grep over `orchestration/reports/M-009/` is clean (no unredacted
  `/c/<id>`, credentials, cookies, tokens, signed URLs, or personal names). Per-message audit:
  `real-audit-log.md`.
- **Never pushed.** Commits: `eb26c9a` (T2), `e386bc4` (T1), `7ac9304` (T3), + the T4/T5 docs/verify commit.

## Honest residual / out of scope
- Real model selection unwired (T3) — fail-closed + documented; follow-up mission.
- UC2 remains ChatGPT-non-deterministic (must choose to emit a downloadable file; else
  `DownloadUnsupportedError`); the download selector is button-text-dependent and fails closed on drift.
- Deep Research / general add-ons: OUT of scope (later mission, per the contract).
- Manager-authored edits (transparency): the one-line fail-closed→opaque test update
  (`test_driver_real_failclosed.py`), `docs/USAGE.md`, and the error-table fix were made by the manager
  (no pi was editing concurrently — no collision); all code/data edits to `driver.py`/`patch.py`/
  `server.py`/`real.json`/test_driver/test_uc2 went through the single pi editor.
