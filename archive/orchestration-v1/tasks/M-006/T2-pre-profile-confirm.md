# T2-pre — Signed-in PROFILE CONFIRMATION (ONE real worker, headed, ZERO messages)

You are a fresh real-site worker. You inherit NOTHING except this file — every rule, path, and recipe you need is below. This is a REAL chatgpt.com leg authorized under D-002, but it sends **ZERO prompts** (zero quota). Your ONLY job: determine which Chromium profile is signed into chatgpt.com, by **rendering the page and reading login state** — never by inspecting profile files. Read the SAFETY BLOCK first and obey it literally.

## ⛔ SAFETY BLOCK — obey exactly (you inherit nothing; this is the whole law)

- Real-site contact is permitted ONLY in this leg for the narrow purpose below. You SEND ZERO prompts (a "message" = a prompt submitted to ChatGPT; you submit none). You only navigate and observe.
- HEADED browser ONLY. Human-paced: small waits (1–3 s) between actions. ONE real session at a time (you are the only real worker; never open two contexts at once — close one before opening the next).
- LOGIN IS NEVER AUTOMATED. If a page is logged out / shows an auth or login wall → record that and STOP (this is a normal classification outcome, not an error to fix). NEVER type into a login form, NEVER submit credentials, NEVER click through sign-in, NEVER test logout, NEVER sign out.
- NEVER read, copy, store, print, screenshot, commit, or log: credentials, cookies, session tokens, auth headers, browser local storage, or browser-profile CONTENTS. The profile path is OPAQUE config you pass to Playwright; you NEVER open or inspect files inside it.
- NO account identifiers anywhere (email, display name, org/workspace name, phone, conversation titles/ids). Classify login state with GENERIC structural markers only (a composer vs login/signup affordances). If a signed-in page incidentally shows a name/email, do NOT record it — record only the boolean "composer present".
- Profile lock: if a Chromium is already running on the profile (lock held), launch will fail. Detect it, raise the named error, STOP. DO NOT kill the operator's browser. DO NOT delete lock files (`SingletonLock` etc.).
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Do NOT edit `src/ask_chatgpt/selector_maps/real.json` in this leg. Do NOT write `.claude/`/`.agents/`. Do NOT touch the shared agent venv (`~/.local/share/agent-python/.venv`). NEVER `git push`. NEVER `git commit` in this leg.

## Why this leg exists (context — verify, don't trust)

A prior worker launched headed Chromium against `--profile-directory=Default` and hit a **login wall** — that profile is logged OUT. The operator states the signed-in chatgpt.com session lives in the Chromium profile **named `agent`**, which maps to the directory **`Profile 1`** under `~/.config/chromium`. Your job is to **independently confirm** that `Profile 1` renders signed-in (and record it), so the next leg targets the right profile. You verify the operator's claim from ground truth; you do not assume it.

Ground truth already probed by the manager at dispatch: Chromium is NOT running, no `SingletonLock` present (profile unlocked), `DISPLAY=:0` with `~/.Xauthority` present, and `~/.config/chromium` contains exactly these profile dirs: `Default`, `Profile 1`, `System Profile`. (`System Profile` is Chromium-internal — IGNORE it; never probe it.)

## Preflight — do FIRST, in this order, 0 messages

1. **Display:** confirm `echo "$DISPLAY"` is non-empty (expect `:0`). If empty/unset → STATUS BLOCKED `no reachable display` (operator action: run the mission from the desktop session so DISPLAY+XAUTHORITY reach the worker). Do NOT fall back to headless.
2. **Lock:** if `~/.config/chromium/SingletonLock` exists (use `os.path.lexists`) OR a real `/usr/bin/chromium` browser process is running (`pgrep -x chromium`) → STATUS BLOCKED `profile locked` (operator action: "close the Chromium using ~/.config/chromium, then resume M-006 T2-pre"). Do not kill it; do not delete the lock.

## Probe procedure — `Profile 1` FIRST, then `Default` only if needed

Write your probe as a Python script under `tmp/` and run it with `uv run python <script>` from the repo root (NOT the shared agent venv). Run `uv sync --all-groups` once first (quick if already synced; Playwright must be importable). Launch recipe — SYSTEM binary against the SYSTEM profile, **headed**:

