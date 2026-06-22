STATUS: DONE

## Findings

### Public `Session` method classification

| Public method | Acquires a pool tab? | Navigation / render cost | Data path | READ/SEND classification |
|---|---:|---|---|---|
| `attach()` | No pool tab (`session.py:316-320`) | No tab; attaches channel only via `self._channel().attach()` (`session.py:317-318`) | No conversation data | Lifecycle |
| `detach(close_managed_tabs=True)` | No acquire; may close existing managed tabs (`session.py:322-327`) | No new navigation | No conversation data | Lifecycle |
| `__enter__` / `__exit__` | No acquire; delegate to attach/detach (`session.py:329-335`) | No new navigation beyond any existing managed-tab close | No conversation data | Lifecycle |
| `create(project=None)` | No (`session.py:337-347`) | No tab; constructs draft URL `https://chatgpt.com/` or project root (`session.py:341`, `session.py:344-346`) | In-memory `ConversationRef` only | CREATE/DRAFT, no send |
| `ask(conv_or_url, prompt, ...)` | Yes, `tab = self.tab_pool.acquire(ref)` (`session.py:366`) | Existing conversation resolves to `/c/<id>` through `TabPool.acquire` -> `conversation_url` (`session.py:83`, `identity.py:123-124`) -> `open_tab`/`goto` (`session.py:94`, `cdp.py:650`); fresh draft is a nuance: `conv_or_url is None` calls `create()` (`session.py:361`) and initially opens root/project URL (`session.py:341`, `identity.py:116`) | SEND uses DOM composer (`session.py:400`, `session.py:410-414`; `send.py:78-86`, `send.py:166-203`), completion polls backend+DOM on the same tab (`session.py:440-449`; `completion.py:45-51`, `completion.py:68`), final canonical data from backend capture (`session.py:453-460`; `capture.py:305-307`) | SEND |
| `scrape(conv_or_url, ...)` | Yes, `tab = self.tab_pool.acquire(ref)` (`session.py:521`) | Heavy `/c/<id>` for persisted conversation via `TabPool.acquire` (`session.py:83`, `identity.py:123-124`, `session.py:94`, `cdp.py:650`) | Backend-API capture (`session.py:523`; `capture.py:305-307`, `capture.py:176-180`), then local store reload (`session.py:525`) | READ; **only always-heavy public read** |
| `history(conv_or_url)` | No (`session.py:530-531`) | No tab | Local store only: `return self.store.load_transcript(conv_or_url)` (`session.py:531`); store reads `transcript.jsonl` bytes (`store.py:244-248`) | READ |
| `fetch(conv_or_url, attachment_ref)` | No (`session.py:533-556`) | No tab | Local store/cached attachment only: loads transcript (`session.py:534`), checks cached `attachment.local_path` (`session.py:547-556`) | READ |
| `loop(conv_or_url, ...)` | Yes, `tab = self.tab_pool.acquire(ref)` (`session.py:579`) | Requires persisted conversation id (`session.py:576-577`), therefore heavy `/c/<id>` via `conversation_url`/`open_tab`/`goto` (`session.py:83`, `identity.py:123-124`, `session.py:94`, `cdp.py:650`) | Repeated SEND via `_run_send_turn` (`session.py:584-594`): DOM composer + completion + backend capture as above | SEND loop |
| `status(conv_or_url=None, probe_browser=True)` | No (`session.py:604-647`) | No tab; optional browser check is `self._channel().preflight()` (`session.py:623-624`), whose CDP implementation calls `/json/version` only (`cdp.py:552-555`) | Local store count/load (`session.py:632`, `session.py:635`; `_conversation_count` at `session.py:748-752`) plus CDP preflight metadata | Diagnostic READ |

### Hypothesis verdicts and decisive evidence

