# M-008b · E2 (pi, single editor) — Build the real-site probe toolkit (connectivity + T2 completion-marker reliability)

You are the SINGLE EDITOR. This task WRITES a script; **YOU DO NOT RUN IT** (the manager runs it against the real site under strict discipline). Do NOT connect to `127.0.0.1:9222`, do NOT launch a browser, do NOT run the probe. Just write the code, and verify it imports/compiles (`uv run python -c "import scripts.m008b_real_probe"` is fine — that does NOT touch the network). NEVER `git push`.

## Environment / safety (you inherit nothing)
- Python `uv` project. `uv sync --all-groups` first if needed. Touch only `scripts/` (new file) — do NOT modify `src/`, `tests/`, or `orchestration/` except your report.
- The manager will run this on the operator's signed-in browser over CDP. The script must be SAFE BY CONSTRUCTION: attach-only, fail-closed on any challenge/login/logout, never automate login, never touch operator tabs, `close()`=detach (never quit the browser), human-paced, redact `/c/<id>`.

## Read FIRST (ground truth)
- `src/ask_chatgpt/driver.py` — `BrowserSession` (channel="cdp"): `start()`, `open_or_create_conversation`, `send_prompt`, `wait_for_completion(timeout_s, max_total_wait_s)`, `close()`, `_raise_challenge_present_if_detected`, `_raise_login_required_for_auth_redirect`, `refresh_active_conversation_ref`. Note: `connect_over_cdp` to `127.0.0.1:9222`; `_new_cdp_page` opens a NEW tab tracked in `_cdp_owned_pages`; `close()` only closes owned pages (detach). The driver checks challenge/login ONLY at `start()` — your probe must ALSO re-check between turns (see below).
- `src/ask_chatgpt/selector_maps/real.json` — `completion_marker` = `button[data-testid="copy-turn-action-button"]`; `streaming_marker` = `button[data-testid="stop-button"]`; `assistant_message` = `[data-message-author-role="assistant"]`; `message_body` = `.markdown`.
- `src/ask_chatgpt/errors.py` — `ChallengePresentError`, `LoginRequiredError`, `ProfileLockedError`, `CDPUnreachableError`, `ResponseTruncatedError`, `RateLimitedError`.

## Deliverable: `scripts/m008b_real_probe.py` (argparse CLI, two subcommands)

### Shared discipline helpers (used by both subcommands)
- `connect()` → build `BrowserSession(channel="cdp", base_url="https://chatgpt.com")` and `start()`. If it raises `CDPUnreachableError` → print `CDP_UNREACHABLE` and exit 3. If `LoginRequiredError`/`ProfileLockedError` → print `HUMAN-ACTION-NEEDED: <named error>` and exit 4. If `ChallengePresentError` → print `HUMAN-ACTION-NEEDED: CHALLENGE_PRESENT` and exit 5.
- `recheck_safe(session)` → between turns, READ-ONLY re-check: call `session._raise_challenge_present_if_detected()` and `session._raise_open_failures()` (login_wall) and `session._raise_login_required_for_auth_redirect(session.page.url)`. If any raises → print `HUMAN-ACTION-NEEDED: <error>` and return False (caller stops sending, leaves the browser as-is, exits 5). NEVER click anything.
- `redact(s)` → replace any `/c/<id>` segment with `/c/<redacted>` (regex on `/c/[^/?#\s]+`). Use on every string you print or log.
- `audit(row: dict)` → append one Markdown table row to `orchestration/reports/M-008b/real-audit-log.md` (the file already has a header table). Columns: `#, timestamp(ISO via datetime.now().astimezone().isoformat()), leg, action, prompt-label(redacted), observation(redacted), markers(stop/copy), result`. Keep a module counter for `#` continuing after the existing rows (read the file, count existing data rows, continue). NEVER write credentials/cookies/tokens/`/c/<id>`.
- Human pacing: `time.sleep(4)` between sends (a few seconds; never a tight loop).

### Subcommand `connectivity` (NO prompt sent — pure precondition check)
1. `connect()`. 2. `session.open_or_create_conversation(None)` (opens a fresh conversation; confirms `ready_root`+`composer` present ⇒ signed-in app reachable). 3. `audit({leg:"T0-connectivity", action:"open new conversation (no send)", observation:"ready_root+composer present", result:"OK"})`. 4. print `CONNECTIVITY: OK` + the redacted URL path shape. 5. `session.close()` (detach). Exit 0. On any challenge/login during these steps → the `connect()`/`recheck_safe` handlers print HUMAN-ACTION-NEEDED and exit non-zero (do NOT proceed).

