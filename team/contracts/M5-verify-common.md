# M5 Verification Panel — common context (READ-ONLY best-of-N; each worker does ONE lens)

You are ONE lens of a 3-worker **independent verification panel** for mission M5 of the `ask-chatgpt` v2 rewrite. You **confirm or refute** the M5 work by inspecting committed artifacts + the real-leg report. You are **READ-ONLY**: do NOT modify any source/test file, do NOT touch any browser/CDP/network/`:9222`, do NOT git add/commit/push. You MAY run read-only commands (`git show`, `git diff`, `grep`, and — only the V2 lens — `uv run pytest` which does not mutate source). Report PASS/FAIL per item with concrete evidence (file:line, commit, single-token verdicts). Never trust the producer's or manager's claims — re-derive from the files.

## What M5 did (context — verify, don't trust)
M5 implemented the live `CdpChannel` (Playwright-over-CDP) **read path** so `scrape` works against real chatgpt.com READ-ONLY, then verified it over the operator's shared Chromium. The capture/scrape pipeline already existed (mock-proven). M5 added `src/ask_chatgpt/channels/cdp.py`, wired `Session(channel="cdp")`, added `catalogue_completion_status_vocab` (in `capture.py`) and `scripts/m5_capture_measure.py`, and ran an attended read-only real leg. **Send path is DEFERRED (M5 step 5 skipped); zero real sends this phase.**

## Artifacts to audit (all on disk; committed on `rewrite-v2`)
- Code: `src/ask_chatgpt/channels/cdp.py` (new), `src/ask_chatgpt/session.py` (cdp wiring), `src/ask_chatgpt/capture.py` (vocab fn), `tests/test_cdp_channel.py` (new), `scripts/m5_capture_measure.py` (new).
- Evidence: `team/evidence/reports/M5-T3-real-leg.md` (the attended real-leg report), `team/evidence/reports/M5-design-lens-{A,B,C}.md`, `team/evidence/reports/M5-E1-cdp-channel.md`.
- Contracts/state: `team/contracts/M5-*.md`, `team/state/M5-manager-state.json`.
- M5 commits to inspect: run `git log --oneline -6` and `git show --stat <sha>` for the M5 commits (subjects starting `M5:`).

## Authoritative facts the manager already established (you may re-derive; cite if you do)
- `uv run pytest` → **205 passed** (188 prior + 17 new), re-derived by the manager.
- No-playwright-import invariant holds: after `import ask_chatgpt` + constructing `CdpChannel`/`Session(channel="cdp")`, no `playwright*` in `sys.modules`.
- Manager mutation spot-check: mutating `fill` to not raise AND `_RedactedHeaders.__repr__` to leak each turned a test RED (`test_cdp_action_methods_are_read_only_deferred`, `test_wait_for_request_...`); restored → 205 passed. (Tests are falsifiable.)
- Real leg: smoke `6a3483b3` captured end-to-end (7 turns/87 nodes); target `6a316aa8` read-only at 20.19 MB/6124 nodes; browser alive after every run (manager re-curled `/json/version` → Chrome/149); `request.all_headers()` exposed all 8 required header names; capture data went to out-of-repo `/tmp` (not committed).
- `stable` must be `779eb40` (unmoved).