- CONFIRM repository baseline: branch `main` observed by `git rev-parse --abbrev-ref HEAD`; version `0.2.0` appears in `pyproject.toml:3` and `src/ask_chatgpt/__init__.py:56`.
- CONFIRM tab acquisition is the heavy step for persisted conversations: `TabPool.acquire` computes `url = conversation_url(ref)` (`session.py:83`), caches by exact URL (`session.py:86`, `session.py:96`), opens it (`session.py:94`), `conversation_url` returns project/nonproject `/c/<id>` URLs (`identity.py:123-124`), and CDP navigates with `page.goto(url, wait_until="domcontentloaded", timeout=30000)` (`cdp.py:650`).
- CONFIRM H1 with nuance: `grep` found only three source call sites of `tab_pool.acquire`: `ask` (`session.py:366`, SEND), `scrape` (`session.py:521`, READ), and `loop` (`session.py:579`, SEND), plus the internal `open_tab` at `session.py:94`; therefore `scrape` is the only public READ that always pays persisted-conversation `/c/<id>` render. `ask(None, ...)` initially opens root/project draft, not `/c`, but it is still SEND.
- CONFIRM H2 / REFUTE the issue's history/fetch claim: `history` is exactly `return self.store.load_transcript(conv_or_url)` (`session.py:530-531`), and `fetch` starts with `transcript = self.store.load_transcript(conv_or_url)` (`session.py:533-534`) then returns an existing local cached file (`session.py:547-556`); `Store.load_transcript` resolves local paths and reads `transcript_jsonl.read_bytes()` (`store.py:244-248`). No tab acquisition or browser page render exists in either path.
- CONFIRM H3 with caveat: persisted `ask` and all `loop` sends legitimately need an interactive conversation tab because `_run_send_turn` waits for/uses the DOM composer (`session.py:400`, `session.py:410-414`; `send.py:78-86`, `send.py:166-203`). Caveat: fresh `ask(None, ...)` uses `create()` (`session.py:361`) and starts on root/project URL (`session.py:341`, `identity.py:116`), then after id-learn the draft branch reloads the learned `/c/<id>` before capture (`session.py:451-453`) for the M7b auth gap.
- CONFIRM backend-API data path for capture: `capture_conversation` harvests headers then streams backend JSON (`capture.py:305-307`), `stream_backend_conversation` fetches `f"/backend-api/conversation/{conversation_id}"` via `tab.channel.fetch_in_page` (`capture.py:171-180`), and CDP evaluates `JS_STREAM_FETCH` in page (`cdp.py:50`, `cdp.py:834`) with `credentials: "include"` (`cdp.py:63`). Normal successful capture is not DOM; `fallback_capture_ui` only reaches DOM probes after explicit clipboard permission path, and default call raises first (`capture.py:493-508`).
- CONFIRM crux / M7b gap: current header harvest waits for a page-observed GET whose path exactly equals the target conversation backend path: target path from `backend_conversation_url` (`capture.py:142`), exact matcher (`capture.py:144-146`), then `wait_for_request` (`capture.py:149`). M7b documented the same failure mode: fresh/client-navigated chat never issued that GET, so `acquire_backend_headers` timed out (`team/evidence/handoffs/M7b-gaps.md:15-16`). A light root tab with this harvest unchanged should therefore fail with `BACKEND_AUTH_UNAVAILABLE` unless the harvest mechanism changes too.
- CONFIRM header subtlety: required names are exactly `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, `x-openai-target-route` (`capture.py:39-47`). `HeaderBundle.for_single_fetch()` returns `dict(self._headers)` verbatim (`capture.py:62-69`), and `stream_backend_conversation` passes those headers through as `{"accept": "application/json", **backend_headers}` (`capture.py:174-175`) without recomputing `x-openai-target-path` or `x-openai-target-route` for the fetched URL.

## Answers to lens-required questions

### CLI mapping and blast radius

| CLI subcommand | Parser lines | Handler -> Session method | Heavy read missed? |
|---|---:|---|---|
| `ask` | `cli.py:125-133` | `_handle_ask` calls `session.ask(...)` (`cli.py:188-201`) | No; SEND path already counted |
| `create` | `cli.py:135-138` | `_handle_create` calls `session.create(...)` (`cli.py:206-208`) | No tab |
| `scrape` | `cli.py:140-144` | `_handle_scrape` calls `session.scrape(...)` (`cli.py:224-226`) | Yes: same sole heavy READ as Session `scrape` |
| `history` | `cli.py:146-149` | `_handle_history` calls `session.history(...)` (`cli.py:231-233`) | No; local store |
| `export` | `cli.py:151-154` | Reuses `_handle_history` -> `session.history(...)` (`cli.py:231-233`) | No; local store |
| `fetch` | `cli.py:156-160` | `_handle_fetch` calls `session.fetch(...)` (`cli.py:238-240`) | No; local cached attachment |
| `status` | `cli.py:162-166` | `_handle_status` calls `session.status(...)` (`cli.py:249-251`) | No; preflight/store only |
| `loop` | `cli.py:168-178` | `_handle_loop` iterates `session.loop(...)` (`cli.py:259-278`) | No; SEND loop already counted |

No CLI read path acquires a heavy tab beyond `scrape`; `export` is just `history`.

### Completion-poll path

`completion.py` acquires no pool tab of its own: `wait_for_completion` receives an existing `tab` (`completion.py:127-136`), and the only source call is `_run_send_turn` passing the already-acquired send tab (`session.py:440-449`). Backend polling harvests headers/fetches on that same tab (`completion.py:45-51`, `completion.py:162`); DOM polling queries turns on that same tab (`completion.py:68`, `completion.py:173`). This is read-like polling inside a SEND, not a public READ-only heavy navigation.

### `status`

`status` does not need DOM, `/c/<id>`, or backend API: it optionally calls CDP preflight (`session.py:623-624`; `cdp.py:552-555`) and reads local store metadata/counts (`session.py:632`, `session.py:635`, `session.py:748-752`). It would not benefit from a light page in the current implementation because it opens no page at all; if future status does a signed-in web probe, that new probe should use a light root page.

### Exhaustive light-read fix touch list

MUST-CHANGE:

- `src/ask_chatgpt/session.py:82-96` (`TabPool.acquire`): add a way to acquire/cache a light read tab (likely keyed by `https://chatgpt.com/`, not the conversation URL) without disturbing existing conversation-tab semantics.
- `src/ask_chatgpt/session.py:512-528` (`Session.scrape`): switch this READ to the light acquisition path and keep release semantics.
- `src/ask_chatgpt/capture.py:140-162` (`acquire_backend_headers`): replace/supplement exact `/backend-api/conversation/<id>` request harvesting; a light root page will not necessarily self-issue that request.
- `src/ask_chatgpt/capture.py:62-69` and `src/ask_chatgpt/capture.py:171-180`: decide and implement correct treatment of `x-openai-target-path` / `x-openai-target-route`; current code passes harvested values verbatim and does not recompute for the actual fetch target.
- `src/ask_chatgpt/channels/mock.py:419-430` plus relevant tests: update the mock/auth-harvest model so offline tests are falsifiable for light-page harvest and do not preserve the old `/c/` reload dependency as a hidden requirement.

