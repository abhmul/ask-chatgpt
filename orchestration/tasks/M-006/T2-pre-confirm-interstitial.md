# T2-pre v3 — CONFIRM the chatgpt.com interstitial (ONE real worker, headed, ZERO messages, DIAGNOSE-ONLY)

You are a fresh real-site worker. You inherit NOTHING except this file. ZERO prompts (zero quota). Two prior probes found that chatgpt.com, opened headed via Playwright on the operator's Chromium profiles, renders **neither the app (no composer) nor a normal logged-out page (no Log in/Sign up)** after 20 s — just chatgpt.com root with a 16-character title that is NOT "ChatGPT". Hypothesis: a **Cloudflare bot-detection interstitial** ("Just a moment…") is blocking the automated browser. Your ONLY job: **CONFIRM or REFUTE** that hypothesis from ground truth, and report whether it ever clears within 45 s. **You DIAGNOSE ONLY — you must NOT attempt to bypass, evade, or defeat any bot challenge** (no stealth flags, no `--disable-blink-features`, no webdriver patching, no clicking a challenge checkbox). Read the SAFETY BLOCK and obey it literally.

## ⛔ SAFETY BLOCK — obey exactly

- ZERO prompts to ChatGPT. Write NOTHING to any audit ledger. You only navigate + observe.
- HEADED only. ONE context at a time; close it in `finally`. Human-paced.
- LOGIN NEVER AUTOMATED. Do NOT type into any form, do NOT click any login/signup/challenge control, do NOT attempt to pass a CAPTCHA/Cloudflare challenge. If you see a challenge, OBSERVE it; do not interact.
- **NO bot-detection evasion.** Launch Chromium plainly (system binary, system profile, no anti-automation flags). We are DIAGNOSING, not bypassing.
- NEVER read/copy/store/log credentials, cookies (values or names), tokens, local storage, or profile CONTENTS. Do NOT call `context.cookies()`. Do NOT read `Cookies`/`Local State`/`Login Data`.
- NO account identifiers. Record the page `<title>` VERBATIM **only if** it matches a known-generic/interstitial prefix (`Just a moment`, `Attention Required`, `ChatGPT`, `Access denied`, `Please wait`, `Verifying`, `One moment`, `Redirecting`); for ANY other title record its length only (it could contain user content). For Cloudflare phrase checks, test for fixed generic strings (below) — never dump arbitrary page text.
- Profile lock → STATUS BLOCKED `profile locked` (operator: close Chromium). No reachable display → BLOCKED. Don't kill browsers, don't delete locks.
- Write only inside the repo (+ `tmp/`). No `.claude/`/`.agents/`. No shared agent venv. No `git push`/`git commit`.

## Probe (Python via `uv run python <script>` from repo root; `uv sync --all-groups` once first)

Probe **`Profile 1`** only (one profile is enough to confirm the interstitial; both prior profiles behaved identically). Launch headed, plainly:

```python
import re, time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

GENERIC_TITLE = re.compile(r"^(Just a moment|Attention Required|ChatGPT|Access denied|Please wait|Verifying|One moment|Redirecting)", re.I)
CF_PHRASES = ["Verifying you are human", "Enable JavaScript and cookies to continue",
              "needs to review the security of your connection", "Checking your browser",
              "Just a moment"]

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir="/home/abhmul/.config/chromium", headless=False,
        executable_path="/usr/bin/chromium", accept_downloads=False,
        args=["--profile-directory=Profile 1"],   # plain launch; NO anti-automation flags
    )
    timeline = []
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=60000)
        cleared_at = None
        for sec in range(0, 46, 2):                     # poll up to 45s
            raw_title = page.title() or ""
            title = raw_title if GENERIC_TITLE.match(raw_title) else f"<non-generic len={len(raw_title)}>"
            host = urlparse(page.url).hostname or ""
            # Cloudflare interstitial markers (generic, no account data):
            cf_iframe = page.locator("iframe[src*='challenges.cloudflare.com']").count()
            cf_running = page.locator("#challenge-running, #cf-challenge-running, #challenge-form, #challenge-stage").count()
            body_txt = (page.locator("body").inner_text(timeout=2000) or "") if True else ""
            cf_phrase = any(ph.lower() in body_txt.lower() for ph in CF_PHRASES)
            cf_present = bool(cf_iframe or cf_running or cf_phrase)
            # app / login markers (did it clear to a real page?):
            composer = page.locator("#prompt-textarea, div[contenteditable='true']").count()
            login_ctl = page.get_by_role("button", name=re.compile(r"log ?in|sign ?up", re.I)).count() \
                        + page.get_by_role("link", name=re.compile(r"log ?in|sign ?up", re.I)).count()
            timeline.append(dict(sec=sec, title=title, host=host, cf_iframe=cf_iframe,
                                 cf_running=cf_running, cf_phrase=cf_phrase, cf_present=cf_present,
                                 composer=composer, login_ctl=login_ctl))
            if composer or login_ctl:
                cleared_at = sec; break
            time.sleep(2)
    finally:
        ctx.close()
    # print timeline + summary for the report
```

IMPORTANT: `inner_text("body")` is read ONLY to test for the fixed Cloudflare phrases above and to set `cf_phrase` — do NOT store, print, or commit the body text itself. Only the boolean leaves the script.

## Output — `orchestration/reports/M-006/T2-pre-v3.md` (cap ~120 lines)

- The poll timeline: for each 2 s tick, the (sanitized) title token, host, the CF marker booleans/counts, composer count, login_ctl count. (Booleans/counts and sanitized titles ONLY — no body text, no ids.)
- **`INTERSTITIAL_CONFIRMED: cloudflare | other | none`** — `cloudflare` if any tick had `cf_present=True` (or the title was "Just a moment…"); `none` if it cleared to app/login; `other` if neither.
- **`CLEARED_TO_APP_OR_LOGIN: yes@<sec> | no`** — did the page ever reach a composer or login control within 45 s?
- `MESSAGES_USED: 0`; confirm zero prompts, ledger untouched, no bypass attempted.

## Footer

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) + `ESTIMATE: T2-pre-v3 7m`.
- Last two lines: `END_TIMESTAMP:` + `T2-pre-v3-STATUS: DONE` (diagnosis captured, whatever it is) / `BLOCKED` (display/lock precondition failed).
