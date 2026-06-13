# T2c — Plumb channel=cdp through the public API/CLI + URL-derive conversation_ref (MOCK-TIER, single editor, TDD)

You are a fresh worker. **You inherit NOTHING except this file + the files it tells you to read.** This leg contacts NOTHING real: mock/loopback + unit tests only. **ZERO real messages.** TDD/RED-first for the behavior changes. Read the SAFETY BLOCK and obey it literally. The repo destructive-guard hook blocks command text containing certain destructive substrings — if you ever need to revert tracked files use `git stash push -u`, never `git checkout`/`git clean`. Do NOT `git commit` (the manager commits after independent verification).

## Why this leg exists (two BLOCKING gaps + one evidence-based fail-close; all confirmed by the manager from ground truth)

Real-site UC1-3 acceptance will run over CDP attach (`channel="cdp"`). The driver supports cdp, but the PUBLIC surface and the conversation-ref logic do not, so UC1-3 cannot run yet. Discovery (T2) also proved the real site emits NO Playwright `Download` event. Fix all three:

- **GAP-1 (blocks UC1 via `ask_chatgpt()` and UC3 via the CLI):** neither the public API nor the CLI can select `channel="cdp"` or a CDP endpoint.
- **GAP-2 (blocks every real call, even a brand-new conversation):** the conversation ref is read from a DOM attribute that is EMPTY on the real site; it must be URL-derived from the `/c/<id>` path.
- **GAP-3 (UC2 trap):** `real.json` `download_artifact` matches a metadata-less real Download button; since no real `Download` event fires, force the proven fenced fallback by fail-closing that key.

## Files to READ FIRST (ground truth; line numbers may drift — verify)

- `src/ask_chatgpt/api.py` — `ask_chatgpt(...)` signature at lines 30-44 (`channel="real"`, `base_url`, `profile_path`; NO `cdp_endpoint`); constructs `BrowserSession(channel=channel, base_url=base_url, profile_path=profile_path)` at line 55 (UC1 path) and line 114 (`_ask_chatgpt_with_bundle`, UC2 path). The UC1 flow (lines 50-74): `open_or_create_conversation(conversation_ref)` → `select_model` → `send_prompt` → `wait_for_completion` → `read_response`; then if `session_identifier`, `active_ref = session.active_conversation_ref or active_ref` and `registry.set(...conversation_ref=active_ref, url=session.page.url...)`.
- `src/ask_chatgpt/cli.py` — `_build_parser()` lines 95-115: `--channel choices=("real","mock") default="real"` at line 111; NO `--cdp-endpoint`. Find where it calls `ask_chatgpt(...)` (around line 55-72) and what it passes.
- `src/ask_chatgpt/driver.py`:
  - `__init__` (~line 71-95): already has `cdp_endpoint: str | None = None` and `_DEFAULT_CDP_ENDPOINT = "http://127.0.0.1:9222"`. The driver side is DONE; only the public surface lacks plumbing.
  - `open_or_create_conversation` (~lines 190-216): open-existing branch ends at line 204 `self._active_conversation_ref = self._read_active_conversation_ref()`; create-NEW branch (after `new_chat_button` click) ends at line 215 with the SAME hard call. **Line 215 is the hard-fail for a brand-new real chat (URL is `/`, no `/c/<id>` yet, DOM attr empty).**
  - `send_prompt` (~line 268): `self._active_conversation_ref = self._try_read_active_conversation_ref() or self._active_conversation_ref` — the FORGIVING read, runs post-send (when the real URL HAS become `/c/<id>`).
  - `_conversation_url` (~line 446): `f"{self._base_url}/c/{quote(ref, safe='')}"` — the URL shape; your URL-derive is the inverse.
  - `_read_active_conversation_ref` (~lines 475-481): `attr = self.selectors.attribute("conversation_ref")` (raises `SelectorUnavailableError` when the map value is `""`), then `root.get_attribute(attr)`.
  - `_try_read_active_conversation_ref` (~lines 483-487): swallows `SelectorUnavailableError`/`SessionNotFoundError`/`PlaywrightError` → returns `None`.
  - `_selector_map_channel` (~line 437): for `channel=="cdp"`, returns `"mock"` if base_url is loopback else `"real"`. (So cdp+loopback uses mock.json; cdp+production uses real.json.)
