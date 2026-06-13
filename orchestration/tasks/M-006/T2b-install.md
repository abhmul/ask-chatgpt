# T2b — Install discovered real-site selectors + asset domain (MOCK-TIER, single editor, NO real contact)

You are a fresh worker. **You inherit NOTHING except this file + the files it tells you to read.** This leg contacts NOTHING real: it is a pure local edit + the default mock/loopback test suite. **ZERO real messages.** Read the SAFETY BLOCK and obey it literally. The repo destructive-guard hook blocks command text containing certain destructive substrings — if you ever need to revert tracked files use `git stash push -u`, never `git checkout`/`git clean`. Do NOT `git commit` — the manager commits after independent verification.

## Goal

T2 (real-site CDP discovery) produced verified selectors in `orchestration/reports/M-006/real-selectors-proposed.json`. Install them into the live fail-closed selector map and add the one newly-observed asset domain to the real allowlist, keeping the FULL default suite green and tier purity intact.

## Files to READ FIRST (ground truth)

- `orchestration/reports/M-006/real-selectors-proposed.json` — the SOURCE of truth for the selector values (already verified by the manager). It has `selectors{20 keys}`, `attributes{2 keys}`, plus `_justifications`/`_unverified`/`_meta` (those three are metadata — do NOT copy them into real.json).
- `src/ask_chatgpt/selector_maps/real.json` — the TARGET. Currently the all-empty fail-closed template: top-level `channel`,`version`,`note`,`selectors{20}`,`attributes{2}`. You edit ONLY the selector/attribute VALUES; keep the exact same keys and structure.
- `src/ask_chatgpt/real_allowlist.py` — `DEFAULT_REAL_ALLOWED_DOMAINS = ("chatgpt.com","openai.com","oaistatic.com","oaiusercontent.com")` and `host_allowed()` which matches a host if it EQUALS a domain or ENDS WITH ".<domain>" (suffix match).
- `tests/test_real_allowlist.py` — read it; if it asserts the EXACT contents/length of `DEFAULT_REAL_ALLOWED_DOMAINS`, you must update that assertion to match your addition (below). If it only tests `host_allowed` behavior, no change needed.
- `tests/test_driver.py` (~line 150) — `test_real_selector_template...` was DECOUPLED in T1b to an empty-map fixture (`tests/fixtures/selector_maps/real_empty.json`); populating the live real.json must NOT break it. If it DOES break, STOP and report (a T1b regression to escalate) — do NOT weaken the fail-closed guarantee.
- `pyproject.toml` — `real_site` marker + `addopts` deselection; dependency groups. `uv sync --all-groups` before testing.

## Deliverables (all REQUIRED)

### D1 — Install selectors into `src/ask_chatgpt/selector_maps/real.json`
- For EVERY key under `selectors` and `attributes` in `real-selectors-proposed.json`: copy its value into the SAME key in `real.json`.
  - Keys whose proposed value is a non-empty string → set that string (verified selector).
  - Keys whose proposed value is `""` → leave `""` in real.json (FAIL-CLOSED; do NOT invent selectors).
- The verified non-empty keys you should end up with (confirm against the proposed file — it is authoritative if it differs):
  - `selectors.ready_root` = `main:has(#prompt-textarea)`
  - `selectors.chat_list` = `nav:has(a[href^="/c/"])`
  - `selectors.chat_item` = `nav a[href^="/c/"]`
  - `selectors.new_chat_button` = `a[aria-label="New chat"]`
  - `selectors.composer` = `#prompt-textarea`
  - `selectors.send_button` = `button[data-testid="send-button"]`
  - `selectors.assistant_message` = `[data-message-author-role="assistant"]`
  - `selectors.message_body` = `[data-message-author-role="assistant"] .markdown`
  - `selectors.streaming_marker` = `button[data-testid="stop-button"]`
  - `selectors.completion_marker` = `button[data-testid="copy-turn-action-button"]`
  - `selectors.copy_button` = `button[data-testid="copy-turn-action-button"]`
  - `selectors.download_artifact` = `button[aria-label*="Download"]`
  - `selectors.upload_input` = `input[type="file"]`
  - `attributes.turn_id` = `data-message-id`
