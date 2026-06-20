# M6-T2 — Scrape target into the repo cache + confirm math fidelity (ATTENDED REAL-LEG, READ-ONLY) — DELIVER THE TRANSCRIPT

You are a **pi worker** for the `ask-chatgpt-dev` team, mission M6 task T2. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit **nothing** but this contract and the files it names. Read `.claude/skills/manager/references/agent-rigor.md` and obey it. This is the **operator's pressing deliverable**: the transcript of conversation `6a316aa8-5dc8-83ea-9014-b8ea38dabc31`.

This is an **ATTENDED, READ-ONLY, REAL-CHATGPT.COM** leg over a **SHARED** browser. The capture/scrape path is **PROVEN** — M5 scraped this exact target read-only (481 turns / 2.03M chars / 6,124 nodes / 20.19 MB; `\widehat`/`\ne`/`\frac` intact). Your job is to run it into the new repo `cache/` and confirm fidelity.

## ░░ SAFETY — real-site, SHARED browser (OBEY EXACTLY; transcribed verbatim) ░░
The browser at `127.0.0.1:9222` is **SHARED with another ACTIVE agent**.
- **own-tab-only**: never read/iterate foreign/operator tabs (there is a prior leak incident). Only the tab(s) the tool itself opens. Never call `context.pages`.
- **READ-ONLY**: scrape is a read. **ZERO sends / new turns / model selection / tool selection / typing / clicks / Enter / uploads.**
- **never quit the browser** (detach only — the proven harness already detaches).
- **preflight** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` BEFORE attaching. If it fails/times out → **STOP**, report `CDP_UNREACHABLE`, do not proceed.
- **login / Cloudflare / "Just a moment…"** → **STOP**, report `HUMAN-ACTION-NEEDED`, do not retry, do not solve, do not log in. (The harness raises `HumanActionNeededError`; treat that as a stop.)
- **no stealth / anti-detection**, ever. Domain allowlist stays enforced (the channel enforces it).
- **NEVER persist or log** `authorization` / `oai-*` / `cookie` header values — names/booleans only. The proven harness already redacts; do not add any logging that could print headers or conversation content.
- read **ONLY** the authorized target `6a316aa8-5dc8-83ea-9014-b8ea38dabc31`. No other conversation.
- **Cache content stays LOCAL** (the repo `cache/` is gitignored). **Never** `git add`/`commit`/`push`. Do not run any git command.
- Branch `rewrite-v2` only; **never** move/commit/checkout `stable`; **never** run `uv tool install/upgrade/reinstall` (use `uv run`/`uv sync` only).
- Do NOT print conversation content or any header value in your report — counts, byte sizes, and booleans only.

## Preconditions you can rely on
- `cache/` is the **default data-dir** now (task T1 landed it) and is gitignored. You will pass `--data-dir cache` explicitly anyway for determinism.
- The proven harness `scripts/m5_capture_measure.py` constructs `Session(channel="cdp", data_dir=...)`, calls `session.scrape(<conversation>)` (writes `transcript.jsonl` + `raw-mapping.json` into the data-dir), writes assistant markdown to `--out`, `session.detach()` in finally, and prints a JSON summary (turn_count, lengths, byte sizes, fidelity booleans, completion vocab, memory) — **never** printing content. Read its top and `build_parser()` / `main()` to confirm before running.

## Steps
1. **Preflight**: `curl -s --max-time 5 http://127.0.0.1:9222/json/version` → confirm a `Browser`/`webSocketDebuggerUrl`. If not, STOP `CDP_UNREACHABLE`.
2. **Scrape into the cache** (PROVEN path):
   ```
   uv run python scripts/m5_capture_measure.py \
     --conversation https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31 \
     --data-dir cache \
     --out cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/target-assistant-export.md
   ```
   Expect exit 0 and a JSON summary. Expect roughly: turn_count ~481, assistant markdown ~2.0M chars, raw-mapping ~20MB, ~6,124 nodes, end-to-end RSS ~350MB (whole-file `json.load` is the M5-approved decision). It takes ~150s — be patient. (A harmless `VIRTUAL_ENV ... will be ignored` warning is expected; `uv run` uses the project `.venv`.)
