# M11 (verify) — Does the CLI leak a browser tab per invocation?

**Status:** DONE
**Verdict:** UNRESOLVED — `ask`, `scrape`, and `loop` leak a managed chatgpt.com tab on **both** the success and post-acquire error paths (`loop` also leaks on its `KeyboardInterrupt`→`130` path). `create`, `history`, `fetch`, `status` never acquire a tab and so do **not** leak (despite also lacking detach).

Round: Round-1 read-only verification (static code analysis only; no fix applied, no tests run, no browser/CDP/network). Branch `fix/m10-light-read-scrape` (working-tree content == merged `main`).

---

## 1. Verdict — per-handler table (re-derived from ground truth)

| handler | acquires a tab? | closed on SUCCESS? | closed on ERROR? | leaks? |
|---|---|---|---|---|
| **ask** | **Yes** — `session.ask` → `tab_pool.acquire(ref)` (`session.py:370`) → `channel.open_tab` (`session.py:98`) | **No** — `_handle_ask` returns `0` with no `with`/`detach`/`finally` (`cli.py:188-203`); `ask`'s own `finally` only `release`s (`session.py:384-385`) | **No** — error propagates to `main` (`cli.py:90-108`) which maps→exit code, no detach | **LEAKS (both)** |
| **scrape** | **Yes** — `session.scrape` → `tab_pool.acquire(ref, render=False)` (`session.py:525`) | **No** — `_handle_scrape` returns `0`, no cleanup (`cli.py:224-228`); `scrape` `finally` only `release`s (`session.py:531-532`) | **No** — propagates to `main`, no detach | **LEAKS (both)** |
| **loop** | **Yes** — `session.loop` → `tab_pool.acquire(ref)` (`session.py:583`) | **No** — `_handle_loop` returns `0`, no detach (`cli.py:289`); `loop` `finally` only `release`s (`session.py:605-606`) | **No** — catches `KeyboardInterrupt`→`return 130` with no `finally` (`cli.py:282-288`); other errors → `main`, no detach | **LEAKS (success, error, AND interrupt/130)** |
| create | No — `Session.create` only builds a `ConversationRef` (`session.py:341-351`); no `acquire` | n/a (no tab) | n/a | no leak |
| history | No — `Session.history` = `store.load_transcript(...)` (`session.py:534-535`); pure local read | n/a | n/a | no leak |
| fetch | No — `Session.fetch` reads local transcript/cache (`session.py:537-561`); no `acquire` | n/a | n/a | no leak |
| status | No — `Session.status` may call `_channel().preflight()` (`session.py:627-628`), but preflight is an HTTP GET of `/json/version` only (`cdp.py:552-587`); page creation lives solely in `open_tab` (`cdp.py:635-651`), never called | n/a | n/a | no leak |

(`export` is an alias of `_handle_history` — `cli.py:151-154` — so it is also tab-free.)

### Root cause (confirmed end-to-end)
1. `_new_session` (`cli.py:183-185`) constructs `Session(...)`; `Session.__init__` (`session.py:266-303`) sets `_attached=False` and opens **nothing** — tab opening is lazy.
2. The leaking verbs call `tab_pool.acquire` → `self._session.attach()` (`session.py:88`) → `channel.open_tab(url)` (`session.py:98`), which on CDP does `context.new_page()` + `page.goto(...)` (`cdp.py:639,650`).
3. Each verb's internal `finally` calls `tab_pool.release` (`session.py:103-109`) which **only flips `leased=False`** — it never closes the page.
4. The **only** close path is `Session.detach()` → `tab_pool.close_all()` → `entry.tab.channel.close_tab(entry.tab)` (`session.py:326-328`, `112-118`) → on CDP `state.page.close(run_before_unload=False)` (`cdp.py:668`). **No CLI handler ever calls `detach()` / `__exit__` / `with`.** `main` (`cli.py:80-108`) maps errors to exit codes but never detaches.

Net: every `ask`/`scrape`/`loop` invocation opens a page and leaves it open — matching the issue's observed "~18 tabs in minutes."

> Note on the issue prose: `issues/2026-06-20-...md` enumerated the leakers imprecisely ("`_handle_ask`, `_handle_scrape`, `_handle_history`-via-create, etc."). Ground truth shows `history`/`create`/`fetch`/`status` are tab-free and do **not** leak; the real leakers are `ask`/`scrape`/`loop`. (agent-rigor: verify every claim, including the contract/issue, from code.)

---

## 2. What was verified (files, file:line, method)

