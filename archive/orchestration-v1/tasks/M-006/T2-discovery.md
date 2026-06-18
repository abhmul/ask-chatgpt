# T2 — Real-site selector + affordance DISCOVERY (ONE real worker, headed, HARD ≤12 messages)

You are a fresh real-site worker. You inherit NOTHING except this file. Everything is below. This is a REAL chatgpt.com leg, authorized ONLY under D-002 within a hard message budget. Read the SAFETY BLOCK first and obey it literally.

## ⛔ SAFETY BLOCK — obey exactly (you inherit nothing; this is the whole law)

- Real-site contact is permitted ONLY in this leg, ONLY within the message budget below, every prompt-send logged to the audit ledger BEFORE you send it.
- HEADED browser ONLY. Human-paced: small waits (1–3 s) between actions; NO rapid-fire sends. ONE real session only (you are the only real worker; never open two).
- LOGIN IS NEVER AUTOMATED. If the page is logged out / shows an auth or login wall → STOP, write the named actionable error, report BLOCKED. NEVER type into a login form, NEVER submit credentials, NEVER test logout, NEVER sign out.
- NEVER read, copy, store, print, screenshot, commit, or log: credentials, cookies, session tokens, auth headers, browser local storage, or browser-profile CONTENTS. The profile path is OPAQUE config you pass to Playwright; you never inspect inside it.
- NO account identifiers anywhere (email, display name, org/workspace name, phone, real conversation titles, private conversation refs). When you record a conversation URL, record only its SHAPE (e.g. `/c/<redacted-uuid>`), never the real id.
- Profile lock: if a Chromium is running on the profile (lock held), launch will fail. Detect it, raise the named error, STOP. DO NOT kill the operator's browser. DO NOT delete lock files (`SingletonLock` etc.).
- Use ONLY disposable new chats and SYNTHETIC data (tiny dummy text/zip, harmless prompts). Never upload private source, the repo, the predecessor archive, or anything real.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Do NOT edit `src/ask_chatgpt/selector_maps/real.json` in THIS leg (a separate editing leg installs your findings). Do NOT write `.claude/`/`.agents/`. Do NOT touch the shared agent venv. NEVER `git push`. NEVER `git commit` in this leg.

## Message budget — HARD CAP ≤ 12 prompt-sends (this leg)

