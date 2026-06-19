# Contract M7-T1b — menus.py Radix + draft-conversation send + real loop (OFFLINE editor)

You are a **single pi editor worker** for `ask-chatgpt-dev`, task **M7-T1b**. Repo `/home/abhmul/dev/ask-chatgpt`, branch **`rewrite-v2`**. You inherit **nothing** but this contract and the files it names. **First read and obey** `.claude/skills/manager/references/agent-rigor.md` and the `tdd` skill (`.claude/skills/tdd/SKILL.md`). This is **OFFLINE** work — **no browser, no network, no real sends** — mock-proven only. **Depends on M7-T1a being committed** (CdpChannel action path, `AdaptiveSendBudget.submission()/record_soft_signal/hard_pause`, `TabPool` idle-TTL). Build on the current `session.py`/`channels/`.

## Mission
Implement three offline pieces of M7, **TDD (red→green per behavior, vertical slices)**, mock-proven:
1. **`menus.py`** — executable label-driven Radix enumeration + select + **reflected-label verification**, fail-closed; **NEVER open `Recent files`/`Projects` submenus** (operator privacy).
2. **Draft-conversation send** — `Session.ask` into a FRESH chat (today `ask(conv_or_url=None)` raises `NotImplementedError` at `session.py:261–262`): open a new chat, send, **learn the server conversation_id**, eager-write under the real id, capture.
3. **Real `loop`** over the persistent `Session` (today `session.py:373–416` is a MOCK-ONLY fake): attach once → per iteration send → **verify-new-turn (gotcha-4)** → wait completion → capture → append transcript → yield; CLI emits JSONL; SIGINT salvage.

`uv run pytest` MUST stay green (baseline after T1a) and the **suite must remain offline and fast (< 3s)** — never introduce real `time.sleep`; drive timing via `ScriptedClock`.

## READ FIRST (authoritative inputs)
- `.claude/skills/manager/references/agent-rigor.md`, `.claude/skills/tdd/SKILL.md`.
- **T1a API surface you build on** (the T1a report was NOT produced — read the AUTHORITATIVE post-T1a SOURCE directly: `src/ask_chatgpt/session.py`, `src/ask_chatgpt/channels/cdp.py`, `src/ask_chatgpt/channels/mock.py`). Verified facts about what T1a committed (commits 9ee0897 + a0d33b5, suite 224 green): (a) `AdaptiveSendBudget` (session.py) exposes the context manager `submission()` — on enter it raises `HumanActionNeededError` if hard-paused, raises `PromptBudgetBusyError` if another submission is active, sleeps to honor politeness-floor + AIMD spacing, and on success bumps `successful_submissions` + the rate; plus `record_soft_signal(kind)` (multiplicative backoff), `hard_pause(reason)`/`resume()`, `snapshot()`. Wrap EACH real send in `with self.send_budget.submission():` exactly as the existing `ask` does (session.py ~369). (b) `TabPool.acquire(ref)/release(tab)/close_all()` open/lease/evict ONLY own tabs (LRU by `last_used` tick; it does NOT enumerate or close foreign tabs). (c) `CdpChannel` action methods (`fill`, `insert_text`, `click`, `hover`, `press`, `upload_files`) are now IMPLEMENTED (no longer raise `HumanActionNeededError`), mirroring `issues/cdp-send-repro/controller.mjs`. Do not re-implement these; call them through the `BrowserChannel` seam. The `MockChannel` scripts the same seam for offline tests.
- `src/ask_chatgpt/menus.py` — the stubs to make executable (`MenuOption`/`SelectionResult` dataclasses keep their shape).
- `src/ask_chatgpt/send.py` — `read_turn_baseline`, `wait_for_composer`, `fill_composer`, `submit_composer`, `verify_prompt_submitted` (gotcha-4 lives here), `wait_for_idle_and_reload_if_needed`, `normalize_prompt`.
- `src/ask_chatgpt/completion.py` — `wait_for_completion`, `salvage_partial`.
- `src/ask_chatgpt/capture.py` — `capture_conversation`, `SendContext` (how a captured turn is written to the store).
- `src/ask_chatgpt/identity.py` — `ConversationRef`, `conversation_url`, `parse_conversation_address`, project URL shapes; check how `conversation_url` handles a draft (`conversation_id=None`).
- `src/ask_chatgpt/store.py` — `resolve_conversation`, `put_conversation_ref`, `begin_send`, `commit_send`, `load_transcript`, `render_markdown`.
- `src/ask_chatgpt/cli.py` — `_handle_loop` (lines ~258–277), `_loop_envelope` (~327–342); the loop JSONL envelope shape.
- `src/ask_chatgpt/channels/base.py` — `BrowserChannel` Protocol, `TurnDomSnapshot` (has `model_labels`), `TabLease`.
- `src/ask_chatgpt/errors.py` — `ModelSelectionNotReflectedError`, `ToolSelectionNotReflectedError`, `PromptNotSubmittedError`, `CompletionTimeoutError`, `MaxTotalWaitExceededError`, `InternalError`, `HumanActionNeededError`.
- `team/evidence/reports/M3-detailed-design.md` §2.6 (menus), §6 (send), §8 (CLI loop) — authoritative design.
- `issues/cdp-send-repro/controller.mjs` — reference for the real menu/url behavior (read-only; do NOT edit/stage).