**Independent manager re-derivation** (read directly, not via the worker):
- `src/ask_chatgpt/cli.py` (full): handlers `_handle_ask` 188-203, `_handle_create` 206-221, `_handle_scrape` 224-228, `_handle_history` 231-235, `_handle_fetch` 238-246, `_handle_status` 249-256, `_handle_loop` 259-289; `_new_session` 183-185; `main` 80-108. No `with`/`detach`/`finally: detach` in any handler.
- `src/ask_chatgpt/session.py` (full): `TabPool.acquire` 84-101, `release` 103-109 (no close), `close_all` 112-122 (real `close_tab`), `Session.detach` 326-331, `__enter__`/`__exit__` 333-339, `attach` 320-324, `ask` 353-385, `scrape` 516-532, `loop` 563-606, `create` 341-351, `history` 534-535, `fetch` 537-561, `status` 608-660.
- `src/ask_chatgpt/channels/cdp.py` 540-679: `preflight` 552-587 (HTTP GET only — no page), `attach` 595-609 (`connect_over_cdp`), `open_tab` 635-651 (`new_page`), `close_tab` 653-670 (**`page.close()` @668** — confirms close machinery is real), `detach` 611-633 (also closes all tracked tabs).
- `src/ask_chatgpt/channels/mock.py` 196-300: `MockChannel` records calls; `call_order` (240) + `method_counts` (244) derived from `self.calls`; `open_tab` records (293), `close_tab` records (300) → the falsifiable test below is feasible with existing infra.
- `tests/test_cli.py` 88-190: the `RecordingSession` stub (monkeypatched over `cli.Session`, `:176`) records verb calls only; **has no `detach`/`__enter__`/`__exit__` and no tab model.** Grep of `tests/test_cli.py` for `detach|__exit__|__enter__|close_tab|close_all|with _new_session` → **No matches.** ⇒ no existing test pins handler lifecycle cleanup, which is why the leak shipped uncaught.

**pi worker** (producer): one read-only worker, tools `read,grep,find,ls,bash` (no `edit`/`write`), launched via `pi-watch.sh --wait-seconds 1500 --tools read,grep,find,ls,bash`. Run dir `.pi-workers/pi-20260622-103302-3075926-11749`; `status`=`0`; `output.log`=43 lines; first line `M11-VERDICT: UNRESOLVED`. Produced the per-handler matrix + fix spec. Its verdict and table match the manager's independent re-derivation.

**Read-only invariant confirmed:** `git status --short` shows **no `src/` modification**; `stable` unmoved at `bbbe027`; no commits/push. (` M issues/cdp-send-repro/controller.mjs` is pre-existing/off-limits; ` M team/state/live-state.json` is concurrent team-lead/M12/M13 activity, not M11 — the M11 worker had no write/edit tools.)

---

## 3. Artifacts + trust level

| artifact | trust |
|---|---|
| `team/evidence/handoffs/M11-verify-cli-tab-leak.md` (this file) | **verified-independently** — manager re-derived every claim from source file:line |
| `.pi-workers/pi-20260622-103302-3075926-11749/output.log` (worker report) | **producer-only** — corroborated by the manager's independent re-derivation; not authoritative on its own |

---

## 4. Blockers

None. The fix itself is a later, separate, **serialized Round-2** task gated on operator review (per `M-backlog-common.md`); this round is verify-only.

---

## 5. Recommended next mission — exact Round-2 fix spec

**Scope of edits:** production change is confined to **`src/ask_chatgpt/cli.py`**; tests in **`tests/test_cli.py`** (stub update + new falsifiable tests). **Do NOT modify `session.py`/`channels/cdp.py`/`channels/mock.py`** — the Session/channel close machinery is already correct (`close_all`→`close_tab`→`page.close`, verified `cdp.py:668`).

### 5a. Production edit (cli.py)
Wrap the post-`_new_session` body of the three leaking handlers in `try/finally: session.detach()`:

```python
def _handle_ask(args):
    conv, prompt = _split_ask_positionals(args.args)
    session = _new_session(args)
    try:
        answer = session.ask(conv, prompt, model=args.model, tools=tuple(args.tool),
                             attach=tuple(args.attach), timeout=args.timeout,
                             max_total_wait=args.max_total_wait, out=args.out)
        content = answer.content_markdown if isinstance(answer, TurnRecord) else str(answer)
        _emit_payload(_ask_payload(content), args.out, args.data_dir, session)
        return 0
    finally:
        session.detach()
```

Same shape for `_handle_scrape` (224-228) and `_handle_loop` (262-289). For `loop`, keep the negative-`max_iterations` `ValueError` **before** the `try` (it runs before any session/tab, so no leak there), then wrap from `session = _new_session(args)` onward; the existing inner `try/except KeyboardInterrupt: return 130` sits **inside** the new outer `try`, so `finally: session.detach()` runs on the `130` return, the `0` return, and any propagated exception.

