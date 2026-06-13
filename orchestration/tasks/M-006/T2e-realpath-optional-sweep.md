# T2e — Sweep: every UC1-3 real-path optional-selector access must tolerate a fail-closed-empty real.json key (MOCK-TIER, single editor, TDD)

You are a fresh worker. **You inherit NOTHING except this file + the files it tells you to read.** ZERO real contact: mock/loopback/unit only. **ZERO real messages.** TDD/RED-first. Read the SAFETY BLOCK and obey it. The repo destructive-guard hook blocks command text with certain destructive substrings — use `git stash push -u` for any revert, never `git checkout`/`git clean`. Do NOT `git commit` (the manager commits).

## Why this leg exists (real run + manager audit confirmed two more same-family gaps)

The real selector map `src/ask_chatgpt/selector_maps/real.json` is deliberately SPARSE — these keys are `""` (intentional fail-closed because discovery could not verify a stable selector): `model_menu`, `model_option`, `model_option_disabled`, `login_wall`, `conversation_not_found`, `truncation_marker`, `rate_limit_marker`, `download_artifact` (blanked on purpose — the real site fires no Playwright Download), and attribute `conversation_ref` (URL-derived, already handled). `SelectorMap.selector(key)`/`attribute(key)` RAISE `SelectorUnavailableError` on an empty value. The driver path was already fixed (T2d: `_present` soft). But the READ path and the BUNDLE-RETRIEVAL path still access OPTIONAL empty keys unconditionally and break on the real map:

- **GAP-7 — `src/ask_chatgpt/readers.py` `DomReader.read` (~line 34):** resolves `truncation_selector = selectors.selector("truncation_marker")` UNCONDITIONALLY, before the try-block. On real (`truncation_marker=""`) this raises `SelectorUnavailableError`, so `DomReader` ALWAYS fails and `read_response` (line ~100-105) falls through to `CopyButtonReader` (clipboard) on EVERY real read — defeating DOM-primary, clobbering the operator clipboard, and likely failing on CDP clipboard permissions. `truncation_marker` is an OPTIONAL truncation guard, not required for reading the body.
- **GAP-8 — `src/ask_chatgpt/patch.py` `_scan_download_artifacts` (~line 307) + `retrieve_patch_bundle` (~line 208):** the scan does `links = turn.locator(selectors.selector("download_artifact"))`; with `download_artifact=""` the `selector()` raises `SelectorUnavailableError`, caught at ~line 311-312 and re-raised as `DownloadUnsupportedError`. `retrieve_patch_bundle` calls the scan at ~line 208 OUTSIDE any try/except, so `DownloadUnsupportedError` PROPAGATES and the fenced base64 fallback (~line 228-249) is NEVER reached. UC2 cannot retrieve a bundle. Intended real behavior: download-primary is disabled (no real Download event) → use the fenced fallback.

## Files to READ FIRST (ground truth; verify line numbers)
- `src/ask_chatgpt/readers.py` (whole file, ~128 lines): `DomReader.read` lines 31-58 (note assistant_message+message_body are REQUIRED and stay required; truncation is optional); `read_response` lines 90-108 (falls through only on `SelectorUnavailableError`).
- `src/ask_chatgpt/patch.py`: `retrieve_patch_bundle` lines ~186-256 (scan at 208 outside try; fenced fallback at 228-249; terminal `DownloadUnsupportedError` at 251-255); `_scan_download_artifacts` lines ~301-350 (turn_id attr at 303 [populated, keep], download_artifact selector at 307, the `(PlaywrightError, SelectorUnavailableError) -> DownloadUnsupportedError` catch at 311-312, the metadata `PatchMalformedError` checks at 319-336 [keep], the `_turn_has_selector` helper at 353-357 which already swallows PlaywrightError).
- `src/ask_chatgpt/driver.py`: ALREADY fixed in T2d (`_present` soft + `_optional_selector` helper + truncation guard). Do NOT re-touch driver.py unless your audit (below) finds a NEW unconditional empty-optional access in a UC1-3 path that T2d missed; if so, fix it with the same pattern and call it out.
- `src/ask_chatgpt/selector_map.py` (~29-39): `selector()`/`attribute()` fail-closed on empty — do NOT change.
- `src/ask_chatgpt/selector_maps/real.json` (the empty keys above) and `mock.json` (these keys ARE populated → mock behavior must stay identical). `tests/test_readers*.py`, `tests/test_patch*.py` — match style; keep all green.

## Deliverables (TDD/RED-first)

### D1 — GAP-7: `DomReader` truncation check optional
In `readers.py` `DomReader.read`, make the `truncation_marker` lookup tolerant: resolve it inside a `try/except SelectorUnavailableError: truncation_selector = None` (or reuse a helper), and only run the truncation check (`turn_locator.locator(truncation_selector).count() > 0 → ResponseTruncatedError`) when `truncation_selector is not None`. `assistant_message` and `message_body` STAY required (unchanged). Net effect: on the real map DomReader reads `message_body` via DOM (DOM-primary preserved); on the mock map (truncation populated) truncation detection is unchanged.