## Part 1 — menus.py executable Radix (fail-closed, label-driven)
Make the stubs executable. Use the channel seam via **named `evaluate` keys** (the pattern `capture.py` uses, e.g. `ask_chatgpt_capture_katex_annotations`) so the `MockChannel` can script them and `CdpChannel` runs real JS. Selectors come from the `SelectorMap`: model trigger candidates `selectors["model_picker_trigger_candidates"]` (`composer-footer button[aria-haspopup="menu"]`), tools trigger `selectors["tools_button"]` (`button[data-testid="composer-plus-btn"]`), portal `selectors["radix_portal"]` (`[data-radix-popper-content-wrapper]`).

- **`open_radix_menu(tab, trigger_selector)`** — `tab.channel.click(tab, trigger_selector)`, then confirm the portal exists (e.g. `wait_for_selector(radix_portal, state="visible")` or an enumerate returning non-empty). Fail-closed (raise) if the portal never appears.
- **`enumerate_radix_options(tab)`** — evaluate a named key (e.g. `ask_chatgpt_menu_enumerate`) returning **only** options inside `[data-radix-popper-content-wrapper]`: each `{label (normalized text), role (menuitem|menuitemradio), checked (bool|None from aria-checked), disabled (bool), path (tuple)}`. Map to `MenuOption`. **Do NOT descend into / open `Recent files` or `Projects` submenus** — if such a submenu trigger is present, it may be listed as an option but you must NEVER open it to enumerate inside it.
- **`select_radix_label(tab, label, *, role=None, submenu_path=())`** — enumerate; require **exactly one** enabled option whose `normalize_prompt(label)` matches (0 or >1 → fail-closed raise). If the target is behind a family submenu (`submenu_path` non-empty, e.g. `("GPT-5.5",)`), open that submenu trigger (NEVER `Recent files`/`Projects`) then enumerate+match the radio. Click the matched option by label via a named eval key (e.g. `ask_chatgpt_menu_click_label` with `{label, role, path}`). Return the chosen `MenuOption`.
- **`select_model(tab, selectors, label)`** — full fail-closed algorithm: locate the model trigger among the candidates (require an unambiguous current-model trigger), `open_radix_menu`, enumerate, `select_radix_label` (exact tier `menuitemradio` or family `menuitem`→radio), then **verify reflected**: re-read `tab.channel.query_turns(tab, selectors).model_labels` and require the requested label is reflected (use the existing `_reflected_model` helper). On reflect → `SelectionResult(requested, reflected, verified=True)`; on absent/ambiguous/not-reflected → `ModelSelectionNotReflectedError` (no further action). 
- **`set_tools(tab, selectors, labels)`** — open the tools menu (`tools_button`), enumerate, for each requested label toggle it (click by label) and **verify reflected** by re-enumerating and confirming the option's `checked` is True (or the tool chip is present). Fail-closed → `ToolSelectionNotReflectedError`. **NEVER open `Recent files`/`Projects` submenus.** Return a `SelectionResult` per tool.
- Keep `assert_reflected_model`/`assert_reflected_tools` delegating to `select_model`/`set_tools`.