- LEAVE EMPTY (fail-closed): `selectors.model_menu`, `selectors.model_option`, `selectors.model_option_disabled`, `selectors.login_wall`, `selectors.conversation_not_found`, `selectors.truncation_marker`, `selectors.rate_limit_marker`, `attributes.conversation_ref`.
- Keep top-level `channel:"real"`, `version:1`. You MAY update the `note` field to: `"Populated from M-006 T2 CDP discovery (verified selectors only); empty values intentionally fail closed."` NO account identifiers anywhere. Keep valid JSON (2-space indent, all 20 selector keys + 2 attribute keys present).

### D2 — Add the one new asset domain to the allowlist
- The T2 session legitimately requested hosts: `chatgpt.com`, `cdn.openai.com`, `cdn.auth0.com`, `sdmntprcentralus.oaiusercontent.com`. Under suffix matching, `cdn.openai.com` (→openai.com) and `sdmntprcentralus.oaiusercontent.com` (→oaiusercontent.com) are ALREADY allowed; `chatgpt.com` is already allowed. Only `cdn.auth0.com` (OpenAI's Auth0 identity CDN) is NOT covered.
- Add the single entry `"cdn.auth0.com"` to `DEFAULT_REAL_ALLOWED_DOMAINS` (keep it tight — the specific host, NOT the broad `auth0.com`). Do NOT add redundant entries already covered by suffix match. Verify with a quick check that `host_allowed("cdn.auth0.com", DEFAULT_REAL_ALLOWED_DOMAINS)` is now `True` and `host_allowed("evil.com", ...)` is still `False`.
- If `tests/test_real_allowlist.py` asserts the exact tuple/length, update that assertion to include `cdn.auth0.com`. Add a one-line comment in `real_allowlist.py` noting `cdn.auth0.com` came from M-006 T2 discovery.

### D3 — (Encouraged, optional) positive regression test
- If quick and low-risk, add a small default-tier test (e.g. in `tests/test_driver.py` or a new `tests/test_real_selector_map_populated.py`) asserting the live `real.json` now loads and its PRIORITY keys (`ready_root`, `composer`, `send_button`, `assistant_message`, `message_body`, `completion_marker`) are non-empty, so an accidental reset to empty is caught. Keep it default-tier (NOT `real_site`-marked). Skip if it risks scope creep.

### D4 — Suite green + tier purity preserved
- `uv sync --all-groups` first. Then run the FULL default suite ONCE (serialize; never two pytest invocations at once): `uv run pytest`. It MUST be GREEN. Capture the exact summary line (e.g. "N passed, M deselected") into your report.
- Tier purity (state it in the report): clean `uv run pytest` still collects ZERO `real_site` tests; the autouse socket guard in `tests/conftest.py` is UNCHANGED; populating real.json did NOT break the decoupled fail-closed test.
- `git diff --stat` must touch ONLY: `src/ask_chatgpt/selector_maps/real.json`, `src/ask_chatgpt/real_allowlist.py`, and (if you added them) `tests/test_real_allowlist.py` / the optional new test. NOT `conftest.py`'s guard, NOT `.claude/`, NOT `.agents/`, NOT driver.py.

## SAFETY BLOCK — obey verbatim (you inherit nothing)
- ZERO real-site contact in this leg. Default-tier tests stay loopback-only; the autouse socket guard must NEVER be weakened. Do NOT add or weaken any network-touching code.
- Never read/copy/store/log credentials, cookies, session tokens, or browser-profile contents. No account identifiers (email, name, org, real conversation ids) in any file, report, or commit.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Archive READ-ONLY. Never write `.claude/`/`.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. NEVER `git push`. Do NOT `git commit` (the manager commits the slice after independent verification).
- ESTIMATE BEFORE EXECUTE: before the test run, state expected wall-clock + output volume; keep runs bounded.

## Reporting (write to `orchestration/reports/M-006/T2b.md`, cap ~250 lines)
1. `START_TIMESTAMP:` / `END_TIMESTAMP:` (`date -Iseconds`) + `ESTIMATE: T2b <min>m`.
2. What you changed (the selector keys installed; the empty keys kept empty; the allowlist addition).
3. The exact authoritative `uv run pytest` summary line + confirmation ZERO real_site collected + socket guard unchanged + fail-closed test still green.
4. `git diff --stat` of your change (prove scope: only real.json + real_allowlist.py [+ optional tests]).
5. `MESSAGES_USED: 0`.
- LAST LINE must be exactly: `T2b-STATUS: DONE` (or `T2b-STATUS: BLOCKED` with the precise blocker).
