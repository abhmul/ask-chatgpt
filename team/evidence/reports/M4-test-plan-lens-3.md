# M4 test plan Lens 3 — offline send, completion, CLI, errors, and concurrency stubs

Scope: falsifiable behavior checklist only; no test code. Target is the M4 offline core over the `mock` channel with no chatgpt.com, no CDP, no browser launch, and no Playwright import required by the default test run. Source basis read first: `team/contracts/M4-common.md`, `team/contracts/M4-offline-core.md`, and the requested sections of `team/evidence/reports/M3-detailed-design.md`.

## Common mock and clock assumptions

- Use a temp `Store` data dir per test, a deterministic `MockChannel` with a call log, and a fake monotonic clock/sleeper for all timeout/cadence tests; no test in this slice should sleep in real time.
- The mock should be able to serve turn DOM snapshots, composer visibility/unmount sequences, submit outcomes, backend completion snapshots, backend header canaries, backend fetch counters, DOM progress snapshots, clipboard permission states, login/challenge states, and status reports.
- Canary secrets for redaction tests should include auth/OAI-like header values, cookies, raw response header values, private operator-tab text, prompt bodies, and assistant text that is not intentionally emitted as salvage payload.
- Do not assert implementation internals except where the design makes an artifact observable: public API return values, CLI stdout/stderr/exit code, store transcripts with `include_pending` variants, mock-channel call logs, and persisted JSONL/raw/status artifacts.

## Falsifiable behavior checklist

### L3-SCOPE-01 — Offline mock channel is the only execution leg
1. Behavior: All send, completion, CLI, error, and status tests in this slice run with `channel='mock'` or an equivalent CLI mock selector and never require CDP preflight except when explicitly testing status/preflight reporting.
2. Why: M4 is offline core only; real chatgpt.com, CDP, browser, and Playwright legs are M5+.
3. Falsifiability: A wrong implementation that imports Playwright at module import time, attempts `/json/version`, opens a real browser, or performs an allowlisted network fetch during mock `ask` must fail under a mock that has no CDP endpoint and a network guard.
4. Required setup: Import CLI/session in a process with no browser/CDP fixture; `MockChannel` records all channel calls; optional import guard that makes Playwright unavailable for default tests.

### L3-SCOPE-02 — Lower modules use only `TabLease.channel`
1. Behavior: `send.py` and `completion.py` operate only through the `TabLease` and its `BrowserChannel` protocol methods; they do not create sessions, enumerate pages, own a rate limiter, or call browser APIs directly.
2. Why: The channel seam is the offline-test boundary and prevents accidental operator-tab or browser ownership.
3. Falsifiability: A wrong implementation that calls `context.pages`, constructs a CDP channel inside `send_prompt`, or bypasses `MockChannel.query_turns` will fail when the mock lease exposes no such objects and logs no expected protocol calls.
4. Required setup: Minimal `TabLease(tab_id, url, channel=mock)` whose channel implements only the protocol; mock raises on unknown attributes and makes page/context enumeration unavailable.

### L3-SCOPE-03 — M4 menu actions fail closed unless already no-op
1. Behavior: With no requested model/tools, send does not touch menus. With requested model/tool changes in M4, the stub/fail-closed path raises `ModelSelectionNotReflectedError` or `ToolSelectionNotReflectedError` before prompt submission and leaves no new user turn.
2. Why: Full Radix menu selection is M7; M4 must not send under an unverified model/tool state.
3. Falsifiability: A wrong implementation that silently ignores `--model`/`--tool` and sends anyway, or clicks ambiguous menus and then sends, must be caught by a mock with a submit-call counter and no reflected state.
4. Required setup: Mock menu state with absent or ambiguous reflected labels; prompt submission call log; temp store to verify only a pending stub may exist and no canonical user is committed.

### L3-SCOPE-04 — `loop`, `TabPool`, and `AdaptiveSendBudget` stay minimal stubs
1. Behavior: M4 tests require only minimal stub semantics needed by single-tab `Session.ask`, `status`, and CLI parsing; they must not require full persistent loop orchestration, measured rate adaptation, or multi-tab eviction behavior.
2. Why: The contract explicitly keeps full loop/menus/TabPool/AdaptiveSendBudget out of M4 except minimal stubs.
3. Falsifiability: A wrong test plan that expects M7 rate-ramp behavior or multi-tab LRU eviction in M4 would fail a correct minimal implementation; a wrong implementation that hides a hard send cap inside the stub must fail the no-hard-cap checks below.
4. Required setup: Stub pool/budget exposing observable snapshots and call counters only; no concurrent browser fixture; fake clock for any budget waits.

## Send and pending-store behavior

### L3-SEND-01 — Send reads a complete `TurnBaseline` before mutating the composer
1. Behavior: `send_prompt` reads latest user id, user count, latest assistant id, and assistant count from the current DOM before fill/submit and before completion begins.
2. Why: Baseline/new-turn verification fixes gotcha #2, the silent no-op send returning a stale response.
3. Falsifiability: A wrong implementation that reads baseline after submit or tracks only user count will accept a pre-existing assistant or miss a stale same-id user case.
4. Required setup: Mock initial snapshot with `latest_user_id=u1`, `user_count=1`, `latest_assistant_id=a1`, `assistant_count=1`; mock call log asserting `query_turns` precedes `fill`, `insert_text`, `click`, or `press`.

### L3-SEND-02 — Assistant baseline is preserved for completion gating
1. Behavior: The `TurnBaseline` passed onward to completion includes the pre-send `latest_assistant_id` and `assistant_count`, not values read after the new user appears.
2. Why: Completion is invalid unless a new assistant id exists after the assistant baseline.
3. Falsifiability: A wrong implementation that overwrites `latest_assistant_id` after submit can return `a1` as the new answer when `a1` was already present.
4. Required setup: Mock send succeeds with new user `u2` but no new assistant; existing assistant `a1` remains visible with attractive markdown; completion mock would return complete if not baseline-gated.

