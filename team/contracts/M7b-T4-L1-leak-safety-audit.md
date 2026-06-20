# M7b-T4-L1 — Independent LEAK + SAFETY audit of the M7b changes (OFFLINE, read-only)

You are an **independent pi auditor** for team `ask-chatgpt-dev`, task **M7b-T4-L1**. You inherit **nothing** but this file. You did NOT produce any of this work — audit it adversarially. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. **Read-only: no edits, no commits, no browser, no sends.**

## Context
Mission M7b closed two real-site gaps via 3 commits on top of the M7 commit `724a308`: gap-1 (live model/tool composer selection) and gap-2 (fresh-chat capture-auth). Real legs ran against a SHARED browser also used by another agent on conversation `6a316aa8`. Your job: **prove no secret/PII leak and that all safety invariants held.**

## Audit these (report each as PASS/FAIL with evidence)
1. **No secret/PII leak in committed content.** Examine `git diff 724a308..HEAD` (all M7b commits) AND the new files (`scripts/m7b_t1_discover.py`, `scripts/m7b_t3_verify.py`, `scripts/m7b_t3b_tools.py`, `scripts/m7b_t3c_tools_verify.py`, `team/evidence/reports/M7b-*.md`, `team/contracts/M7b-*.md`). Grep for any **literal value** of: a bearer/authorization token, any `oai-*` header value, a cookie/`cf_clearance`/`__Secure-`/session-token value, or **conversation content** (assistant/user message text). Model/tool product names ("Web search", "Pro Extended", "High") and conversation IDs/URLs are NOT secrets. The PONG smoke's only content was the prompt "Reply with only the word: PONG" and a 4-char reply — confirm neither the reply text nor any backend headers appear in any committed file. Note: scraped conversation content lives ONLY in gitignored `cache/` — confirm `cache/` is NOT tracked (`git ls-files cache | head`) and not in the diff.
2. **`stable` branch unmoved.** `git rev-parse stable` must equal `779eb40b196e1a458a820248b2dbbca22411b0d3`. Confirm no M7b commit is on `stable` and `stable` was never checked out/committed.
3. **No `uv tool` / installed-tool rebuild.** Grep all M7b scripts + reports for `uv tool` (install/upgrade/reinstall) — must be ABSENT. The drivers use `uv run`/`Session`/`CdpChannel` only.
4. **Own-tab-only discipline in the drivers.** In each `scripts/m7b_*.py`, confirm: NO `/json/list` call, NO `context.pages`/`browser.contexts` enumeration, NO ad-hoc tab walking — they use `CdpChannel.open_tab`/`Session.tab_pool` (the recorder's own tab) and close only their own lease. Confirm the target conversation `6a316aa8` is only ever referenced as a GUARD (a `!=` check / "not touched"), never opened/sent-to.
5. **Send-count budget.** From the reports, the only real send in M7b was the **1** PONG smoke in `team/evidence/reports/M7b-T3-verify.md` (T1, T3b, T3c report 0 sends). Confirm mission total ≤ 4 and that every send was to a FRESH throwaway chat (a newly-learned `/c/<id>`), never the target/foreign. List the throwaway `/c/<id>` created.
6. **Forbidden paths not committed.** Confirm `issues/cdp-send-repro/controller.mjs`, `human/`, and `cache/` are NOT in any M7b commit (`git diff 724a308..HEAD --name-only`). (They may be dirty/untracked in the worktree — that's fine; they must not be COMMITTED.)
7. **Redaction discipline.** The drivers reuse a `_scrub()`/scrub helper and emit safe metadata. Confirm the reports show no raw header/cookie values and that scrub sensitive-key lists cover authorization/oai/cookie/token.

## Method
- Use `git`, `grep`/`rg`, `sed`/`cat` over the repo. You MAY run `git ls-files`, `git diff 724a308..HEAD`, `git log --oneline 724a308..HEAD`. Do NOT modify anything, do NOT commit, do NOT open a browser.
- If you find a real leak, quote the file + line but **do NOT reproduce the secret value** in your report — describe it (e.g. "a bearer token value appears at scripts/X:NN") so it can be scrubbed; naming the value would re-leak it.

## Output
Write `team/evidence/reports/M7b-T4-L1-leak-safety.md`: `Status:` (`PASS` if all 7 checks pass, else `FAIL`); each check 1–7 with verdict + concrete evidence (commands run, counts, file:line refs); an explicit list of any leak found (described, not quoted); and a one-line overall verdict. Be adversarial — your value is finding what the producers missed. The report file is your deliverable.
