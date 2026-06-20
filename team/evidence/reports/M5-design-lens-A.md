# M5 design lens A — CDP attach lifecycle, own-tab request/header observation

Offline design only. I did not touch the browser, CDP endpoint, ChatGPT/OpenAI network, or source files.

## 1. Recommendation

### Playwright 1.60.0 API facts used

Offline introspection showed `BrowserType.connect_over_cdp(endpoint_url, *, timeout=None, slow_mo=None, headers=None, is_local=None, no_defaults=None) -> Browser`, `Browser.contexts` is a property, `BrowserContext.new_page() -> Page`, `BrowserContext.new_cdp_session(page) -> CDPSession`, `Page.goto(url, *, timeout=None, wait_until=None, referer=None)`, `Page.reload(*, timeout=None, wait_until=None)`, `Page.wait_for_load_state(state=None, *, timeout=None)`, `Page.wait_for_timeout(timeout)`, `Page.close(*, run_before_unload=None, reason=None)`, `Page.on(event, f)`, `Page.remove_listener(event, f)`, `Request.all_headers() -> Dict[str, str]`, `Request.headers` is a property, `CDPSession.send(method, params=None) -> Dict`, `CDPSession.on(event, f)`, `CDPSession.detach()`, and `Playwright.stop()`. Playwright generated docs state `Request.headers` omits security-related headers, including cookie-related ones, while `Request.all_headers()` returns all request HTTP headers with lower-cased names; therefore `request.headers` is rejected for auth capture and `request.all_headers()` is the primary mechanism. CDP protocol typings in the installed package state `Network.requestWillBeSentExtraInfo.headers` are raw request headers as sent over the wire and that `requestWillBeSent` / `requestWillBeSentExtraInfo` ordering is not guaranteed.

### Preflight: urllib only, no Playwright

`CdpChannel.preflight(timeout_s=5.0)` should perform a plain local HTTP GET to `<cdp_endpoint>/json/version` using `urllib.request.urlopen(..., timeout=timeout_s)`, not Playwright. On success, parse JSON and return `PreflightResult(ok=True, cdp_endpoint=<endpoint>, browser=data.get("Browser"), protocol_version=data.get("Protocol-Version"), websocket_url_present=bool(data.get("webSocketDebuggerUrl")))`; never store or return the websocket URL value. On timeout, connection refusal, invalid JSON, or HTTP error, return `PreflightResult(ok=False, ..., error_code="CDP_UNREACHABLE", error=<redacted class/reason>)`. `preflight` should not infer login state; login/Cloudflare is an own-tab navigation/read concern.

### Attach: CDP connect, existing context, no page enumeration

Use a lazy Playwright import inside `attach`, then `pw = sync_playwright().start()` and `browser = pw.chromium.connect_over_cdp(self.cdp_endpoint, timeout=timeout_s * 1000)`. Obtain the persistent signed-in context with `contexts = browser.contexts; context = contexts[0]` after checking at least one context exists. Do not call `context.pages`, do not iterate pages, do not call `browser.new_page()` or `browser.new_context()`, and do not use Playwright `launch`. If more than one context appears, do not inspect pages to disambiguate; use `contexts[0]` only if the attended run confirms that is Playwright's existing default context, otherwise fail closed.

### Open tab: create only an owned page, register observers before navigation

`open_tab(url)` must run `Allowlist.require_allowed_url(url)` before any Playwright action. Then create exactly one page with `page = context.new_page()`, allocate a private `tab_id`, store `{tab_id: _TabState(page=page, url=url, ... )}`, and return only `TabLease(tab_id, url, self)`. Register page-scoped observers before `page.goto`: `page.on("request", on_request)` and `page.on("requestfinished", on_requestfinished)`. Do not use `context.on("request")`, because that would observe foreign/operator pages in the shared context.

Recommended fallback setup is also before navigation: create a same-page CDP session with `cdp = context.new_cdp_session(page)`, register `cdp.on("Network.requestWillBeSent", ...)` and `cdp.on("Network.requestWillBeSentExtraInfo", ...)`, then `cdp.send("Network.enable")`. This is still own-page-only. It is necessary if the fallback must work without an extra reload, because `requestWillBeSentExtraInfo` is not retroactive.

Navigate with `page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)`; avoid `networkidle` for ChatGPT's SPA. If known login/challenge markers are detected on the owned page, raise `HumanActionNeededError` and do not automate login/challenge. The exact markers are real-leg evidence, not an offline claim.

