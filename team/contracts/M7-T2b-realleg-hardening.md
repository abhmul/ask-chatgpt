# Contract M7-T2b — OFFLINE real-leg hardening (sustained model read + submit settle + 2 falsifiability tests)

You are the **single OFFLINE pi EDITOR worker** for `ask-chatgpt-dev`, task **M7-T2b**. Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**. You inherit **nothing** but this contract and the files it names. **First read and obey** `.claude/skills/manager/references/agent-rigor.md` and the `tdd` skill (`.claude/skills/tdd/SKILL.md`). This is **OFFLINE** work — no browser/CDP/network/real sends — mock-proven only. Build on the current committed `rewrite-v2` (HEAD includes T1a+T1b; `uv run pytest` = 240 passed).

## Why (a 3-lens verify panel found these BEFORE the first real sends)
The next mission task drives the LIVE ChatGPT UI (scarce real sends on a shared account). A code-reading fidelity panel (vs the REAL-PROVEN `issues/cdp-send-repro/controller.mjs`) found two production gaps that would likely cause **false-failures on real legs**, plus two test-quality gaps. Fix all four, TDD, mock-proven, suite staying green + fast (<3s, no real `time.sleep` — drive timing via the channel's injected clock, the `ScriptedClock` seam).

## READ FIRST
- `.claude/skills/manager/references/agent-rigor.md`, `.claude/skills/tdd/SKILL.md`.
- `src/ask_chatgpt/menus.py` (`_reflected_model` @248-254, `_require_unambiguous_model_trigger` @235-245, `select_model`, `set_tools`).
- `src/ask_chatgpt/send.py` (`submit_composer` @124-125, `wait_for_composer` @66-83, `fill_composer` @112-121).
- `src/ask_chatgpt/channels/base.py` (`BrowserChannel` Protocol; `TurnDomSnapshot.model_labels`; how `monotonic`/`sleep`/`query_turns`/`click`/`wait_for_selector` are scripted), `src/ask_chatgpt/channels/mock.py` (the `MockChannel` you will extend to script SEQUENCES), `src/ask_chatgpt/channels/cdp.py` (the real `query_turns`/`click` — for context; the sustained read lives in `menus.py`, channel-agnostic).
- `src/ask_chatgpt/selectors/real.json` (`send_button_unverified_no_input`, `composer`).
- `issues/cdp-send-repro/controller.mjs` (READ-ONLY reference: `confirmViolation` does 6 reads × `sleep(2000)` tolerating a transient `Extra High`; it waits for the composer/send-button to settle before clicking). **Never edit or stage `controller.mjs`.**

## FIX 1 — Sustained (poll-until-settled) model-label read [the #1 real-leg risk]
`_reflected_model` and `_require_unambiguous_model_trigger` each read `tab.channel.query_turns(tab, selectors).model_labels` **once**. On reload/hydration the composer model button **transiently shows `Extra High`** before settling (documented live-site behavior), so a single read can FALSE-FAIL model verification right after the pipeline's reload. Make both reads **sustained**, mirroring `controller.mjs` `confirmViolation`:
- Add a helper (e.g. `_sustained_model_labels(tab, selectors, *, want: str|None, attempts: int = 6, interval_s: float = 2.0)`) that polls `query_turns(...).model_labels` up to `attempts` times spaced by `interval_s`, **sleeping via the channel clock** (`tab.channel.sleep`/`monotonic` exactly as `send.py:_monotonic`/`_sleep_until` do — NEVER real `time.sleep`).
- `_reflected_model`: SUCCEED as soon as the requested label appears in a sample (transient resolves); return `None` (→ `ModelSelectionNotReflectedError`) only if the requested label is **never** reflected across the whole window (sustained absence).
- `_require_unambiguous_model_trigger`: tolerate transient hydration — poll until **exactly one** normalized model label is present; fail (absent/ambiguous) only if that never holds within the window.
- Keep all existing behavior otherwise; `select_model`/`set_tools`/fail-closed semantics unchanged. The window must collapse to ~instant under `ScriptedClock` so the suite stays <3s.

**Falsifiable tests (each must be able to fail):**
- `sustained_tolerates_transient`: MockChannel scripts `model_labels` = [`Extra High`] (or wrong) for the first K reads then the requested label; `select_model` returns `verified=True`. A single-read implementation would raise — proving the test bites.
- `sustained_absence_fails_closed`: every sample is the wrong label for the full window → `ModelSelectionNotReflectedError` (nothing further selected/sent). Assert the channel was sampled multiple times (e.g. a read-count seam) so a degenerate one-shot can't pass.
- `trigger_tolerates_transient_then_unambiguous`: trigger read is briefly 0/ambiguous then settles to exactly one → no raise.

## FIX 2 — Settle before send click (wait for visible+ENABLED send button, bounded retry)
`submit_composer` calls `tab.channel.click(...)` immediately; `CdpChannel.click` raises if there is no visible+**enabled** button, so an async enable-gap after fill can hard-fail a real send. Make `submit_composer` **wait (bounded, channel-clock) for the send button to be visible+enabled, then click, with a small retry** (mirror controller.mjs's pre-click settle). Use the existing `wait_for_selector(..., state="visible")` plus an enabled check, or a short poll. Keep gotcha-4 (`verify_prompt_submitted`) as the fail-closed net unchanged.

**Falsifiable tests:**
- `submit_waits_for_enabled_button`: MockChannel scripts the send button disabled for the first K polls then enabled → `submit_composer` succeeds (clicks once enabled). A no-wait implementation would raise/click-while-disabled — proving the test bites.
- `submit_fails_closed_if_never_enabled`: button never enables within the window → a clear raise (no silent no-op). Assert it polled more than once.

## FIX 3 — Send-button selector fallback (cheap real-leg robustness)
In `src/ask_chatgpt/selectors/real.json`, append `, button[aria-label="Send prompt"]` to `send_button_unverified_no_input` (controller.mjs uses that aria-label as a real fallback). Confirm `tests/` selector-map tests still pass (adjust expected string if a test pins it). No behavior change beyond selector coverage.

## FIX 4 — Two missing falsifiability tests (the panel's L2 findings)
- **Tool not-reflected negative test** (in `tests/test_menus.py`): a scenario where a tool (e.g. `Web search`) is **clicked but its `checked` never becomes True** → expect `ToolSelectionNotReflectedError` and assert the click WAS recorded (`menu_clicks` contains the tool). Without this, a broken `set_tools` that trusts click-success without checked-state reflection would pass. (Model already has this; tools did not.)
- **Strengthen the draft bogus-id assertion** (in `tests/test_session_draft_loop.py`, the `post_submit_url_has_no_conversation_id` test ~line 150-163): in addition to "no `learned-123` transcript", assert **no conversations directory / no `transcript.jsonl` is written anywhere** under the temp data dir (e.g. `assert not (data_dir / "conversations").exists()` or zero transcript files), so a write under ANY bogus id is caught.

## Safety / isolation (HARD RULES)
- Branch `rewrite-v2` only. NEVER checkout/commit/merge/move `stable`. NEVER `uv tool install/upgrade/reinstall` (use `uv run`/`uv sync`). NEVER `git push`.
- OFFLINE: no browser/CDP/network/real sends. Suite stays green AND <3s; NEVER introduce real `time.sleep` — drive all new waits via the channel clock seam.
- NEVER edit or stage `issues/cdp-send-repro/controller.mjs` or `human/`; never stage `cache/`, `.pi-workers/`, `team/state/*-manager-state.json`. Commit with EXPLICIT paths (never `git add -A`), NO `Co-Authored-By`.
- No auth/OAI/cookie/bearer/prompt/response values anywhere (mock canaries only).

## Commit policy
Sole editor. Suggested increments (commit each green, explicit paths): (1) FIX 1 sustained read + tests; (2) FIX 2 submit settle + tests; (3) FIX 3 selector + FIX 4 two tests. After each: `uv run pytest` green → `git add <explicit files>` → `git commit -m "M7-T2b: <area>"`. Confirm `controller.mjs`/`human/` stay unstaged.

## Success criteria
- Sustained model read tolerates the transient `Extra High` and fails closed only on sustained absence; submit waits for an enabled send button with bounded retry; selector fallback added; the two new falsifiability tests exist and genuinely bite. `uv run pytest` green (offline, <3s). `stable` unmoved. Increments committed (explicit paths). No real `time.sleep` introduced.

## Handoff — write `team/evidence/reports/M7-T2b.md`
Status token at top (DONE/PARTIAL/BLOCKED); `uv run pytest` tail (N passed, seconds — expect > 240); commit hashes + one-liners; files changed; for EACH new test the behavior it pins + exactly how it could fail (falsifiability); confirmation no real `time.sleep` was added (new waits use the channel clock); confirmation `controller.mjs`/`human/` unstaged; blockers; complexity signals. No secrets/real content. If low on budget: commit green work, write resume-ready PARTIAL, stop.
