# ResponseTruncatedError on long Pro Extended reply: --out file not written, session registry not saved

**Date:** 2026-06-14
**Severity:** Medium-High
(Blocks reliable use of `--session` + `--out` for long-running frontier-math queries; the caller receives no partial output and must re-send the entire prompt.)

---

## Environment

- Binary: `~/.local/bin/ask-chatgpt` (stable build on PATH)
- Channel: `--channel cdp` (operator-launched Chromium at `localhost:9222`, signed in)
- Model: `--model-settings '{"model":"Pro Extended"}'`
- Timeout: `--timeout 3600`
- OS: Linux (Arch), Python 3.x

---

## Exact commands

**Failing first call:**
```bash
ASK_CHATGPT_STATE_DIR=$HOME/wsc-gpt/collar \
  ask-chatgpt \
  --channel cdp \
  --model-settings '{"model":"Pro Extended"}' \
  --timeout 3600 \
  --session wsc4-collar \
  --out /path/to/wsc4-W8-gptpro-collar-raw.md \
  "$(cat /path/to/wsc4-W8-gptpro-collar-prompt.md)"
```

**Retry (succeeded to launch; currently running):**
```bash
ASK_CHATGPT_STATE_DIR=$HOME/wsc-gpt/collar2 \
  ask-chatgpt \
  --channel cdp \
  --model-settings '{"model":"Pro Extended"}' \
  --timeout 3600 \
  --out /path/to/wsc4-W8-gptpro-collar-raw.md \
  "$(cat /path/to/wsc4-W8-gptpro-collar-prompt.md)"
```

The driver changed exactly two things for the retry: dropped `--session wsc4-collar` and used a fresh state dir (`collar2`).

---

## Exact error (recovered from transcript background-task output)

```
ResponseTruncatedError: Assistant response appears incomplete: end marker missing, turn still
in progress, or payload truncated. Operator action: retry, reduce payload size, or inspect
the UI. Detail: completion marker did not appear before timeout
```

Exit code: 7 (per CLI error table). Raised from `driver.py` at the `now >= deadline` branch:
```python
raise ResponseTruncatedError("completion marker did not appear before timeout")
```

The prompt was a long frontier-math elicitation; the Pro Extended model was still generating when `--timeout 3600` (1 hour) was exhausted.

---

## Correction of the original working hypothesis

The incident description hypothesized that `--session <new-name>` against a fresh/empty `ASK_CHATGPT_STATE_DIR` raises `SessionNotFoundError` (exit 4). **This is incorrect.**

Inspecting `session_registry.py` (`_load`, line 72-74): if `sessions.json` does not exist, `_load()` returns `{}` (empty dict) — it does not raise. Inspecting `api.py` (`ask_chatgpt`, lines 52-54): a `session_identifier` with no stored ref simply sets `conversation_ref = None`, which causes `open_or_create_conversation` to start a fresh conversation. So `--session` with a fresh/empty state dir is **not** the cause of the failure; the tool correctly starts a new session in that case.

The actual failure is `ResponseTruncatedError` on timeout — a known error mode — with two compounding problems described below.

---

## Bug 1: --out file not written on ResponseTruncatedError

**Expected:** When `--out FILE` is specified and the call raises `ResponseTruncatedError`, the tool should write whatever partial text it captured to `FILE` (or at minimum note that the file was not written in the error message).

**Actual:** `cli.py` calls `ask_chatgpt(...)` and only writes `--out` on the success path (lines 78-79, 88). When `ask_chatgpt` raises, execution jumps to `_error_exit(exc)` and `--out FILE` is never created. The caller is left with no text output and no file at the `--out` path. Confirmed: `ls collar/` showed empty directory; `wc -l <out-file>` showed `FILE_MISSING`.

**Root cause:** `ResponseTruncatedError` does not carry the partial text that was already rendered in the browser. The exception is raised in `driver.wait_for_completion` before `read_response` is called, so there is nothing to write. Even if partial text were available, the CLI does not attempt a partial write.

---

## Bug 2: Session registry not saved on ResponseTruncatedError

**Expected:** When `--session wsc4-collar` is passed and the call sends the prompt and starts receiving a reply (i.e. a conversation was opened/created), the session registry should be persisted so the caller can resume or retry into the same ChatGPT conversation.

**Actual:** In `api.py` (lines 66-76), `resolved_registry.set(...)` is called only after `wait_for_completion` returns successfully. If `wait_for_completion` raises `ResponseTruncatedError`, the registry write is skipped entirely. The caller loses the conversation reference for the in-flight turn; resuming is impossible without the operator manually finding the conversation URL.

---

## Expected vs. actual (summary)

| | Expected | Actual |
|---|---|---|
| `--out FILE` on timeout | File contains whatever partial text is available, or tool documents the empty-output case | File not created; no output whatsoever |
| `--session` registry on timeout | Conversation ref is saved so caller can resume | Registry not written; state dir left empty |
| `--session` with fresh state dir | New session created (not an error) | Correctly starts new session — **not a bug** |

---

## Repro steps (minimal)

