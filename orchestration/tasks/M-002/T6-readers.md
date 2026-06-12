# T6 — Readers: ResponseReader interface + DomReader (primary) + CopyButtonReader (fallback), D-001 order, adversarial-proof. TDD.

You are an INDEPENDENT pi worker. You inherit NOTHING except this file and what it tells you to read. Repo root = `/home/abhmul/dev/ask-chatgpt` (your cwd). T1–T5 DONE/committed. The driver (`src/ask_chatgpt/driver.py` `BrowserSession`) drives the complete mock fixture: `wait_for_completion(timeout_s) -> Locator` returns the LATEST COMPLETED assistant-turn locator and exposes `.page` (Playwright Page) and `.selectors` (a `SelectorMap`, fail-closed). 38 tests green.

## STEP 0 — Confirm you inherit a GREEN tree
`uv sync --all-groups` then `uv run pytest -q`. MUST be green (38 passed). If not, STOP, report BLOCKED with output.

## Read these files FIRST (in order)
1. This contract in full.
2. `/home/abhmul/dev/ask-chatgpt/docs/DECISIONS.md` — **D-001 #1 is THE spec for this leg:** PRIMARY = bounded DOM extraction; FALLBACK = copy-button/clipboard; one `ResponseReader` interface, configurable order, **DOM default**; both pass the same adversarial fixtures; latest completed assistant turn ONLY, selector-map-scoped, explicit completion detection, **no history sweep**, fail-closed with actionable errors (`RESPONSE_TRUNCATED`, selector-unavailable). Read the "Why DOM-primary" section.
3. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/driver.py` — `BrowserSession`: `.page`, `.selectors`, `wait_for_completion() -> Locator` (the latest completed turn). Note how it locates the latest completed assistant turn; you reuse that boundary. Note whether the mock context grants clipboard permissions (see clipboard note below).
4. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/selector_map.py` — `SelectorMap.selector(key)`/`.attribute(key)` (fail-closed). 
5. `/home/abhmul/dev/ask-chatgpt/src/ask_chatgpt/errors.py` — named errors (`SelectorUnavailableError`, `ResponseTruncatedError`, ...).
6. `/home/abhmul/dev/ask-chatgpt/tests/test_fixture_adversarial.py` + `tests/fixtures/mock_chatgpt/server.py` — how to script booby-trap turns, the virtualized variant, and `copy_mode` (ok/missing/wrong/stale/truncated). The `copy_button` writes `navigator.clipboard`; tests grant clipboard permissions on the loopback context.

## Scope — build the readers (`src/ask_chatgpt/readers.py`)
1. **`ResponseReader` interface** (ABC or Protocol): `read(self, turn_locator: Locator, page: Page, selectors: SelectorMap) -> str`, plus a `name` attribute. `turn_locator` is the LATEST COMPLETED assistant-turn element (from `wait_for_completion`). Readers extract ONLY from within that turn — never older turns, never a transcript sweep.
2. **`DomReader(ResponseReader)` — PRIMARY:** read the rendered text of the `message_body` WITHIN `turn_locator` (selector-map-scoped). If the turn bears the `truncation_marker` → `ResponseTruncatedError`. If the `message_body`/`assistant_message` selector is missing/empty → `SelectorUnavailableError` (fail closed). Return the bounded latest-turn text. No history sweep, no clipboard.
3. **`CopyButtonReader(ResponseReader)` — FALLBACK:** find the `copy_button` WITHIN `turn_locator`; if absent → `SelectorUnavailableError`. Click it, then read `navigator.clipboard.readText()` via `page.evaluate`. Return the clipboard text. (This is the UI-owned serialization fallback.) Clipboard note: reading the clipboard requires the browser CONTEXT to have `clipboard-read`/`clipboard-write` permissions granted on the loopback origin. If the driver's mock context does NOT already grant them, you MAY update `BrowserSession`'s MOCK context creation to grant `clipboard-read`/`clipboard-write` (loopback only) — do NOT change real-channel behavior (real clipboard perms are an operator-runbook unknown, memo §7 item 5).
4. **`read_response(turn_locator, page, selectors, order=None) -> str`** — composite: try readers in `order` (DEFAULT = `(DomReader(), CopyButtonReader())` per D-001). Fall through to the NEXT reader ONLY on `SelectorUnavailableError` (the affordance is unavailable). Any OTHER named error (`ResponseTruncatedError`, `LoginRequiredError`, ...) PROPAGATES immediately (fail-closed — a real honest failure must NOT be masked by trying the fallback). If all readers are exhausted (all unavailable) → raise `SelectorUnavailableError` with an actionable message. `order` is configurable (a constant, not a redesign) so the operator can flip DOM/copy precedence later.