**Why `try/finally: session.detach()` and NOT `with _new_session(args) as session:`** — `Session.__enter__`→`attach()` (`session.py:333-334,320-324`) eagerly opens a CDP `connect_over_cdp` connection. Using `with` on the tab-free handlers (`history`/`fetch`/`status`, esp. `status --no-browser-probe`) would force a browser connection they currently never make — a regression. By contrast `session.detach()` is a **safe no-op** when nothing was attached: `close_all()` is a no-op on an empty pool, and channel-detach is guarded by `if self._attached` (`session.py:326-331`). Return codes and the `--out`/stdout/partial-on-timeout behavior are preserved because `finally` swallows neither the return value nor the exception (the `main` `CompletionTimeoutError`/`AskChatGPTError`→exit-code mapping at `cli.py:90-108` is unaffected).

`create`/`history`/`fetch`/`status` need **no** change to fix the leak (they never acquire a tab). Optionally add the same `try/finally: session.detach()` to all 7 for uniform defense-in-depth — it is a safe no-op for the tab-free ones — but it is not required.

### 5b. Test-stub update (REQUIRED — the detail to not miss)
`tests/test_cli.py` `RecordingSession` (~88-176) is monkeypatched over `cli.Session` by every existing CLI test. Once handlers call `session.detach()`, those tests will raise `AttributeError` unless the stub gains the method:

```python
def detach(self, *, close_managed_tabs: bool = True):
    self.calls.append(("detach", (), {"close_managed_tabs": close_managed_tabs}))
```

(If the `with` form were chosen instead, `__enter__`/`__exit__` would be required — another reason to prefer `try/finally`.) The worker's fix spec omitted this; without it the existing `test_cli.py` suite breaks.

### 5c. Falsifiable test (tests/test_cli.py) — provably fails pre-fix
Drive each tab-acquiring handler against a **real `Session` + `MockChannel`** so open/close are observable (mirrors the existing `tests/test_session_stubs.py` style, which already drives `Session(channel=MockChannel())` and asserts `open_tab`):

- Mechanism: `monkeypatch.setattr(cli, "_new_session", lambda args: Session(data_dir=tmp_path, channel=mock_channel, selector_map=<mock map>))`, where `mock_channel` is a `MockChannel` scripted via `tests/mock_scenarios.py` to let `ask`/`scrape`/`loop` complete. The test holds the `mock_channel` reference.
- **Success assertion:** `code == 0`; `mock_channel.method_counts.get("open_tab", 0) == 1`; `mock_channel.method_counts.get("close_tab", 0) == 1`; and `"close_tab"` follows `"open_tab"` in `mock_channel.call_order`.
  - **Falsifiability:** pre-fix `close_tab == 0` (handlers never detach; `Session` only `release`s) → **test FAILS**; post-fix `close_tab == 1` → passes.
- **Error path:** script the channel/step to raise after `open_tab` (e.g. a `PROMPT_NOT_SUBMITTED`/completion error). Assert `main` returns the mapped exit code (e.g. `30`) **and** `method_counts["close_tab"] == 1`. Pre-fix `close_tab == 0`.
- **loop interrupt:** scenario raising `KeyboardInterrupt` mid-loop; assert `return 130` **and** `close_tab == 1`.

### 5d. Parallelism / file-conflict notes
- M11 fix touches only `cli.py` + `tests/test_cli.py`.
- **M13** (per `M-backlog-common.md`) touches `capture.py` / `tests/test_capture.py` — **disjoint**, no conflict.
- **M12** is read-only (rate-limit verification) — no source conflict.
- Single-writer-per-file still applies: any other Round-2 task that also edits `cli.py` or `tests/test_cli.py` must serialize with this one.

---

## 6. Complexity / paradigm-shift signals

- **Low complexity, high confidence.** Localized to 3 handlers; the underlying close machinery already works. No paradigm shift needed for the fix.
- **Design signal (for the lead, optional):** the leak exists because tab lifecycle is owned by `Session.detach()` while the CLI's atomic verbs construct a per-invocation `Session` and never detach — the spec's "atomic ops attach→act→detach" intent (REWRITE-SPEC decision C) is not enforced structurally. A more robust paradigm than three per-handler `try/finally` blocks would be a **single cleanup site** in `main` (wrap `args.handler(args)` so every verb detaches, or have handlers receive an already-managed session). For the bounded Round-2 fix, per-handler `try/finally` on `ask`/`scrape`/`loop` is the minimal correct change; the broader refactor can be a separate item.
- Once the fix lands, the consumer-side mitigation (`reap_our_tabs()` in the weak-simplex driver) can be retired.
- Re-derivation corrected the issue's imprecise leaker list (prose said `history`-via-`create` leaks; ground truth: it is tab-free) — a reminder that handler-level claims must come from code, not the issue text.