3. **Confirm cache artifacts exist** (use `ls -l`, NOT git): 
   - `cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/transcript.jsonl` (expect ~5.2MB)
   - `cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/raw-mapping.json` (expect ~20MB)
   - `cache/index.json`
   Report their byte sizes.
4. **Math fidelity (STRENGTHENED, falsifiable).** The harness prints `fidelity` booleans, but its `no_flattened_frac_observed` is a weak self-referential check. Compute a **stronger, falsifiable** check over the captured markdown export file you wrote in step 2 (read it with Python; do NOT print it). Report these counts/booleans:
   - `contains \widehat` (and count of `\widehat{` i.e. brace-followed — a flattened/stripped form would lack the brace),
   - `contains \ne` or `\neq`,
   - `count(\frac)` and `count(\frac{)` — these MUST be **equal** (every `\frac` is a well-formed `\frac{...}{...}`; a flattened fraction `a/b` would drop `\frac` entirely, and a malformed one would make these counts diverge),
   - `no literal "≠"` present (a literal `≠` where `\ne` belonged is the gotcha-#1 corruption signature),
   - whether any bare `\frac` NOT followed by `{` exists (must be **none**).
   This check **can fail** — if the backend had flattened/corrupted math, `\frac{` count would drop or literal `≠` would appear. State the verdict: **FIDELITY CONFIRMED** only if widehat present, ne/neq present, `count(\frac)==count(\frac{)` and both > 0, no literal `≠`, no bare `\frac`. Otherwise report the exact failing signal.
5. **Prove cache acts as a cache (read-without-browser).** Run, and confirm exit 0 + non-empty output **without any browser/CDP** (this reads the cache you just populated):
   ```
   uv run python -m ask_chatgpt.cli history https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31 --data-dir cache --out cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/transcript.md
   ```
   (`history` is store-only and must NOT preflight/attach.) Confirm `cache/conversations/<id>/transcript.md` was written from the cache with no browser activity, and report its byte size. Do NOT print its content.
6. **Browser-alive check**: re-run the preflight curl; confirm the browser is still up after your run (you must not have quit it).

## Acceptance (re-derive from artifacts; do NOT trust the harness's own telemetry alone)
- `transcript.jsonl` + `raw-mapping.json` present in `cache/conversations/6a316aa8-…/` at the expected scale.
- Rendered markdown export(s) present in the cache.
- **FIDELITY CONFIRMED** by the strengthened step-4 check (or an honest failure report).
- `history --data-dir cache` rendered the transcript with **no browser** (cache semantics proven live).
- Browser still alive; ZERO sends; own-tab-only; no headers/content printed or persisted; nothing committed.

## Report (write your handoff here)
Write `team/evidence/reports/M6-T2-transcript.md`, in order:
1. **STATUS:** `DONE` / `PARTIAL` / `BLOCKED` (single token).
2. **Preflight** result (browser string only) — before and after.
3. **Cache delivery:** absolute cache paths + byte sizes of `transcript.jsonl`, `raw-mapping.json`, `index.json`, the markdown export(s); turn_count / mapping_node_count / assistant-markdown length from the JSON summary.
4. **Fidelity verdict:** the strengthened step-4 counts/booleans and the single-token verdict (`FIDELITY CONFIRMED` or the failing signal).
5. **Cache-as-cache proof:** the `history` exit code + that it used no browser + the transcript.md size.
6. **Safety audit:** own-tab-only held; ZERO sends; browser left alive; no auth/oai/cookie values or conversation content in this report or any committed file; data-dir was the gitignored repo `cache/`; no git/`uv tool`/`stable` actions.
7. **Blockers / anomalies** (e.g. completion-vocab surprises, memory near threshold).
Counts/sizes/booleans ONLY — never conversation content or header values.
