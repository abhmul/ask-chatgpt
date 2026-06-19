# M5-T3 — ATTENDED real-CDP READ-ONLY verification of scrape (pi worker)

You are an **attended real-leg pi worker** for `ask-chatgpt` mission M5. You run the **production `scrape`** over the operator's **already-running, signed-in Chromium** via CDP and verify end-to-end real capture — **strictly READ-ONLY**. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit nothing but this contract.

## ⚠️⚠️ CRITICAL SAFETY — SHARED BROWSER, READ TWICE, OBEY EXACTLY ⚠️⚠️
The Chromium at **`http://127.0.0.1:9222`** is the **operator's** and **ANOTHER AGENT IS ACTIVELY USING IT RIGHT NOW** (a keep-pushing loop on conversation `/c/6a316aa8`). A prior probe LEAKED another agent's conversation by walking all tabs. You must NOT repeat it. The following are ABSOLUTE:

1. **USE ONLY THE PRODUCTION DRIVER.** Run capture **only** through `scripts/m5_capture_measure.py` (which uses the project's `CdpChannel` — own-tab-only by construction: it creates its own page via `context.new_page()` and never enumerates `context.pages`). For the OPTIONAL header-name check (step 4) you may use the **production `CdpChannel` class** as shown — but you must **NEVER** write raw Playwright that iterates `context.pages`, reads/clicks/screenshots/navigates any tab you did not open, or attaches to existing targets. If you cannot do a step with the production code, SKIP it and report — do not improvise tab-walking.
2. **READ-ONLY. ZERO SENDS.** Run ONLY scrape/capture. **NO** `ask`/`send`/`loop`/`create`, no typing, no Enter, no model/tool selection, no clicking. (The CdpChannel action methods raise by design — do not work around them.)
3. **ONLY THESE TWO CONVERSATIONS.** Smoke `6a3483b3-9850-83ea-a9f7-3e269932e387` (full read) and target `6a316aa8-5dc8-83ea-9014-b8ea38dabc31` (READ-ONLY, scale/fidelity only — do NOT pass `--with-attachments`; the full target attachment scrape is M6). **NO other conversation, ever.**
4. **PREFLIGHT before every real run:** `curl -s --max-time 5 http://127.0.0.1:9222/json/version`. If it fails/times out → **STOP**, report `CDP_UNREACHABLE`, do nothing else.
5. **NEVER quit/close the browser.** The driver detaches via `browser.close()` which for a `connect_over_cdp` connection only DISCONNECTS the client (does not kill Chromium). **After every run, re-run the preflight curl to CONFIRM the browser is still alive.** If the browser is gone after a run → STOP, report it as a CRITICAL regression immediately.
6. **Login wall / Cloudflare "Just a moment…" / any challenge → STOP.** Do not solve it, do not automate login, do not enter credentials. Report `HUMAN-ACTION-NEEDED` and stop.
7. **NEVER persist or log `authorization`/`oai-*`/`cookie` header VALUES.** The driver does not print them; do not add code that does. If you write any diagnostic, emit header **NAMES/booleans only**, never values.
8. **NO conversation content in any committed file.** Send `--data-dir` and `--out` to **OUT-OF-REPO** paths under `$(mktemp -d)` (e.g. `/tmp/...`). Do NOT `cat`/paste captured markdown or raw-mapping into your report. Report only booleans, counts, byte sizes, measured memory numbers, vocab summaries, and top-level key NAMES. Do NOT `git add`/commit the data-dir or out files (they are out-of-repo anyway).
9. **Isolation:** branch `rewrite-v2` only; **NEVER** move/commit/merge/checkout `stable` (must stay `779eb40`); **NEVER** `uv tool install/upgrade/reinstall`; use `uv run` only; **NEVER** `git push`; **NEVER** `git commit`/`git add` (the manager commits). Never touch `issues/cdp-send-repro/controller.mjs` or `team/state/live-state.json`. No stealth/anti-detection.

## Steps

### Step 0 — Preflight
Run `curl -s --max-time 5 http://127.0.0.1:9222/json/version`. Record the `Browser` string. If it fails → STOP `CDP_UNREACHABLE`.

### Step 1 — SMOKE scrape (the core acceptance)
```
D=$(mktemp -d); echo "data-dir=$D"
uv run python scripts/m5_capture_measure.py \
  --conversation 6a3483b3-9850-83ea-a9f7-3e269932e387 \
  --data-dir "$D/data" --out "$D/smoke.md"
```
Capture the printed JSON summary (turn_count, lengths, raw_mapping_byte_size, mapping_node_count, raw_top_level_keys, fidelity booleans, completion_vocab, memory{after_attach_open_header_acquire, fetch_only, end_to_end}). This is the **end-to-end real capture** verdict: if the driver exits 0 and the summary shows a non-empty transcript with `raw_top_level_keys` matching M2 (`conversation_id`, `mapping`, `current_node`, `default_model_slug`, `async_status`, …) and canonical markdown, real backend-api capture is **CONFIRMED**.
Then **re-run the Step 0 preflight curl** and confirm the browser is still alive.

If the driver raises `BACKEND_AUTH_UNAVAILABLE`/`CDP_UNREACHABLE`/`HUMAN-ACTION-NEEDED`/any error, capture the redacted error code + message and report it (do NOT retry blindly; a login/Cloudflare stop means STOP).

### Step 2 — TARGET read-only scale + fidelity (do NOT use --with-attachments)
Same driver on `6a316aa8-5dc8-83ea-9014-b8ea38dabc31` into a fresh `$(mktemp -d)`. This yields the ~17MB-scale RSS/tracemalloc + a heavy-math/DR fidelity sample. Record the same summary fields. **Re-run preflight curl afterward; confirm browser alive.**

### Step 3 — Memory decision (empirical, per agent-rigor)
From the two summaries, state the measured numbers and apply the decision rule (from `team/evidence/reports/M5-design-lens-B.md`): fetch-only ≤128 MiB RSS / 32 MiB tracemalloc-peak over post-attach baseline, AND end-to-end (fetch+parse+store) ≤512 MiB RSS / 256 MiB tracemalloc-peak on the ~17 MB target → **keep the current whole-file `json.load` parse**; if exceeded → flag that an event/streaming parser is needed before M6. Also compute and report the measured constant **bytes-per-mapping-node** = raw_mapping_byte_size / mapping_node_count for the target (so M6 can size scale). Record ESTIMATE vs ACTUAL wall-clock for the target scrape.

### Step 4 — (OPTIONAL, safe, names-only) confirm `all_headers()` exposes the 8 required headers
Resolves a key design uncertainty. Use the **production CdpChannel** (own-tab-only) — NOT raw Playwright tab-walking. Write a throwaway script under the out-of-repo `$(mktemp -d)` (or run inline `uv run python - <<'PY'`) that:
- builds `from ask_chatgpt.channels.cdp import CdpChannel; from ask_chatgpt.capture import REQUIRED_CAPTURE_HEADERS`; `c=CdpChannel(); c.attach(); tab=c.open_tab("https://chatgpt.com/c/6a3483b3-9850-83ea-a9f7-3e269932e387")`;
- defines `pred = lambda r: r.method.upper()=="GET" and r.url.rstrip("/").endswith("/backend-api/conversation/6a3483b3-9850-83ea-a9f7-3e269932e387")`; `snap=c.wait_for_request(tab, pred, timeout_s=30)`;
- prints, for **each name** in `REQUIRED_CAPTURE_HEADERS`, a boolean `name in snap.headers` — **NAMES/booleans only, NEVER values**; then `c.detach()`.
- Re-run the preflight curl afterward; confirm browser alive.
Report which of the 8 names were present (so we know whether `all_headers()` alone suffices or the CDP `requestWillBeSentExtraInfo` fallback is load-bearing). If this step errors or feels risky, SKIP it and rely on Step 1's end-to-end success as proof headers were obtained.

### Step 5 — Completion vocabulary
The driver already includes `completion_vocab` (from `catalogue_completion_status_vocab` over the captured raw-mapping) in each summary. Report the observed `async_status`, node/message `status`, `is_complete`, `is_finalizing`, and `pro_progress` enum/type/count summaries (redacted — they already are). Note whether you observed in-progress vs complete states (the target may be actively updating). **Do not** probe `/stream_status` (left disabled this phase).

## OUTPUT → `team/evidence/reports/M5-T3-real-leg.md`
Structured, redacted:
1. **Status** `DONE`/`PARTIAL`/`BLOCKED`.
2. **Preflight**: Browser string; browser-alive-after-each-run = yes/no.
3. **Real capture verdict**: smoke end-to-end CONFIRMED/REFUTED with evidence (exit code, turn_count, raw_top_level_keys names, mapping_node_count). Confirm `transcript.jsonl` + `raw-mapping.json` + markdown `--out` were written (paths under the out-of-repo tmp dir; report existence + byte sizes, NOT content).
4. **Fidelity booleans** for smoke and target (`\widehat`, `\ne`/`\neq`, `\frac` present; no `≠` literal replacement).
5. **Memory**: smoke + target RSS/tracemalloc (after-attach / fetch-only / end-to-end); the decision-rule verdict (keep whole-parse vs need event parser); bytes-per-node constant; ESTIMATE/ACTUAL wall-clock.
6. **Completion vocab** catalogue (redacted).
7. **Header mechanism** (Step 4 result, names/booleans only) or "skipped, end-to-end success implies headers obtained".
8. **SAFETY AUDIT** (explicit): own-tab-only held (you used only the production scrape/CdpChannel; never touched context.pages or foreign tabs); ZERO sends/new turns; browser left running (preflight passed after every run); no header values or conversation content in this report or any committed file; data-dir/out were out-of-repo tmp and not staged.
9. **Blockers** + **recommended next** (M6 target full scrape).

Begin with Step 0 preflight. If anything looks like a login/challenge or the browser disappears, STOP and report. Do NOT commit. Do NOT push.
