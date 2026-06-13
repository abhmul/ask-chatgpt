# T2 (CDP) — Real-site selector + affordance DISCOVERY over a CDP-attached tab (ONE real worker, HARD ≤12 messages)

You are a fresh real-site worker. **You inherit NOTHING except this file.** Everything is below. This is a REAL chatgpt.com leg, authorized ONLY under D-002 (and its CDP addendum) within a hard message budget. Read the SAFETY BLOCK first and obey it literally. The repo destructive-guard hook blocks command text containing certain destructive substrings — if you ever need to revert tracked files use `git stash push -u`, never `git checkout`/`git clean`.

## ⛔ SAFETY BLOCK — obey exactly (you inherit nothing; this is the whole law)

- **Real channel = CDP ATTACH, never launch.** The operator's OWN signed-in Chromium is already running with `--remote-debugging-port=9222`. You ATTACH to it via `connect_over_cdp("http://127.0.0.1:9222")`. You NEVER launch a browser, NEVER use `launch_persistent_context`, NEVER pass a profile path. (Cloudflare hard-blocks Playwright-LAUNCHED browsers on chatgpt.com — that is why this whole leg is CDP-attach. Do not try to launch.)
- **NO stealth / anti-detection of ANY kind.** No fingerprint spoofing, no `navigator.webdriver` patching, no `--disable-blink-features=AutomationControlled`, no UA spoofing, no evasion libraries. This is explicitly forbidden (D-002 CDP addendum). If a challenge appears, a HUMAN clears it (protocol below) — you never circumvent it.
- **Tab discipline (hard invariant — the #1 safety rule):** at attach, the operator's existing tabs live in `context.pages`. You record them and **NEVER touch, read, navigate, click, or close any of them.** You open exactly ONE brand-new tab via `context.new_page()` and that new page is the ONLY page you ever act on. You MAY freely navigate/click/inspect YOUR OWN tab. You may open at most one or two extra of your own tabs if needed, tracking each, and close only those.
- **NEVER quit / close the browser (detach only).** Do **NOT** call `browser.close()` or `context.close()` on the CDP-attached browser — Playwright would quit the operator's entire browser. Teardown = close ONLY the tab(s) YOU opened, then let the `with sync_playwright()` block exit to drop the CDP connection. The browser must still be alive and the operator's tabs untouched when you finish. (Reference implementation to MIRROR: `src/ask_chatgpt/driver.py` `_start_cdp_context()` ~line 404 and its `close()`/detach path — read it; it was verified in T1b to detach-not-quit.)
- **LOGIN/LOGOUT IS NEVER AUTOMATED.** If the attached tab shows a logged-out / auth / login wall → STOP, write the named actionable error, report BLOCKED `logged out`. NEVER type into a login form, NEVER submit credentials, NEVER test logout, NEVER sign out.
- **Cloudflare / human-verification challenge → challenge-pause protocol (below).** STOP all automation, log `HUMAN-ACTION-NEEDED`, poll READ-ONLY (no clicks/keystrokes) ≤10 min for the human to clear it; cleared → continue; else → PARTIAL.
- NEVER read, copy, store, print, screenshot, commit, or log: credentials, cookies, session tokens, auth headers, browser local storage, or browser-profile CONTENTS. You never query `/json/list`-style tab inventories that could capture the operator's tab URLs.
- **NO account identifiers anywhere** (email, display name, org/workspace name, phone, real conversation titles/refs). When you record a conversation URL, record only its SHAPE (e.g. `/c/<redacted-uuid>`), never the real id.
- Use ONLY disposable new chats and SYNTHETIC data (tiny dummy text/zip, harmless prompts). Never upload private source, the repo, the predecessor archive, or anything real.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Do **NOT** edit `src/ask_chatgpt/selector_maps/real.json` in THIS leg (a separate editing leg installs your findings). Do NOT write `.claude/`/`.agents/`. Do NOT touch the shared agent venv. NEVER `git push`. NEVER `git commit` in this leg.
- ONE real worker only — you are it; never open two real sessions. Human-paced: 1–3 s waits between actions; no rapid-fire sends.

## Message budget — HARD CAP ≤ 12 prompt-sends (this leg)

A "message" = one prompt actually SENT to ChatGPT (consumes the operator's quota). Pure DOM observation, opening menus, navigation, reopening a chat by URL, and attaching a file WITHOUT sending are NOT messages (0 cost). Only a click that SUBMITS a prompt counts.

- Maintain an integer counter starting at 0. **BEFORE each send**, append ONE line to the shared ledger, THEN send:
  `printf '%s\tT2\t%s\t%s\n' "$(date -Iseconds)" "<one-word-purpose>" "<conv-shape e.g. /c/redacted>" >> tmp/real-audit-20260612T194143/messages.log`
- The ledger ALREADY exists (header only); APPEND only, never truncate. The 30-message mission cap spans ALL legs and ALL ledgers; your share is ≤12.
- If you reach 12 sends, STOP sending, finish observing/reporting with what you have, report STATUS PARTIAL with `MESSAGES_USED: 12`.
- Spend frugally. **Target ~5–8 sends total.** Prioritize the UC1–3-critical keys (see "PRIORITY").

## Preflight — do FIRST, in this order, 0 messages

1. **CDP reachable?** `urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5)` returns JSON (loopback GET, read-only, 0 messages). If it fails/refuses → BLOCKED `CDP_UNREACHABLE` (operator action: `chromium --profile-directory='Profile 1' --remote-debugging-port=9222`, signed into chatgpt.com). Do NOT launch anything yourself.
2. **Attach:** `browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")`. Get `ctx = browser.contexts[0]` (the operator's default context). If there are zero contexts → BLOCKED `unexpected CDP topology` (report what you saw). Record `preexisting = list(ctx.pages)` — these are the operator's tabs; never touch them.
3. **Open YOUR tab:** `page = ctx.new_page()`. Navigate it: `page.goto("https://chatgpt.com", wait_until="load", timeout=60000)`; `time.sleep(2)`.
4. **Challenge check (read-only):** if `page.title()` lower-cases to contain `"just a moment"` OR `page.query_selector("iframe[src*='challenges.cloudflare.com'], #challenge-running, #cf-challenge-running")` is present → run the **challenge-pause protocol** (below) before any further action.
5. **Login check (read-only):** inspect `page.url`. If host contains `auth.openai.com`/`auth0`/ starts `accounts.`, OR path starts `/auth`,`/login`,`/api/auth`, OR a login wall is visibly present → BLOCKED `logged out` (operator action: "sign into chatgpt.com in the running browser, then resume M-006 T2"). NEVER automate sign-in.
6. Only if logged in, on chatgpt.com, no challenge → proceed to discovery.

### Challenge-pause protocol (verbatim — replaces all "launch" rules)
On detecting a Cloudflare/human-verification UI at ANY point:
1. STOP all automation actions immediately (no clicks, no keystrokes, no sends, no navigation of any tab).
2. Print + record to your report: `HUMAN-ACTION-NEEDED: a Cloudflare/human-verification challenge is present in the tool's tab; please clear it in the browser window.`
3. Poll READ-ONLY every ~20 s up to 10 minutes total: re-read `page.title()` + the challenge marker selectors ONLY (no interaction).
4. Cleared (markers gone, chatgpt app renders) → continue discovery. Not cleared after 10 min → end the leg, STATUS PARTIAL, state `CHALLENGE_NOT_CLEARED` and that the operator must clear the challenge then resume T2.
NEVER interact with the challenge UI programmatically. NEVER use stealth to avoid it.

## Attach + teardown recipe (raw `connect_over_cdp`; MIRROR driver.py's verified-safe detach)

Write your exploration as a Python script run via `uv run python <script>` (NOT the shared agent venv; this repo's venv via `uv run`). Skeleton — keep the teardown EXACTLY as shown:

```python
import time, json, urllib.request
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
hosts = set()                      # asset-domain enumeration (HOST only, never full URL)

# preflight 1: CDP reachable (read-only loopback GET)
urllib.request.urlopen(CDP + "/json/version", timeout=5)   # -> BLOCKED CDP_UNREACHABLE on failure

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)             # ATTACH — never launch
    ctx = browser.contexts[0]                              # operator's existing context
    preexisting = list(ctx.pages)                          # operator tabs — NEVER touch
    ctx.on("request", lambda r: hosts.add(urlparse(r.url).hostname or ""))
    page = ctx.new_page()                                  # OUR tab — the ONLY page we drive
    my_pages = [page]
    try:
        page.goto("https://chatgpt.com", wait_until="load", timeout=60000)
        time.sleep(2)
        # ... challenge check -> pause protocol; login check -> BLOCKED; then DISCOVERY ...
    finally:
        for pg in my_pages:
            try: pg.close()        # close ONLY tabs we opened
            except Exception: pass
        # DETACH: do NOT browser.close(); do NOT ctx.close(); exiting the `with` drops the
        # CDP connection WITHOUT quitting the operator's browser (verified in T1b).
```

- Record requested HOSTS only (never full URLs/query — they can carry tokens). `hosts` becomes your asset-domain list for the allowlist.
- Allow assets to load (do NOT abort) so the page renders for observation. (Allowlist ENFORCEMENT is validated in a later leg; here you ENUMERATE the legit domains.)
- Confirm at the end that `len(ctx.pages) >= len(preexisting)` and every `preexisting` page is still present (tab-hygiene self-check; record the result).

## What to resolve (map each finding to a real.json key; leave UNVERIFIED keys EMPTY)

Target selector map schema (EXACT keys from `src/ask_chatgpt/selector_maps/real.json`):
`selectors = {ready_root, chat_list, chat_item, new_chat_button, composer, send_button, model_menu, model_option, model_option_disabled, assistant_message, message_body, streaming_marker, completion_marker, copy_button, download_artifact, upload_input, login_wall, conversation_not_found, truncation_marker, rate_limit_marker}`; `attributes = {conversation_ref, turn_id}`.

Prefer STABLE selectors: ARIA roles, `data-testid`/`data-*` attributes, accessible names — NOT volatile hashed class names. For each filled key record the selector AND a one-line justification of why it's stable.

**PRIORITY (must-have for downstream UC1–3):** `ready_root`, `composer`, `send_button`, `new_chat_button`, `assistant_message`, `message_body`, `completion_marker`, and the `conversation_ref` source. Get these FIRST (all 0-message). Then `download_artifact`, `upload_input`. The rest are best-effort.

- **0-message (pure observation):** open a new chat → `ready_root`, `composer`, `send_button`, `new_chat_button`, `chat_list`, `chat_item`. Open the model picker → `model_menu`, `model_option`, `model_option_disabled` (note the disabled-state hook), then close it. Navigate YOUR tab to a bogus `https://chatgpt.com/c/<random-uuid>` → `conversation_not_found` marker (this navigates only your tab). `conversation_ref`: report how the active conversation id is obtained — almost certainly the URL `/c/<id>`; if there is NO DOM attribute carrying it, SAY SO explicitly (key finding — the driver may need a URL-based source, not a DOM attribute).
- **1 send — completion + response selectors:** send a tiny prompt (e.g. "Reply with exactly one short word."). Observe streaming→complete: `assistant_message` (latest assistant turn container), `message_body`, `streaming_marker` (present while generating), `completion_marker` (the most reliable end-of-turn signal — describe what it ACTUALLY is: stop-button-gone / copy-button-appears / a data attribute), `copy_button`. Record the recommended completion strategy + a stable wait (ms).
- **1–2 sends — download affordance (UC2):** ask GPT to produce a TINY downloadable file (small zip or text file, synthetic content). Observe whether a download artifact/card/link appears (`download_artifact`) and whether a Playwright `Download` event fires (wrap any download-control click in `with page.expect_download() as dl:`). Record: download offered? normal browser `Download` seen? suggested filename/MIME (nonsecret)? If NO download affordance appears, RECORD that (D-001 revisit signal — fenced base64 fallback then carries UC2).
- **1 send — upload affordance (UC2):** locate the attachment/upload `input[type=file]` (`upload_input`; may be hidden behind a "+"/attach menu — open it; attaching a file is 0 messages). Attach a tiny SYNTHETIC zip (2–3 small text files), then send a prompt asking GPT to list the files it sees. Record: upload accepted? zip accepted? README/files visible to model? selectors for the file input/chip.
- **Cannot/Must-not trigger (leave EMPTY, explain):** `login_wall` (do NOT log out to see it — the URL heuristic covers logged-out), `truncation_marker` (do not force a giant generation), `rate_limit_marker` (NEVER provoke rate limits). `turn_id`: only fill if a stable per-turn id attribute genuinely exists; else empty + note.
- **Session pinning (0 messages):** note the new chat's URL shape; navigate YOUR tab away and back to that URL; confirm it reopens the same conversation. (You cannot restart the operator's browser — do NOT attempt; instead document reopen-by-URL within the session and note that cross-restart persistence is operator-observable, not tested here.) UC1 continuity depends on URL pinning.

Also answer the **10 unknowns** in `docs/runbooks/observe-chatgpt-unknowns.md` (read it for the full question set: zip upload limits; download offering + Playwright Download integrity; session pinning; model-selection hooks; copy/clipboard behavior; completion signal; upload UI hooks; text truncation limits; artifact↔turn identity; operator UX/failure messaging). For each: fact observed, selector(s)/behavior, anonymized evidence, and any D-001 revisit signal.

## Outputs (this leg writes NO source files)

1. `orchestration/reports/M-006/real-selectors-proposed.json` — the FULL schema (all 20 selector keys + 2 attribute keys present), verified keys filled with the chosen selector string, every UNVERIFIED key set to `""` (fail-closed). Add a sibling `"_justifications"` object mapping each filled key → its one-line stability rationale, and a `"_unverified"` list naming empty keys + why. NO account identifiers, NO real conversation ids.
2. `orchestration/reports/M-006/discovery.md` — per-unknown answers (the 10 above) with fact + selector(s)/behavior + anonymized evidence (path-shape URLs only) + D-001 revisit signals (is DOM-read reliable vs copy? is download-primary real for bundles?). Include the ENUMERATED asset-domain/host list (distinct hostnames the real session legitimately requested) for the enforced allowlist. Include `MESSAGES_USED: <n>` and a per-send purpose list matching the ledger. Include the tab-hygiene self-check result. **This OVERWRITES the stale BLOCKED discovery.md from the pre-CDP probe — that is expected.**

## Honest BLOCKED conditions (STOP, report, name the exact operator action)

`CDP_UNREACHABLE` (→ operator launches `chromium --profile-directory='Profile 1' --remote-debugging-port=9222`, resume T2) · `logged out` (→ operator signs in, resume T2) · `CHALLENGE_NOT_CLEARED` (→ operator clears the Cloudflare challenge, resume T2) · `unexpected CDP topology` (report what you saw). On any BLOCKED/PARTIAL: run the safe teardown (close only your tabs; detach; never quit the browser), write whatever partial findings you have. A blocked leg MUST leave `src/real.json` and the test suite untouched (you never edit them here).

## Telemetry + report footer (write report to `orchestration/reports/M-006/discovery.md`, cap ~250 lines)

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T2 <minutes>m`.
- Near top: `MESSAGES_USED: <n>` (MUST equal the count of T2 lines you appended to the ledger).
- Last two lines: `END_TIMESTAMP:` (`date -Iseconds`) and `T2-STATUS: DONE` (full discovery) / `PARTIAL` (budget hit or some keys unverified but usable) / `BLOCKED` (named precondition failed). If PARTIAL/BLOCKED, state the EXACT resume action.
