# M-008a / T5 Lens C — safety / parser-integrity / tier-purity (independent non-producer). READ-ONLY.

You are a pi (GPT-5.5) worker acting as an INDEPENDENT non-producer verifier. You inherit NOTHING except this file and what you read. Verify from ground truth; do not rubber-stamp.

## Rules (MANDATORY)
- Repo root: `/home/abhmul/dev/ask-chatgpt`. `uv run` from root for any python; NEVER bare `python`; NEVER touch `~/.local/share/agent-python/.venv`.
- **READ-ONLY:** no edit/commit/checkout/stash. Do NOT set `ASK_CHATGPT_REAL`; do NOT touch `127.0.0.1:9222`. Do NOT re-run the full suite (read `orchestration/reports/M-008a/authoritative-pytest.txt`). Targeted greps/reads are fine.

## Context
M-008a (mock/build half, NO real site), commits `87a0ee8` (T1 driver completion hardening), `c71c96a` (T2 bundle prompt rewrite, base64=parser-only), `484cacf` (T3 mock recall mode + continuity/truncation tests). The patch retrieve/validate path (`src/ask_chatgpt/patch.py`) and the mock download affordance already existed before this mission and should be UNCHANGED by it.

## Your lens — safety / parser-integrity / tier-purity. Verify each, independently:
1. **Parser integrity preserved:** confirm `src/ask_chatgpt/patch.py` was NOT modified in this mission (`git diff 0dfe258..HEAD -- src/ask_chatgpt/patch.py` should be empty; or `git log --oneline -- src/ask_chatgpt/patch.py` shows nothing newer than the mission base). The fenced base64url parser must remain intact as the SILENT fallback.
2. **base64 is parser-only:** zero base64 wording in GPT-facing text (`grep -niE 'base64|begin_patch_bundle|end_patch_bundle|fenced' src/ask_chatgpt/bundle.py` → none), but the protocol DOC still documents the fenced token spec as the tolerated fallback (`grep -ciE 'base64|begin_patch_bundle' docs/bundle-protocol.md` → some). Confirm both.
3. **Download-path integrity (by inspection, not re-run):** confirm the suite includes passing zip-slip / path-escape / validate-before-mutate / dry-run-default coverage (read the relevant tests in `tests/test_patch.py`; cross-check they are in the authoritative passing run). Confirm download-path integrity = structural zip validity + per-member path-safety + caps (no GPT-declared SHA needed on the download path) per `docs/bundle-protocol.md` §3/§5/§6.
4. **Fail-closed real selectors:** `src/ask_chatgpt/selector_maps/real.json` — `download_artifact` is `""` and any `completion_affordance` seam added by T1 is honored-if-present / absent-degrades and is NOT populated with a real value. No real selector invented this mission.
5. **Tier purity + socket guard intact:** read `tests/conftest.py` — confirm the autouse loopback socket guard is present and the `real_site` deselection/skip gating requires `ASK_CHATGPT_REAL=1`. Confirm the authoritative run had `ASK_CHATGPT_REAL` unset and `1 deselected` (real_site gated), ZERO real_site collected. Confirm the T1 completion change touched ONLY the `real`/`cdp` branch, not the mock path.
6. **No leakage:** scan the M-008a reports/artifacts (`orchestration/reports/M-008a/*`) for any credential, cookie, session token, profile path, or raw `/c/<id>` conversation id. Expect none (mock-only; nonces are synthetic `ASKCG-NONCE-…`).

## Deliverable — write `orchestration/reports/M-008a/T5-lensC.md`:
- Evidence table (claim → command/file → PASS/FAIL).
- Any defects or "none".
- Final line exactly: `VERDICT: PASS` (or `PARTIAL` / `FAIL`) with a one-clause reason.
Do NOT edit anything. Stop when the report is written.