### L3-SEND-03 — `Store.begin_send` eagerly writes a pending stub before risky UI submission
1. Behavior: After baseline and before composer/submit can fail, `Session.ask` appends a pending local user record with `message_id='local:<client_send_id>'`, prompt content, conversation ref, requested model, and active tools.
2. Why: Lead decision accepts eager pending stubs in transcript JSONL; failures must not lose the prompt/session.
3. Falsifiability: A wrong implementation that writes only after verified submit loses the prompt when the composer never appears or submit no-ops.
4. Required setup: Temp store; mock composer permanently absent or submit no-op; inspect `load_transcript(include_pending=True)` and JSONL artifact after failure.

### L3-SEND-04 — Pending stubs are hidden by default until committed
1. Behavior: A pre-submit pending local record is present when `include_pending=True` but excluded from default transcript/history reads until it is superseded by a canonical user record.
2. Why: Lead decision says local pending stubs are hidden/superseded in default reads; default history should not present local stubs as confirmed turns.
3. Falsifiability: A wrong implementation that exposes `local:<client_send_id>` in normal history after a failed send, or drops it entirely, must be caught.
4. Required setup: Temp store after an induced send failure; compare `load_transcript(..., include_pending=False)` vs `include_pending=True`.

### L3-SEND-05 — Composer transient-unmount retry succeeds
1. Behavior: `wait_for_composer` tolerates a transient missing/unmounted `#prompt-textarea` and retries until it remounts within `composer_wait_timeout_s`, then fill/submit proceeds.
2. Why: M3 send strategy names composer staleness/unmount as an M4 mock behavior.
3. Falsifiability: A wrong implementation that treats the first missing composer as fatal fails even though the composer remounts; a wrong implementation that spins without fake-clock sleeps ignores timeout control.
4. Required setup: Mock `wait_for_selector` or composer snapshot sequence absent, absent, visible; fake clock advances per poll; assert final canonical user is committed.

### L3-SEND-06 — Composer never remounts fails closed and preserves pending prompt
1. Behavior: If the composer remains absent until `composer_wait_timeout_s`, send raises `SelectorNotFoundError` or the chosen selector error, does not submit, does not wait for completion, and leaves only the pending stub as salvageable local state.
2. Why: Required selector missing must not become a blind send or a stale assistant return.
3. Falsifiability: A wrong implementation that presses Enter against the page or starts completion despite no composer will produce channel submit/completion calls and fail.
4. Required setup: Mock composer absent for the whole fake-clock window; channel raises if submit/completion methods are called; temp store includes pending stub.

### L3-SEND-07 — Filled composer text is verified after normalization
1. Behavior: The prompt inserted into the editor is verified against the normalized composer text before submit; normalization is the same normalization used to compare the later user turn.
2. Why: Rich editor `insertText`/InputEvent fallback can fail or transform text; send must prove the prompt is in the composer.
3. Falsifiability: A wrong implementation that submits without verifying composer content accepts a mock where fill is ignored or only half the prompt appears.
4. Required setup: Mock fill/insert path with one case matching normalized prompt and one case producing truncated editor text; fake prompt containing leading/trailing whitespace and newlines. Ambiguity: the exact normalization function is not specified in the read sections, so tests should make the normalization contract explicit once implemented rather than compare with a self-answering helper.

### L3-SEND-08 — Submit uses an enabled send control, with Enter fallback only while focused
1. Behavior: Submit clicks an enabled `button[data-testid='send-button']` or `#composer-submit-button` after input, and uses Enter fallback only when the composer is focused.
2. Why: UI-only actions are required; blind Enter can send in the wrong context.
3. Falsifiability: A wrong implementation that presses Enter globally will create a mock side effect flagged as unsafe; a wrong implementation that clicks a disabled button reports success without a new user turn.
4. Required setup: Mock selectors for enabled/disabled send button and composer focus state; call log distinguishing `click` and `press`.

### L3-SEND-09 — Verified send requires a new user turn carrying the normalized prompt
1. Behavior: `verify_prompt_submitted` returns success only when a user turn newer than baseline appears by different latest user id or increased user count and that turn carries the normalized prompt.
2. Why: This is the core gotcha #2 acceptance point.
3. Falsifiability: A wrong implementation that checks only count, only id, or only text will accept either an unrelated new user turn, an old turn with matching text, or a stale DOM snapshot.
4. Required setup: Parameterized mock snapshots: new id plus prompt succeeds; increased count plus prompt succeeds; new id with wrong text fails; old id/count with prompt fails.

### L3-SEND-10 — No-op submit raises `PromptNotSubmittedError`
1. Behavior: If submit produces no new user turn carrying the prompt within `send_verify_timeout_s`, send raises `PromptNotSubmittedError` with code `PROMPT_NOT_SUBMITTED` and does not proceed to completion.
2. Why: This directly targets the silent no-op gotcha.
3. Falsifiability: A wrong implementation that returns the previous assistant reply, waits for completion anyway, or returns a successful `SubmittedTurn` from the baseline snapshot must fail.
4. Required setup: Mock no-op send fixture with unchanged users and existing assistant `a-old`; completion mock set to raise if called; CLI/API assertion that no stale assistant markdown is returned.

### L3-SEND-11 — Prompt mismatch after apparent submit is still a submission failure
1. Behavior: A new user id/count whose visible text differs from the normalized prompt raises `PromptNotSubmittedError` and must not be treated as a successful send.
2. Why: A concurrent/manual user action or stale UI could create a different user turn; returning its assistant would be unsafe.
3. Falsifiability: A wrong implementation that accepts any new user turn will pass the wrong prompt through.
4. Required setup: Mock submit outcome creates `u2` with text `manual text`, while requested prompt is `expected text`; store pending stub remains uncommitted.

