# M4-E6 — Step 6 `cli.py` verbs + status + minimal pool/budget/loop stubs (SINGLE EDITOR, TDD)

**READ FIRST, IN FULL:** `team/contracts/M4-common.md` (safety + 12 MANAGER DECISIONS — esp. **3** (ask stdout = raw content + one `\n`; render format), **9** (`StatusReport` field names), **10** (`create` has `--project`; `ask` does NOT)). Then `team/evidence/reports/M4-test-plan.md` section **(F)** items **F1–F8**, and these `team/evidence/reports/M3-detailed-design.md` sections: **§2.2** (Session), **§2.11** (`cli.main`, `Allowlist`), **§7** (concurrency — M4 = minimal `TabPool`/`AdaptiveSendBudget` STUBS only), **§8** (CLI verbs table + stdout/stderr discipline + loop JSONL + status JSON), **§9** (error taxonomy + exit codes + `ERROR <CODE>: <message>` stderr format).

Branch `rewrite-v2`. Build on committed E1–E5. **OFFLINE** — mock/store only; never import Playwright/network. This is the LAST M4 editor step; after it, the WHOLE `uv run pytest` must be GREEN — that is the M4 acceptance gate.

## Scope
1. **`src/ask_chatgpt/cli.py`** — REPLACE the scaffold with a thin parser/output/error-mapping layer over `Session` (NO business logic). Verbs + flags per §8 table:
   - `ask <conv?> "<prompt>"` → `Session.ask`; flags `--model`, repeatable `--tool`, repeatable `--attach`, `--timeout`, `--max-total-wait` (omitted → `None`), `--out`, `--data-dir`. **NO `--project` on `ask`** (DECISION 10). Stdout = the new assistant `content_markdown` (raw, DECISION 3) with exactly one trailing `\n`.
   - `create` → `Session.create`; `--project` (forwarded), `--json`, `--data-dir`. May report draft/null id.
   - `scrape <conv>` → `Session.scrape`; `--with-attachments`, `--out`, `--data-dir`. Stdout = `render_markdown` export; also writes store/raw.
   - `history <conv>` and `export <conv>` → `Session.history` (store-only; **NO CDP preflight/browser**); `--out`, `--data-dir`. Stdout = rendered local markdown.
   - `fetch <conv> <attachment>` → `Session.fetch`; `--json`, `--data-dir`. (M4: cached-ref/local; no attach when cached.)
   - `status [<conv>]` → `Session.status(conv, probe_browser=not --no-browser-probe)`; `--json`, `--no-browser-probe`, `--data-dir`.
   - `loop <conv>` → minimal bounded stub (see F8).
   - Common: `--cdp-endpoint`, `--selector-channel real|mock`. Diagnostics/progress/errors → **stderr**; payload/status-JSON → **stdout**.
2. **`src/ask_chatgpt/session.py`** finalize — add the §7 minimal **`TabPool`** and **`AdaptiveSendBudget`** stubs OWNED by `Session` (F7): lower modules get leases only; the budget gates prompt submission but NOT completion waiting; **no hard message cap** (repeated successful sends in one Session must not fail at some N); pool opens/reuses/closes ONLY tool-created tabs; `detach(close_managed_tabs=True)` closes managed tabs and disconnects WITHOUT quitting the browser or closing foreign tabs; `context.pages` enumeration never used. Keep these MINIMAL — full pool/rate behavior is M7.
3. **`Session.status`** → build a `StatusReport` (DECISION 9 exact field names: `ok, cdp, signed_in, login_or_challenge, selector_valid, conversations, blocking_code, details`); offline/`--no-browser-probe` path does NOT preflight CDP; per-selector `present=null` when unchecked; redact `last_error`; exit may be nonzero (blocking condition) while the report still prints.

