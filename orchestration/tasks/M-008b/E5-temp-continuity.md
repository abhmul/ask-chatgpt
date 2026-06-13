# M-008b · E5 (pi, single editor) — Add a memory-immune Temporary-Chat continuity probe subcommand

You are the SINGLE EDITOR. WRITE code only; **DO NOT RUN the probe / DO NOT touch the network or `127.0.0.1:9222`** (the manager runs it on the real site). Offline-validate via `ast.parse` + import only. NEVER `git push`.

## Why
The M-008b real continuity test found the operator's ChatGPT account has cross-chat Memory enabled, so a fresh NORMAL conversation leaks a planted nonce — defeating the "fresh conversation can't recall" falsifiability control. A ChatGPT **Temporary Chat** (`https://chatgpt.com/?temporary-chat=true`) does NOT use or create memory, so a fresh temp chat genuinely cannot recall a nonce planted in a *different* temp chat. This gives a clean, memory-immune, falsifiable conversation-scoped continuity proof. (Verified over CDP: the temp-chat URL loads a usable composer; `temporaryChatTextPresent: True`; affordance "Turn off temporary chat" present.)

## Read FIRST
- `scripts/m008b_real_probe.py` — REUSE its discipline helpers verbatim: `connect()`, `recheck_safe()`, `_check_safe_or_raise()`, `redact()`, `audit()`, `_marker_selectors()`, `_wait_for_real_completion()` (or `session.wait_for_completion`), `HumanActionStop`, `HUMAN_ERRORS`, `HUMAN_PACE_S`. Keep ALL existing discipline: attach-only, `close()`=detach (never quit browser / never touch operator tabs), fail-closed on challenge/login, human pacing, redact `/c/<id>`, never log credentials/tokens.
- `tests/test_continuity_mock.py` — import `_new_nonce`, `_plant_prompt`, `RECALL_PROMPT`, `_assert_recall_prompt_does_not_leak_nonce` (do NOT rewrite them). NOTE: that file is under `tests/`; import via `from tests.test_continuity_mock import ...` (the probe already inserts `src` on `sys.path`; also ensure repo root is importable — add `ROOT` to `sys.path` if needed so `tests` is importable, OR re-declare the 3 tiny constants/prompts locally with the SAME values and a comment that they mirror `tests/test_continuity_mock.py`). Prefer importing; fall back to mirroring only if the import is fragile.
- `src/ask_chatgpt/driver.py` — `BrowserSession`: `send_prompt`, `wait_for_completion(timeout_s, max_total_wait_s)`, `_latest_assistant_turn`, `_latest_assistant_body_text`. `send_prompt`/`wait_for_completion` operate on the current page and do NOT require a `/c/<id>` ref (temp chats may have none) — that's fine.

## Add a helper
`_latest_assistant_text(session) -> str` — return the latest assistant turn's `.markdown` inner_text (full text, not just length). Reuse `_latest_assistant_body_text`/the `assistant_message`+`message_body` selectors. (The nonce `ASKCG-NONCE-<32hex>` is hyphenated/markdown-inert and round-trips verbatim.)

## Add subcommand `continuity-temp`
TEMP_URL = `https://chatgpt.com/?temporary-chat=true`. `_open_temp_chat(session)` = `session.page.goto(TEMP_URL, wait_until="load", timeout=60000)` then `session.page.wait_for_selector('main:has(#prompt-textarea)', timeout=30000, state="attached")`.

Flow:
1. `nonce = _new_nonce()`; `_assert_recall_prompt_does_not_leak_nonce(RECALL_PROMPT, nonce)` (guard — abort if it raises).
2. **Conversation A (plant+recall in ONE temp chat):**
   - `sessionA = connect()`; `_open_temp_chat(sessionA)`; `recheck_safe`.
   - `audit` + `sessionA.send_prompt(_plant_prompt(nonce))`; `sessionA.wait_for_completion(timeout_s=120, max_total_wait_s=300)`; record plant reply text (redacted) — do NOT assert on it.
   - `time.sleep(HUMAN_PACE_S)`; `recheck_safe`.
   - `audit` + `sessionA.send_prompt(RECALL_PROMPT)`; `sessionA.wait_for_completion(...)`; `recall_text = _latest_assistant_text(sessionA)`.
   - `recall_ok = nonce in recall_text`. Write `orchestration/reports/M-008b/T5-temp-recall.txt` (redacted; the nonce MAY appear — it is test data, not a credential).
   - `sessionA.close()` (detach).
3. `time.sleep(HUMAN_PACE_S)`.
4. **Conversation B (control — a SEPARATE fresh temp chat):**
   - `sessionB = connect()`; `_open_temp_chat(sessionB)`; `recheck_safe`.
   - `audit` + `sessionB.send_prompt(RECALL_PROMPT)` (SAME recall prompt; nonce ABSENT); `sessionB.wait_for_completion(...)`; `control_text = _latest_assistant_text(sessionB)`.
   - `control_clean = nonce not in control_text`. Write `orchestration/reports/M-008b/T5-temp-control.txt` (redacted; nonce must be ABSENT).
   - `sessionB.close()`.
5. Write `orchestration/reports/M-008b/T5-temp-continuity.json`: `{nonce_recalled_in_conversation: recall_ok, control_is_clean: control_clean, recall_len, control_len, verdict: ("FALSIFIABLE_CONTINUITY_PROVEN" if recall_ok and control_clean else "RECALL_FAILED" if not recall_ok else "CONTROL_LEAKED")}`. Redact.
6. `audit` a summary row. Print `TEMP-CONTINUITY: recall_ok=<bool> control_clean=<bool> verdict=<...>`. Exit 0 normally; exit 5 if a challenge/logout stopped it (and DO NOT close on the human-action path — leave the browser as-is, like the existing subcommands).
7. Keep the `argparse` wiring consistent with the existing subcommands; register `continuity-temp` with `set_defaults(func=run_continuity_temp)`.

## Hard rules (same as the existing probe)
- Attach-only; NEVER `browser.close()`/`context.close()`; only `session.close()`. Never touch operator tabs.
- Fail-closed on challenge/login (reuse `connect()`/`recheck_safe`); never click a challenge; never automate login.
- Human-paced; redact `/c/<id>`; never log credentials/cookies/tokens.

## Verify (OFFLINE — do NOT run the probe)
- `uv run python -c "import ast; ast.parse(open('scripts/m008b_real_probe.py').read()); print('PARSE_OK')"`
- `uv run python -c "import scripts.m008b_real_probe as m; assert hasattr(m,'run_continuity_temp'); print('IMPORT_OK')"`
- Confirm no `src/` or `tests/` files changed (probe + report only). Save outputs to your report.

## Report `orchestration/reports/M-008b/E5-worker-report.md`
STATUS; the subcommand behavior; how you handled the `tests/` import (import vs mirror); parse/import outputs; confirmation you did NOT run it / did NOT touch the network; commit sha (no push); `ESTIMATE:`/`ACTUAL:`/`REWORK-CAUSE:`.

Commit the slice. NEVER `git push`. Do NOT run the probe.