### D2 — GAP-8: download-scan tolerates an unmapped `download_artifact` → fenced fallback
In `patch.py` `_scan_download_artifacts`, when `download_artifact` is UNMAPPED/empty (`selector("download_artifact")` raises `SelectorUnavailableError`), treat it as "no download affordance configured" → return a `_DownloadScan` with `candidate=None` (and `unsupported=False`, `stale_artifact_seen=False`, `delayed=False`) so `retrieve_patch_bundle` proceeds to the fenced fallback. Keep ALL existing behavior when `download_artifact` IS mapped: a real PlaywrightError still maps as today; the metadata `PatchMalformedError` checks stay; the turn_id attribute read stays. Do NOT change `retrieve_patch_bundle`'s terminal `DownloadUnsupportedError` (lines ~251-255) — that correctly fires only when BOTH download and fenced are absent.
- Distinguish: an UNMAPPED download selector (→ no candidate, go fenced) vs a genuine Playwright failure on a mapped selector (→ keep current `DownloadUnsupportedError`). The cleanest implementation: resolve the selector first via a guarded lookup; if unmapped, set count=0/no links and skip to the delayed/unsupported markers + return no-candidate.

### D3 — Comprehensive audit (prevent the next whack-a-mole)
Grep ALL of `src/ask_chatgpt/*.py` for `.selector("..")` and `.attribute("..")`. For EACH call, classify the key as REQUIRED (must stay fail-closed) or OPTIONAL marker, and whether it is reachable in a UC1-3 happy path (open→select_model(None)→[upload]→send→wait_for_completion→read→[retrieve_patch_bundle]). For any UNCONDITIONAL access to an OPTIONAL key that is EMPTY in real.json AND reachable in that path, apply the same "treat unmapped as absent/skip" fix and list it in your report. KNOWN-OK / DO NOT CHANGE: `model_menu`/`model_option`/`model_option_disabled` are accessed ONLY in `select_model`, which is a no-op unless `model_settings` requests a model — their fail-closed raise is the INTENDED behavior (the real run never passes model_settings on the happy path); leave them. Required selectors (`ready_root`,`composer`,`send_button`,`new_chat_button`,`assistant_message`,`message_body`,`completion_marker`,`copy_button`,`upload_input`) stay fail-closed.

### D4 — Tests (DEFAULT-TIER; mock/loopback/unit; NOT real_site; RED-first)
- GAP-7: a `DomReader.read` test with a selector map whose `truncation_marker=""` (real-like) but `assistant_message`/`message_body` populated, against a fake/loopback turn, returns the body text WITHOUT raising and WITHOUT needing the copy fallback. Keep a test that truncation IS detected when the marker is mapped + present (mock-like).
- GAP-8: a `retrieve_patch_bundle` (or `_scan_download_artifacts`) test with `download_artifact=""` and a turn whose text contains a valid fenced bundle → returns the fenced bundle (reaches fenced; does NOT raise `DownloadUnsupportedError` from the scan). Keep existing download-primary tests (mapped selector) green.
- All existing tests stay green; the mock UC1/UC2 happy paths unchanged.

### D5 — Suite green + tier purity + scope
- `uv sync --all-groups`; run the FULL default suite ONCE (serialize): `uv run pytest`. MUST be GREEN; expect >= the prior 151 passed. Capture the summary line.
- Clean run collects ZERO `real_site`; socket guard + `mock.json` + `real.json` UNCHANGED (you do NOT edit real.json/mock.json in this leg).
- `git diff --stat` touches ONLY `src/ask_chatgpt/readers.py`, `src/ask_chatgpt/patch.py` (and driver.py ONLY if your audit found a new genuine gap — call it out), plus your new/edited tests. NOT real.json, NOT mock.json, NOT conftest, NOT selector_map.py, NOT api.py/cli.py.

## SAFETY BLOCK — obey verbatim (you inherit nothing)
- ZERO real-site contact. Mock/loopback/unit only. Socket guard NEVER weakened. Preserve fail-closed for REQUIRED selectors; only OPTIONAL unmapped markers become non-blocking.
- Never read/copy/store/log credentials, cookies, tokens, profile contents. No account identifiers anywhere.
- Write ONLY inside `/home/abhmul/dev/ask-chatgpt`. Archive READ-ONLY. Never write `.claude/`/`.agents/`. Never touch the shared agent venv. `uv sync --all-groups` ALWAYS. Serialize pytest. NEVER `git push`. Do NOT `git commit`.
- ESTIMATE BEFORE EXECUTE.

## Reporting (write to `orchestration/reports/M-006/T2e.md`, cap ~250 lines)
1. `START_TIMESTAMP:`/`END_TIMESTAMP:` + `ESTIMATE: T2e <min>m`.
2. The GAP-7 + GAP-8 changes (final line numbers) + RED→GREEN evidence + the D3 audit table (every `.selector()/.attribute()` access, classified, and whether changed).
3. Authoritative `uv run pytest` summary + ZERO real_site + socket guard/mock.json/real.json unchanged.
4. `git diff --stat` (prove scope).
5. `MESSAGES_USED: 0`.
- LAST LINE: `T2e-STATUS: DONE` (or `T2e-STATUS: BLOCKED` + precise blocker).
