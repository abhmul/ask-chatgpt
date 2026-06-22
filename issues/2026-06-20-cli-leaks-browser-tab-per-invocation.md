# BUG: ask-chatgpt CLI leaks a browser tab per invocation (no tab close on exit)

**Version:** 0.2.0 (installed pinned-stable). **Severity:** high for any looping/automated use.

## Symptom
Running `ask` / `scrape` (any CDP verb) repeatedly leaves a growing pile of open chatgpt.com tabs in the operator's browser. A perpetual driver that calls `scrape`+`ask`+`scrape` per iteration accumulated **18 open tabs to one conversation in minutes** (observed 2026-06-20, conv 6a374c1d).

## Root cause
`Session` opens a tab via `TabPool.acquire -> channel.open_tab(url)` and only `release`s it (marks unleased) — it never closes it. Tabs are closed solely in `Session.detach(close_managed_tabs=True)` / `Session.__exit__` (`tab_pool.close_all()`). But the CLI handlers (`cli.py` `_handle_ask`, `_handle_scrape`, `_handle_history`-via-create, etc.) construct the session and call `session.ask(...)`/`scrape(...)` **without a `with` block and without ever calling `detach()`**. So on normal CLI exit the managed tab is left open in the browser (pages created via Playwright `connect_over_cdp` persist after the client disconnects). Every invocation leaks ≥1 tab.

## Repro
1. `ask-chatgpt ask --selector-channel real <conv> "hi" >/dev/null` (×N).
2. `curl -s localhost:9222/json/list | jq '[.[]|select(.type=="page")]|length'` grows by ≥1 each time.

## Suggested fix
Wrap the session in a context manager (or `try/finally: session.detach()`) in every CLI handler so managed tabs are closed on exit. E.g. in `_handle_ask`:
```python
with _new_session(args) as session:
    answer = session.ask(...)
    _emit_payload(...)
```
(`Session.__exit__` already calls `detach()` which closes managed tabs.) Verify `ask`/`scrape`/`create`/`fetch`/`status`/`loop` all release+close their tabs on both success and error paths. Consider also an option to REUSE an existing tab for a conversation URL across invocations instead of always opening a new one.

## Mitigation in place (consumer side)
The weak-simplex perpetual driver (`tmp/weak-simplex-push/driver/driver.sh`) now calls a `reap_our_tabs()` that closes idle tabs **for its own conversation id only** (via `/json/list` + `/json/close/<id>`, never touching foreign tabs) at each iteration start and each completion poll, bounding live tabs. This is a workaround; the tool should close its own tabs.
