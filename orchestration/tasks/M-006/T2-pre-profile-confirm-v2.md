# T2-pre v2 — ROBUST signed-in profile confirmation (ONE real worker, headed, ZERO messages)

You are a fresh real-site worker. You inherit NOTHING except this file. This is a REAL chatgpt.com leg under D-002 that sends **ZERO prompts** (zero quota). A prior probe (v1) used only a 3-second settle and reported `Profile 1` logged-out / `Default` ambiguous — but the operator states they ARE signed into the profile named `agent` (= dir `Profile 1`). v1's verdict may be a **page-hydration timing artifact** (chatgpt.com is a heavy JS SPA; 3 s is too short, and v1's "Default = nothing rendered" result is a tell-tale incomplete-load sign). Your job: **re-classify robustly** with proper load-waiting and richer markers, so we either confirm signed-in or confirm logged-out with high confidence. Read the SAFETY BLOCK and obey it literally.

## ⛔ SAFETY BLOCK — obey exactly (you inherit nothing; this is the whole law)

- You SEND ZERO prompts (a "message" = a prompt submitted to ChatGPT; you submit none). You only navigate and observe. Write NOTHING to any audit ledger.
- HEADED browser ONLY. Human-paced. ONE real session at a time — close one context before opening the next; never two at once.
- LOGIN IS NEVER AUTOMATED. Logged-out is a normal classification OUTCOME, not an error to fix. NEVER type into a login form, submit credentials, click sign-in, test logout, or sign out.
- NEVER read, copy, store, print, screenshot, commit, or log: credentials, cookies (values OR names), session tokens, auth headers, local storage, or browser-profile CONTENTS. Do NOT call `context.cookies()` or read `Cookies`/`Local State`/`Login Data` files. The profile path is OPAQUE config passed to Playwright; you never open files inside it.
- NO account identifiers anywhere: email, display name, org/workspace, phone, conversation titles, conversation ids/URLs. You may COUNT elements (e.g. number of `a[href^='/c/']` links) but NEVER record their href values, text, or any id. Do NOT record the page title if it is anything other than a generic value containing exactly "ChatGPT" — instead record `title_generic=true/false` and its character length only.
- Profile lock: if `~/.config/chromium/SingletonLock` exists or `/usr/bin/chromium` is running → STATUS BLOCKED `profile locked` (operator: "close Chromium using ~/.config/chromium, then resume"). Do not kill it; do not delete locks.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Do NOT edit `src/.../real.json`. Do NOT write `.claude/`/`.agents/`. Do NOT touch the shared agent venv. NEVER `git push`/`git commit`.

## Preflight (0 messages)

1. `echo "$DISPLAY"` non-empty (expect `:0`); else STATUS BLOCKED `no reachable display`.
2. `os.path.lexists("~/.config/chromium/SingletonLock")` is False AND `pgrep -x chromium` empty; else STATUS BLOCKED `profile locked`.
3. Record the worker's secret-backend env (safe diagnostics, no profile contents): value of `DBUS_SESSION_BUS_ADDRESS` (set/unset), and whether `gnome-keyring-daemon` / `kwalletd5` / `kwalletd6` processes are running (`pgrep`). This tells us whether keyring-based cookie decryption is even possible in this session.

## Robust probe (Python via `uv run python <script>` from repo root; run `uv sync --all-groups` once first)

Launch headed, SYSTEM binary on the SYSTEM profile. KEY DIFFERENCE vs v1: wait for the SPA to hydrate before classifying.

