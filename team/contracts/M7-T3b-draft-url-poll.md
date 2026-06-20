# Contract M7-T3b — OFFLINE fix: poll post-submit URL for /c/<id> (draft SPA-navigation latency)

You are the **single OFFLINE pi EDITOR worker** for `ask-chatgpt-dev`, task **M7-T3b**. Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**. You inherit **nothing** but this contract and the files it names. **First read and obey** `.claude/skills/manager/references/agent-rigor.md` and the `tdd` skill. **OFFLINE** only — no browser/CDP/network. Build on committed `rewrite-v2` (`uv run pytest` = 246 passed).

## Why (a REAL leg found this)
The first real draft send was attempted live. The send itself WORKED (gotcha-4 passed: a new user turn appeared, `send_budget.successful_submissions == 1`), but `Session.ask(None, ...)` then raised a bare `InternalError` and learned no `/c/<id>`. Root cause (confirmed in source): `Session._learn_post_submit_ref` (`src/ask_chatgpt/session.py:457-476`) reads the post-submit URL **exactly once** (`tab.channel.evaluate(tab, "ask_chatgpt_current_url", ...)`, line 458) and immediately raises `InternalError` (lines 460/463) if it is not yet `/c/<id>`. On the real SPA the navigation `https://chatgpt.com/` → `https://chatgpt.com/c/<id>` **lags the submit**, so a single immediate read sees the pre-navigation URL. The mock returns the final URL instantly, so offline tests never exercised the latency. This is the same single-read-vs-poll shape that T2b already fixed for model labels.

## Fix — poll the post-submit URL until /c/<id> appears (bounded, channel clock)
Rewrite `_learn_post_submit_ref` to **poll** `ask_chatgpt_current_url` until `parse_conversation_address(value)` yields a `conversation_id`, OR a bounded deadline elapses. Mirror the existing channel-clock wait helpers in `src/ask_chatgpt/send.py` (`_monotonic(tab)` / `_sleep_until(tab, target)`) — **NEVER** real `time.sleep`, so offline tests stay fast (<3s) under `ScriptedClock`.
- Use a bounded window (reuse `self.send_verify_timeout_s`, or add a dedicated `draft_url_learn_timeout_s` defaulting to ~15s) with a poll interval ~0.5s.
- On success: keep the existing project-id check and return the same `ConversationRef(...)` (lines 466-476) unchanged.
- On timeout (URL never became `/c/<id>`): fail closed with a CLEAR error including the elapsed window and the LAST observed URL **only if it is same-origin chatgpt.com and contains no secrets** — to be safe, include only a boolean `saw_url`/the attempt count in `details`, NOT the raw URL (it could contain query params). Keep it `InternalError` (or `PromptNotSubmittedError`) with a descriptive message like `"post-submit URL did not navigate to /c/<id> within {N}s"`.
- Keep `_run_send_turn` semantics otherwise identical (gotcha-4 before id-learning; eager-write after).

## Mock support
The `MockChannel`/`MockScenario` currently return a single `current_url` (`src/ask_chatgpt/channels/mock.py:325-327`, scenario field `current_url`). Add the ability to script a **sequence** of `current_url` values consumed one per read (e.g. `current_url_sequence: tuple[str, ...]` consumed in order, falling back to `current_url` once exhausted), and keep the existing `counters["current_url_reads"]` increment. This lets a test simulate the SPA navigating after K reads.

## Falsifiable tests (each MUST be able to fail) — in `tests/test_session_draft_loop.py`
- `draft_url_poll_tolerates_spa_navigation_latency`: scenario scripts `current_url` = `["https://chatgpt.com/", "https://chatgpt.com/", "https://chatgpt.com/c/learned-xyz"]`; `ask(None, ...)` returns a record with `conversation_id == "learned-xyz"`, transcript written under it, and `counters["current_url_reads"] >= 3`. A single-read implementation would raise `InternalError` — proving the test bites.
- `draft_url_poll_fails_closed_when_never_navigates`: every `current_url` read stays `https://chatgpt.com/` for the whole window → fail-closed raise (no transcript under any id; assert no conversations dir written). Assert it polled more than once (`current_url_reads > 1`) so a degenerate one-shot can't pass.
- Keep the existing draft happy-path / gotcha-4 / bogus-id tests green (the happy path may now need its `current_url` available across the poll — adjust the scenario, not the assertion).

## Safety / isolation (HARD RULES)
- Branch `rewrite-v2` only. NEVER move/commit/merge `stable`; NEVER `uv tool install/upgrade/reinstall` (use `uv run`/`uv sync`); NEVER `git push`.
- OFFLINE: no browser/CDP/network/real sends. Suite green AND <3s; NO real `time.sleep` — channel-clock waits only.
- NEVER edit/stage `issues/cdp-send-repro/controller.mjs` or `human/`; never stage `cache/`, `.pi-workers/`, `team/state/*-manager-state.json`. Commit explicit paths (never `git add -A`), NO `Co-Authored-By`.
- No auth/OAI/cookie/bearer/prompt/response values (mock canaries only). Do NOT log raw URLs that could carry query params.

## Commit + handoff
Commit the green increment(s) (explicit paths: `session.py`, `channels/mock.py`, `tests/test_session_draft_loop.py`) → `git commit -m "M7-T3b: poll post-submit URL for draft conversation id"`. Confirm `controller.mjs`/`human/` unstaged.
Write `team/evidence/reports/M7-T3b.md`: status token; `uv run pytest` tail (N passed, seconds — expect > 246); commit hash + one-liner; the new tests' falsifiability (how each can fail); confirmation no real `time.sleep`; confirmation `controller.mjs`/`human/` unstaged. No secrets. If low on budget: commit green work, resume-ready PARTIAL, stop.