### L3-SEND-12 — Canonical user commit supersedes the pending local stub
1. Behavior: After verified submission, `Store.commit_send` writes the canonical user record with the real `user_message_id` and supersedes `local:<client_send_id>` so default transcript reads show one confirmed user turn, not both.
2. Why: Lead decision requires pending-stub supersession rather than a separate outbox or duplicate visible turns.
3. Falsifiability: A wrong implementation that leaves both local and canonical records visible, mutates the local id without an append/upsert trail, or never commits the canonical id must fail.
4. Required setup: Successful mock send; inspect `load_transcript(include_pending=False)` for exactly one user prompt with canonical id and `include_pending=True` for a superseded/hidden local record if the public store exposes it.

### L3-SEND-13 — No separate outbox is used for pending sends
1. Behavior: Pending send state is represented in the transcript/store layout by the accepted local message id, not by an independent outbox file that default APIs depend on.
2. Why: Lead decision explicitly rejects a separate outbox file.
3. Falsifiability: A wrong implementation that loses pending state when an outbox file is absent, or creates an outbox artifact as the only source of truth, must fail an artifact/layout check.
4. Required setup: Temp data dir after `begin_send`; inspect public conversation paths/artifacts. This is more artifact-level than black-box and should be limited to the lead-decision layout acceptance.

### L3-SEND-14 — Existing generation is made idle before a new send
1. Behavior: Before reading the final baseline and submitting, send waits for any existing generation to be idle and performs the between-turn reload needed to clear SPA staleness.
2. Why: M3 §6 includes idle/reload to avoid composer staleness and no-op sends.
3. Falsifiability: A wrong implementation that sends while `stop_visible=True` or skips reload after idle will be caught by a mock that no-ops submissions until reload occurs.
4. Required setup: Mock starts with active generation then idle; channel call log for `wait_for_load_state`/`reload` or equivalent; submit only succeeds after the expected idle/reload sequence.

### L3-SEND-15 — Session ask returns a new assistant turn, not the submitted user or stale assistant
1. Behavior: On success, `Session.ask` returns the captured assistant `TurnRecord` whose `message_id` is newer than the baseline and whose content is from final capture for that new turn.
2. Why: Public API semantics are send → verify → wait → capture → persist → return assistant.
3. Falsifiability: A wrong implementation that returns `SubmittedTurn`, the pending user record, `CompletionState`, or pre-existing assistant `a-old` will fail type/id/content checks.
4. Required setup: Mock conversation with old assistant `a-old`, successful new user `u2`, completion new assistant `a2`, and final backend capture containing distinct markdown for `a2`.

## Completion behavior

### L3-COMP-01 — Completion wait starts only after verified send
1. Behavior: `completion.wait_for_completion` is invoked only after `verify_prompt_submitted` returns a `SubmittedTurn`; failed sends do not enter completion polling.
2. Why: Waiting after a no-op send is how stale responses were returned in v1.
3. Falsifiability: A wrong implementation that always calls completion after clicking submit will trip a mock completion method configured to fail on no-op send.
4. Required setup: No-op submit fixture; channel call log or sentinel completion mock.

### L3-COMP-02 — Same assistant id as baseline is never complete
1. Behavior: A completion state is invalid unless it contains an assistant id different from and newer than `baseline.latest_assistant_id`.
2. Why: M3 §2.5 and §5 explicitly require new assistant gating.
3. Falsifiability: A wrong implementation that sees non-empty old assistant text and returns complete will fail.
4. Required setup: Baseline `latest_assistant_id=a1`; backend and DOM snapshots repeatedly expose `a1` with stable text and complete-looking status; expected outcome is continued polling until timeout/salvage, not success.

### L3-COMP-03 — A new assistant id alone is insufficient while active or empty without explicit empty-complete
1. Behavior: A new assistant id becomes complete only when text is non-empty or an explicit empty-complete signal exists, and no relevant async/node/finalizing signal remains active.
2. Why: Conservative completion rule avoids premature finalization on active Pro/DR turns.
3. Falsifiability: A wrong implementation that returns success on first new id or first non-empty token while `is_finalizing=True` must fail.
4. Required setup: Backend timeline with `a2` appearing empty, then text grows while node status active, then final inactive state.

### L3-COMP-04 — Active-looking or unknown-incomplete states keep polling
1. Behavior: `async_status`, node status, `async_source`, `is_complete=False`, `is_finalizing`, and `pro_progress` values that are active, in-progress, finalizing, or unknown-but-active-looking prevent success.
2. Why: Exact live vocabularies are deferred, so offline defaults must be conservative.
3. Falsifiability: A wrong implementation that treats unknown statuses as complete or ignores `is_complete=False` returns too early.
4. Required setup: Mock backend states with new assistant text plus each active/incomplete signal; final state changes only at the end.

### L3-COMP-05 — `activity_timeout_s` is a no-activity window
1. Behavior: Timeout is measured since the last progress token change, not since wait start.
2. Why: Gotcha #3; long Pro/DR runs must not be killed by a wall-clock timeout when progress continues.
3. Falsifiability: A wrong implementation using `start + activity_timeout_s` fails a timeline where progress occurs just before every activity window and completion arrives much later.
4. Required setup: Fake clock; completion timeline with progress at `activity_timeout_s - epsilon` intervals for several windows, then complete.

### L3-COMP-06 — Every authoritative progress token resets the no-activity window
1. Behavior: The activity window resets independently on changes to `update_time`, `current_node`, new node id, new assistant id, assistant text hash, assistant text length, `async_status`, node status, `pro_progress`, and `is_finalizing`.
2. Why: M3 §5 lists these progress signals explicitly.
3. Falsifiability: A wrong implementation that resets only on text length will time out in cases where only `pro_progress` or `update_time` changes.
4. Required setup: Parameterized fake-clock timelines where exactly one listed token changes per window and text may remain constant; each should avoid timeout until a final no-progress case.