1. Launch Chromium: `chromium --profile-directory='Profile 1' --remote-debugging-port=9222` and sign into chatgpt.com.
2. Run a prompt that will take longer than the timeout to generate (or set `--timeout 1` on a long prompt):
   ```bash
   ASK_CHATGPT_STATE_DIR=/tmp/test-state \
     ask-chatgpt --channel cdp --session test-sess --out /tmp/out.txt --timeout 1 \
     "Write a 10000-word essay on the history of mathematics."
   ```
3. Observe: exit code 7, `/tmp/out.txt` does not exist, `/tmp/test-state/sessions.json` does not exist.

---

## Workaround

**Immediate:** Omit `--session` (the retry did this). This avoids the phantom expectation of resumability but does not recover the partial text. The only way to get the response is to re-send the full prompt and wait again — or for the operator to manually find the conversation in the browser and copy the partial text out.

**If resumability is needed:** The operator can manually locate the ChatGPT conversation URL from the browser and pre-populate `sessions.json` by hand before retrying with `--session`.

There is no workaround for recovering partial `--out` text that was never written.

---

## Suggested fix direction

1. **Partial-text salvage on timeout:** In `driver.wait_for_completion`, before raising `ResponseTruncatedError`, attempt to read whatever text is already visible in the latest assistant turn and attach it to the exception (e.g. `ResponseTruncatedError.partial_text: str | None`). The CLI can then write `partial_text` to `--out` if provided and print a warning to stderr. This gives the caller something to work with even on a timeout.

2. **Save session ref eagerly:** In `api.py`, persist the conversation ref to the registry immediately after `open_or_create_conversation` returns (i.e. before `send_prompt`), not only after successful completion. On error the stored ref points to the in-flight conversation, letting the caller re-attach and see the partial or completed response.

3. **Clearer error guidance for `--out` + timeout:** The `ResponseTruncatedError` action text says "retry or reduce payload size" — it should explicitly mention that `--out FILE` was not written so the caller does not waste time looking for a partial file.

---

## Additional evidence — premature truncation on long Pro Extended calls (lead-verified 2026-06-14)

### What was observed

A real `Pro Extended` call (`--model-settings '{"model":"Pro Extended"}' --timeout 3600`, prompt ~9.2 KB) raised the exact `ResponseTruncatedError` (exit 7) after **less than 13 minutes** of wall time — far short of the 3600 s (60 min) `--timeout`. GPT Pro Extended legitimately takes 10–45 min for deep-reasoning tasks, so the response was plausibly still generating when the error was raised.

The error text says "completion marker did not appear **before timeout**", but `--timeout 3600` was clearly not reached.

### Root cause identified in source

The `--timeout` flag is NOT the only deadline governing `wait_for_completion`. There is an independent absolute ceiling:

- `driver.py`, line 46: `_REAL_COMPLETION_CEILING_S = 600.0` — a module-level constant set to **600 seconds (10 minutes)**
- `driver.py`, lines 366–369 (`wait_for_completion`):
  ```python
  max_total_wait = _REAL_COMPLETION_CEILING_S if max_total_wait_s is None else max(0.0, float(max_total_wait_s))
  absolute_deadline = start + max_total_wait
  deadline = min(deadline, absolute_deadline)
  ```
  When `max_total_wait_s` is not passed by the caller, `absolute_deadline` is set to `start + 600.0` regardless of `timeout_s`. `deadline` is then `min(start + timeout_s, start + 600.0)`, so the ceiling dominates for any `--timeout` larger than 600 s.

- The `api.py` caller (`ask_chatgpt`, line 60) passes only `timeout_s=timeout_s` to `session.wait_for_completion(timeout_s=timeout_s)` — it does NOT pass `max_total_wait_s`. So the 600 s ceiling is always active for the current CLI path.

**Conclusion:** this is scenario (a) — an internal hard ceiling (`_REAL_COMPLETION_CEILING_S = 600.0`) fires independently of `--timeout` and much sooner. It is NOT a false-positive completion detection on the Pro Extended thinking UI; the poll loop simply hits the 10-minute wall and raises. `--timeout 3600` has no effect for real/CDP channels beyond 600 s under the current code.

### Impact

**HIGH — this is the actual blocker for long Pro Extended probes.** Session-based Pro Extended calls that need 10–45 min will always fail before they finish. Combined with the existing bugs (no `--out` write + lost session ref on `ResponseTruncatedError`), the entire long response is discarded and the call cannot be resumed.

### Additional suggested-fix direction

4. **Make the completion-marker timeout respect (or be derived from) `--timeout`:** The ceiling should be `max(_REAL_COMPLETION_CEILING_S, timeout_s)` or the `api.py` call site should pass `max_total_wait_s=timeout_s` so `--timeout 3600` actually gives 3600 s of wall time. The 600 s default is appropriate for normal tiers but breaks Pro Extended.

5. **On a suspected truncation, persist partial reply + session/conversation ref:** If `wait_for_completion` times out mid-generation, the partial visible text and the conversation ref should both be captured before raising so the caller can resume rather than losing everything (see fix directions 1–2 above; this finding makes them more urgent).

6. **Document the 600 s ceiling prominently:** `docs/USAGE.md` and `PARALLEL-GPT-RECIPE.md` do not mention `_REAL_COMPLETION_CEILING_S`. The `--timeout` help text ("completion timeout in seconds", `cli.py` line 116) implies it is the sole deadline; this is misleading for Pro Extended users.
