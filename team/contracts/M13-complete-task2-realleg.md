# WORKER CONTRACT — M13-complete TASK 2 (ATTENDED REAL SITE): confirm scrape --with-attachments over the light path

You are a single WORKER (pi, tools `read,grep,find,ls,bash`) for repo `/home/abhmul/dev/ask-chatgpt`.
This contract is FULLY SELF-CONTAINED. You inherit nothing. Read it in full and execute end-to-end IN ORDER. Print a structured report to stdout (your stdout IS the deliverable).

This is an **ATTENDED REAL chatgpt.com leg** against a **shared, paid, operator-owned account** over an operator CDP Chromium at `http://127.0.0.1:9222`. Treat every step as consequential.

## ☢️ SAFETY / LEAK RULES — these dominate everything (read first, obey absolutely)
- **OWN-TAB-ONLY.** Inspect ONLY tabs the tool itself opens. NEVER read/touch operator or foreign tabs. **NEVER call `/json/list`** (only `/json/version` is allowed). NEVER quit the browser — the tool only ever *detaches* (it never closes foreign tabs; `Session.detach()`/`tab_pool.close_all()` only closes the tool's own tabs).
- **≤ 2 real sends TOTAL.** A "send" = a committed new user turn. Fresh THROWAWAY conversation ONLY. NEVER send into conversation `6a316aa8` or any pre-existing/foreign conversation. Human-paced; no bursts.
- **NEVER print, log, echo, or persist any of:** auth/`Authorization`/bearer token VALUES, `oai-*` header VALUES, cookies, `x-openai-target-path`/`x-openai-target-route` VALUES, conversation content/markdown, file ids, attachment bytes, OR the conversation id / URL. **Header NAMES, request PATHS (with the file id redacted), HTTP status classes, booleans, and counts are OK to print.** Model picker LABELS are public UI text and OK to print.
- **Redirect ALL `ask`/`scrape` stdout to `/dev/null`** — these commands mirror their payload to stdout. Never let payload reach your stdout/logs.
- Use `uv run ask-chatgpt` and `uv run python` (PROJECT `.venv`). NEVER the bare installed `ask-chatgpt`. NEVER `uv tool install/upgrade/reinstall`. Do NOT `git commit/push/checkout/stash`, do NOT switch branches, do NOT edit any file (you have no edit/write tool — drive everything via `bash`, using `uv run python - <<'PY' … PY` heredocs which do not create files).
- If at ANY point the tool's OWN tab shows a Cloudflare "Just a moment", a login screen, or an account-picker / any challenge → **STOP IMMEDIATELY, do not send, print `HUMAN-ACTION-NEEDED`** and report.

## Why Pro quota is protected (ground-truth fact you can rely on)
In `src/ask_chatgpt/session.py` the send pipeline calls `assert_reflected_model(...)` (which selects + verifies the model, failing **closed** with `ModelSelectionNotReflectedError`) **before** the composer fill/submit block. Therefore `ask --model "<label>"` either selects that model and sends, or raises and sends **nothing** — it can never silently fall back to and burn Pro. The model gate below additionally avoids even attempting a send when no non-Pro model is reliably selectable.

## Step 0 — clean scratch dirs
```bash
rm -rf /tmp/m13-attach-data /tmp/m13-attach-probe /tmp/m13-enum
```

## Step 1 — preflight (record "up/down" + browser NAME only)
```bash
curl -s --max-time 5 http://127.0.0.1:9222/json/version | head -c 200; echo
```
Expect a JSON with `"Browser": "Chrome/149..."`. If curl fails / times out → STOP, print `CDP_UNREACHABLE`, report. (Do NOT call `/json/list`.)

## Step 2 — MODEL GATE: enumerate the model picker READ-ONLY (ZERO send), pick a non-Pro label
Run this EXACT read-only enumeration. It opens the tool's OWN fresh **composer (render) tab** on a draft (exactly as `ask` does), runs the SAME composer-hydration waits the production send path runs **before** model selection (`wait_for_idle_and_reload_if_needed` then `wait_for_composer`), opens the Radix model picker, lists options, and detaches — no send, no foreign-tab access. (The hydration waits are essential: the model "pill" `button[aria-haspopup="menu"]` only exists after the composer hydrates; opening the picker before that raises `SelectorNotFoundError` — a false "no picker".)
```bash
uv run python - <<'PY'
from ask_chatgpt.session import Session
from ask_chatgpt.send import wait_for_idle_and_reload_if_needed, wait_for_composer
from ask_chatgpt.menus import open_radix_menu, enumerate_radix_options, _close_radix_menu

s = Session(cdp_endpoint="http://127.0.0.1:9222", data_dir="/tmp/m13-enum", channel="cdp")
try:
    ref = s.create()                       # local draft ref -> https://chatgpt.com/ (no network, no send)
    tab = s.tab_pool.acquire(ref)          # render=True: opens the tool's OWN composer tab
    wait_for_idle_and_reload_if_needed(tab, s.selector_map, timeout_s=s.composer_wait_timeout_s)
    wait_for_composer(tab, s.selector_map, timeout_s=s.composer_wait_timeout_s)
    open_radix_menu(tab, s.selector_map["model_picker_trigger_candidates"])
    opts = enumerate_radix_options(tab)
    for o in opts:
        # labels are public UI text -> safe to print; role tells selectability
        print(f"OPT\trole={o.role}\tdisabled={o.disabled}\tlabel={o.label!r}")
    try:
        _close_radix_menu(tab)
    except Exception:
        pass
    print("ENUM_OK", len(opts))
finally:
    s.detach()   # closes only the tool's own tab; never quits the browser
PY
```
- If this raises / prints 0 options / cannot open the picker **even after the hydration waits** → treat as **could not reliably enumerate** → STOP, do NOT send, print `BLOCKED-model-gate`, and report whatever labels (if any) you saw + the exact error type. (Also STOP with `HUMAN-ACTION-NEEDED` if the failure looks like a Cloudflare/login challenge.)
- If you still get `SelectorNotFoundError` on `open_radix_menu` after the waits, retry the whole snippet ONCE more (transient hydration). If it fails twice, report `BLOCKED-model-gate` with the error type so the lead can check whether the `model_picker_trigger_candidates` selector drifted.
- **Selection rule.** A model is *reliably selectable* iff it appears as a top-level `role=menuitemradio`, `disabled=False`, option whose label does **NOT** contain "pro" (case-insensitive). (Top-level radios are the live-validated path; models reachable only via a `role=menuitem` family submenu are the M9-known-unreliable path — do NOT rely on them.)
  - If ≥1 such label exists → choose the one that most clearly denotes a lightweight / base / non-Pro model and call it `<NON_PRO_LABEL>`.
  - If **0** such label exists (only Pro tiers at top level, or non-Pro only behind family submenus) → STOP, do NOT send, print `BLOCKED-model-gate`, and list ALL enumerated labels (names only) so the lead/operator can choose.

## Step 3 — create the fixture (exactly ONE send, FRESH throwaway conversation)
```bash
printf 'M13 attachment download test\nline two\n' > /tmp/m13-attach.txt
uv run ask-chatgpt ask --selector-channel real --cdp-endpoint http://127.0.0.1:9222 --data-dir /tmp/m13-attach-data --model "<NON_PRO_LABEL>" --attach /tmp/m13-attach.txt "Acknowledge the attached file in one short sentence." > /dev/null
echo "ASK_EXIT=$?"
```
Notes: positionals MUST come AFTER all options; keep the prompt SHORT and SINGLE-LINE (long/multiline composer fill exits 30). No conv positional ⇒ a brand-new conversation is created.
- If `ask` raises `ModelSelectionNotReflectedError` / a model-selection failure (no send occurred): **STOP — do NOT retry blindly.** Print `BLOCKED-model-gate` and report. (Do not thrash the account.)
- Confirm a real send committed by inspecting the STORE (NOT stdout): a conversation dir now exists and the transcript has a user turn. Do this without printing the id/content:
```bash
ls -1 /tmp/m13-attach-data/conversations | wc -l            # expect 1
uv run python - <<'PY'
import glob, os, json
dirs = sorted(glob.glob("/tmp/m13-attach-data/conversations/*"))
assert dirs, "no conversation persisted -> send did not commit"
tj = os.path.join(dirs[0], "transcript.jsonl")
roles=[]
with open(tj) as f:
    for line in f:
        line=line.strip()
        if not line: continue
        rec=json.loads(line)
        r=rec.get("role") or rec.get("author_role")
        if r: roles.append(r)
print("HAS_USER_TURN", "user" in roles)   # boolean only; never print content/ids
PY
```
If no user turn committed → the send failed; report FAIL/BLOCKED accordingly. **Total real sends used so far must be ≤ 2** (this should be exactly 1).

## Step 4 — scrape over the light path + observe the descriptor request (leak-safe)
This driver runs the **production light-path scrape** — it calls `Session.scrape(ref, with_attachments=True)`, which is exactly what the CLI `scrape --with-attachments` subcommand wraps (`cli.py` → `session.scrape`, `header_mode="ambient_backend"`, `render=False`). It is READ-ONLY (zero sends). It also reads the channel's in-memory, required-header-projected request record (`channel._cdp_requests`) — NOT `/json/list` — to confirm the descriptor request's header NAMES, printing only names / booleans / redacted paths / counts:
```bash
uv run python - <<'PY'
import glob, os
from ask_chatgpt.session import Session
from ask_chatgpt.identity import ConversationRef
from ask_chatgpt.capture import REQUIRED_CAPTURE_HEADERS

DATA="/tmp/m13-attach-data"
conv_dir = sorted(glob.glob(os.path.join(DATA,"conversations","*")))[0]
conv_id = os.path.basename(conv_dir)                      # used internally only; NEVER printed
conversation_path = f"/backend-api/conversation/{conv_id}"
ref = ConversationRef(conv_id, f"https://chatgpt.com/c/{conv_id}")

s = Session(cdp_endpoint="http://127.0.0.1:9222", data_dir=DATA, channel="cdp")
crashed=False
try:
    transcript = s.scrape(ref, with_attachments=True)     # production light path; read-only
    print("SCRAPE_OK True")
    channel = s._channel()
    descriptor_seen=False; descr_names=[]; descr_target_is_conv=None
    for tab_id, by_id in getattr(channel, "_cdp_requests", {}).items():
        for rid, info in by_id.items():
            url = info.url or ""
            hdrs = info.headers or {}
            if "/backend-api/files/" in url and url.rstrip("/").endswith("/download"):
                descriptor_seen=True
                descr_names=sorted(hdrs.keys())                       # NAMES only
                descr_target_is_conv = (hdrs.get("x-openai-target-path")==conversation_path)  # boolean only
    print("DESCRIPTOR_SEEN", descriptor_seen)
    print("DESCRIPTOR_METHOD_PATH", "GET /backend-api/files/<redacted>/download")
    print("DESCRIPTOR_HEADER_NAMES", descr_names)
    print("DESCRIPTOR_HAS_ALL_8", set(REQUIRED_CAPTURE_HEADERS) <= set(descr_names))
    print("DESCRIPTOR_TARGET_PATH_IS_CONVERSATION", descr_target_is_conv)
    # file landed? (store artifacts -> proves descriptor 2xx + byte 2xx)
    states=[a.download_state for t in transcript.turns for a in t.attachments]
    nonnull_local=any(getattr(a,"local_path",None) for t in transcript.turns for a in t.attachments)
    files=[f for f in glob.glob(os.path.join(conv_dir,"attachments","**","*"), recursive=True) if os.path.isfile(f)]
    print("DOWNLOAD_STATES", states)            # state strings only, not content
    print("ANY_NONNULL_LOCAL_PATH", nonnull_local)
    print("ATTACHMENT_FILE_COUNT", len(files))
except Exception as e:
    crashed=True
    print("SCRAPE_OK False")
    print("SCRAPE_ERROR_TYPE", type(e).__name__)   # type name only; never the message (may contain ids)
finally:
    s.detach()
print("RENDERER_CRASH", crashed)
PY
```
Then ALSO confirm the CLI verb itself exits 0 (it will likely dedupe the already-downloaded attachment; that is fine — we already observed the descriptor on the scrape above). Keep stdout redirected:
```bash
CONV="$(ls -1 /tmp/m13-attach-data/conversations | head -n1)"
uv run ask-chatgpt scrape --selector-channel real --cdp-endpoint http://127.0.0.1:9222 --data-dir /tmp/m13-attach-data --with-attachments --out /tmp/m13-attach-data/scrape.md "$CONV" > /dev/null
echo "SCRAPE_CLI_EXIT=$?"
```
(The `$CONV` shell var is never echoed; only the exit code is printed.)

## Step 5 — verdict
- **PASS** iff ALL of: the scrape completed (`SCRAPE_OK True`, `RENDERER_CRASH False`, `SCRAPE_CLI_EXIT=0`); `DESCRIPTOR_SEEN True` with `DESCRIPTOR_HAS_ALL_8 True` and `DESCRIPTOR_TARGET_PATH_IS_CONVERSATION True`; the file landed (`ATTACHMENT_FILE_COUNT ≥ 1`, `DOWNLOAD_STATES` contains `"downloaded"`, `ANY_NONNULL_LOCAL_PATH True`).
  - Note: file landing independently proves the descriptor GET returned 2xx and the byte fetch returned 2xx (a 4xx descriptor or non-2xx byte fetch would leave `download_state` = `error`/`not_downloadable` and no file). The byte fetch carries no explicit auth headers by design (`capture.py` passes none on the byte `fetch`), so it rides same-origin cookies.
  - If `DESCRIPTOR_SEEN True` but `DESCRIPTOR_HEADER_NAMES` is empty (the browser's ExtraInfo headers were not captured for that request) yet the file landed → report it as **PASS with header-names not directly observed**; the offline mock test (TASK 1) is the direct header-name proof and the live file-landing proves acceptance.
- **FAIL** modes → record the recommendation:
  - file did NOT land AND `DESCRIPTOR_SEEN True` with all 8 names present ⇒ the conversation-path `x-openai-target-path` is NOT tolerated on the light path ⇒ recommend the **Lens-A descriptor retarget** (`_fetch_attachment_descriptor`: retarget headers to the descriptor URL) — a code change for a follow-up round.
  - file did NOT land and bytes never fetched / byte non-2xx with no harvested header names ⇒ `download_url` is not self-authenticating ⇒ recommend passing auth headers / reworking byte handling.

## Report (print to stdout — this IS your deliverable)
Print, clearly labeled (NAMES / PATHS / STATUS-CLASSES / BOOLEANS / COUNTS ONLY — never values/ids/content):
- `STATUS: DONE | PARTIAL | BLOCKED`
- `REAL-LEG: PASS | FAIL | BLOCKED-model-gate | HUMAN-ACTION-NEEDED | CDP_UNREACHABLE`
- Preflight result (up/down + browser name).
- The model picker option labels you enumerated (names + role + disabled), and which `<NON_PRO_LABEL>` you chose (or why you blocked).
- Real sends used (count of committed user turns — must be ≤ 2; expect 1).
- The descriptor observations: `DESCRIPTOR_SEEN`, `DESCRIPTOR_HEADER_NAMES` (the sorted list), `DESCRIPTOR_HAS_ALL_8`, `DESCRIPTOR_TARGET_PATH_IS_CONVERSATION`, `DOWNLOAD_STATES`, `ATTACHMENT_FILE_COUNT`, `SCRAPE_CLI_EXIT`, `RENDERER_CRASH`.
- Any FAIL recommendation, or any blocker with the exact action needed.
- Confirm you never called `/json/list` and never printed any secret value / id / content.
