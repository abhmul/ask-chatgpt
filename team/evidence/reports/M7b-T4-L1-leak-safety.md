Status: PASS

# M7b-T4-L1 leak + safety audit

Auditor: independent pi auditor for `ask-chatgpt-dev`, task `M7b-T4-L1`. Scope: M7b commits `724a308..HEAD` (`1ea867a`, `90281f3`, `cc14d91`) on branch `rewrite-v2`, plus the M7b scripts/reports/contracts named by the contract. This audit was offline/read-only except for writing this report; no browser was opened and no sends were made.

## 1. No secret/PII or conversation-content leak in committed M7b content — PASS

Evidence:
- `git diff --name-status 724a308..HEAD` shows the expected M7b additions/modifications and no `cache/` entries.
- Sanitized added-line scan over `git diff --unified=0 724a308..HEAD` for bearer/authorization values, `oai-*` values, cookie assignments (`cf_clearance`, `__Secure-*`, `session-token`), and cookie header values found `0` potential secret-value matches.
- Sensitive term refs in added lines are scrub-key/config/report text only, e.g. scrub lists in `scripts/m7b_t1_discover.py:29-48`, `scripts/m7b_t3_verify.py:40-65`, `scripts/m7b_t3b_tools.py:32-60`, `scripts/m7b_t3c_tools_verify.py:32-61`, and safe report confirmations such as `team/evidence/reports/M7b-T3-verify.md:65`.
- `rg` over `team/evidence/reports/M7b-*.md` for potential bearer/authorization/oai/cookie/session values found `0` matches. Header terms in reports are only safe descriptions/confirmations: `team/evidence/reports/M7b-T3-verify.md:45`, `:65`; `M7b-T3b-tools.md:367`; `M7b-T3c-tools-verify.md:29`.
- `rg -n 'PONG|Reply with only the word' team/evidence/reports/M7b-*.md` returned no matches. The known static PONG-smoke prompt literal appears only in the driver source (`scripts/m7b_t3_verify.py:34`) and contracts; no captured user/assistant message body or standalone assistant reply is reported/committed. T3 reports only bools/counts/metadata (`M7b-T3-verify.md:36-46`).
- `git ls-files cache | head` returned no tracked cache files; scraped transcript paths are referenced as metadata only (`M7b-T3-verify.md:46`) and remain under gitignored `cache/`.

Leak found: none.

## 2. `stable` branch unmoved / no M7b commit on stable — PASS

Evidence:
- `git rev-parse stable` => `779eb40b196e1a458a820248b2dbbca22411b0d3` (required value).
- `git log --oneline 724a308..stable` returned no commits.
- `git branch --contains 1ea867a`, `--contains 90281f3`, and `--contains cc14d91` listed `rewrite-v2` only, not `stable`.
- `git reflog show --date=iso stable -20` shows only the older create/reset events, no M7b update; `git reflog -n 100 | grep 'checkout: moving from .* to stable'` returned no recent checkout-to-stable entries.

## 3. No `uv tool` / installed-tool rebuild — PASS

Evidence:
- `rg -n 'uv tool\s+(install|upgrade|reinstall)' scripts/m7b_*.py team/evidence/reports/M7b-*.md` returned no matches.
- Literal `uv tool` appears only as negated confirmations, not commands: `team/evidence/reports/M7b-T2-editor.md:42`, `team/evidence/reports/M7b-T2b-tools-fix.md:19`.
- Drivers use `Session`, `CdpChannel`, and project `uv run` expectations only; no installed-tool rebuild command is committed.

## 4. Own-tab-only discipline / target conversation guard — PASS

Evidence:
- No runtime `/json/list`, `context.pages`, `browser.contexts`, page/context enumeration, or ad-hoc tab walking was found in `scripts/m7b_*.py`. The only `/json/list` occurrences are report strings saying it was not used.
- Own-tab acquisition/close refs: `scripts/m7b_t1_discover.py:808` (`CdpChannel.open_tab`) and `:911` (`close_tab`); `scripts/m7b_t3b_tools.py:784`/`:905`; `scripts/m7b_t3_verify.py:606`/`:728` (`Session.tab_pool.acquire/release`); `scripts/m7b_t3c_tools_verify.py:475`/`:555`.
- Target conversation `6a316aa8` is only a guard/not-touched check, never opened or sent to: `scripts/m7b_t3_verify.py:614-624`, `:744-762`; `scripts/m7b_t3b_tools.py:74`, `:796-798`; `scripts/m7b_t3c_tools_verify.py:74`, `:489-491`.

## 5. Send-count budget and fresh throwaway sends — PASS

Evidence:
- Reports show T1 zero sends (`M7b-T1-selectors.md:230`), T3b zero sends (`M7b-T3b-tools.md:365`), and T3c zero sends (`M7b-T3c-tools-verify.md:13`, `:27`).
- T3 reports exactly one send: `M7b-T3-verify.md:13-14` (`final=1`, leg1=0, leg2=1, loop=0), below the mission cap `<=4`.
- The only created fresh throwaway chat is `/c/6a3591ae-d330-83ea-8a18-543701a8c33f` (`M7b-T3-verify.md:18-20`), and the protected conversation is reported not touched (`M7b-T3-verify.md:20`; T3b `:369`; T3c `:33`).

## 6. Forbidden paths not committed / cache untracked — PASS

Evidence:
- `git diff --name-only 724a308..HEAD | grep -E '^(issues/cdp-send-repro/controller\.mjs|human/|cache/)' | wc -l` => `0`.
- `git ls-files cache | head` returned no output.
- Current worktree has allowed dirty/untracked forbidden paths (`M issues/cdp-send-repro/controller.mjs`, `?? human/`), but they are not in the M7b committed diff.

## 7. Redaction discipline — PASS

Evidence:
- Every M7b driver has `_scrub()` and sensitive key/value lists covering authorization, bearer, oai, cookie, session/session-token, token, and headers: `scripts/m7b_t1_discover.py:29-48`, `:374-391`; `scripts/m7b_t3_verify.py:40-65`, `:77-94`; `scripts/m7b_t3b_tools.py:32-60`, `:285-302`; `scripts/m7b_t3c_tools_verify.py:32-61`, `:89-106`.
- Emission/report paths call `_scrub()` before stdout/reporting sensitive structures, e.g. `scripts/m7b_t3_verify.py:102`, `:527-553`, `:578`.
- Reports contain no raw auth/oai/cookie/session values per the report secret-value scan; only safe metadata, booleans, ids/URLs, roles, counts, product labels, and redacted fields appear.

## Commands run (representative)

- `git log --oneline 724a308..HEAD`; `git diff --name-status 724a308..HEAD`; `git diff --name-only 724a308..HEAD`.
- Sanitized `git diff --unified=0 724a308..HEAD | perl ...` scans for secret-value and sensitive-term categories without printing matched values.
- `rg`/`grep` over `scripts/m7b_*.py`, `team/evidence/reports/M7b-*.md`, and `team/contracts/M7b-*.md` for `uv tool`, `/json/list`, tab enumeration, target id guards, send counts, PONG markers, and sensitive terms.
- `git rev-parse stable`; `git log --oneline 724a308..stable`; `git branch --contains <M7b commit>`; `git reflog show stable`; `git ls-files cache | head`.

Overall verdict: PASS — no M7b secret/PII/conversation-content leak found, `stable` is unmoved, no installed-tool rebuild occurred, drivers are own-tab-only, send count is 1 fresh throwaway send (<=4), forbidden paths/cache are not committed, and redaction discipline is present.