### L3-COMP-07 — Text hash changes count as progress even when length is unchanged
1. Behavior: A same-length assistant text update with a different hash resets activity.
2. Why: M3 lists text hash and length separately; streaming edits can preserve length.
3. Falsifiability: A wrong implementation tracking only length times out or misses progress when text changes from `abc` to `abd`.
4. Required setup: Backend or DOM progress snapshots with same `assistant_message_id`, same length, different text/hash across windows.

### L3-COMP-08 — `max_total_wait_s=None` is truly unbounded
1. Behavior: With `max_total_wait_s=None`, wait continues past 600 seconds of fake time as long as progress keeps resetting activity, and eventually returns the final new assistant.
2. Why: Explicit acceptance point; hidden 600s ceiling must fail.
3. Falsifiability: A wrong implementation with any hard-coded 600s cap raises timeout at fake t=600 despite progress.
4. Required setup: Fake clock long-progress fixture lasting e.g. 1200s with synthetic progress every activity window and final completion after the hidden-ceiling boundary.

### L3-COMP-09 — Explicit `max_total_wait_s` is the only wall-clock cap
1. Behavior: When caller sets `max_total_wait_s`, wait raises `MaxTotalWaitExceededError` once total fake elapsed time exceeds that cap even if activity progress continues.
2. Why: Design allows an opt-in total cap distinct from no-activity timeout.
3. Falsifiability: A wrong implementation that ignores explicit max total will run to final completion; one that conflates it with activity timeout will raise the wrong class/code.
4. Required setup: Fake clock timeline with continuous progress beyond a small explicit cap; assert code `MAX_TOTAL_WAIT_EXCEEDED` and exit code 51 at CLI layer if surfaced.

### L3-COMP-10 — Cheap DOM progress poll cadence is separate from backend check cadence
1. Behavior: `progress_poll_interval_s` schedules cheap own-tab DOM progress checks only; sparse authoritative backend checks use `backend_check_interval_s`, not the short DOM interval.
2. Why: M3 forbids full/heavy backend fetches every short progress tick.
3. Falsifiability: A wrong implementation that performs backend checks every 2s when DOM poll is 2s and backend interval is 30s will exceed mock fetch/header counters.
4. Required setup: Fake clock; `progress_poll_interval_s=2`, `backend_check_interval_s=30`; mock counts DOM polls, header acquisitions, and backend fetches.

### L3-COMP-11 — `backend_check_interval_s=None` uses a channel/mock default, not DOM cadence
1. Behavior: When backend interval is `None`, the measured channel default or mock override controls sparse backend checks; it must not silently collapse to `progress_poll_interval_s`.
2. Why: M5 will measure real intervals; M4 mock must preserve the distinction.
3. Falsifiability: A wrong implementation that substitutes the DOM interval for `None` produces too many backend calls under the mock default.
4. Required setup: Mock channel exposing a deterministic backend-check default. Ambiguity: the exact default value is not specified in the read sections, so cadence tests should use an explicit interval for exact counts and a separate `None` test for non-collapse.

### L3-COMP-12 — Backend completion checks acquire one-use headers freshly
1. Behavior: Each backend completion check acquires a fresh `HeaderBundle`, calls `for_single_fetch()` for exactly one request, and discards it; no header object or value is retained across loop iterations.
2. Why: Header safety invariant in §2.3/§5; no long-lived auth/OAI headers.
3. Falsifiability: A wrong implementation that caches headers across checks fails when the mock invalidates each header after one use or when canary values appear in progress state/logs.
4. Required setup: Mock header observer issuing unique one-use canary headers; backend fetch rejects reused headers; artifact redaction scan for canaries.

### L3-COMP-13 — Full backend conversation fetch is not done per progress tick
1. Behavior: During wait, backend checks are lightweight/sparse; the full backend conversation capture is performed for final capture and explicit salvage snapshots, not on every progress poll.
2. Why: M3 §5 says real code must not fetch a full large conversation every short poll.
3. Falsifiability: A wrong implementation that calls full capture each tick will exceed mock full-fetch count and be slow even under fake clock.
4. Required setup: Mock with separate counters for lightweight status checks and full raw mapping fetch; large synthetic mapping fixture to catch accidental repeated full fetches.

### L3-COMP-14 — DOM consensus fallback is baseline-gated and stable-window based
1. Behavior: DOM completion fallback requires a new assistant id different from baseline, stop button absent for the stable window, text hash/length stable for the same stable window, and `saw_streaming` or non-empty body.
2. Why: DOM fallback is a completion signal only and must not accept old/stale turns.
3. Falsifiability: A wrong implementation that accepts old stable DOM text, ignores stop button, or ignores stable-window duration will return prematurely.
4. Required setup: Fake clock DOM snapshots: old stable assistant, new assistant with stop visible, new assistant text changing, then stable absent-stop state.

### L3-COMP-15 — Backend impossible shapes do not become success
1. Behavior: Unknown impossible backend shapes trigger DOM fallback and/or salvage, not a successful canonical completion.
2. Why: Conservative offline default; parser updates belong to later evidence.
3. Falsifiability: A wrong implementation that treats parse failure as complete returns malformed or stale content.
4. Required setup: Mock backend response with incompatible shape and a DOM fallback path; separate case with no DOM fallback expects capture failure/salvage error.

### L3-COMP-16 — No-activity timeout raises and salvages partial
1. Behavior: When no progress occurs for `activity_timeout_s`, wait raises `CompletionTimeoutError`, and the orchestration persists a partial assistant record if any partial source exists.
2. Why: M3 §5 salvage order and error taxonomy; gotcha #3 plus lose-nothing persistence.
3. Falsifiability: A wrong implementation that raises without a store partial, or returns success with partial text, must fail.
4. Required setup: Fake clock timeline with new assistant partial then no progress; temp store; mock salvage source available.