- `src/ask_chatgpt/selector_map.py` (~lines 35-39): `attribute()` raises `SelectorUnavailableError` on empty/whitespace.
- `src/ask_chatgpt/selector_maps/real.json` — `attributes.conversation_ref=""` (the cause of GAP-2); `selectors.download_artifact='button[aria-label*="Download"]'` (the GAP-3 key to fail-close).
- `tests/test_driver.py` (mock UC1 happy path, ~line 22) + `tests/test_driver_cdp_attach.py` (cdp throwaway-browser tests) + `tests/test_api*.py` / `tests/test_cli*.py` if present — match their style. `pyproject.toml` — `uv sync --all-groups` before testing.

## Deliverables (all REQUIRED; TDD/RED-first for behavior)

### D1 — GAP-1: plumb `cdp_endpoint` + `channel="cdp"` through the public surface
- `api.py`: add param `cdp_endpoint: str | None = None` to `ask_chatgpt(...)` AND to `_ask_chatgpt_with_bundle(...)`; pass `cdp_endpoint=cdp_endpoint` into BOTH `BrowserSession(channel=channel, base_url=base_url, profile_path=profile_path)` calls (lines ~55 and ~114) and forward it from `ask_chatgpt` into `_ask_chatgpt_with_bundle`. Keep `channel="real"` default unchanged.
- `cli.py`: add `"cdp"` to `--channel choices` → `choices=("real","mock","cdp")`; add `--cdp-endpoint` (metavar URL, default `"http://127.0.0.1:9222"`, help text "CDP endpoint for channel=cdp"); thread `cdp_endpoint=args.cdp_endpoint` into the `ask_chatgpt(...)` call. Do NOT change other defaults.

### D2 — GAP-2: URL-derive the conversation ref (preserve mock behavior exactly)
Implement so the MOCK path is byte-for-byte unchanged (it has a DOM `conversation_ref` attribute) and the REAL/cdp path works with an empty attribute:
1. Add a small helper, e.g. `_conversation_ref_from_url(self, url: str) -> str | None`: parse `urlparse(url).path`, split on `/`, and if the first two non-empty segments are `["c", "<id>"]` return `unquote("<id>")`, else `None`. (Inverse of `_conversation_url`.)
2. Rewrite `_read_active_conversation_ref()` to: (a) try the DOM attribute FIRST — `try: attr = self.selectors.attribute("conversation_ref") except SelectorUnavailableError: attr = None`; if `attr` and `root.get_attribute(attr)` is truthy, return it (MOCK path, unchanged). (b) else fall back to `_conversation_ref_from_url(self._require_page().url)`; return it if truthy. (c) else raise `SessionNotFoundError` as today. `_try_read_active_conversation_ref` stays the forgiving wrapper.
3. Make the create-NEW-conversation branch tolerate "no ref yet": change line ~215 from the hard `_read_active_conversation_ref()` to the forgiving `self._try_read_active_conversation_ref() or ""` and return that. (A brand-new real chat has no `/c/<id>` until after the first send; the ref is then captured post-send at line ~268. The mock still returns its DOM-attr ref unchanged.) The open-EXISTING branch (line ~204) may KEEP the hard read (after navigating to `/c/<ref>` the URL-derive or DOM attr yields a ref; a genuine miss SHOULD raise `SessionNotFoundError`).
4. Add the needed imports (`urlparse`, `unquote`) to driver.py.

