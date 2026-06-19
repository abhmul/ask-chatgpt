# Contract M7-T4 — Independent send-count + leak/privacy + safety audit (READ-ONLY)

You are a **READ-ONLY independent pi AUDITOR** for `ask-chatgpt-dev`, task **M7-T4**. Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**. You inherit **nothing** but this contract. **First read and obey** `.claude/skills/manager/references/agent-rigor.md`. Your job is to **independently audit** the M7 mission's real-leg safety — do NOT trust the worker reports; re-derive every claim from git + the files. This is critical (a prior incident leaked an operator conversation), so be adversarial: assume a leak or a miscount exists and try to find it.

## Background (verify, don't trust)
M7 implemented model/tool selection + draft send + loop offline (mock-proven, suite 247), then attempted REAL legs over a SHARED CDP browser (another agent is keep-pushing the protected conversation `6a316aa8`). Two real attempts each submitted ONE send (gotcha-4 passed) then failed downstream (T3: id-learning, fixed; T3c: capture-auth `BACKEND_AUTH_UNAVAILABLE`/clipboard). Reported mission total real sends = **2** (cap ≤4). Real conversation data went to the **gitignored** `cache/` store.

## Audit dimensions — re-derive each from ground truth, give file:line / command evidence
1. **Send count ≤ 4.** Read `team/evidence/reports/M7-T3.md` and `team/evidence/reports/M7-T3c.md`: each reports a `send_budget.successful_submissions`. Confirm T3=1, T3c=1, total=2 ≤ 4. Read the real-leg driver scripts `scripts/m7_t3_real.py` and `scripts/m7_t3c_real.py`: confirm they perform a BOUNDED number of `ask`/`loop` sends, **no retry loop**, **no extra/hidden sends**, and that the loop leg was NOT reached (so no loop sends occurred). Flag any code path that could send more than reported.
2. **Leak / privacy — the critical one.** Grep the ENTIRE mission diff and ALL committed files for leaks:
   - `git log --oneline 779eb40..HEAD` then inspect each commit's content (`git show <hash>`). 
   - Confirm **NO conversation content** (assistant/user message text beyond the literal sentinel prompt `Reply with only the word: PONG` / `continue`), **NO auth/OAI/cookie/bearer/token/header VALUES**, **NO `oai-*`/`Authorization`/`__Secure`/`cf_clearance`** appear in any committed file — especially `scripts/m7_t3_real.py`, `scripts/m7_t3c_real.py`, `team/evidence/reports/M7-T3.md`, `M7-T3c.md`, and any code/test.
   - Confirm `cache/` (which holds REAL sent-conversation data) is **NOT tracked by git**: `git ls-files cache/ | head` must be EMPTY and `git check-ignore cache/` (or `.gitignore`) must cover it. Confirm no `cache/` path is staged or committed anywhere in `779eb40..HEAD`.
   - Confirm the protected id `6a316aa8` appears ONLY as a "do-not-touch" guard string (if at all), never as a send/scrape target, in any committed file.
3. **Safety invariants.** From the scripts + reports, confirm: own-tab-only (no `/json/list`, no `browser.pages()/contexts()`, no ad-hoc tab enumeration in either driver); browser never quit (detach only); `stable` unmoved (`git rev-parse stable` == `779eb40b196e1a458a820248b2dbbca22411b0d3`); no `uv tool install/upgrade/reinstall` invoked; nothing pushed (this is local-only — confirm no push command in any script).
4. **Offline suite still green.** Run `uv run pytest -q` ONCE (you are the only auditor running it) and confirm it passes (expect 247). Report the exact tail.

## Rules
READ-ONLY except the single `uv run pytest`. Do NOT edit/commit/`git add`/push, never move `stable`, never stage/touch `controller.mjs` or `human/`, no browser/CDP/network (do NOT run the real scripts). Do NOT print any conversation content you might find — report a leak by file:line + classification, NOT by reproducing it.

## Output — write `team/evidence/reports/M7-T4-audit.md`
Line 1: single-token verdict `PASS` / `CONCERN` / `FAIL` (FAIL if ANY leak, miscount > 4, or safety violation). Then per-dimension findings with commands run + evidence; the exact computed send count; the `git ls-files cache/` result; the `uv run pytest` tail; a severity-tagged list of any issues. If clean after a genuine adversarial effort, say so explicitly and list exactly what you checked.