A "message" = one prompt actually SENT to ChatGPT (consumes the operator's quota). Pure DOM observation, opening menus, navigation, and reopening a chat by URL are NOT messages (0 cost). Only `send_button` clicks that submit a prompt count.

- Maintain an integer counter starting at 0. BEFORE each send, append ONE line to the shared ledger, then send:
  `printf '%s\tT2\t%s\t%s\n' "$(date -Iseconds)" "<one-word purpose>" "<conv-shape e.g. /c/redacted>" >> tmp/real-audit-20260612T100518/messages.log`
- The ledger ALREADY exists and may hold other legs' lines; APPEND only, never truncate. The 30-message mission cap spans all legs; your share is ≤12.
- If you reach 12 sends, STOP sending, finish observing/reporting with what you have, and report STATUS PARTIAL with `MESSAGES_USED: 12`.
- Spend frugally. Target ~5–8 sends total. Prioritize the UC1–3-critical keys (see "Priority").

## Preflight — do FIRST, in this order, 0 messages

1. Display: confirm `echo "$DISPLAY"` is non-empty (expect `:0`). If empty/unset → BLOCKED `no reachable display` (operator action: run the mission from the desktop session / ensure DISPLAY+XAUTHORITY reach the worker). Do NOT fall back to headless.
2. Lock: if `~/.config/chromium/SingletonLock` exists (use `os.path.lexists`) OR a real `/usr/bin/chromium` browser process is running → BLOCKED `profile locked` (operator action: "close the Chromium using ~/.config/chromium, then resume M-006 T2"). Do not kill it; do not delete the lock.
3. Launch headed persistent context (recipe below). If launch raises a profile-in-use/singleton error → BLOCKED `profile locked` (same operator action). If launch/connection fails with a protocol/version mismatch (Playwright 1.60.0 vs system Chromium 149) → BLOCKED `playwright/chromium protocol mismatch` (operator action: note the exact error; recommend the Firefox fallback lane as an operator/manager decision — DO NOT switch browsers or copy the profile yourself).
4. Navigate to `https://chatgpt.com` (`wait_until="load"`, timeout 60000). Inspect `page.url`: if it is an auth/login redirect (host contains `auth.openai.com`/`auth0`/`accounts.`, or path starts `/auth`,`/login`,`/api/auth`) OR a login wall is visibly present → BLOCKED `logged out` (operator action: "sign into chatgpt.com in the browser, then resume M-006 T2"). NEVER automate the sign-in.
5. Only if logged in and on chatgpt.com → proceed to discovery.

## Launch recipe (use the SYSTEM binary against the SYSTEM profile)

Write your exploration as a Python script run via `uv run python <script>` (NOT the shared agent venv). Skeleton (adapt as needed; keep it headed and on the system binary):

```python
import os, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE = "/home/abhmul/.config/chromium"          # opaque; never inspect contents
CHROMIUM = "/usr/bin/chromium"                       # MANDATORY: matches the system profile (Chromium 149)
hosts = set()                                         # asset-domain enumeration (host only!)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE, headless=False, executable_path=CHROMIUM,
        accept_downloads=True, args=["--profile-directory=Default"],
    )
    try:
        ctx.on("request", lambda r: hosts.add(__import__("urllib.parse", fromlist=["urlparse"]).urlparse(r.url).hostname or ""))
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://chatgpt.com", wait_until="load", timeout=60000)
        time.sleep(2)
        # ... preflight login check, then discovery ...
    finally:
        ctx.close()   # ALWAYS clean-close so no stale lock is left
```

- Record requested HOSTS only (never full URLs/query — they can carry tokens). `hosts` becomes your asset-domain list.
- Always `ctx.close()` in `finally`. If a crash leaves a stale lock, do NOT delete it — report it.
- Allow assets to load (do not abort) so the page renders for observation. (Allowlist ENFORCEMENT is validated in a later leg; here you ENUMERATE the legit domains.)

## What to resolve (map each finding to a real.json key; leave UNVERIFIED keys EMPTY)

Target selector map schema (same keys as `src/ask_chatgpt/selector_maps/real.json`): selectors = {ready_root, chat_list, chat_item, new_chat_button, composer, send_button, model_menu, model_option, model_option_disabled, assistant_message, message_body, streaming_marker, completion_marker, copy_button, download_artifact, upload_input, login_wall, conversation_not_found, truncation_marker, rate_limit_marker}; attributes = {conversation_ref, turn_id}.

Prefer STABLE selectors: ARIA roles, `data-testid`/`data-*` attributes, accessible names — NOT volatile hashed class names. For each key, record the selector AND a one-line justification of why it's stable.

PRIORITY (must-have for downstream UC1–3): `ready_root`, `composer`, `send_button`, `new_chat_button`, `assistant_message`, `message_body`, `completion_marker`, and the `conversation_ref` source. Get these first. Then `download_artifact`, `upload_input`. The rest are best-effort.

- **0-message (pure observation):** open a new chat → `ready_root`, `composer`, `send_button`, `new_chat_button`, `chat_list`, `chat_item`. Open the model picker → `model_menu`, `model_option`, `model_option_disabled` (note disabled-state hook). Navigate to a bogus `https://chatgpt.com/c/<random-uuid>` → `conversation_not_found` marker. `conversation_ref`: report how the active conversation id is obtained (almost certainly the URL `/c/<id>`); if there is no DOM attribute carrying it, SAY SO explicitly (this is a key finding — the driver currently reads it as a DOM attribute and may need a URL-based source).
- **1 send — completion + response selectors:** send a tiny prompt (e.g. ask it to reply with one short line). Observe the streaming→complete transition: `assistant_message` (latest assistant turn container), `message_body`, `streaming_marker` (present while generating), `completion_marker` (the most reliable end-of-turn signal — describe what it actually is: stop-button-gone, copy-button-appears, a data attribute, etc.), `copy_button`. Record the recommended completion strategy + a stable wait.
- **1–2 sends — download affordance (UC2):** ask GPT to produce a TINY downloadable file (e.g. a small zip or text file with synthetic content). Observe whether a download artifact/card/link appears (`download_artifact`) and whether a Playwright `Download` event fires (use `with page.expect_download() as dl:` around the click if a download control exists). Record: download offered? normal browser `Download` event seen? suggested filename/MIME (nonsecret)? If no download affordance appears, RECORD that (D-001 revisit signal — fenced fallback then carries UC2).
- **1 send — upload affordance (UC2):** locate the attachment/upload `input[type=file]` (`upload_input`; it may be hidden behind a "+"/attach menu — open it). Attach a tiny SYNTHETIC zip (2–3 small text files), send a prompt asking GPT to list the files it sees. Record: upload accepted? zip accepted? readme/files visible to model? selectors for the file input/chip.
- **Cannot/Must-not trigger (leave EMPTY, explain):** `login_wall` (do NOT log out to see it — leave empty; the URL heuristic covers logged-out), `truncation_marker` (do not force a giant generation — leave empty unless naturally seen), `rate_limit_marker` (NEVER provoke rate limits — leave empty). `turn_id`: only fill if a stable per-turn id attribute genuinely exists; else empty + note.
- **Session pinning (0 messages):** note the new chat's URL shape, `ctx.close()`, relaunch, navigate back to that URL, confirm it reopens the same conversation. Record reopen-after-restart behavior (UC1 continuity depends on URL pinning).

## Outputs (this leg writes NO source files)

1. `orchestration/reports/M-006/real-selectors-proposed.json` — the FULL schema (all 20 selector keys + 2 attribute keys present), verified keys filled with the chosen selector string, every UNVERIFIED key set to `""` (fail-closed). Add a sibling `"_justifications"` object mapping each filled key → its one-line stability rationale, and a `"_unverified"` list naming empty keys + why. NO account identifiers, NO real conversation ids.
2. `orchestration/reports/M-006/discovery.md` — per the 10 unknowns in `docs/runbooks/observe-chatgpt-unknowns.md` (read it for the full question set), answer each with: fact (observed), the selector(s)/behavior, evidence (anonymized — path-shape URLs only), and any D-001 revisit signal (is DOM-read reliable vs copy? is download-primary real for bundles?). Include the ENUMERATED asset-domain/host list (distinct hostnames the real session legitimately requested) for the enforced allowlist. Include `MESSAGES_USED: <n>` and a per-send purpose list matching the ledger.

## Honest BLOCKED conditions (STOP, report, name the exact operator action)

`no reachable display` · `profile locked` (→ close Chromium, resume T2) · `logged out` (→ sign in, resume T2) · `playwright/chromium protocol mismatch` (→ record error; Firefox fallback is an operator/manager decision). On any BLOCKED: clean-close the browser, write whatever partial findings you have, set STATUS BLOCKED with the exact resume action. A blocked leg must leave `src/real.json` and the test suite untouched (you never edit them here).

## Telemetry + report footer (write report to `orchestration/reports/M-006/discovery.md`, cap ~250 lines)

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T2 <minutes>m`.
- Near top: `MESSAGES_USED: <n>` (must equal the count of T2 lines you appended to the ledger).
- Last two lines: `END_TIMESTAMP:` (`date -Iseconds`) and `T2-STATUS: DONE` (full discovery) / `PARTIAL` (budget hit or some keys unverified but usable) / `BLOCKED` (named precondition failed). If PARTIAL/BLOCKED, state the EXACT resume action.