### D3 — GAP-3: fail-close `download_artifact` in `real.json`
- Set `selectors.download_artifact` to `""` in `src/ask_chatgpt/selector_maps/real.json` (leave all other keys as-is). Rationale (put in your REPORT, not the JSON): T2 discovery proved the real site fires NO Playwright `Download` event; download-primary is not viable, so fail-close it to force the proven checksummed fenced-base64 fallback for UC2 and avoid a `PatchMalformedError` on a metadata-less Download button. real.json stays valid (all 20 selector + 2 attribute keys present).

### D4 — Tests (DEFAULT-TIER; mock/loopback/unit only; NOT `real_site`-marked; RED-first)
Add tests proving the three fixes WITHOUT real contact:
- `_conversation_ref_from_url`: unit-test it directly — `https://chatgpt.com/c/abc123` → `"abc123"`; `https://chatgpt.com/` → `None`; a loopback `…/c/<id>` → `<id>`; a quoted id round-trips.
- GAP-2 integration (if cleanly feasible with the mock fixture / a stub page): a session whose selector map has an EMPTY `conversation_ref` attribute but whose page URL is `/c/<id>` resolves the ref via URL. If a full integration is awkward, a focused unit test of `_read_active_conversation_ref`'s fallback (e.g. via a minimal fake page/selectors) plus the helper test is acceptable — state which you did and why.
- GAP-1: `ask_chatgpt(..., channel="cdp", cdp_endpoint=...)` forwards `cdp_endpoint` into `BrowserSession` (assert via a constructed session or a monkeypatched `BrowserSession` capturing kwargs); the CLI parses `--channel cdp --cdp-endpoint URL` and forwards it (assert via argparse + a patched `ask_chatgpt`). Do NOT attach to any real browser in these tests.
- Keep ALL existing mock tests green. The mock UC1 happy path MUST still pass (proves D2 didn't regress the DOM-attr path).

### D5 — Suite green + tier purity preserved
- `uv sync --all-groups`, then run the FULL default suite ONCE (serialize): `uv run pytest`. MUST be GREEN. Capture the exact summary line. Expect >= the prior 136 passed (you are ADDING tests).
- Clean run still collects ZERO `real_site` tests; the autouse socket guard in `tests/conftest.py` is UNCHANGED; `mock.json` UNCHANGED.
- `git diff --stat` touches ONLY: `src/ask_chatgpt/api.py`, `src/ask_chatgpt/cli.py`, `src/ask_chatgpt/driver.py`, `src/ask_chatgpt/selector_maps/real.json`, and your new/edited test files. NOT `conftest.py` guard, NOT `mock.json`, NOT `.claude/`/`.agents/`.

## SAFETY BLOCK — obey verbatim (you inherit nothing)
- ZERO real-site contact. Mock/loopback/unit only. Default-tier tests stay loopback-only; the autouse socket guard must NEVER be weakened; do NOT add network-touching code paths reachable by default tests.
- Preserve fail-closed semantics everywhere: never invent selectors; the only key you blank is `download_artifact` (D3). Do not populate any other empty real.json key.
- Never read/copy/store/log credentials, cookies, tokens, profile contents. No account identifiers anywhere.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Archive READ-ONLY. Never write `.claude/`/`.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. NEVER `git push`. Do NOT `git commit`.
- ESTIMATE BEFORE EXECUTE: before the test run, state expected wall-clock + output volume.

## Reporting (write to `orchestration/reports/M-006/T2c.md`, cap ~250 lines)
1. `START_TIMESTAMP:`/`END_TIMESTAMP:` (`date -Iseconds`) + `ESTIMATE: T2c <min>m`.
2. The exact changes per D1/D2/D3 (with final line numbers) and the RED→GREEN evidence (the failing test you wrote first, then passing).
3. The authoritative `uv run pytest` summary line + confirmation ZERO real_site collected + socket guard + mock.json unchanged + the mock UC1 happy path still green.
4. `git diff --stat` (prove scope).
5. Any design judgment where you deviated and why; anything you could not prove deterministically.
6. `MESSAGES_USED: 0`.
- LAST LINE must be exactly: `T2c-STATUS: DONE` (or `T2c-STATUS: BLOCKED` with the precise blocker).