### Subcommand `completion-reliability` (T2 — the GATING measurement)
Purpose: settle the M-008a gate concern — *is the real `completion_marker` (copy-turn-action button) reliably present-and-stable at genuine end-of-turn, so the affordance-only completion logic does not produce false `ResponseTruncatedError`?*
1. `connect()`; `ref = session.open_or_create_conversation(None)`.
2. For each prompt in a small varied set (define inline):
   - `("short-ping", "Reply with exactly the word PING and nothing else.")`
   - `("short-two", "In one short sentence, say hello.")`
   - `("medium-40", "Output the numbers 1 through 40, one per line, then a final line with exactly DONE.")`
   - `("long-120", "Output the numbers 1 through 120, one per line, then a final line with exactly DONE.")`
   Steps per prompt:
   a. `recheck_safe(session)`; if unsafe, stop the loop (leave browser, exit 5).
   b. `session.send_prompt(prompt_text)`; `audit({leg:"T2", action:"send", prompt-label, ...})`.
   c. **Capture an end-of-turn marker timeline** WITHOUT relying solely on the driver: poll up to ~90s, every 0.25s, recording samples `{t, stop_count, copy_count, copy_visible, text_len}` where:
      - `stop_count` = `page.locator('button[data-testid="stop-button"]').count()`
      - `copy_count` = `page.locator('button[data-testid="copy-turn-action-button"]').count()`
      - `copy_visible` = whether the LAST copy button `.is_visible()` WITHOUT hovering (wrap in try/except → False)
      - `text_len` = len of the latest assistant `.markdown` inner_text (best-effort)
      Stop sampling when `stop_count==0 and copy_count>=1` has held for ~2s (stable), or the 90s cap hits. Derive: `copy_appeared` (bool), `stop_gone_at`/`copy_present_at` timestamps, `gap_stop_gone_to_copy_present_s`, `copy_stable_2s` (bool), `copy_visible_without_hover` (bool).
   d. **Independently** also call the real logic: `session.wait_for_completion(timeout_s=120, max_total_wait_s=300)` in a try/except and record `wait_outcome` = `"returned"` or `"ResponseTruncatedError"` or other error name. (Send already happened; this observes the same turn. If it returns, read the body text length.)
   e. `audit({leg:"T2", action:"observe-completion", observation:"copy_appeared=..,gap=..s,stable=..,visible_no_hover=..", markers:f"stop:{final_stop}/copy:{final_copy}", result:wait_outcome})`.
   f. `time.sleep(4)` (human pace).
3. After all prompts: `session.refresh_active_conversation_ref()` is fine but DO NOT print the ref (redact). Write a structured JSON to `orchestration/reports/M-008b/T2-completion-observations.json`: a list of per-turn records (label, the timeline-derived fields from (c), wait_outcome, body_len) PLUS a top-level summary `{turns, all_copy_appeared, all_wait_returned, max_gap_stop_to_copy_s, any_false_truncation}`. Redact any `/c/<id>` (there should be none in this JSON anyway).
4. `session.close()` (detach). Print a one-line `T2-SUMMARY: copy_appeared=<k>/<n> wait_returned=<k>/<n> max_gap=<s>s` and exit 0 (exit 5 if a challenge/logout stopped it early).

### Hard rules baked into the script
- NEVER call `browser.close()`/`context.close()`; only `session.close()` (which detaches owned pages). NEVER iterate/close pre-existing operator tabs.
- NEVER automate login; NEVER click a challenge; on detection, stop and surface HUMAN-ACTION-NEEDED.
- NEVER print/log/store cookies, tokens, credentials, profile contents, or un-redacted `/c/<id>`.
- No tight retry loops against the site; honor the 4s pacing.

## Verify (offline only — do NOT run the probe)
- `uv run python -c "import ast,sys; ast.parse(open('scripts/m008b_real_probe.py').read()); print('PARSE_OK')"` and `uv run python -c "import scripts.m008b_real_probe as m; print('IMPORT_OK', [c for c in dir(m)][:0] or 'ok')"` — confirm it imports without touching the network (guard any top-level execution behind `if __name__=='__main__':`). Save both outputs to your report.
- Confirm the full offline suite still passes is NOT required (you added no test). Just ensure no `src/`/`tests/` files changed.

## Report `orchestration/reports/M-008b/E2-worker-report.md`
STATUS; the file path; a summary of each subcommand's behavior; the parse/import check outputs; confirmation you did NOT run the probe / did NOT touch the network or real site; the commit sha (no push); and:
```
ESTIMATE: E2 <m>m
ACTUAL: E2 <m>m
REWORK-CAUSE: <none|...>
```
Commit the working slice. NEVER `git push`. Do NOT run the probe.