### L3-COMP-17 — Non-timeout completion/capture errors also salvage partial when possible
1. Behavior: Backend auth/capture shape/fail-closed errors during wait or final capture attempt salvage and persist available partial text with honest status instead of dropping it.
2. Why: M3 §5 and §6 require timeout/error salvage and persistence.
3. Falsifiability: A wrong implementation that only salvages timeouts loses partials on `BackendCaptureShapeError` or `CaptureFailedClosedError`.
4. Required setup: Mock completion has partial `a2`, then backend final capture raises a shape/fail-closed error; DOM or backend partial source remains available.

### L3-COMP-18 — Salvage order is backend partial, then allowed clipboard, then DOM text
1. Behavior: Salvage chooses latest backend partial for the new turn if available; otherwise copy-button/clipboard output only when explicit attended permission exists; otherwise DOM textContent of the new assistant turn. Default clipboard prompt fails closed as `HumanActionNeededError` and never auto-reads clipboard.
2. Why: M3 §5 plus lead decision on clipboard fallback.
3. Falsifiability: A wrong implementation that reads clipboard by default, prefers lower-fidelity DOM over backend partial, or marks clipboard prompt as success must fail.
4. Required setup: Three mock cases: backend partial and DOM disagree; backend absent with clipboard permission prompt; backend absent with explicitly allowed clipboard vs DOM fallback.

### L3-COMP-19 — Persisted partial records are honest and redacted
1. Behavior: Persisted salvage record has `status='partial'` or `status='error'` as appropriate, `partial=true`, actual `capture_source` and `fidelity`, new assistant/user linkage when known, and redacted error details without tokens/headers/prompt bodies.
2. Why: M3 salvage and error taxonomy require honest capture-source/fidelity and redaction.
3. Falsifiability: A wrong implementation that stores partial as complete/canonical backend, omits `partial=true`, lies about source, or writes auth canaries to JSONL must fail.
4. Required setup: Temp store; backend/DOM/clipboard salvage variants with canary secrets embedded in exception details; inspect public transcript and raw artifacts.

### L3-COMP-20 — CLI `ask` emits salvaged markdown on completion timeout when available
1. Behavior: If `Session.ask` times out but records salvage, CLI `ask` writes the salvaged markdown to stdout before exiting with the completion error code, and may additionally write `--out` if supplied.
2. Why: M3 §8/§9 says `ask` stdout still receives salvaged partial markdown if any.
3. Falsifiability: A wrong implementation that suppresses stdout on nonzero exit, prints only an error, or prints stale complete text will fail.
4. Required setup: CLI harness with mock session raising `CompletionTimeoutError` carrying a partial record or store salvage; capture stdout/stderr/exit and optional out file.

## CLI behavior

### L3-CLI-01 — Supported verbs dispatch to the correct `Session` methods
1. Behavior: `ask`, `create`, `scrape`, `history`, `export`, `fetch`, and `status` construct/use `Session` and call respectively `Session.ask`, `Session.create`, `Session.scrape`, `Session.history`, `Session.history`, `Session.fetch`, and `Session.status`.
2. Why: M3 §8 CLI table is a public contract for M4 CLI verbs.
3. Falsifiability: A wrong implementation that maps `export` to `scrape`, maps `history` to browser capture, or leaves a scaffold `not implemented` path will fail method-call assertions.
4. Required setup: CLI test harness monkeypatching/injecting a fake `Session` that records calls and returns deterministic payloads; no real channel.

### L3-CLI-02 — `ask` forwards all relevant flags and positional inputs
1. Behavior: CLI `ask <conv?> <prompt>` forwards conversation or `None`, prompt, `--model`, repeated `--tool`, repeated `--attach`, `--timeout`, `--max-total-wait`, `--out`, and `--data-dir` to `Session.ask`/constructor with correct types and order.
2. Why: CLI is an agent-facing public interface; send semantics depend on flags reaching Session.
3. Falsifiability: A wrong parser that swaps conv/prompt, drops repeated tools, treats omitted conv as a prompt, or coerces `max_total_wait` to the default 600 must fail.
4. Required setup: Fake `Session.ask` call recorder; argument cases with no conv, bare id conv, URL conv, two tools, two attachments, explicit timeouts, and omitted `max_total_wait` expecting `None`.

### L3-CLI-03 — `create` forwards project/json/data-dir and emits URL/id or JSON
1. Behavior: CLI `create` calls `Session.create(project=...)`, supports `--json`, and prints either a URL/id line or structured JSON, allowing draft/null conversation id if returned.
2. Why: M3 §8 verb table includes create and draft semantics.
3. Falsifiability: A wrong implementation that requires a server id, ignores `--project`, or emits diagnostics on stdout with JSON fails.
4. Required setup: Fake `Session.create` returning both normal and draft `ConversationRef`; stdout JSON parser in `--json` case.

### L3-CLI-04 — `scrape` forwards read-only capture flags and output path
1. Behavior: CLI `scrape <conv>` calls `Session.scrape(conv, with_attachments=..., out=...)` and prints rendered markdown payload.
2. Why: M3 §8 table; scrape is read-only browser capture but still payload-to-stdout.
3. Falsifiability: A wrong implementation that maps scrape to history only, ignores `--with-attachments`, or suppresses stdout when `--out` exists must fail.
4. Required setup: Fake `Session.scrape` returning a transcript rendered by store or a deterministic markdown helper; out-file temp path.

### L3-CLI-05 — `history` and `export` are store-only and do not preflight CDP
1. Behavior: CLI `history <conv>` and `export <conv>` call `Session.history`/store rendering and never attach/preflight/probe browser.
2. Why: M3 §2.2 and §8 state history/export browser column is no; user explicitly called this out.
3. Falsifiability: A wrong implementation that calls `Session.attach`, `status(probe_browser=True)`, or channel `preflight` before local history will fail when the mock preflight raises.
4. Required setup: Fake `Session` with `history` returning local transcript and `attach/preflight` raising; temp store transcript.

