# `--channel cdp` against an already-complete session: prompt is silently NOT sent, stale prior response returned as success (exit 0)

**Date:** 2026-06-18
**Severity:** High
(Any loop/automation that re-sends into an existing conversation can report success on every iteration while never actually sending a new turn. Silent — no error, exit 0, plausible-looking output.)

**Repo state at filing:** HEAD `bf208d8`. Note `src/ask_chatgpt/driver.py` is **dirty in the working tree** (uncommitted edits by another developer + a prior agent's `model_settings` experiment), so the line numbers below are against the current working tree and may drift; method names are stable references.

---

## Summary

Calling `ask-chatgpt --channel cdp --session <id> '<prompt>'` against a conversation whose **latest turn is an already-complete assistant response** returns the **verbatim text of that pre-existing response** and exits 0 — **without ever submitting the new prompt**. No new user turn is created in the DOM.

This is the "false positive" described in `tmp/weak-simplex-push/HANDOFF_TO_CLAUDE.md` and is consistent with `issues/2026-06-14-response-truncated-drops-out-file-and-session.md`. It was previously attributed to "model-menu hydration"; this issue pins it to two compounding defects in `driver.py` and backs it with a falsifiable CDP repro.

---

## Environment

- Binary: `~/.local/bin/ask-chatgpt` (pinned stable build on PATH; decoupled from the working-tree source)
- Channel: `--channel cdp --cdp-endpoint http://127.0.0.1:9222` (operator Chromium, signed in)
- Session: `weak-simplex-conjecture` → `https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31`, model `Pro Extended`
- The target conversation was **idle** (last turn a completed assistant response; stop control absent; global copy button present).

---

## Exact command

```bash
ask-chatgpt --channel cdp --cdp-endpoint http://127.0.0.1:9222 \
  --session weak-simplex-conjecture --timeout 2400 'keep pushing!!'
```

## Observed (falsifiable evidence)

A CDP probe captured the latest **user** turn's `data-message-id` immediately before and ~20 s after the call:

```
BEFORE: {"userCount":3,"latestUserId":"ed186661-6ff8-4780-b6da-2a94a5ed61d0","stop":false}
AFTER : {"userCount":3,"latestUserId":"ed186661-6ff8-4780-b6da-2a94a5ed61d0","stop":false}
```

- **Latest user-turn id is unchanged** → no new user turn was ever added.
- Only **one** tab for the conversation (ruled out a stray new-tab submission).
- The call **exited 0 in ~20 s** (not the 2400 s wait), and its **stdout was the verbatim existing assistant response** (the prior "Generalized-inertia independentization theorem" reply already visible in the UI).
- stderr only contained benign `Blocked real-channel request outside allowlist: scheme=https host=www.google.com` lines.

**Expected:** a new user turn `keep pushing!!` is submitted, a fresh assistant response generates, and that *new* response is returned (or a clear error if submission failed).
**Actual:** nothing is submitted; the old response is returned as success.

---

## Root cause (two compounding defects)

The `api.py` flow is correct in shape (`open_or_create_conversation` → `select_model` → `send_prompt` → `wait_for_completion` → `read_response`). Both defects are in `driver.py`.

### Defect 1 — `send_prompt` never verifies a turn was submitted

`_send_prompt_real_mechanics` (driver.py ~333–368) clicks the composer, fills text, tries the send button, and falls back to `Enter`, tracking a local `submitted` bool. It **never confirms a new user turn actually appeared** in the DOM. If the composer is in a transient/re-rendering state (common right after a turn completes — the composer and toolbar re-mount during the "Stopped thinking" → idle transition), the fill/click/Enter can silently no-op and the method returns **without error**.

### Defect 2 — `wait_for_completion` has no "new turn" baseline; returns the stale turn

`wait_for_completion` (driver.py ~370+) returns `latest_assistant` via (line ~458):

```python
if stop_absent_stable and (streaming_seen or bool(last_text)):
    return latest_assistant
```

The `bool(last_text)` "never-saw-streaming" branch (the M-009 ultra-fast-reply / second-wait path) fires here: when no prompt was actually submitted, the latest assistant turn is the **pre-existing completed one** (non-empty body), the streaming marker is absent, and the **global** `completion_marker` (copy button, intentionally matched outside the turn per the M-008b note at line ~434) is present. So `stop_absent_stable` becomes true and the method returns the **old** turn. There is no captured baseline (latest user/assistant `data-message-id` before send) requiring the returned turn to be *newer* than what existed pre-send.

Net: a no-op send (Defect 1) + a pre-existing complete response (Defect 2) ⇒ instant, silent false "success".

---

## Repro steps (minimal)

1. In the operator browser, open any conversation and let a response finish (idle: no stop button, copy button visible).
2. Register/point a `--session` at it.
3. `ask-chatgpt --channel cdp --cdp-endpoint http://127.0.0.1:9222 --session <id> 'ping'`.
4. Observe: exit 0; stdout is the *previous* response; the conversation has **no** new `ping` user turn (check the latest `[data-message-author-role="user"]` `data-message-id` before/after).

---

## Suggested fix direction

1. **Post-send submission guard (Defect 1):** before submitting, capture the latest user-turn `data-message-id` (or user-turn count). After submit, poll briefly (e.g. ≤10 s) for a **new** user turn carrying the prompt; if none appears, raise a distinct `PromptNotSubmittedError` (composer was not in a submittable state) instead of returning. This alone converts the silent failure into a loud, retryable one.
2. **New-turn baseline in `wait_for_completion` (Defect 2):** accept a `since_assistant_id` / baseline captured before `send_prompt`, and require the returned `latest_assistant` to be **newer** than baseline (different `data-message-id`) — OR that `streaming_seen` is true. This prevents the `bool(last_text)` path from ever returning a stale completed turn. The global-completion-marker fallback stays, but is gated on "a new turn exists."
3. **Tie them together in `api.py`:** capture the baseline ids right before `send_prompt`, pass them into `wait_for_completion`, so "did we send?" and "did a new response complete?" are both verified.

---

## Working CDP reference (how reliable sending + verification looks)

A standalone CDP controller that **does** reliably send is preserved in this repo at `issues/cdp-send-repro/` (the live copies run from gitignored `tmp/weak-simplex-push/`). CDP endpoint: `http://127.0.0.1:9222`.

- `issues/cdp-send-repro/controller.mjs` — persistent CDP loop: attach to the existing tab, **reload when idle** (clears SPA staleness), send `keep pushing!!`, **verify a new user turn id appeared**, wait for completion (stop-absent + text-stable), repeat. Resilient to transient composer/model-label absence.
- `issues/cdp-send-repro/status-probe.mjs` — read-only state probe.
- `issues/cdp-send-repro/README.md` — usage + endpoint notes.

The key correctness move (mirrors fix directions 1–2): the fill targets `#prompt-textarea` via `execCommand('insertText', …)`, then clicks `button[data-testid="send-button"]`, and only counts success when the latest `[data-message-author-role="user"]` `data-message-id` **changes** from the pre-send value:

```js
// after fill + send-button click:
const newUser = after.latestUser.includes(prompt)
  && (after.latestUserId !== before.latestUserId || after.users > before.users);
if (!newUser) throw new Error('message did not appear after send'); // <- the guard the CLI lacks
```

Operator note: the composer transiently un-mounts during turn transitions, so a single instantaneous read of `#prompt-textarea` can miss it — wait/retry for the composer rather than treating absence as fatal, and reload the page when idle between turns to clear accumulated SPA staleness.