### Request observation and `wait_for_request`

Event handlers must not call `request.all_headers()`; in the sync API, do that from `wait_for_request` after events are buffered. The `request` handler should record only cheap metadata (`url`, `method`, sequence/time, and the Playwright `Request` object) for the owned page. `requestfinished` should mark completion/cleanup only. `wait_for_request(tab, predicate, timeout_s)` validates the private tab, scans its buffered observations from a per-tab cursor, and pumps future events with short `page.wait_for_timeout(...)` slices until timeout.

To minimize secret exposure while preserving the current capture contract, first call the predicate with a cheap `RequestSnapshot(url, method, headers={})`. The current driver in `capture.acquire_backend_headers` predicates only on method/path, so this selects the target before any sensitive values are materialized. For a cheap match, call `request.all_headers()`, immediately lower/select only `REQUIRED_CAPTURE_HEADERS`, delete the raw header dict, wrap the selected mapping in a redacted-`repr` mapping, and build `RequestSnapshot(url, method, headers=selected)`. If the selected set is complete and the predicate still matches, return it.

Primary answer to the header-exposure question: use `Request.all_headers()`, not `Request.headers`. The installed Playwright API contract says `all_headers()` is the complete lower-cased request-header set, while `headers` is explicitly partial. The attended real leg must still confirm the live ChatGPT request includes all eight required names via `all_headers()`.

### CDP fallback for missing required names

If `all_headers()` lacks any required name, consult the already-enabled same-page CDP observer before returning a deficient snapshot. The CDP observer correlates `Network.requestWillBeSent` and `Network.requestWillBeSentExtraInfo` by `requestId`; because ordering is unspecified, store only selected required header names/values from ExtraInfo while waiting for the matching URL/method, never the full raw header map or `associatedCookies`. When both sides are known for a `GET` whose path is `/backend-api/conversation/<id>`, append a fallback `RequestSnapshot` with the selected required headers. If CDP provides the complete set, return that snapshot. If CDP also misses names by timeout, return the best deficient snapshot so `capture.acquire_backend_headers` raises `BackendAuthUnavailableError` with missing names, not values.

Reacquisition should be non-intrusive: observers live for the owned tab lifetime, while `wait_for_request` uses cursors and consumes only matching observations. A second header acquisition waits for a later already-observed/future SPA request; it must not reload, navigate, inspect foreign tabs, or read storage. If policy wants a reload, a higher-level caller must explicitly call `reload(tab)`; `wait_for_request` itself is passive.

### Reload, load wait, close, detach

`reload(tab)` validates the private tab, re-checks the current owned-page URL against the allowlist if available, and calls `page.reload(wait_until="domcontentloaded")`; the existing observers remain installed. `wait_for_load_state(tab, timeout_s=...)` validates the private tab and calls `page.wait_for_load_state("domcontentloaded", timeout=timeout_s * 1000)` unless a caller-specific state is later added.

`close_tab(tab)` validates `tab.channel is self` and `tab_id in self._tabs`, detaches the page CDP session if present, removes page listeners if possible, calls `page.close(run_before_unload=False, reason="ask-chatgpt close_tab")`, clears any pending selected header dicts, and deletes only that private tab state. It must never read or close `context.pages`.

`detach()` should best-effort close remaining own pages, clear own state, then disconnect the Playwright/CDP client without quitting Chromium. Python has no public `browser.disconnect()` in 1.60.0; use `browser.close(reason="ask-chatgpt detach")` only for a browser obtained by `connect_over_cdp`, then `playwright.stop()`. The installed Python docs say `Browser.close()` on a connected browser disconnects from the browser server, and the bundled server source for `connectOverCDP` sets the browser process close/kill handlers to close the CDP WebSocket transport (`chromeTransport.closeAndWait`) rather than killing the OS browser process. The attended leg must still verify that operator Chromium and foreign tabs remain alive after detach.

## 2. Alternatives considered and rejected

- Reusing or inspecting existing tabs via `context.pages`: rejected; it violates own-tab discipline and can leak operator/other-agent content.
- `context.on("request")` or browser-global CDP sessions: rejected; they observe the shared context/browser, not only the owned page.
- `browser.new_context()` / `browser.new_page()`: rejected; new contexts may not share the operator's authenticated profile and create lifecycle ambiguity.
- `Request.headers`: rejected by Playwright docs because it omits security-related headers; use `Request.all_headers()`.
- Enabling CDP fallback only after `all_headers()` misses: rejected for the no-extra-reload requirement because CDP ExtraInfo is not retroactive.
- Reading cookies, localStorage, IndexedDB, JS globals, app internals, or HAR: rejected as broader and more fragile than observing the owned page's own request.
- Calling `context.close()` or Playwright `launch`: rejected; default context close is invalid/destructive, and launch is Cloudflare-blocked and out of scope.

