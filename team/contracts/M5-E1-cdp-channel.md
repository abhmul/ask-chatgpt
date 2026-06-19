# M5-E1 — Implement live CdpChannel READ path + wire `scrape` over CDP (SINGLE pi EDITOR, TDD, OFFLINE)

You are the **single source-mutating pi editor** for mission M5 of the `ask-chatgpt` v2 rewrite. You implement the live `CdpChannel` (Playwright-over-CDP) **read path** and wire `Session(channel="cdp")` so `scrape` works against real chatgpt.com — but **you do this OFFLINE with TDD only**. You do **NOT** run any browser, CDP, or network this task. A later **attended** worker runs the real legs. Your job: land correct, mock/offline-proven code so the real leg verifies in one pass.

Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**. Load and obey the `tdd` skill (red→green per behavior, **vertical slices** — one test, one minimal impl, repeat; never write all tests then all code).

## ISOLATION / SAFETY (HARD — transcribed; you inherit nothing)
- Work on **`rewrite-v2`** ONLY. **NEVER** checkout/commit/merge/move **`stable`** (must stay `779eb40`). **NEVER** `uv tool install/upgrade/reinstall`. Use **`uv run` / `uv sync`** (project venv) only. **NEVER** `git push`.
- **Do NOT** run git commits yourself — leave staging/commit to the manager. If you must check state, `git status` only. **NEVER** `git add -A`. Another agent concurrently edits `issues/cdp-send-repro/controller.mjs` — never touch/stage it. Never touch `team/state/live-state.json`.
- **This task is OFFLINE.** Do NOT call `connect_over_cdp`, do NOT launch a browser, do NOT touch `http://127.0.0.1:9222`, do NOT hit chatgpt.com/openai or any network. You may introspect the installed Playwright API by **import only** (`uv run python -c "import inspect, playwright.sync_api as s; ..."`). Everything you build is verified offline with fakes/stubs + `uv run pytest`.
- **READ-ONLY phase:** the code you write must make real **sends structurally impossible** this phase — the mutating action methods MUST raise (see §Action methods). Zero send/new-turn capability is exercised in M5.
- **NEVER persist or log** `authorization`/`oai-*`/`cookie` header VALUES anywhere (repr, logs, exceptions, raw-mapping, transcript, status, fixtures, any file). Redaction is a correctness requirement with explicit tests (see §Redaction).

## READ FIRST (ground truth — read in full; do not trust this summary alone)
- `src/ask_chatgpt/channels/base.py` — the `BrowserChannel` Protocol you implement + `TabLease`, `RequestSnapshot`, `FetchResult`, `TurnDom*`.
- `src/ask_chatgpt/channels/mock.py` — reference realization of every method (match names/kwargs/return types EXACTLY).
- `src/ask_chatgpt/capture.py` — esp. `acquire_backend_headers` (~137), `stream_backend_conversation` (~168), `capture_conversation` (~296), `fallback_capture_ui` (~323), `REQUIRED_CAPTURE_HEADERS` (~163 region / top), `_channel_monotonic` (666), `_KATEX_EVAL_KEY`/`_DOM_TEXT_EVAL_KEY` (47-48), `_fetch_bytes_written` (660). This is exactly how the channel is DRIVEN.
- `src/ask_chatgpt/session.py` — `_channel()` (201-209, the wiring gap), `scrape` (321-337), `status` (413-450), `attach`/`detach` (211-222).
- `src/ask_chatgpt/allowlist.py`, `src/ask_chatgpt/errors.py`, `src/ask_chatgpt/models.py` (`PreflightResult`).
- **Design detail (authoritative):** `team/evidence/reports/M5-design-lens-A.md` (lifecycle/headers), `-B.md` (streaming/measurement), `-C.md` (offline-test/Protocol/vocab). These three contain code sketches — follow them. The load-bearing synthesis is transcribed below.

## WHAT TO BUILD

