# M9 · V-B — Independent leak / safety / send-count / isolation audit (READ-ONLY)

You are an independent **pi verifier** for `ask-chatgpt-dev`, branch `rewrite-v2`, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. **READ-ONLY**: do not edit `src/`/`tests/`, do not commit, do not run the browser/CDP. You may run `git`, `uv run pytest`, and read files. Write ONLY your report file. Use `uv run` for python.

## Your job
Independently audit the M9 change for **leaks, safety, true send count, and isolation**, re-derived from ground truth (not from anyone's prose). Read `team/evidence/M9-change-map.md` as a NAVIGATION map only — verify everything against the actual diff/files.

## Checks (re-derive each; report a single-token verdict per check + evidence)
1. **No secret/credential/content leak in anything that could be committed.** Scan the full M9 diff and all M9 artifacts — `git diff main -- src tests docs VERIFICATION.md`, plus `scripts/m9_w*.py`, `team/evidence/handoffs/M9-*.md`, `team/evidence/reports/M9-*` — for: `authorization`/`bearer`/`oai-`/`cookie`/`session` **values** (header NAMES as constants are fine; VALUES are not), real account email/org/user-UUID, and conversation **content** (assistant/user message text beyond the throwaway `PONG`/`m9 upload smoke canary`). Confirm drivers carry a `_scrub`/redaction helper and emit only safe metadata. Report any hit with file:line (but do NOT quote the secret value — name the location only).
2. **TRUE real send count.** The mission cap is **≤2 real sends, all fresh throwaway, ZERO to target `6a316aa8`/foreign.** Re-derive the ACTUAL count from the W4/W6 reports + handoffs: note that `send_budget.successful_submissions` may read 0 while real user turns were created (W6 raised `PromptNotSubmittedError` AFTER submit). Count a real send wherever a **new user turn was created on the server** (W6 shows `last_seen_user_count 0→1` twice). Confirm: total real sends, per-leg (W2/W4/W6), and that NONE targeted `6a316aa8` or any foreign conversation. State the honest number and whether the ≤2 cap held.
3. **Own-tab-only / isolation in the drivers.** Read `scripts/m9_w2_discover.py`, `scripts/m9_w4_smoke.py`, `scripts/m9_w6_reverify.py`: confirm NO `/json/list`, NO `context.pages`/page enumeration, NO foreign-tab access; tabs come only from `CdpChannel.open_tab`/`Session`/`TabPool`; a `6a316aa8` guard exists; `detach()` (not quit) is used.
4. **Repo isolation.** `git rev-parse stable` == `779eb40b196e1a458a820248b2dbbca22411b0d3` (UNMOVED). No `origin/rewrite-v2` push (nothing pushed). No `uv tool install/upgrade/reinstall` evidence. `cache/`, `issues/cdp-send-repro/controller.mjs`, `human/` are NOT staged and would NOT be swept into the intended commit (the manager will stage only `src/ tests/ docs/ VERIFICATION.md team/`). Confirm `.gitignore` covers `cache/` and `.pi-workers/`.
5. **Suite sanity.** `uv run pytest` → confirm the actual pass count + exit 0 (report the number you observe).

## Handoff (write ONLY this, then stop)
Write `team/evidence/reports/M9-panel/LB-leak-safety-sendcount.md`:
1. **Status** (single token: `PASS`/`CONCERNS`/`FAIL`), top.
2. Per-check verdict (1–5) with evidence (file:line, counts, `git` output). For check 2 give the explicit honest send number.
3. Any leak/safety/isolation issue with exact location (never quote the secret).
4. The `uv run pytest` count you observed.
Credential-free; name locations, never quote secrets.
