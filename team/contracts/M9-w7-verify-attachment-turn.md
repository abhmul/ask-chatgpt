# M9 · W7 — Make `verify_prompt_submitted` tolerate attachment-bearing user turns (OFFLINE)

You are a **pi worker** (single source editor) for `ask-chatgpt-dev`, branch **`rewrite-v2`**, repo `/home/abhmul/dev/ask-chatgpt`. You **inherit nothing** but this contract and the files it names. **OFFLINE — do NOT touch the browser/CDP/chatgpt.com.** There is **NO further real-leg budget** (the mission's ≤2 real sends are spent), so this fix must be correct + falsifiable purely offline.

## Ground truth from the W6 live leg (re-derive from `team/evidence/handoffs/M9-W6-reverify.md` + `team/evidence/reports/M9-W6-reverify.txt`)
- With the W5 send-enable fix, `ask(attach=[file])` live **DID submit**: each of 2 attempts created a **real new user turn** (`baseline_user_count=0 → last_seen_user_count=1`, real `last_seen_user_id` UUIDs). The attachment + prompt reached chatgpt.com.
- But both attempts then raised **`PromptNotSubmittedError` ("submit did not produce a new user turn carrying the prompt")**. Root cause: `verify_prompt_submitted` (`src/ask_chatgpt/send.py`) requires `normalize_prompt(latest_user.text) == normalized` (EXACT equality). An **attachment-bearing user turn's DOM `innerText` includes the attachment filename/chip** (e.g. `"m9-upload.txt\nReply with only the word: PONG"`), so it never exactly equals the bare prompt → the verifier polls until timeout → `PromptNotSubmittedError`, even though the send succeeded.
- This is a real bug that breaks **every** attachment send. Fix it so attachment sends verify correctly, while keeping the strict guard for normal sends (the gotcha-#2 / silent-no-op protection).

## WORKER PYTHON GOTCHA
Bare `python`/`python3` → shared agent-python venv WITHOUT playwright/ask_chatgpt. Use **`uv run`** (`uv run pytest`).

## What to implement
- In `src/ask_chatgpt/send.py`, make `verify_prompt_submitted` accept a signal that **attachments are present** (e.g. add a keyword-only param `has_attachments: bool = False`, or `match_mode`). When attachments are present, the match condition becomes: a **new** user turn (count increased OR latest id != baseline id) **AND** the normalized prompt is **contained as a substring** of the normalized user-turn text (`normalized in normalize_prompt(latest_user.text)`), rather than exact equality. When there are **no** attachments, keep the existing **exact-equality** match (do NOT weaken the no-attachment path — it guards against matching a stale/wrong turn).
- Thread the flag from the callers:
  - `send_prompt` (`send.py`): pass `has_attachments=bool(attach)` to `verify_prompt_submitted`.
  - `Session._run_send_turn` (`session.py`, the production path, ~line 418 `verify_prompt_submitted(...)`): pass `has_attachments=bool(attachment_specs)` (it already materializes `attachment_specs`).
- Keep it **fail-closed**: if no new user turn appears at all, still raise `PromptNotSubmittedError` (unchanged). The relaxation is ONLY the text-equality→substring change, ONLY when attachments are present. Do not change the no-attachment behavior.
- Keep the returned `SubmittedTurn.normalized_prompt` = the normalized **prompt** (the canonical user record uses it as `content_markdown`); do not substitute the turn's full innerText.

## Falsifiability test (REQUIRED — must flip RED on revert)
Add a test (in `tests/test_send_completion.py` or `tests/test_session_draft_loop.py`) that models an **attachment-bearing user turn whose DOM text is `"<filename>\n<prompt>"`** (prompt as a substring, not the whole text):
- With attachments present, `verify_prompt_submitted` / the production `ask(attach=[...])` **succeeds** (returns the submitted turn / completes), matching by substring.
- **Revert** the substring relaxation (force exact-equality even with attachments) → the test must go **RED** with `PromptNotSubmittedError`. Demonstrate this and paste the `uv run pytest -k` RED output.
- Keep/confirm a no-attachment test still requires exact match (the existing gotcha-#2 no-op/wrong-turn test in `tests/test_send_completion.py` must still pass — verify it does).

## Acceptance
- `uv run pytest` → all green (incoming baseline **264**; you add ≥1 test). Capture tail to `team/evidence/reports/M9-W7-pytest.txt`.
- Falsifiability demonstrated (RED on revert). No existing test weakened (upload-happens, fail-closed-no-chip, send-enable-after-attach, DR chip, family, gotcha-#2 exact-match).
- `git status --porcelain` shows ONLY your intended `src/`+`tests/` changes (+ your report). Do NOT commit. Do NOT touch `cache/`, `archive/`, `human/`, `issues/cdp-send-repro/controller.mjs`.

## Safety / isolation
OFFLINE only. Branch `rewrite-v2`. NEVER move/commit/checkout `stable`; NEVER `uv tool …`; NEVER `git push`; do not `git commit` (manager commits). No secrets/content anywhere.

## Handoff (write, then stop)
Write `team/evidence/handoffs/M9-W7-verify-attachment-turn.md`:
1. **Status** (single token, top).
2. **What changed** — exact files + line ranges (`send.py` verify, `session.py` caller, the test).
3. **Falsifiability evidence** — the RED `uv run pytest -k` output on revert; green full-suite tail (count+exit) from `M9-W7-pytest.txt`.
4. **Artifacts**(+trust); **Blockers**; **Recommended next** (note that live end-to-end capture re-verify is deferred — send budget spent).
Credential-free, factual, re-derived from the captured pytest output.