## Behaviors (map F1–F8)
- **F1:** importing CLI/session + running with `channel="mock"` never imports Playwright / preflights CDP / opens a browser / hits network; `history`/`export` are store-only.
- **F2:** verbs dispatch to the documented `Session` methods; flags forwarded faithfully (no hidden defaults like a 600s max-total; `export` → `Session.history`, not scrape; `create` forwards `--project`). Test with a fake `Session` recorder.
- **F3 [gotcha #4]:** `ask`/`scrape`/`history`/`export` print payload to **stdout** AND additionally write `--out`; stdout is NEVER suppressed by `--out`; identical bytes; exactly one trailing newline for `ask` content already/!ending in newline; diagnostics not mixed into stdout.
- **F4:** on `CompletionTimeoutError`, `ask` prints the salvaged partial markdown to stdout (and `--out` if given) BEFORE exiting with the completion error code; stderr gets the redacted error.
- **F5:** `status --json` machine schema (the §8 fields); `--no-browser-probe` does NOT probe; nonzero exit on blocking CDP/login while stdout still has the report.
- **F6:** non-JSON errors → first stderr line `ERROR <CODE>: <message>`; JSON-mode → redacted error JSON on stderr (stdout uncorrupted); exit = `AskChatGPTError.exit_code`; unexpected exception → redacted `InternalError` exit 99; NEVER print tracebacks by default, lowercase codes, prompt bodies, or header/cookie canaries.
- **F7/F8:** as in Scope 2 + `create` draft/normal refs; `fetch` cached-local; `loop` is a BOUNDED mock-only stub emitting JSONL turn envelopes (`schema_version`, `type="turn"`, `iteration`, ids, status, partial, capture_source, fidelity, content_markdown, paths) for `--max-iterations`, with NO unbounded real-browser loop, NO rate adaptation, NO hidden message cap.

## test_smoke.py
The scaffold `cli.py` "not yet implemented" behavior is being REPLACED. **Update `tests/test_smoke.py`** to match the real CLI: keep `--version`/`--help` if you preserve them (preferred), and REPLACE `test_unimplemented_command_is_actionable_and_nonzero` with real-verb tests (e.g. a mock-backed `history`/`status` happy path + an error mapping). Do not delete coverage — convert it to real-CLI coverage.

## TDD (incremental, falsifiable — observe RED before GREEN; assert LITERAL values)
Use a fake/recording `Session` (monkeypatch) for parser/dispatch/output tests, and the real `Session(channel=mock,...)` for offline end-to-end. MUST-cover falsifiables: `--out FILE` still prints full payload to stdout (a stdout-suppressing impl fails) and the file bytes equal stdout (F3); `export` calls `Session.history` not `scrape` (F2); `ask` has no `--project` and `create` forwards it (DECISION 10/F2); `CompletionTimeoutError` → salvaged stdout + nonzero exit + `ERROR COMPLETION_TIMEOUT:` on stderr (F4/F6); `PromptNotSubmittedError` → exit 30, no prompt body in stderr (F6); `status --no-browser-probe` performs no CDP preflight (a probing impl fails) and JSON has the exact fields (F5); repeated successful mock sends in one Session do not fail at some N (no hidden cap, F7); `loop --max-iterations 2` emits exactly 2 JSONL envelopes and stops (F8).

## Acceptance (verify by INSPECTION) — THIS IS THE M4 GATE
`uv run pytest` GREEN across the ENTIRE suite (all prior + new + updated smoke). CLI verbs map to Session; stdout-AND-`--out` (gotcha #4) holds; salvage-on-timeout to stdout; `status --json` schema; error codes/exit/redaction correct; offline (no Playwright/CDP/network).

## If low on budget
Prioritize F1/F2/F3/F4/F6 (the acceptance-bar CLI core) + updating test_smoke; F5/F7/F8 polish may trail as minimal stubs. Commit GREEN work; return **STATUS PARTIAL** with a per-item F1–F8 ledger. Never leave the suite RED.

## Commit + handoff
- Commit increment(s) on `rewrite-v2`: `git add src/ask_chatgpt tests`. Plain messages e.g. `M4 step 6: cli verbs + status + minimal session stubs over mock`. **NO `git add -A`, NO Co-Authored-By.** `git status --porcelain` first; never stage `issues/...controller.mjs`, `team/state/live-state.json`, `human/`.
- Handoff to **`team/evidence/handoffs/M4-E6-cli.md`**: STATUS line 1 (+ F1–F8 ledger if PARTIAL); pasted FULL `uv run pytest` summary (the M4 gate); falsifiability notes for stdout-AND-out, export→history, salvage-on-timeout, status-no-probe, and no-hidden-send-cap; commit hashes + `git log --oneline -3` + `git show --stat HEAD`; how test_smoke was updated; blockers; recommended M5 next steps.
