PASS

# M9 panel LB — leak / safety / send-count / isolation audit

## 1. PASS — leak scan

Evidence: scanned `git diff main -- src tests docs VERIFICATION.md` (26,984 lines), `scripts/m9_w*.py` (3 files), `team/evidence/handoffs/M9-*.md` (7 files), and pre-existing `team/evidence/reports/M9-*` files (8 files). Targeted secret-value candidates reduced to synthetic test/mock canaries or header-name/redaction constants, not real credentials.

- No real auth/bearer/OAI/cookie/session credential values found in M9 artifacts. M9 handoff/report assertions also state no auth/OAI/cookie/bearer/conversation content logged: `team/evidence/handoffs/M9-W2-discovery.md:31`, `team/evidence/handoffs/M9-W4-smoke.md:27`, `team/evidence/handoffs/M9-W6-reverify.md:34`, `team/evidence/reports/M9-W4-smoke.txt:57`, `team/evidence/reports/M9-W6-reverify.txt:58-59`.
- Diff candidate value hits in `src/`/`tests/` are synthetic canaries used to test redaction, not real secrets: examples are mock header canaries at `src/ask_chatgpt/channels/mock.py:42-47`, CLI/error/store canary tests at `tests/test_cli.py:111-117`, `tests/test_store_atomic_raw.py:35-46`, `tests/test_errors.py:58-60`, and synthetic URL/email canaries at `tests/test_allowlist.py:70,83`.
- No real account email/org/account-UUID found. UUID candidates are protected-target guard constants (`scripts/m9_w2_discover.py:27,68`, `scripts/m9_w4_smoke.py:43`, `scripts/m9_w6_reverify.py:43`) plus W6 server user-turn/message IDs in error metadata (`team/evidence/reports/M9-W6-reverify.txt:48`); I did not identify any account UUID and I am not quoting the message IDs.
- No real assistant/user conversation content found beyond the allowed throwaways. The live-send drivers define only `m9 upload smoke canary` and `PONG` prompts at `scripts/m9_w4_smoke.py:49-50` and `scripts/m9_w6_reverify.py:49-50`; W6 report redacts UI text at `team/evidence/reports/M9-W6-reverify.txt:24`.
- Driver redaction helpers are present and used: W2 `SENSITIVE_*` + `scrub` + `emit` at `scripts/m9_w2_discover.py:31-57,432-457`; W4 `_scrub` + scrubbed report writes at `scripts/m9_w4_smoke.py:52-69,148-173,1133-1178`; W6 `_scrub` + scrubbed report writes at `scripts/m9_w6_reverify.py:52-69,185-210,1195-1242`.

Leak/safety issue locations: none found. Hygiene note only: W6 report line 48 contains server user-turn/message IDs; not account credentials/content, but scrub-to-count-only would be cleaner for public evidence.

## 2. PASS — TRUE real send count

Honest actual count: **2 real sends total**, both W6 upload attempts, both within the ≤2 cap.

- W2: 0 real sends. Evidence: `team/evidence/handoffs/M9-W2-discovery.md:24` says the driver did not submit/send; `team/evidence/handoffs/M9-W2-discovery.md:25` says own fresh tab only and no target/foreign touch.
- W4: 0 real sends. Evidence: `team/evidence/reports/M9-W4-smoke.txt:12-15` records family/DR/upload/final `send_budget` all 0; `team/evidence/handoffs/M9-W4-smoke.md:4-7` says no backend user turn/conversation was created.
- W6: `send_budget.successful_submissions` is misleadingly 0 (`team/evidence/reports/M9-W6-reverify.txt:12-15`), but upload had 2 attempts (`team/evidence/reports/M9-W6-reverify.txt:40`) and each `PromptNotSubmittedError` occurred after `baseline_user_count=0` and `last_seen_user_count=1` (`team/evidence/reports/M9-W6-reverify.txt:48`; IDs intentionally not quoted). Per the contract, each new server user turn counts as a real send, so W6 upload = 2 real sends; W6 family = 0 and DR = 0 (`team/evidence/reports/M9-W6-reverify.txt:12-13,28,37`).
- Target/foreign isolation held for the counted sends: W4 says fresh throwaway and protected/foreign untouched at `team/evidence/reports/M9-W4-smoke.txt:52-53`; W6 says fresh throwaway and protected/foreign untouched at `team/evidence/reports/M9-W6-reverify.txt:53-54`; W2 says no target/foreign touch at `team/evidence/handoffs/M9-W2-discovery.md:25`.

## 3. PASS — own-tab-only / driver isolation

Evidence: grep over `scripts/m9_w2_discover.py`, `scripts/m9_w4_smoke.py`, and `scripts/m9_w6_reverify.py` found 0 `/json/list`, 0 `context.pages`, 0 `pages(`, 0 `list_tabs`, and 0 `quit(` hits.

- W2 opens only one owned tab through `CdpChannel.open_tab` (`scripts/m9_w2_discover.py:675`), has a `6a316aa8` guard (`scripts/m9_w2_discover.py:68,554,686-688`), records no page enumeration (`scripts/m9_w2_discover.py:648`), and detaches (`scripts/m9_w2_discover.py:974`).
- W4 uses `Session(channel="cdp")`, `session.create()`, and `session.tab_pool.acquire(...)` (`scripts/m9_w4_smoke.py:1224,426-428`), guards target URLs/conversation IDs (`scripts/m9_w4_smoke.py:290-305,422,435,905,932`), records no `/json/list`/page enumeration (`scripts/m9_w4_smoke.py:1038,1167`), and detaches (`scripts/m9_w4_smoke.py:1282`).
- W6 uses `Session(channel="cdp")`, `session.create()`, and `session.tab_pool.acquire(...)` (`scripts/m9_w6_reverify.py:1288,463-465`), guards target URLs/conversation IDs (`scripts/m9_w6_reverify.py:327-342,459,472,966,993`), records no `/json/list`/page enumeration (`scripts/m9_w6_reverify.py:1101,1231`), and detaches (`scripts/m9_w6_reverify.py:1346`).

## 4. PASS — repo isolation

- `git rev-parse stable` returned `779eb40b196e1a458a820248b2dbbca22411b0d3`.
- No pushed `origin/rewrite-v2` evidence: `git rev-parse --verify --quiet refs/remotes/origin/rewrite-v2` found no local remote ref, and `git ls-remote --heads origin rewrite-v2` returned no head.
- No M9-scope `uv tool install/upgrade/reinstall` invocation evidence: grep over `scripts/m9_w*.py` and `team/evidence/{handoffs,reports}/M9-*` found 0 command invocations. Broader historical docs contain prohibitions/old references only, not M9 execution evidence.
- Protected paths are not staged: `git diff --cached --name-only` was empty; `git status --short -- cache issues/cdp-send-repro/controller.mjs human` showed `issues/cdp-send-repro/controller.mjs` modified and `human/` untracked, but neither staged. These paths would not be swept by the intended manager stage set (`src/ tests/ docs/ VERIFICATION.md team/`).
- `.gitignore` covers `.pi-workers/` at `.gitignore:10` and `cache/` at `.gitignore:15`; `git check-ignore -v cache/ .pi-workers/` confirmed both patterns.

## 5. PASS — suite sanity

Ran exactly `uv run pytest` without browser/CDP. Exit 0; observed `267 passed in 1.01s`.