**Mock support:** add the minimal `MockScenario`/`MockChannel` fields needed to script: the enumerated options when a menu is open (keyed by which trigger was clicked is ideal, but a single scripted enumeration per scenario is acceptable), a way to assert the click-by-label happened, and a way to drive the reflected `model_labels` after select (the existing `turn_timeline`/`model_labels` seam). Record menu clicks so tests can assert `Recent files`/`Projects` were NEVER opened.

**Falsifiable tests** (each MUST be able to fail):
- model select happy path: open→enumerate→select tier `High`→reflected `model_labels` shows `High`→`verified=True`.
- family submenu: select `GPT-5.5` (path `("GPT-5.5",)`) opens the family submenu then the radio; reflected.
- fail-closed absent: requesting a label not in the menu → `ModelSelectionNotReflectedError`, **nothing clicked/sent**.
- fail-closed ambiguous: two options share the label → raise, nothing selected.
- fail-closed not-reflected: select clicks but `model_labels` never reflects the request → `ModelSelectionNotReflectedError`.
- **never-open-forbidden**: a scenario whose menu includes `Recent files` and `Projects` submenu triggers → assert menus.py issues **zero** opens/clicks against them in every path (model select, tools set, enumerate).
- tools: toggling `Web search` reflects checked; absent tool → `ToolSelectionNotReflectedError`.