## REQUIRED_CAPTURE_HEADERS (the 8 secret header names — values must NEVER appear anywhere)
`authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, `x-openai-target-route`.

## The three lenses (each worker executes EXACTLY ONE — named in your launch prompt)

### LENS V1 — Safety & leak audit (READ-ONLY)
Audit every committed M5 artifact (code + tests + scripts + team/ reports/contracts/state + the M5 commit diffs via `git show`). Verify PASS/FAIL with evidence:
- **No header-value leak:** no `authorization`/`oai-*`/`cookie` VALUE anywhere (only NAMES are acceptable). Grep for bearer/JWT/`sess-`/device-id-like patterns and for the literal header names followed by a value. (Header NAMES and name-presence booleans are OK; VALUES are not.)
- **No conversation content leak:** the smoke/target conversation text must not appear in any committed file (the real-leg report should contain only counts/sizes/booleans/key-names). Confirm capture output (`raw-mapping.json`, `transcript.jsonl`, `*.md` exports) is NOT in the repo (it went to `/tmp`).
- **Redaction correctness (cite file:line):** `HeaderBundle` is `repr=False`; `_RedactedHeaders.__repr__`/`__str__` masks values; `_safe_response_headers` drops `authorization`/`cookie`/`set-cookie`/`oai-*`; `fetch_in_page` sanitizes `page.evaluate` exceptions; `catalogue_completion_status_vocab` summarizes/hashes `pro_progress` (no raw content) and its enum-token guard rejects secret-ish tokens.
- **Zero-send capability:** all UI action methods (`fill`/`insert_text`/`click`/`hover`/`press`/`upload_files`) raise; `read_clipboard` raises; `scrape`'s read path never calls them; the real leg ran only `scrape`/header-name-check (no `ask`/`send`/`loop`/`create`).
- **Own-tab-only:** `cdp.py` never references `context.pages`; `open_tab` uses `context.new_page()`; `detach` uses `browser.close()` (disconnect for connect_over_cdp) + `playwright.stop()` and never enumerates/kills foreign tabs/the browser.
- **Isolation:** `git rev-parse stable` == `779eb40` (UNMOVED); no `uv tool` invocation in any M5 artifact; nothing pushed (no push evidence); `issues/cdp-send-repro/controller.mjs` and `human/` are NOT staged in any M5 commit (`git show --stat`); no `team/state/live-state.json` edit in M5 commits.

### LENS V2 — Offline falsifiability & correctness (READ-ONLY; may run `uv run pytest`)
Re-derive `uv run pytest` (report the exact pass count). Then judge **falsifiability + behavior-focus** of `tests/test_cdp_channel.py` (read the source): for each M5 acceptance behavior — lazy-import boundary; preflight mapping (ok/http-error/timeout/refused/invalid-json/missing-ws); allowlist-before-Playwright-import; own-tabs-only (fake context whose `.pages` raises); Protocol signatures + `FetchResult` stream/non-stream shapes; `wait_for_request` cheap-predicate + REQUIRED-name projection + CDP ExtraInfo fallback by requestId + redacted repr; **pure stream decode incl. multibyte-UTF-8-split-across-chunks**; redaction canary; `catalogue_completion_status_vocab`; action-methods-raise — map it to its test and state whether the test (a) exercises real behavior via the public surface and (b) could actually fail (cite the asserting line). **Identify any acceptance behavior with NO falsifiable test (a coverage gap).** Confirm the existing 188 still pass and the no-playwright pins exist (`tests/test_channels_base.py`, `tests/test_mock_channel.py`). You may run `uv run pytest -k <subset>` read-only; do **NOT** mutate any source file (the manager already did mutation testing).

### LENS V3 — Acceptance conformance & honesty audit (READ-ONLY)
Map the M5 **Acceptance bar** (read `team/contracts/M5-capture-scrape.md` lines ~38-39 and the Scope items 1-6) to concrete evidence in `team/evidence/reports/M5-T3-real-leg.md` + the code. For each, mark CONFIRMED/PARTIAL/REFUTED **from inspected artifacts, not claims**:
1. Real end-to-end backend-api capture of smoke `6a3483b3` returns canonical markdown (headers from the page's own request, never logged).
2. `scrape` writes `transcript.jsonl` + `raw-mapping.json` + rendered markdown to stdout/`--out`.
3. Fidelity: `\widehat`, `\ne`/`\neq`, `\frac{}{}` present/correct, no flattened/`≠`-replaced math.
4. ~17 MB (now 20.19 MB) target scale measured (RSS/tracemalloc) read-only; the whole-parse-vs-event-parser decision is sound (note the 253.8 vs 256 MiB headroom and the growing target — is "keep whole-parse for M5/M6" defensible, and did they flag the risk?).
5. Completion-status vocabulary catalogued from live data.
6. ZERO sends; own-tab-only held; no header/conversation leakage in committed artifacts; offline pytest green; committed to `rewrite-v2`; `stable` unmoved; no `uv tool`; nothing pushed.
**Honesty check:** does any report claim more than the artifacts prove? Is anything labelled CONFIRMED that is actually only producer-asserted? Explicitly note what is still OPEN for M6 (target full `--with-attachments` scrape) and the DEFERRED send-smoke (M5 step 5), so the handoff cannot overclaim full M5.

## Output (write to the path named in your launch prompt; concise + structured)
- **Lens verdict:** `CONFIRM` / `CONFIRM-WITH-FINDINGS` / `REFUTE`.
- **Per-item PASS/FAIL table** with evidence (file:line / commit / verdict token).
- **Findings** (any defect, gap, overclaim, or risk) — ranked; each with a concrete fix or follow-up.
- **What you could NOT verify** and why.
Do NOT modify any file except writing your own report. Do NOT touch the browser/CDP/network. Begin now.