## 3. Offline-testable vs real-leg-only

Offline-testable: preflight result mapping via an injectable URL opener/local stub; fake Playwright lifecycle order (`connect_over_cdp`, `browser.contexts[0]`, `context.new_page`, no `context.pages`, no `launch`); own-tab validation and close-only-owned behavior with fake pages; observer buffering without calling `all_headers()` inside callbacks; `wait_for_request` cheap-predicate filtering, selected-header projection, redacted mapping `repr`, timeout behavior; CDP `requestWillBeSent` / `requestWillBeSentExtraInfo` out-of-order correlation by fake `requestId`; allowlist rejection before Playwright action.

Real-leg-only: successful `connect_over_cdp` to operator Chromium; whether `browser.contexts[0]` is the correct signed-in persistent context when other agents are active; whether `context.new_page()` inherits the needed ChatGPT auth; live navigation timing and whether it triggers the target backend request without reload; whether `request.all_headers()` exposes all eight required ChatGPT header names; whether same-page CDP ExtraInfo sees the same headers if primary misses; whether `browser.close()` after CDP attach leaves Chromium and foreign tabs alive; login/Cloudflare/rate marker detection.

## 4. Redaction points

Do not log or persist header values at any point. In handlers, store URL/method/request object only; for CDP ExtraInfo, immediately project to the required-name allowset and discard raw headers/cookies. In `wait_for_request`, `raw = request.all_headers()` lives only in a local variable, is projected to selected required headers, then deleted. Return `RequestSnapshot.headers` as a `Mapping[str, str]` whose `__repr__` redacts values; optionally also make `RequestSnapshot` `repr=False` as a hardening change. Internal queues must not retain selected header values after a snapshot is consumed, superseded, timed out, or the tab closes. Errors/status/details may include sanitized URL, method, conversation id, and header names/missing names only, never values. `HeaderBundle` already uses `repr=False`; after `for_single_fetch()` the copied dict should be passed directly to the page fetch path and then allowed to go out of scope. No fixtures, raw mapping, transcript, logs, or report should contain `authorization`, `oai-*`, cookie, or selected header values.

## 5. Uncertainties the attended real leg must confirm

- `Request.all_headers()` on the live ChatGPT backend conversation request includes exactly the required names, including `authorization` and all `oai-*` / `x-openai-target-*` names.
- Same-page CDP `Network.requestWillBeSentExtraInfo` supplies the required names if `all_headers()` does not, and page-level CDP sees the request even if service workers are involved.
- `browser.contexts[0]` is the correct existing signed-in context under the operator's running Chromium.
- `page.goto(..., wait_until="domcontentloaded")` plus passive waiting observes the SPA backend request; if not, the explicit caller reload policy must be measured.
- `browser.close()` on this `connect_over_cdp` browser disconnects only the Playwright client and leaves Chromium/foreign tabs running.
- Login, Cloudflare, and rate-limit markers that should map to `HumanActionNeededError` from own tabs only.

## 6. Editor checklist

- Add `CdpChannel` with lazy Playwright import and wire `Session._channel()` for `cdp` only after offline tests pin no Playwright import for mock use.
- Implement `preflight` with `urllib` `/json/version`, redacting websocket URL to a boolean.
- In `attach`, call `connect_over_cdp`, use `browser.contexts[0]`, and never call `context.pages`.
- In `open_tab`, allowlist first, create `context.new_page()`, register page-scoped observers and same-page CDP fallback before `goto`, then return a private `TabLease`.
- Implement `wait_for_request` as a passive buffered observer with primary `request.all_headers()`, selected required headers only, CDP fallback by `requestId`, redacted mapping repr, and no reload.
- Implement `reload`, `wait_for_load_state`, `close_tab`, and `detach` with private-tab validation; close only own pages; use `browser.close()` only for CDP-connected browsers and then `playwright.stop()`.
- Add offline fake tests proving no `context.pages`, no global request observers, no header-value repr/logging, correct out-of-order CDP correlation, and own-pages-only cleanup.
- In the attended run, verify the listed uncertainties before trusting the live scrape path.