### L3-CLI-06 — `fetch` maps to `Session.fetch` and cached refs do not attach
1. Behavior: CLI `fetch <conv> <attachment>` calls `Session.fetch`; if the fake/session reports a cached local path, CLI prints that path or JSON metadata without browser preflight.
2. Why: M3 §8 says fetch browser use is maybe; cached refs do not attach.
3. Falsifiability: A wrong implementation that always attaches or scrapes before checking local cache fails under raising preflight.
4. Required setup: Fake `Session.fetch` returning a temp path; attach/preflight sentinel; `--json` and plain cases.

### L3-CLI-07 — `status` maps `--no-browser-probe` to `probe_browser=False`
1. Behavior: CLI `status [conv]` calls `Session.status(conv_or_url, probe_browser=not --no-browser-probe)` and supports `--json`.
2. Why: M3 §8 status semantics distinguish store/status report from optional browser probe.
3. Falsifiability: A wrong implementation that probes even with `--no-browser-probe`, or never probes by default, fails fake-session call assertions.
4. Required setup: Fake `Session.status` recorder returning blocking and non-blocking `StatusReport` variants.

### L3-CLI-08 — `ask --out` never suppresses stdout
1. Behavior: Successful CLI `ask` prints the new assistant `content_markdown` to stdout with exactly one trailing newline and additionally writes the same payload to `--out` when provided.
2. Why: Gotcha #4, `--out` suppressing stdout, is explicitly fixed.
3. Falsifiability: A wrong implementation that writes only the file, writes different content to file and stdout, or prints diagnostics mixed with payload fails.
4. Required setup: Fake `Session.ask` returning assistant markdown containing multiple lines; temp out path; capture stdout/stderr.

### L3-CLI-09 — `scrape --out` never suppresses stdout
1. Behavior: Successful CLI `scrape` prints rendered markdown to stdout with a trailing newline and additionally writes `--out`.
2. Why: Same gotcha #4 rule applies to scrape.
3. Falsifiability: A wrong implementation that treats `--out` as redirect or omits stdout fails.
4. Required setup: Fake scrape transcript/rendered markdown; temp out path; capture stdout/stderr.

### L3-CLI-10 — Payload goes to stdout; diagnostics/errors go to stderr
1. Behavior: Normal payloads and status JSON go to stdout only; progress, diagnostics, and errors go to stderr only.
2. Why: Agent callers need machine-usable stdout.
3. Falsifiability: A wrong implementation that logs progress on stdout corrupts markdown/JSON; one that prints payload on stderr fails captured stream checks.
4. Required setup: Fake session that emits a warning/progress diagnostic through CLI path; capture streams for success and error cases.

### L3-CLI-11 — Newline policy is deterministic
1. Behavior: `ask` stdout is assistant markdown or salvage markdown plus exactly one trailing newline; it does not add extra blank lines or strip meaningful internal/trailing content beyond the agreed final newline rule.
2. Why: M3 §8 specifies exactly one trailing newline for ask payload.
3. Falsifiability: A wrong implementation using bare `print` on content already ending with newline may emit two trailing newlines; one using `rstrip` may damage markdown.
4. Required setup: Fake assistant content with no final newline, with one final newline, and with meaningful internal blank lines.

### L3-CLI-12 — `status --json` has the required schema and redaction
1. Behavior: JSON status includes store counts, CDP preflight result, attached/signed-in/login-wall/cloudflare state from a tool-owned diagnostic tab when probed, selector-map validity and per-selector `present` values with `null` when not safely checked, tab-pool snapshot, rate/budget snapshot, last redacted error, and optional per-conversation model/tools/turn counts/last turn/attachments/branch/paths.
2. Why: M3 §8 gives status JSON content requirements.
3. Falsifiability: A wrong implementation omitting `last_error`, using booleans instead of `null` for unchecked selector presence, including raw header/prompt canaries, or reporting private tabs must fail schema/redaction checks.
4. Required setup: Fake `StatusReport` with all fields populated, one unchecked selector, a redacted last error, and optional conversation details. Ambiguity: exact top-level field names depend on the final `StatusReport` dataclass; tests should pin names once the dataclass lands while preserving these semantic fields.

### L3-CLI-13 — Blocking `status` can exit nonzero while still printing the report
1. Behavior: `status --json` or human status writes the report to stdout even when CDP down/login/challenge creates a nonzero exit; exit 0 means no blocking condition.
2. Why: M3 §8 says stdout still contains the report on blocking conditions.
3. Falsifiability: A wrong implementation that prints only `ERROR` and no status body, or exits 0 on login wall, fails.
4. Required setup: Fake status reports for healthy, CDP unreachable, login wall, and Cloudflare states; capture stdout and exit.

### L3-CLI-14 — Error stderr format is stable, with JSON error mode where documented
1. Behavior: Non-JSON errors write first stderr line `ERROR <CODE>: <message>`; JSON-mode commands additionally emit redacted error JSON on stderr without corrupting stdout.
2. Why: M3 §9 error taxonomy specifies CLI error formatting.
3. Falsifiability: A wrong implementation that prints tracebacks by default, lower-case codes, prompt bodies, or error JSON on stdout fails.
4. Required setup: Fake `Session` methods raising representative `AskChatGPTError` subclasses in plain and `--json` commands.