MUST-NOT-CHANGE for light-read purposes:

- `src/ask_chatgpt/session.py:366` and `src/ask_chatgpt/session.py:579`: persisted `ask`/`loop` are SEND paths and should continue using conversation tabs.
- `src/ask_chatgpt/session.py:400-414` and `src/ask_chatgpt/send.py:78-86`, `src/ask_chatgpt/send.py:166-203`: DOM composer interactions are required for sending.
- `src/ask_chatgpt/session.py:440-456` / `src/ask_chatgpt/completion.py:127-173`: completion reuses the send tab; do not create a separate heavy read tab here as part of the read fix.
- `src/ask_chatgpt/session.py:530-556`: `history` and `fetch` are already tab-free local-store reads; do not convert them to browser/backend operations.
- `src/ask_chatgpt/session.py:604-647`: `status` is already no-tab; no light-read change needed.
- `src/ask_chatgpt/cli.py:188-278`: CLI simply dispatches to Session; no separate CLI read acquisition layer to fix unless exposing a new flag/API is desired.

## Risks / unknowns

- Real-site unknown: whether a root/light page exposes all nonsecret OAI request headers needed for conversation fetch, especially `x-openai-target-path` and `x-openai-target-route`; offline code proves current pass-through behavior but not live header semantics.
- A naive root-tab change to `scrape` without harvest redesign is expected to regress to `BACKEND_AUTH_UNAVAILABLE` for the exact M7b reason.
- If implementation harvests from another backend request, ensure target-specific headers are recomputed or intentionally overridden for `/backend-api/conversation/<id>` and validated offline before any attended real-site probe.
- I did not run `uv run pytest`; this was a no-code-edit investigation and the safety rule allowed only this handoff write.

## Recommended next steps

1. Implement a light-tab acquire path used only by `Session.scrape`, plus a light-safe auth/header acquisition strategy.
2. Add falsifiable unit tests proving `scrape` opens `https://chatgpt.com/` (or another light page) while `ask`/`loop` persisted conversations still open `/c/<id>`.
3. Add tests that would fail if header harvest still requires observing `/backend-api/conversation/<id>` from a `/c` reload.
4. Add/adjust tests for `x-openai-target-path` / `x-openai-target-route` behavior; do not assume those headers are global.
5. Run `uv run pytest` and inspect the pytest summary/output, not just the exit code; only then consider an attended, redacted real-site probe for header semantics.