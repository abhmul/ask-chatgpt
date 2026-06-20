# M9 · W1 — Wire outgoing file upload (fix the silent-no-op stub) + falsifiable test (OFFLINE)

You are a **pi worker** (single source editor) for the `ask-chatgpt-dev` team, on branch **`rewrite-v2`** in repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. Do exactly this task, then write the handoff named at the end. **This is an OFFLINE task — do NOT touch chatgpt.com, the browser, or CDP.**

## Why (the bug — M8 found it)
`ask --attach FILE` / `Session.ask(..., attach=[...])` currently **sends the prompt WITHOUT uploading the file, silently** — no error, no test pins it. This is the "silent no-op" class the v2 rewrite exists to kill. Root cause: `src/ask_chatgpt/send.py` `upload_attachments` (lines ~91–114) does `del tab, selectors` and only builds `AttachmentRef` metadata — it **never calls `tab.channel.upload_files`**. Your job: make the attach path **actually upload** (and **fail-closed** if it can't confirm the upload), with a **falsifiable** test.

## Ground truth you must rely on (verified by the manager — re-verify by reading the files)
- `CdpChannel.upload_files` **already exists** at `src/ask_chatgpt/channels/cdp.py:841` →
  `def upload_files(self, tab, selector, paths): state=self._validate_tab_state(tab); state.page.set_input_files(selector, [str(p) for p in paths])`. **Do not rewrite it.**
- `MockChannel.upload_files` **already exists** at `src/ask_chatgpt/channels/mock.py:475` — it **records** a `MockCall(method="upload_files", selector=..., file_count=...)` and increments `counters["upload_files"]`. So a test can assert it was invoked with the right selector + count.
- `BrowserChannel.upload_files(tab, selector, paths)` is in the Protocol (`channels/base.py:100`). Good.
- **Selector-loader gotcha (CRITICAL):** `src/ask_chatgpt/selectors/__init__.py` `_validate_selector_map` returns `{key: ... for key in REQUIRED_SELECTOR_KEYS}` — it **projects ONLY `REQUIRED_SELECTOR_KEYS`**. A new key added to `real.json` alone is **silently dropped**. You MUST add your new key(s) to **all three**: `REQUIRED_SELECTOR_KEYS` (`selectors/__init__.py`), the `SelectorMap` TypedDict (`src/ask_chatgpt/models.py:204`), and `real.json`.
- The production send path is `Session._run_send_turn` (`src/ask_chatgpt/session.py:381`), which at line ~409 calls `upload_attachments(tab, self.selector_map, _attachment_specs(attach))` **before** `fill_composer`/`submit_composer`. Keep that ordering (upload BEFORE submit).
- `AttachmentSpec` = `models.py:226` (`path: Path`, `display_name: str|None`, `mime: str|None`). `AttachmentRef` = `models.py:82`.
- Error base class: `_KnownAskChatGPTError` in `src/ask_chatgpt/errors.py` (existing siblings: `SelectorNotFoundError`, `PromptNotSubmittedError`, `AttachmentNotFoundError`, `AttachmentFetchError`). There is **no** outgoing-upload error yet.

## WORKER PYTHON GOTCHA (read or you will waste a cycle)
Bare `python`/`python3` in this harness resolves to a **shared agent-python venv that does NOT have playwright or ask_chatgpt installed**. For ALL project work use **`uv run`** (the repo's own venv): `uv run pytest`, `uv run python -c ...`. Never bare `python`.

## What to implement (the wire + fail-closed guard)
1. **New selector keys.** Add to `REQUIRED_SELECTOR_KEYS`, the `SelectorMap` TypedDict, and `src/ask_chatgpt/selectors/real.json`:
   - `"file_input"`: hypothesis value **`"input[type=\"file\"]"`** (standard chatgpt.com composer file input; the existing `test_cdp_channel.py:567` already uses `input[type=file]`). A later real-leg worker (W2) confirms/corrects this; wire it now with the hypothesis.
   - `"attachment_chip"`: hypothesis value **`"[data-testid=\"composer-attachment\"], div[data-testid*=\"attachment\"], button[aria-label*=\"Remove\" i]"`** — a composer attachment-preview/chip indicator. W2 will confirm/correct the real value. Pick a reasonable fail-closed multi-candidate selector; it only needs to match the staged-attachment chip in the composer.
2. **Rewrite `send.py:upload_attachments`** so that, after validating each file exists and building the `AttachmentRef`s, **if there are any files** it:
   - calls `tab.channel.upload_files(tab, selectors["file_input"], paths)` (the real `set_input_files`), then
   - **waits for the attachment chip to appear** (poll `tab.channel.wait_for_selector(tab, selectors["attachment_chip"], state="visible", timeout_s=...)` or an evaluate-based presence poll) up to a **bounded timeout** (use a module constant, e.g. `_ATTACHMENT_CHIP_TIMEOUT_S = 30.0`, poll ~0.25–0.5s). Use the channel's `_monotonic`/`_sleep_until` helpers already in `send.py` for the poll loop so the ScriptedClock-based mock tests stay deterministic.
   - **Fail-closed:** if the chip never appears within the timeout, **raise a named, credential-free error** — add `AttachmentUploadError(_KnownAskChatGPTError)` to `errors.py` (with a stable `code`, mirroring the existing siblings) and raise it (e.g. `"attachment upload was not confirmed (no composer attachment chip appeared)"`, details = `{"file_count": n}` — NEVER include file contents or paths beyond basename). **Attach must NEVER silently no-op:** either the upload is confirmed by a chip, or it raises. Keep returning the `tuple[AttachmentRef, ...]` on success.
   - Keep the existing `FileNotFoundError` for a missing local file.
3. Keep `_run_send_turn`'s call site (`session.py:409`) working (signature unchanged: `upload_attachments(tab, selectors, files) -> tuple[AttachmentRef,...]`).

## Falsifiable tests (REQUIRED — both must flip to RED when the wire is reverted)
Add tests (reuse the existing harness — `tests/test_session_draft_loop.py` has a working draft-`ask` mock scenario via its `_session`/`_scenario` helpers + `MockChannel`; `tests/test_send_completion.py` exercises `send_prompt`; `tests/mock_scenarios.py` has fixtures). Choose the cleanest home. You MUST add:
1. **Upload-happens (production path):** drive the real send path (`Session.ask(None, prompt, attach=[a_tmp_file])` against a mock scenario where the attachment chip selector is present, OR `send_prompt(..., attach=[spec])`) and assert the **mock recorded an `upload_files` call** with `selector == selectors["file_input"]` and `file_count == 1` (inspect `channel.calls` / `channel.method_counts["upload_files"]`). **Revert the wire (restore `del tab, selectors`) → this test MUST fail.** Verify that yourself: temporarily revert, `uv run pytest -k <yourtest>` → RED, then restore.
2. **Fail-closed (no silent no-op):** a scenario where the chip selector is **absent** after upload → `upload_attachments` / `ask(attach=...)` **raises `AttachmentUploadError`** (NOT a silent success, NOT a generic crash). Assert the raise. This pins the "never silently no-op" guarantee.
   - For the mock: chip presence is controlled by `MockScenario.selector_presence` / `selector_timeline` (see `mock.py` `_selector_present`, and note `wait_for_selector` raises `SelectorNotFoundError` when a selector is absent — your fail-closed code should treat absence-until-timeout as the failure and raise `AttachmentUploadError`).
3. Do NOT weaken any existing test. Existing `test_cdp_channel.py` upload_files tests + `test_session_stubs.py:108` (which monkeypatches `upload_attachments`) must still pass — check them.

## Acceptance (you must verify, not assume)
- `uv run pytest` → all green (baseline was **254 passed**; you will add tests, so expect 254 + your new count). Capture the tail to `team/evidence/reports/M9-W1-pytest.txt`.
- Both falsifiability checks personally demonstrated: revert wire → upload-happens test RED; remove chip-wait/raise → fail-closed test RED. Restore and re-run green. Report the exact RED test output lines.
- `git status --porcelain` shows ONLY your intended `src/` + `tests/` changes (+ the report you wrote). Do **NOT** stage/commit (the manager commits). Do **NOT** create/modify anything under `cache/`, `archive/`, `human/`, or `issues/cdp-send-repro/controller.mjs`.

## Safety / isolation (hard rules)
- OFFLINE only. No chatgpt.com, no browser, no CDP, no network sends.
- Branch `rewrite-v2` only. **NEVER** move/commit/checkout `stable`. **NEVER** run `uv tool install/upgrade/reinstall`. **NEVER** `git push`. Do not `git commit` at all (manager commits).
- Never write secrets/credentials/conversation content anywhere.

## Handoff (write this file, then stop)
Write `team/evidence/handoffs/M9-W1-upload-wire.md` with, in order:
1. **Status:** `DONE` / `PARTIAL` / `BLOCKED` (single token, top).
2. **What you changed** — exact files + line ranges (send.py upload wire, errors.py new class, models.py SelectorMap, selectors/__init__.py REQUIRED_SELECTOR_KEYS, real.json, the test file(s)).
3. **Falsifiability evidence** — the exact `uv run pytest -k` RED output when you reverted the wire, and the RED output when you removed the chip-wait/raise, plus the green full-suite tail (count + exit). Re-derived from the captured `M9-W1-pytest.txt`, not memory.
4. **The selector values you used** for `file_input` + `attachment_chip` (so W2 can confirm/correct against the live DOM).
5. **Artifacts** + trust level; **Blockers** (exact action needed); **Recommended next**.
Keep it credential-free and factual. Do not report success you did not observe in the captured output file.
