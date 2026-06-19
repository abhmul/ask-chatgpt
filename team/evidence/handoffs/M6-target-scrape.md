# M6 — Deliver the target scrape (with attachments) into the repo cache — HANDOFF

STATUS: **DONE** — transcript delivered, math fidelity CONFIRMED, attachments downloaded, cache semantics proven, independently verified by a 3-lens panel (all PASS). Read-only, leak-clean, `stable` unmoved, nothing pushed.

## DELIVERABLE TO THE OPERATOR
The target conversation `6a316aa8-5dc8-83ea-9014-b8ea38dabc31` is fully captured in the **repo-local, gitignored cache** (the cache acts as your local store; its content is NEVER committed):

`cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/`
- `transcript.jsonl` — append-only current-branch transcript (501 turns on last-writer-wins read). ~37.9 MB on disk (append-only: holds superseded all-`pending` records from the first scrape + T4's download-updated re-emit; reads dedupe by `message_id`).
- `raw-mapping.json` — full backend mapping, ~21.6 MB, sensitive keys (`authorization`/`cookie`/`oai-*`) stripped.
- `transcript.md` — rendered full (User+Assistant) markdown export, ~2.13 MB.
- `target-assistant-export.md` — assistant-only markdown, ~2.11 MB.
- `attachments/` — **10 distinct downloaded files, 55,168,133 bytes** (PDFs + 1 zip).
- top-level `cache/index.json` (338 B).

To read it WITHOUT a browser (cache-as-cache): `uv run python -m ask_chatgpt.cli history <id-or-url> --data-dir cache` (or `export`). `cache/` is the **default** data-dir now, so `--data-dir cache` is optional from the repo root.

## What was verified (evidence; re-derived from ground truth, not producer claims)
- **Cache is the default data-dir** (`f469f44`): `Store().resolve_data_dir()` → `<repo>/cache` (walk up to `pyproject.toml`; CWD/`cache` fallback). `--data-dir` and `ASK_CHATGPT_DATA_DIR` still override. Confirmed by L3 (`Store(env={}).resolve_data_dir()` → repo cache).
- **Transcript delivered + math fidelity CONFIRMED** (`9648c68`): scraped read-only via the proven `scripts/m5_capture_measure.py`. Fidelity re-derived content-free over the cached markdown (by me and independently by L3): `\widehat`=129, `\ne`/`\neq`=537, `\frac`=6575, **`\frac` immediately/whitespace-followed-by-`/` (flattened-fraction signature) = 0**, **literal `≠` (U+2260) = 0** → no corruption. (Brace-less `\frac12`/`\widehat p` are valid LaTeX; an earlier "FAIL" was a false alarm from an over-strict `count(\frac)==count(\frac{)` criterion I had specified — corrected.)
- **Cache acts as a cache** (no browser/re-scrape): L3 ran `history`/`export` with an injected no-browser channel (`browser_call_count=0`, 501 turns) and with an exploding-CDP-constructor (`exit 0`, `cdp_construct_count=0`). `Session.history` → `Store.load_transcript` only.
- **Attachment byte-route discovered + implemented** (`adfee14`, `a03a814`): general resolver `AttachmentRef → file id → GET /backend-api/files/<id>/download` (web-app auth headers) → follow `download_url` (host `chatgpt.com`, cookie-bound) → stream bytes. **Requires a non-empty `download_url`** (HTTP 200 alone is NOT success — `run_id`s return 200 error-JSON). Dedups by resolved file id; size-verified; idempotent; fail-closed (`unsupported`/`not_downloadable`/`error`).
- **Attachments shipped** (last-writer-wins over `transcript.jsonl`, confirmed by me and L3): per `source_kind` — `user_upload` downloaded 10, `file_reference` downloaded 209, `generated_asset` downloaded 140, `code_execution_output` **unsupported** 125. These resolve to **10 distinct physical files** (file_reference + generated_asset tokens overlap the user_upload files), **0 missing bytes**, all under the gitignored `attachments/` dir. (My contract's ~66 estimate was an overcount: distinct *source refs* ≠ distinct *backend tokens*; honestly flagged by T4.)
- **Offline suite green**: `uv run pytest` = **212 passed** (205 baseline + 7 new), re-run by me and by L2. Falsifiable tests added (cache default, history/export-no-browser via raising fakes, attachment download, 200-error-gotcha, unsupported, dedup, default no-op).

## Independent verification (3-lens panel — all PASS, ground-truth-derived)
- **L1 safety/leak/no-send/own-tab** (`M6-T6-L1.md`): PASS. 0 leak matches vs cache-derived operator file-id/filename/content tokens across all 4 M6 commits + tracked tree; `authorization`/`download_url`/`cookie`/`oai-` substrings in cached transcript/raw-mapping = 0; CDP `fill`/`click`/`press`/`upload_files`/`read_clipboard` all raise `HumanActionNeededError` (7 raises); no production `context.pages` enumeration; cache gitignored, 0 tracked cache entries; `controller.mjs`/`human/` not staged.
- **L2 offline correctness + falsifiability** (`M6-T6-L2.md`): PASS. 212 passed; 0 Playwright imports; line-cited falsifiability arguments + named failure modes for the load-bearing tests.
- **L3 acceptance/cache-as-cache/fidelity/shipment** (`M6-T6-L3.md`): PASS. All re-derived numbers above.

## Safety held
own-tab-only; **ZERO sends/new-turns/model-or-tool selection** (all real legs read-only: scrape + attachment GET downloads); browser left alive (CDP preflight OK before+after every real leg); no `authorization`/`oai-*`/`cookie` values or signed `download_url`s persisted/logged/committed; no conversation content, operator file-ids, or filenames in git; read ONLY the authorized target; `stable` `779eb40` unmoved; no `uv tool`; no `git push`; cache content never committed.

## Commits (CODE/config + evidence only; cache content never committed)
`f469f44` (cache default + tests), `9648c68` (T2 report), `adfee14` (routes + helper scripts + T4 contract), `a03a814` (attachment download impl + report), `6e93bf2` (verify panel). All on `rewrite-v2`, none pushed.

## Blockers / anomalies (none blocking)
- **None blocking.** Mission acceptance met.
- Procedural lesson (encoded for future real-legs): `ask`/`scrape`/`history`/`export --out` mirror payload to **stdout AND** the file by design (gotcha-#4 fix). Agent runs must redirect stdout (`>/dev/null`) so content does not land in bash/tool logs (T2 hit this; the transient `/tmp` log was removed; nothing reached git).
- Sediment caveat (fail-closed): only `sediment://` pointers with an embedded `file_…`/`file-…` token were live-confirmed; bare sediment fragments are `unsupported` until separately confirmed. `code_execution_output` (`run_id`) has no byte route → `unsupported`.
- Download-url host was `chatgpt.com` (cookie-bound same-origin), not a cookie-free `oaiusercontent.com` pre-signed URL on this target; allowlist retains both.

## Complexity / scale signals
- `transcript.jsonl` grows append-only across re-scrapes (3503 lines → 501 messages on last-writer-wins). Functionally correct (idempotent, reads dedupe), but an optional **compaction** of superseded records is a reasonable future nicety if files get large.
- Target memory end-to-end tracemalloc peak ~264.5 MiB (slightly over the 256 soft note) but RSS ~366 MiB << 512 MiB ceiling; whole-file `json.load` still fine. Watch for an event-parser only if the conversation grows much further (it grew 481→501 turns since M5; it is active).

## Recommended next (M7)
- `menus.py` executable Radix model/tool selection (fail-closed; `Recent files`/`Projects` never enumerated).
- `TabPool` + `AdaptiveSendBudget` (real pacing/backoff; no hard message cap).
- `loop` over one persistent `Session` (attach once, verify each turn).
- Real verified-SEND smoke (low-risk operator-approved prompt) before the keep-pushing loop — note the **stable send no-op bug** is for the separately-installed pinned tool, not rewrite-v2; M5 deferred a real send-smoke.
- Optional: project create/send if prioritized; transcript compaction; confirm a cookie-free `oaiusercontent.com` attachment variant if one appears.