### 1. `src/ask_chatgpt/channels/cdp.py` — the ONLY Playwright adapter
- **No top-level `playwright` import.** Import Playwright **only inside** the production attach path (e.g. a private `_start_playwright()` that does `from playwright.sync_api import sync_playwright, Error, TimeoutError`). `import ask_chatgpt`, `import ask_chatgpt.channels`, and **`import ask_chatgpt.channels.cdp`** must NOT import any `playwright*` module (offline test pins this).
- **Constructor** with test-injection hooks (production defaults `None`):
  `CdpChannel(*, cdp_endpoint="http://127.0.0.1:9222", allowlist=None, http_get_json=None, playwright_factory=None, monotonic=None, sleeper=None)`. Private state: `_pages: dict[str, page]`, `_tab_urls`, per-tab request buffers + per-tab CDP session refs. **Do NOT** add a `monotonic` attribute/method (capture's `_channel_monotonic` checks `getattr(channel,"monotonic",None)`; absence → it uses `time.monotonic()`, which is what we want).

- **`preflight(*, timeout_s=5.0) -> PreflightResult`** — plain HTTP, NOT Playwright. GET `<endpoint>/json/version` via injectable `http_get_json` (prod default = a small `urllib.request.urlopen` JSON getter). Map: success+websocket present → `ok=True` with `browser`/`protocol_version`; HTTP error / timeout / connection-refused / invalid JSON / missing websocket → `ok=False, error_code="CDP_UNREACHABLE"`, redacted **categorical** `error` string. Store websocket URL only as a **bool** (`websocket_url_present`), never the value.

- **`attach()`** — lazy import; `pw = sync_playwright().start()`; `browser = pw.chromium.connect_over_cdp(self.cdp_endpoint, timeout=...)`; `context = browser.contexts[0]` (require ≥1 context; fail closed otherwise). **NEVER** read/iterate `context.pages`. **NEVER** `chromium.launch` / `browser.new_context`.

- **`open_tab(url) -> TabLease`** — `allowlist.require_allowed_url(url)` **before any** lazy import / page creation / nav. Then `page = context.new_page()`; private `tab_id`; store page. Register **page-scoped** observers BEFORE nav: `page.on("request", ...)` (record only url/method/Request object — do **NOT** call `all_headers()` in the handler), `page.on("requestfinished", ...)`. Also create a same-page CDP fallback before nav: `cdp = context.new_cdp_session(page)`, register `Network.requestWillBeSent` + `Network.requestWillBeSentExtraInfo` handlers (correlate by `requestId`; store only **selected required** header names/values, never full map/cookies), `cdp.send("Network.enable")`. Navigate `page.goto(url, wait_until="domcontentloaded", timeout=...)`. **NEVER** `context.on(...)` (would observe operator pages). Return `TabLease(tab_id, url, self)`.

- **`wait_for_request(tab, predicate, *, timeout_s) -> RequestSnapshot`** — passive, own-tab buffer + per-tab cursor; pump future events with short `page.wait_for_timeout(...)` slices until timeout. Call `predicate` first with a **cheap** `RequestSnapshot(url, method, headers={})` (capture's predicate only checks method+path). On cheap match: `raw = request.all_headers()`; lower-case + project **only** `capture.REQUIRED_CAPTURE_HEADERS`; `del raw`; wrap selected in a **redacted-repr** mapping; build `RequestSnapshot`. If selected set incomplete, consult the CDP ExtraInfo fallback (by `requestId`) before returning. Return the best snapshot (capture raises `BackendAuthUnavailableError` listing missing **names** — never values). **No** reload/navigation here.

- **`fetch_in_page(tab, url, *, method="GET", headers=None, body=None, stream_to=None, timeout_s=None) -> FetchResult`** — validate tab; resolve relative `url` against `tab.url` for the allowlist check (allow single-slash same-origin paths like `/backend-api/conversation/<id>`; reject `//...`, non-http schemes); `allowlist.require_allowed_url(absolute)`.
  - **`stream_to` set (the ~17MB path):** open the temp path exclusively (`open(stream_to,"xb")`), install a **UUID-named** binding via `page.expose_binding(name, sink)`. The `sink` validates source page identity then calls the **pure** `consume_stream_event(state, event, out.write)` helper. Run `page.evaluate(JS_STREAM_FETCH, {...})`: in-page `fetch(url,{method,headers,credentials:"include",cache:"no-store",signal})`, `response.body.getReader()`, pump **base64** chunks (128 KiB raw bytes/chunk) via `await window[name]({kind:"chunk",streamId,seq,dataB64})`, then `{kind:"done"}`, return only `{status, headers}` (NEVER the body). Use `AbortController` for `timeout_s` (page.evaluate has no timeout param). Close binding + file; assert `state.done`; return `FetchResult(status, <sanitized response headers>, body_path=stream_to, body_bytes=None)`. Encoding = base64 (NOT array-of-ints); write **bytes**, decode only at JSON-parse time (UTF-8 safety). Backpressure is automatic (`await` the binding).
  - **`stream_to` None:** non-stream small path — return `FetchResult(status, headers, body_path=None, body_bytes=...)`. Minimal; not used by `scrape`. (Behind a small size cap is fine.)
  - Header VALUES live only in the evaluate arg + fetch init; let locals die after evaluate; never in `FetchResult`/logs/exceptions.

- **`reload(tab)`** / **`wait_for_load_state(tab, *, timeout_s)`** — validate tab; `page.reload(wait_until="domcontentloaded")` / `page.wait_for_load_state("domcontentloaded", timeout=...)`. Observers persist.

- **`evaluate(tab, js, *, arg=None, timeout_s=None) -> JsonValue`** — validate tab. Dispatch sentinel keys (capture passes these, NOT raw JS):
  - `js == "ask_chatgpt_capture_katex_annotations"` → run real JS `Array.from(document.querySelectorAll('annotation[encoding="application/x-tex"]')).map(n=>n.textContent)` → list[str].
  - `js == "ask_chatgpt_capture_dom_text"` → run real JS returning the visible assistant turns' text (reasonable lossy salvage; e.g. concatenated `innerText` of `[data-message-author-role="assistant"]`) → str.
  - else → `page.evaluate(js, arg)` generic.

- **`query_turns(tab, selectors) -> TurnDomSnapshot`** — read-only DOM via `page.evaluate` over the selector map: users/assistants (`message_id`+`text`), `stop_visible`, `composer_visible`, `model_labels`. (Not on the scrape happy path but Protocol-required + used by `status`/completion.)

- **`close_tab(tab)`** — validate `tab.channel is self` and known id; detach the page CDP session; remove listeners; `page.close(run_before_unload=False)`; drop only that private state. NEVER read/close `context.pages`.

- **`detach()`** — best-effort close own pages; clear state; then **`browser.close()`** — for a `connect_over_cdp` browser this **DISCONNECTS the Playwright client only and does NOT quit Chromium** (documented Playwright behavior; the real leg will confirm Chromium stays alive). Then `playwright.stop()`. **NEVER** `context.pages`; **NEVER** kill the Chromium process.

#### Action methods — DEFERRED (zero-send safety)
`fill`, `insert_text`, `click`, `hover`, `press`, `upload_files` MUST raise a clear deferred error (e.g. `HumanActionNeededError("CDP action/send path deferred to M7; M5 is read-only")` or a dedicated message) — do NOT implement live UI mutation this phase. `read_clipboard` raises `HumanActionNeededError(reason="clipboard_permission")`. This makes accidental real sends impossible in M5.

### 2. Pure offline-testable helpers (in `cdp.py` or a small module)
- `consume_stream_event(state, event, write_bytes) -> None` (validate `streamId`, monotonic `seq`, `kind`; base64-decode with `validate=True`; `write_bytes(data)`; bump `bytes_written`; mark `done`; never decode text; raise on wrong streamId / out-of-order seq / bad base64 / duplicate done).
- `decode_stream_chunk_base64(chunk)->bytes`, `append_decoded_stream_chunk(sink, chunk)->int`.

### 3. `catalogue_completion_status_vocab(raw_path) -> dict` (M5 step 6 reader)
Pure function (put in `capture.py` near the raw readers, or a small new module). Read top-level `async_status` and walk `mapping` collecting **redacted** enum/type/count summaries for `node.status`, `message.status`, `metadata.is_complete`, `metadata.is_finalizing`, `metadata.pro_progress` (booleans/short enum strings counted verbatim; high-cardinality/object `pro_progress` summarized by type/keys/len/hash, not content). Offline-tested over a fixture raw-mapping.

### 4. Wire `session.py`
- `_channel()` (line ~204): add a `cdp` branch — `if self._channel_arg == "cdp": from ask_chatgpt.channels.cdp import CdpChannel; self._browser_channel = CdpChannel(cdp_endpoint=self.cdp_endpoint); return self._browser_channel`. Keep the `mock` branch. Keep the import lazy (inside the method).
- `status()` (lines ~432-444): the `NotImplementedError` fallback is now obsolete; `self._channel().preflight()` returns a real `PreflightResult`. Keep `status` robust (a down CDP still returns a report). Don't break the existing `status --json --no-browser-probe` schema/tests.
- Do NOT change `scrape()` logic — it already calls `capture_conversation`; it just needed a real channel.

### 5. `scripts/m5_capture_measure.py` — measurement+fidelity+vocab driver (offline-written; run ATTENDED by the next worker)
A committed, parameterized driver: args `--conversation <id> --data-dir <path> [--out <file>]`. It constructs `Session(cdp_endpoint=..., data_dir=..., channel="cdp")`, wraps `session.scrape(conv, out=<tmp out>)` with `tracemalloc` (peak) + RSS (`resource.getrusage(RUSAGE_SELF).ru_maxrss`), records baseline after attach/open/header-acquire vs fetch-only vs end-to-end (fetch+parse+store). It prints a **redacted JSON summary ONLY**: turn count, total markdown length (int), raw-mapping byte size, mapping node count, top-level keys (names), the **fidelity booleans** (does any assistant turn's `content_markdown` contain `\widehat`, `\ne` or `\neq`, `\frac`; no replacement of `\ne`/`\neq` by a literal `≠`; no flattened `\frac`), the **completion-vocab** summary from `catalogue_completion_status_vocab`, and the RSS/tracemalloc numbers. It must **NOT** print conversation content (markdown goes only to the `--out` file, which the operator/worker keeps under a gitignored/throwaway path). It must **NEVER** print/log header values. Keep it import-light so it runs under `uv run python scripts/m5_capture_measure.py ...`.

## OFFLINE TEST LIST (falsifiable — `tests/test_cdp_channel.py`, split if large)
Write these red→green, vertically. Each must be able to FAIL:
1. **Lazy import:** after `import ask_chatgpt` / `import ask_chatgpt.channels.cdp` / a mock-channel test, `playwright` not in `sys.modules` (extend the existing pins at `tests/test_channels_base.py:114`, `tests/test_mock_channel.py:37`). Constructing `CdpChannel()` (no attach) imports no playwright. `Session(channel="cdp")` constructs + `status(probe_browser=False)` works with no playwright import.
2. **preflight mapping** via injected `http_get_json`: ok+websocket / HTTP-error / timeout / connection-refused / invalid-JSON / missing-websocket → correct `PreflightResult` (ok flag, `CDP_UNREACHABLE`, redacted error).
3. **allowlist before import:** `open_tab`/`fetch_in_page` with disallowed host, `//evil`, `javascript:` → `DomainNotAllowedError`, with a `playwright_factory` that **raises if touched** proving allowlist wins first.
4. **own-tabs-only:** fake context whose `.pages` raises on access + fake browser whose `.close()` is observable → `open_tab`/`close_tab`/`detach` never touch `context.pages`; `detach` calls `browser.close()` exactly once (disconnect) + `playwright.stop()`; only private pages closed.
5. **Protocol conformance:** signatures/return types via fake page — `TabLease(channel=self)`, `RequestSnapshot`, `FetchResult` (stream → `body_path` set/`body_bytes None`; non-stream → `body_bytes` set/`body_path None`), `TurnDomSnapshot`.
6. **wait_for_request:** cheap-predicate selection; projects only `REQUIRED_CAPTURE_HEADERS`; redacted repr; out-of-order CDP ExtraInfo correlation by fake `requestId`; timeout path → snapshot with missing names (capture would raise `BackendAuthUnavailableError`).
7. **pure stream decode:** `consume_stream_event` — in-order chunks reassemble; **multibyte UTF-8 split across two chunks** reassembles correctly (decode the on-disk bytes at the end); invalid base64 raises; wrong streamId raises; out-of-order seq raises; duplicate done raises.
8. **redaction canary:** feed a fake header value sentinel (e.g. `CANARY_SECRET`) through wait_for_request/fetch paths; assert it appears in **no** repr/str/exception/`FetchResult`/log/`RequestSnapshot.__repr__`.
9. **catalogue_completion_status_vocab** over a fixture raw-mapping with varied `async_status`/`status`/`is_complete`/`is_finalizing`/`pro_progress` → expected redacted summary.
10. **action methods raise** (fill/insert_text/click/hover/press/upload_files + read_clipboard) — zero-send safety.
11. Existing **188 tests stay green**.

## ACCEPTANCE (re-derive from ground truth; never exit codes alone)
- `uv run pytest` GREEN with the new offline tests; the **188 prior tests still pass** (so ≥188 + your new ones). Show the authoritative tail.
- `import ask_chatgpt` and all mock tests import **no** playwright (pinned by test).
- `cdp.py` realizes every `BrowserChannel` method; read-path methods implemented; action methods raise (read-only).
- Redaction tests pass (no header value leaks).
- `scripts/m5_capture_measure.py` exists, imports cleanly under `uv run python -c "import ast; ast.parse(open('scripts/m5_capture_measure.py').read())"` (syntax) and `--help`/dry construct works offline WITHOUT connecting (it should only connect when actually run with a live endpoint — guard so `import`/`--help` does no I/O).
- You ran **no** browser/CDP/network. `stable` unmoved. No `uv tool`. Nothing pushed. You staged/committed nothing (manager commits).

## OUTPUT
Write your report to `team/evidence/reports/M5-E1-cdp-channel.md`: **Status** (DONE/PARTIAL/BLOCKED); files created/modified; the authoritative `uv run pytest` tail (exact pass count); the offline test list mapped to test names; what is **real-leg-verified-only** (connect_over_cdp, goto, live request observation, live 17MB stream, detach-leaves-Chromium-alive) and therefore NOT proven by your offline suite; redaction proof; any deviations from the design synthesis and why; blockers. Do NOT commit. Do NOT touch the browser. Begin now.