```python
import os, time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

PROFILE_DIR = "/home/abhmul/.config/chromium"   # opaque; NEVER inspect contents
CHROMIUM    = "/usr/bin/chromium"               # MANDATORY: matches the system profile

def classify(profile_directory):
    """Return one of: 'signed-in' | 'logged-out' | 'ambiguous', plus a short generic reason.
    NEVER type into any form. NEVER record account identifiers."""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR, headless=False, executable_path=CHROMIUM,
            accept_downloads=False, args=[f"--profile-directory={profile_directory}"],  # space in 'Profile 1' is fine as ONE list element
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://chatgpt.com", wait_until="load", timeout=60000)
            time.sleep(3)                      # human-paced settle
            host = (urlparse(page.url).hostname or "")
            path_shape = urlparse(page.url).path  # SHAPE only; never log query string
            # --- generic structural markers (NO account info) ---
            # signed-in: a prompt composer exists in the main app
            composer = page.locator(
                "#prompt-textarea, textarea[data-testid*='prompt'], "
                "div[contenteditable='true'], textarea[placeholder]"
            ).first
            composer_present = composer.count() > 0 and composer.is_visible()
            # logged-out: redirected to an auth host, or visible login/signup affordances
            auth_host = any(h in host for h in ("auth.openai.com", "auth0", "accounts."))
            login_cta = page.get_by_role("button", name=__import__("re").compile(r"log ?in|sign ?up", __import__("re").I)).count() \
                        + page.get_by_role("link", name=__import__("re").compile(r"log ?in|sign ?up", __import__("re").I)).count()
            # --- decide, prefer the unambiguous signal ---
            if auth_host:
                return "logged-out", f"redirected to auth host; path-shape={path_shape}"
            if composer_present and login_cta == 0:
                return "signed-in", f"composer visible on host={host}; path-shape={path_shape}"
            if (not composer_present) and login_cta > 0:
                return "logged-out", f"login/signup affordance present on host={host}; path-shape={path_shape}"
            return "ambiguous", f"composer_present={composer_present} login_cta={login_cta} host={host} path-shape={path_shape}"
        finally:
            ctx.close()   # ALWAYS clean-close so no stale lock is left
```

Procedure:
1. **Probe `Profile 1` first.** Print the verdict + reason. If `signed-in` → that profile WINS; skip step 2.
2. **Only if `Profile 1` is `logged-out` or `ambiguous`:** wait ~2 s (ensure the first context fully closed), then probe `Default` once. (Probe `Profile 1` and `Default` only — never `System Profile`.)
3. **Decide the winner:** the FIRST profile that classifies `signed-in` wins; record its `--profile-directory` name (`Profile 1` or `Default`). If neither is `signed-in`, there is no winner → PARTIAL (operator action below).
4. Never relaunch more than necessary; never open two contexts simultaneously; always `ctx.close()` in `finally`. If a crash leaves a stale lock, do NOT delete it — report it.

## Output — write `orchestration/reports/M-006/T2-pre.md` (cap ~120 lines)

Record, in plain terms (NO account identifiers, NO cookies/tokens, NO profile-file contents):
- Per probed profile: the verdict (`signed-in` / `logged-out` / `ambiguous`) and the GENERIC reason string (composer presence, auth-host redirect, login-CTA count, path-SHAPE only).
- **`SIGNED_IN_PROFILE_DIRECTORY: <name>`** — the winning `--profile-directory` value (e.g. `Profile 1`), or `NONE` if no profile was signed-in.
- Confirmation that ZERO prompts were sent and the audit ledger was NOT written (this leg spends 0 messages).
- `MESSAGES_USED: 0`.

## Honest outcomes (name the exact next action)

- **`Profile 1` signed-in** → STATUS DONE, `SIGNED_IN_PROFILE_DIRECTORY: Profile 1`. Next: manager dispatches T2 discovery against `Profile 1`.
- **`Profile 1` logged-out but `Default` signed-in** → STATUS DONE, `SIGNED_IN_PROFILE_DIRECTORY: Default` (note the discrepancy vs operator's expectation). Next: T2 targets `Default`.
- **Neither signed-in** → STATUS PARTIAL, `SIGNED_IN_PROFILE_DIRECTORY: NONE`. Exact operator action: "Open Chromium, sign into chatgpt.com in the profile named 'agent' (Profile 1), confirm a chat composer is visible, then CLOSE Chromium and tell the team lead to resume M-006." Report the per-profile verdicts so the operator sees what rendered.
- **`profile locked` / `no reachable display`** → STATUS BLOCKED with the named operator action above. Clean-close the browser; leave locks alone.

## Telemetry + report footer

- First lines: `START_TIMESTAMP:` (`date -Iseconds`) and `ESTIMATE: T2-pre 5m`.
- Near top: `MESSAGES_USED: 0`.
- Last two lines: `END_TIMESTAMP:` (`date -Iseconds`) and `T2-pre-STATUS: DONE` (a signed-in profile was confirmed) / `PARTIAL` (no signed-in profile found) / `BLOCKED` (named precondition failed). If PARTIAL/BLOCKED, state the EXACT resume action.