### L3-CLI-15 — CLI exit codes match the taxonomy
1. Behavior: CLI exits with the exact `exit_code` carried by `AskChatGPTError` subclasses and 99 for unexpected internal errors after redaction.
2. Why: M3 §9 table defines public automation semantics.
3. Falsifiability: A wrong implementation that returns generic 1/2 for all runtime errors or treats retryable send failures as success fails.
4. Required setup: Matrix of fake raised errors covering at least prompt-not-submitted 30, completion-timeout 50, max-total-wait 51, human-action-needed 21, selector-not-found 24, store-error 70, and internal unexpected exception 99.

### L3-CLI-16 — Project flags are parsed but live project send/create is not asserted in M4
1. Behavior: CLI parsing should accept/forward documented `--project` where exposed, but M4 tests should not require live project create/send semantics beyond mock/fail-closed behavior and identity parsing handled elsewhere.
2. Why: Common contract places project URL identity parsing in M4 but project send/create in M7; the mission contract text is easy to overread.
3. Falsifiability: A wrong M4 test that demands real project UI behavior would fail a correct offline core; a wrong parser that crashes before forwarding `--project` should still fail.
4. Required setup: Fake `Session.create(project='p')` or `Session.ask(..., project...)` only if final CLI API exposes it. Ambiguity: `Session.ask` signature in §2.2 has no `project` parameter while the CLI table lists `--project`; lead needs a final CLI routing decision for ask-with-project.

### L3-CLI-17 — `loop` remains explicit minimal/stub behavior in M4
1. Behavior: If the CLI exposes `loop` in M4, tests should require only explicit stub/fail-closed behavior or a clearly bounded mock-only dispatch, not the full persistent iteration/rate behavior from M7.
2. Why: User instruction and contract keep loop out of M4 except stubs.
3. Falsifiability: A wrong implementation that silently runs an unbounded loop, hides a message cap, or touches real browser/CDP must fail; a correct stub should not be failed for lacking M7 features.
4. Required setup: CLI `loop` invocation under mock with fake session; assert documented stub exit/message or minimal JSONL if final manager chooses to include one. Ambiguity: M3 §8 lists loop, but the M4 slice request excludes it from verb mapping and calls it a minimal stub.

## Error taxonomy and redaction

### L3-ERR-01 — All public errors share the required base fields
1. Behavior: Every `AskChatGPTError` subclass carries `code`, `exit_code`, `retryable`, `retry_action`, `message`, and redacted `details` suitable for CLI/status JSON.
2. Why: M3 §9 is a public automation contract.
3. Falsifiability: A wrong error class missing `retry_action`, returning non-redacted details, or deriving from a generic exception without code/exit metadata fails introspection and CLI formatting.
4. Required setup: Instantiate each subclass with details and cause canaries; inspect attributes, string/repr, and JSON/dict renderer if present.

### L3-ERR-02 — Exact class/code/exit mapping is preserved
1. Behavior: The taxonomy matrix is exact: `CDPUnreachableError` `CDP_UNREACHABLE` 20; `HumanActionNeededError` `HUMAN-ACTION-NEEDED` 21; `DomainNotAllowedError` `DOMAIN_NOT_ALLOWED` 22; `ConversationNotFoundError` `CONVERSATION_NOT_FOUND` 23; `SelectorNotFoundError` `SELECTOR_NOT_FOUND` 24; `PromptNotSubmittedError` `PROMPT_NOT_SUBMITTED` 30; `ModelSelectionNotReflectedError` `MODEL_SELECTION_NOT_REFLECTED` 31; `ToolSelectionNotReflectedError` `TOOL_SELECTION_NOT_REFLECTED` 32; `BackendAuthUnavailableError` `BACKEND_AUTH_UNAVAILABLE` 40; `BackendCaptureShapeError` `BACKEND_CAPTURE_SHAPE` 41; `CaptureFailedClosedError` `CAPTURE_FAIL_CLOSED` 42; `CompletionTimeoutError` `COMPLETION_TIMEOUT` 50; `MaxTotalWaitExceededError` `MAX_TOTAL_WAIT_EXCEEDED` 51; `AttachmentNotFoundError` `ATTACHMENT_NOT_FOUND` 60; `AttachmentFetchError` `ATTACHMENT_FETCH_FAILED` 61; `TabPoolExhaustedError` `TAB_POOL_EXHAUSTED` 62; `StoreError` `STORE_ERROR` 70; `InternalError` `INTERNAL_ERROR` 99.
2. Why: M3 §9 table defines exit semantics.
3. Falsifiability: A wrong implementation with typo codes, duplicate exits, or code/exit swaps fails a table-driven assertion.
4. Required setup: Subclass registry or explicit class imports; no channel needed.

### L3-ERR-03 — Retryability and retry action are meaningful
1. Behavior: Retryable flags match the taxonomy intent: e.g. prompt-not-submitted is retryable, model/tool reflection is retryable after UI correction, domain-not-allowed is not retryable until input/config fixed, completion timeout advises inspect/scrape before blind resend.
2. Why: Agents will automate based on retryability and retry action.
3. Falsifiability: A wrong implementation marking `PromptNotSubmittedError` non-retryable or `DomainNotAllowedError` blindly retryable will fail.
4. Required setup: Instantiate representative errors and inspect `retryable`/`retry_action` values.

### L3-ERR-04 — `PromptNotSubmittedError` contains no prompt body
1. Behavior: Prompt submission failures expose code/metadata but not the full prompt body in message, details, stderr, status, logs, or repr.
2. Why: Error taxonomy bans prompt/response text except intended partial salvage output.
3. Falsifiability: A wrong implementation that says `failed to submit prompt: <prompt>` leaks a prompt canary and fails redaction scan.
4. Required setup: No-op send with prompt canary; capture exception, CLI stderr, status `last_error`, and store artifacts.

### L3-ERR-05 — `CompletionTimeoutError` and `MaxTotalWaitExceededError` are distinct
1. Behavior: No-activity timeout raises `CompletionTimeoutError` code 50; explicit total cap raises `MaxTotalWaitExceededError` code 51; both can carry redacted salvage metadata but not header/prompt canaries.
2. Why: They imply different retry actions.
3. Falsifiability: A wrong implementation that uses one generic timeout for both fails class/code assertions and CLI exit checks.
4. Required setup: Fake-clock no-activity timeline and explicit total cap timeline.