```python
import os, re, time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

PROFILE_DIR = "/home/abhmul/.config/chromium"   # opaque; NEVER inspect contents
CHROMIUM    = "/usr/bin/chromium"

def probe(profile_directory):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR, headless=False, executable_path=CHROMIUM,
            accept_downloads=False, args=[f"--profile-directory={profile_directory}"],
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            # POLL up to 20s for a CONFIDENT signal instead of a fixed sleep
            verdict, reason, snap = "ambiguous", "", {}
            for _ in range(20):
                host = urlparse(page.url).hostname or ""
                path_shape = urlparse(page.url).path
                auth_host = any(h in host for h in ("auth.openai.com", "auth0", "accounts."))
                # signed-in-only chrome (guest mode does NOT have conversation history links):
                composer   = page.locator("#prompt-textarea, div[contenteditable='true']").first
                composer_v = composer.count() > 0 and composer.is_visible()
                hist_links = page.locator("a[href^='/c/']").count()          # COUNT only; never read hrefs
                model_btn  = page.locator("[data-testid='model-switcher-dropdown-button'], button[aria-label*='Model' i]").count()
                acct_btn   = page.locator("[data-testid*='profile-button'], button[aria-label*='Account' i], [data-testid='accounts-profile-button']").count()
                # logged-out chrome (chatgpt.com shows BOTH Log in and Sign up):
                login_ctl  = page.get_by_role("button", name=re.compile(r"log ?in", re.I)).count() + page.get_by_role("link", name=re.compile(r"log ?in", re.I)).count()
                signup_ctl = page.get_by_role("button", name=re.compile(r"sign ?up", re.I)).count() + page.get_by_role("link", name=re.compile(r"sign ?up", re.I)).count()
                signed_in_chrome = composer_v or hist_links > 0 or model_btn > 0 or acct_btn > 0
                logged_out_chrome = auth_host or (login_ctl > 0 and signup_ctl > 0)
                snap = dict(host=host, path_shape=path_shape, composer=composer_v, hist_links=hist_links,
                            model_btn=model_btn, acct_btn=acct_btn, login_ctl=login_ctl, signup_ctl=signup_ctl)
                if signed_in_chrome and not (login_ctl > 0 and signup_ctl > 0):
                    verdict, reason = "signed-in", f"signed-in chrome present {snap}"; break
                if logged_out_chrome and not signed_in_chrome:
                    verdict, reason = "logged-out", f"logged-out chrome {snap}"; break
                time.sleep(1)
            else:
                reason = f"no confident signal after 20s poll {snap}"
            return verdict, reason, snap
        finally:
            ctx.close()
```

Procedure: probe **`Profile 1` first**; print `verdict, reason`. Then probe **`Default`** (also robustly — v1 left it ambiguous). Never `System Profile`. Never two contexts at once; always `ctx.close()`.

Decision: first profile that classifies **signed-in** wins; record its `--profile-directory` name. If neither → NONE.

## Output — `orchestration/reports/M-006/T2-pre-v2.md` (cap ~120 lines)

- Worker secret-backend env: `DBUS_SESSION_BUS_ADDRESS` set?/unset; gnome-keyring/kwallet running? (yes/no).
- Per profile (`Profile 1`, `Default`): the verdict (`signed-in`/`logged-out`/`ambiguous`) + the structural snapshot dict (booleans/counts only — NO hrefs, NO ids, NO titles beyond `title_generic`+length).
- **`SIGNED_IN_PROFILE_DIRECTORY: <name|NONE>`**.
- Confirm ZERO prompts sent, ledger untouched. `MESSAGES_USED: 0`.

## Honest outcomes (name the exact next action)

- **A profile is signed-in** → STATUS DONE, `SIGNED_IN_PROFILE_DIRECTORY: <name>`. (Then manager runs T2 discovery there.)
- **Neither signed-in, but the snapshots show login+signup chrome after full hydration** → STATUS PARTIAL, `NONE`, conclusion = genuinely logged out. Operator action: "Open Chromium, sign into chatgpt.com in the profile named 'agent' (Profile 1) IN THIS desktop session, confirm a chat composer + your conversation sidebar are visible, CLOSE Chromium, then tell the team lead to resume M-006."
- **Neither signed-in AND keyring is absent AND render is ambiguous (no clear login/composer)** → STATUS PARTIAL, `NONE`, FLAG the possibility that the session cookie cannot be decrypted in this environment; recommend the operator confirm whether their signed-in Chromium runs in this same TTY+X session (no keyring daemon) or elsewhere. Do NOT guess — report the snapshot facts and let the manager/operator decide.
- **`profile locked` / `no reachable display`** → STATUS BLOCKED with the named operator action.

## Telemetry + footer

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T2-pre-v2 6m`.
- `MESSAGES_USED: 0` near top.
- Last two lines: `END_TIMESTAMP:` and `T2-pre-v2-STATUS: DONE|PARTIAL|BLOCKED`.