### TDD tests — `tests/test_readers.py` (write FIRST, watch fail, implement) — channel="mock"
Drive `mock_chatgpt` via `BrowserSession` (channel="mock"). Cover:
- **DomReader happy path:** scripted latest completed turn → returns exactly its text.
- **DomReader adversarial (THE key D-001 property):** script an OLDER turn with `BOOBYTRAP-<token>` + a latest completed turn with the real answer; `DomReader` returns the real answer and the sentinel is NOT in the result. Repeat under the `virtualized` layout variant.
- **DomReader truncation:** `response_truncated` mode → `ResponseTruncatedError`.
- **CopyButtonReader happy path:** `copy_mode=ok` → returns latest text from the clipboard.
- **CopyButtonReader missing:** `copy_mode=missing` → `SelectorUnavailableError`.
- **Default-order resists booby-trapped copy (D-001 rationale):** set `copy_mode=wrong` (copy would yield an OLDER/booby-trap text) AND a booby-trap older turn; `read_response(..., order=None)` (DOM primary) returns the REAL latest text, NOT the wrong copy. This demonstrates why DOM is primary.
- **Configurable fallback:** make the DOM affordance unavailable (e.g. load a `SelectorMap` whose `message_body` is empty, or use a fixture mode that omits the body) so `DomReader` raises `SelectorUnavailableError`; `read_response` falls through to `CopyButtonReader` (`copy_mode=ok`) and returns the latest text. Also test `order=(CopyButtonReader(), DomReader())` runs copy first.
- **Fail-closed not masked:** with DOM primary, a `ResponseTruncatedError` from `DomReader` PROPAGATES (the composite does NOT silently fall back to copy).
- Full `uv run pytest -q` GREEN (38 existing + new). Bound waits.

## SAFETY BLOCK (verbatim — obey exactly; you inherit nothing)
- Tests and ALL work NEVER contact chatgpt.com/openai or any external service. Drive ONLY the loopback `mock_chatgpt` via channel="mock". Clipboard permissions are granted ONLY on the loopback context. Do not weaken the conftest socket guard. Never navigate to chatgpt.com; never run the real channel.
- Never read/store/log credentials, cookies, session tokens, or browser-profile contents. Booby-trap sentinels are synthetic test strings, never secrets. The reader returns ONLY the bounded latest assistant turn — NEVER a transcript-wide sweep.
- The ONLY ever-permitted external download is chromium — ALREADY CACHED. ZERO new pip deps (existing `playwright`). Never sudo/apt/install.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt` (+ `tmp/`). Archive READ-ONLY (never `archive/`/`human/`). Never write `.claude/`/`.agents/`.
- Python: `uv run <cmd>` from repo root ONLY. NEVER bare `python`/`pip`. NEVER touch `~/.local/share/agent-python/.venv`. `uv sync --all-groups` ALWAYS.
- You are the ONLY editor right now. Serialize pytest. Tear down browsers you start. NEVER `git push`. Do NOT `git commit`. Do not break the 38 existing tests. ESTIMATE BEFORE EXECUTE for anything >2 min.

## Telemetry v2 (REQUIRED — report `orchestration/reports/M-002/T6-report.md`)
- `date -Iseconds` at START + END → literal `START_TIMESTAMP:` / `END_TIMESTAMP:` lines.
- `ESTIMATE: T6 <min>m`.
- Report ≤200 lines: files created/modified, the reader interface + the two readers + composite order semantics (when it falls through vs propagates), whether you changed the driver's mock context for clipboard perms, the adversarial test results (sentinel never returned), the exact `uv run pytest -q` summary, deviations, trust notes (bounded latest-turn only, loopback-only, no secrets).
- End with `T6-STATUS: DONE` (or `BLOCKED` + exact error + next action) LAST.

## Success criteria (all must hold)
- `ResponseReader` interface; `DomReader` (PRIMARY, bounded latest completed turn, truncation→`ResponseTruncatedError`, fail-closed); `CopyButtonReader` (FALLBACK, clipboard); `read_response` with DOM-default configurable order, falling through ONLY on `SelectorUnavailableError`, propagating other named errors.
- Adversarial: booby-trap/older/injected text is NEVER returned (proven in stable AND virtualized variants); default order returns correct text even when the copy affordance is booby-trapped.
- `tests/test_readers.py` green; full `uv run pytest -q` green (38 existing pass); zero new deps; clipboard perms only on loopback context.
- Report with telemetry + `T6-STATUS:` last.