### L3-ERR-06 — Human-action-needed is fail-closed for login/challenge/clipboard prompt
1. Behavior: Login wall, Cloudflare/challenge, or required clipboard permission raise `HumanActionNeededError` with code `HUMAN-ACTION-NEEDED`, stop the action, and permit only read-only polling on own diagnostic tabs.
2. Why: Safety invariant and clipboard lead decision.
3. Falsifiability: A wrong implementation that auto-reads clipboard on prompt, keeps trying to send through login wall, or reports success fails.
4. Required setup: Mock login wall, challenge, and clipboard permission prompt states; submit/fetch calls after the stop are forbidden.

### L3-ERR-07 — Allowlist/domain errors occur before navigation/fetch
1. Behavior: URLs or backend fetch targets outside the allowlist raise `DomainNotAllowedError` before any channel navigation/fetch side effect.
2. Why: Safety invariant, even in mock tests.
3. Falsifiability: A wrong implementation that calls `open_tab` or `fetch_in_page` before checking domain fails call-order assertions.
4. Required setup: Disallowed conversation URL and disallowed backend URL fixture; mock records attempted side effects.

### L3-ERR-08 — Redaction covers headers, cookies, raw response headers, private tab data, and non-salvage prompt/response text
1. Behavior: Error messages, details, stderr, status reports, fixtures produced by tests, JSONL metadata, and repr/log strings do not contain bearer/OAI headers, cookies, raw response headers, private operator tab data, prompt bodies, or assistant response text except the intentionally emitted/persisted salvage markdown.
2. Why: M3 §9 and header safety invariant.
3. Falsifiability: A wrong implementation that stores `authorization`, `oai-session-id`, cookie values, or prompt canaries in details/status fails canary scans.
4. Required setup: Mock canary values in headers, errors, request snapshots, DOM private text, prompt, and partial response; scan all public outputs/artifacts.

## Concurrency stub behavior

### L3-CONC-01 — `Session` is the sole owner of pool and budget stubs
1. Behavior: A persistent `Session` owns one `TabPool` stub and one `AdaptiveSendBudget` stub; lower modules receive leases and never instantiate or retain their own pool/budget.
2. Why: M3 §2.2 and §7 place lifecycle/orchestration ownership in Session.
3. Falsifiability: A wrong implementation that constructs a new pool/budget per send loses call history and cannot serialize same-conversation operations under the stub.
4. Required setup: Fake pool/budget constructors or injected stubs with identity/call counters; two sequential `ask` calls in one Session.

### L3-CONC-02 — Send submission is budget-gated, completion wait is not
1. Behavior: The budget stub gates prompt submission only; after a verified submit, completion waiting does not hold or consume the send budget.
2. Why: M3 §7 says AdaptiveSendBudget gates only prompt submission, not completion waiting.
3. Falsifiability: A wrong implementation that holds the gate during long completion blocks a second independent send attempt in the mock or records budget lease duration through completion.
4. Required setup: Budget stub with enter/exit timestamps under fake clock; long completion fixture; optional second send queued after first submission.

### L3-CONC-03 — No hard message cap is hidden in the budget stub
1. Behavior: The M4 budget stub may apply a politeness floor if chosen, but it must not enforce an arbitrary total message cap or account ceiling.
2. Why: M3 §7 says no hard message cap; defaults are unmeasured assumptions.
3. Falsifiability: A wrong implementation that fails the N+1th send with a cap error after a small fixed count must fail under repeated mock successes.
4. Required setup: Single Session, fake clock satisfying any politeness wait, repeated successful mock sends more than any suspicious small cap.

### L3-CONC-04 — Pool stubs own only tool-created tabs and never enumerate operator pages
1. Behavior: The pool stub returns/reuses only tabs it opened through the channel and does not inspect `context.pages` or private operator tabs.
2. Why: M3 §7 own-tab safety invariant.
3. Falsifiability: A wrong implementation that enumerates pages fails when the mock makes page enumeration unavailable or includes a poisonous private page.
4. Required setup: Mock channel with `open_tab` returning owned leases; page enumeration raises; optional private-page canary that must not appear in status/errors.

### L3-CONC-05 — Detach/close stubs never quit Chromium or close non-owned tabs
1. Behavior: `Session.detach(close_managed_tabs=True)` and pool close-all close only managed mock tabs and call channel detach; they never call browser quit or close unknown tabs.
2. Why: Safety invariant applies even to offline seam design.
3. Falsifiability: A wrong implementation invoking `quit`, closing all pages, or closing a foreign lease triggers mock guard failures.
4. Required setup: Mock channel with two owned tabs and one foreign/private sentinel; methods raise on quit or foreign close.

## Ambiguities to resolve before pinning final tests

- Prompt normalization is required but not fully specified in the read sections; tests should pin a clear normalization contract once implementation chooses it, and include raw-vs-normalized adversarial prompts.
- Exact `CaptureSource` and `CaptureFidelity` enum names are not in the requested sections; tests should assert semantic honesty and then pin final enum values from the data model.
- `StatusReport` exact field names are not in the requested sections; tests should assert the required schema semantics and pin names when the dataclass lands.
- `backend_check_interval_s=None` default value is intentionally deferred to measured channel/mock defaults; use explicit intervals for exact cadence tests.
- CLI `--project` for `ask` is listed in the verb table but not in the `Session.ask` signature; M4 should not assert live project send/create beyond parse/forward/fail-closed behavior until the lead resolves routing.
- CLI `loop` is listed in M3 §8 but the M4 instruction treats loop as a minimal stub; do not require full M7 loop/rate behavior in M4.
