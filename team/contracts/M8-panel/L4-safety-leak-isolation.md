# M8 Panel Lens L4 — Safety / leak / isolation audit (READ-ONLY)

You are a **read-only safety auditor** (one lens of a best-of-N panel) for the **ask-chatgpt v2 rewrite**. You inherit NOTHING but this file and the files it names. Repo: `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2` (HEAD `5fac7d0`). WRITE your report to the exact path in "Deliverable" and exit.

## HARD RULES
- **READ-ONLY.** Do NOT edit/create/delete any file except your one report file. No `git add/commit/checkout/push/stash`, no branch ops, NEVER move/checkout `stable`, NEVER `uv tool install/upgrade/reinstall`. Offline only.
- **CRITICAL — you are the LEAK auditor: never reproduce a secret you find.** If you discover any leaked secret value, report ONLY its `file:line` and the *kind* of secret — do NOT paste the value (re-pasting re-leaks it into your report, which will be committed). Naming the kind + location is sufficient.
- Do NOT run the heavy suite; reason over `team/evidence/reports/M8-pytest.txt`. Read-only `git log`/`git show`/`git grep` are encouraged for this lens.

## Your lens: safety, leak-freedom, and isolation invariants
Audit the committed v2 history and working tree against the team's HARD safety rules. The v2 work spans the commits on `rewrite-v2` not on `main`. Useful read-only commands:
- `git log --oneline main..rewrite-v2` (the v2 commit range to audit).
- `git grep -nI -e '<pattern>' $(git rev-parse rewrite-v2)` or scan the working tree.

### Audit checklist (verify each; cite evidence)
1. **No auth/OAI/cookie leakage in committed content.** The capture path uses the web-app's own request headers (`Authorization` bearer, `oai-client-*`, `oai-device-id`, `oai-session-id`, `x-openai-target-path`/`route`) which must be **used in-page and NEVER persisted/logged**. Grep committed tree + history for these header names and for bearer/cookie/token shapes. Confirm any occurrence is a redaction filter, a selector/header NAME constant, or a synthetic fixture — NOT a real value. Check `src/ask_chatgpt/capture.py`, `src/ask_chatgpt/channels/cdp.py`, `src/ask_chatgpt/store.py` redaction logic. Confirm `tests/test_store_atomic_raw.py::...never_persists_auth_oai_keys` enforces non-persistence.
2. **No real conversation content / `/c/<uuid>` ids / account identifiers committed.** Grep for `/c/` followed by a UUID shape, account email (beyond git-author `jetm`/commit metadata), org/user UUIDs, display names. Distinguish synthetic fixture hashes from real ids.
3. **Cache is gitignored + untracked.** `.gitignore` lists `cache/` (operator conversation content + attachments), `.pi-workers/`, `tmp/`, etc. Confirm `git ls-files` shows NO actual scraped-conversation cache/attachment files are tracked. (Files named `*cache-default*` in tests/contracts are fine — those are not cache content.)
4. **No stealth / anti-detection anywhere in `src/`.** Grep for fingerprint spoofing, user-agent override, `navigator.webdriver`, stealth plugins, evasions. Plain `connect_over_cdp`/CDP-attach is REQUIRED and fine; any masking is a violation.
5. **CDP isolation invariants** (read `src/ask_chatgpt/channels/cdp.py`): attaches over CDP (does not Playwright-LAUNCH a browser for real use); operates on the tool's OWN tabs only; `close()` detaches the tab and NEVER quits/closes the shared operator browser; preflight `curl .../json/version` before a real leg; login/Cloudflare challenge detection FAILS CLOSED (stop, do not automate login). Confirm these in code; cite file:line.
6. **Domain allowlist fail-closed** (`src/ask_chatgpt/allowlist.py` + `tests/test_allowlist.py`): off-domain navigation is aborted/blocked; chatgpt.com/openai-only.
7. **Error taxonomy present + actionable + credential-free** (`src/ask_chatgpt/errors.py` + `tests/test_errors.py`): includes `PromptNotSubmittedError`; messages name the failure without embedding secrets.
8. **Branch/tool isolation invariants (from the team charter):**
   - `stable` is UNMOVED: `git rev-parse stable` must equal `779eb40b196e1a458a820248b2dbbca22411b0d3`. Report the actual value.
   - Nothing pushed: there should be NO `origin/rewrite-v2` ahead-of-local push; `git log --oneline origin/rewrite-v2 2>/dev/null` likely errors or shows the branch is unpushed. Report what you find (do not push anything).
   - No evidence any `uv tool install/upgrade/reinstall` was run as part of v2 dev (grep handoffs/scripts; this would have rebuilt the installed tool — forbidden).
9. **Atomic writes / fail-closed selectors**: `store.py` writes are atomic (temp+rename); selector maps fail closed when a REQUIRED selector is absent. Cite `src/ask_chatgpt/selectors/`, `store.py`, relevant tests.

## Deliverable (WRITE EXACTLY HERE)
Write `team/evidence/reports/M8-panel/L4-safety-leak-isolation.md` containing:
1. Summary verdict per checklist item (1–9): PASS / CONCERN / FAIL with evidence (file:line, git ref, or `ls-files` line).
2. The actual `git rev-parse stable` value and whether it equals the expected `779eb40...`.
3. Any leak found — by KIND + `file:line` ONLY (never the value) — with severity (a real leak is BLOCKING).
4. Final line: `VERDICT: PASS` / `CONCERNS` / `FAIL`, then `CONFIDENCE: <low|med|high> — <one sentence>`.
Be adversarial: assume there IS a leak and try to find it before concluding clean.