## Part 2 — draft-conversation send (fresh chat → learn id → eager-write)
Make `Session.ask(conv_or_url, prompt, ...)` support a **draft** (when `conv_or_url is None`, or a `ConversationRef` with `conversation_id is None` / `is_draft`):
- Resolve to a draft ref via `self.create(project=...)` semantics → new-chat URL (`https://chatgpt.com/`, or `/g/g-p-<project_id>` for a project draft). `TabPool.acquire` opens that own tab. (Confirm `conversation_url` returns the new-chat URL for a draft; fix if it doesn't.)
- `wait_for_idle_and_reload_if_needed` → optional model/tool selection (via T1's menus) → `read_turn_baseline` (a fresh chat has 0 user/assistant turns) → fill → submit → `verify_prompt_submitted` (gotcha-4: a NEW user turn carrying the prompt must appear, else `PromptNotSubmittedError` and stop — no id-learning, no completion wait).
- **Learn the server conversation_id**: after the verified new user turn, read the post-submit page URL via a named eval key (e.g. `ask_chatgpt_current_url` → `() => window.location.href`) which the SPA navigates to `https://chatgpt.com/c/<id>`. Parse the id (`identity.parse_conversation_address`). If no `/c/<id>` is learnable → fail-closed (`InternalError`/`PromptNotSubmittedError` with a clear reason). Build the real `ConversationRef(conversation_id=<learned>, …)`.
- **Eager-write under the real id**: `put_conversation_ref` + `begin_send`/`commit_send` for the user turn → `wait_for_completion` (newer assistant required) → `capture_conversation` → return the new assistant `TurnRecord`. On timeout/error, salvage partial as the existing `ask` path does.
- Refactor: factor the per-turn pipeline (`wait_idle → model/tools → baseline → begin_send → submission() → fill/submit/verify → commit_send → wait_completion → capture → select new assistant`) into a private `_run_send_turn(ref, prompt, …)` shared by `ask` (existing-id path), draft-`ask`, and `loop`, so gotcha-4 + eager-write + salvage are identical everywhere. Keep `ask`'s stdout/`--out` behavior unchanged (gotcha-4 of the CLI: stdout AND `--out`).

**Falsifiable mock tests:**
- draft happy path: submit yields a new user turn AND post-submit url `https://chatgpt.com/c/learned-123` → returned record `conversation_id == "learned-123"`; transcript written under that id; user+assistant turns present.
- draft id-not-learned: post-submit url stays `https://chatgpt.com/` → fail-closed raise (no transcript under a bogus id). Must be able to fail.
- draft gotcha-4: no new user turn → `PromptNotSubmittedError`; no id learned; no completion wait; nothing captured.

## Part 3 — real `loop` over the persistent Session
Replace the mock-only fake. `Session.loop(conv_or_url, *, message="keep pushing!!", model, tools, attach, timeout, max_total_wait, max_iterations, out_dir) -> Iterator[TurnRecord]`:
- One persistent attached `Session` (attach once; reuse the leased tab across iterations). For `i in range(max_iterations)`: call `_run_send_turn(ref, message, …)` (the shared pipeline → verify-new-turn each iteration via gotcha-4, governed by `self.send_budget` for human-paced spacing), append transcript (capture does), `yield` the new assistant `TurnRecord`.
- Works on **both** mock and cdp channels — REMOVE the `if channel != "mock": raise HumanActionNeededError` guard.
- `max_iterations` is workflow control, **not** an account cap; **no hidden message cap**.
- **SIGINT salvage**: on `KeyboardInterrupt` during an iteration, attempt `salvage_partial` of the in-flight turn, record/yield a partial `TurnRecord`, then stop cleanly.
- CLI `_handle_loop`: emit one JSONL envelope per yielded turn (existing `_loop_envelope`); on `KeyboardInterrupt`, emit a final partial envelope and `return 130`.

**Falsifiable tests:**
- loop 2 iterations (mock): two distinct new assistant turns (distinct `message_id`s), both in the transcript, `send_budget.successful_submissions == 2`, no cap.
- loop verify-each-turn: an iteration whose submit is a no-op → `PromptNotSubmittedError` (loop stops; gotcha-4 per iteration).
- loop SIGINT: `KeyboardInterrupt` mid-iteration → partial salvaged + loop stops; CLI test asserts exit 130 + a partial JSONL envelope.
- loop on cdp channel no longer raises the mock-only guard (structural).

## Safety / isolation (HARD RULES)
- Branch `rewrite-v2` only. **NEVER** checkout/commit/merge/move `stable`. **NEVER** `uv tool install/upgrade/reinstall` (use `uv run`/`uv sync`). **NEVER** `git push`.
- OFFLINE: no browser/CDP/network/real sends. **NEVER** edit or stage `issues/cdp-send-repro/controller.mjs` or the untracked `human/` dir; never stage `cache/`, `.pi-workers/`, or `team/state/*-manager-state.json`.
- Redaction: no auth/OAI/cookie/bearer values, no prompts/tokens/response bodies in code/tests/fixtures/logs (mock canaries are the only allowed sentinels).

## Commit policy (you commit your own TDD increments)
Sole editor during this run. Commit each green increment locally to `rewrite-v2`, explicit paths only — **never `git add -A`**. Suggested increments: (1) menus.py + mock menu support + tests; (2) draft-send (+ `_run_send_turn` refactor) + tests; (3) real loop + CLI SIGINT + tests. After each: `uv run pytest` green → `git add <explicit files>` → `git commit -m "M7-T1b: <area>"` (no `Co-Authored-By`, no push). Confirm `controller.mjs`/`human/` stay unstaged.

## Success criteria
- `menus.py` executable + fail-closed + reflected-verify + **never opens `Recent files`/`Projects`**; falsifiable tests.
- Draft-conversation send learns the server id + eager-writes + gotcha-4; falsifiable tests.
- Real `loop` over the persistent Session (mock+cdp), verify-each-turn, SIGINT salvage, no cap; CLI emits JSONL + exit 130 on SIGINT; falsifiable tests.
- `_run_send_turn` shared by ask/draft/loop. `uv run pytest` green (offline, < 3s). Increments committed (explicit paths). `stable` unmoved.

## Handoff (write `team/evidence/reports/M7-T1b.md`)
Status token at top; `uv run pytest` tail (N passed); commits (hashes + one-line); files changed; each new test's behavior + how it could fail (falsifiability); confirmation forbidden-submenu paths are never opened; confirmation `controller.mjs`/`human/` unstaged; blockers; complexity signals. No secrets/content. If low on budget: commit green work, write resume-ready PARTIAL, stop.
