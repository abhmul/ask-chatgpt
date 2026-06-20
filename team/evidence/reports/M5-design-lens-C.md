# M5 design lens C — offline testability, Protocol conformance, completion-vocab read, real-only seam

## 1. Recommendation

### Lazy-import boundary

Implement `src/ask_chatgpt/channels/cdp.py` as the only Playwright adapter, but keep it runtime-lazy: importing `ask_chatgpt`, `ask_chatgpt.channels`, and preferably `ask_chatgpt.channels.cdp` must not import any `playwright*` module. Use `Any`/`object` for runtime attributes and import Playwright only inside the production attach path, e.g. `_start_playwright()`.

```python
class CdpChannel:
    def __init__(self, *, cdp_endpoint="http://127.0.0.1:9222", allowlist=None, http_get_json=None, playwright_factory=None, monotonic=time.monotonic, sleeper=time.sleep):
        self._endpoint = cdp_endpoint.rstrip("/")
        self._allowlist = allowlist or Allowlist()
        self._http_get_json = http_get_json or _urllib_get_json
        self._playwright_factory = playwright_factory  # test-only fake hook; production None
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages: dict[str, object] = {}
        self._tab_urls: dict[str, str] = {}
```

Production `_start_playwright()` is the only place that imports `from playwright.sync_api import sync_playwright, Error, TimeoutError`. Offline tests inject a fake factory/context and assert `sys.modules` remains free of `playwright` until the production path is explicitly exercised.

Offline introspection performed only by imports, no CDP/browser calls: Playwright `1.60.0`; `sync_playwright() -> PlaywrightContextManager`; `BrowserType.connect_over_cdp(endpoint_url: str, *, timeout=None, slow_mo=None, headers=None, is_local=None, no_defaults=None) -> Browser`; `BrowserContext.new_page() -> Page`; `BrowserContext.new_cdp_session(page) -> CDPSession`; `Page.evaluate(expression: str, arg=None) -> Any`; `Page.expose_binding(name: str, callback: Callable) -> SyncContextManager`; `Page.on(event: str, f: Callable[..., None]) -> None`; `Request.all_headers() -> Dict[str, str]`.

### Offline-testable preflight

`preflight()` must use plain HTTP against `${cdp_endpoint}/json/version`, never Playwright. Make the HTTP getter injectable so unit tests use local stubs, not sockets.

```python
def preflight(self, *, timeout_s: float = 5.0) -> PreflightResult:
    try:
        info = self._http_get_json(f"{self._endpoint}/json/version", timeout_s)
    except HttpStatusError as exc:
        return _cdp_unreachable(self._endpoint, f"http_{exc.status}")
    except TimeoutError:
        return _cdp_unreachable(self._endpoint, "timeout")
    except OSError:
        return _cdp_unreachable(self._endpoint, "connection_refused")
    except ValueError:
        return _cdp_unreachable(self._endpoint, "invalid_json")
    browser = info.get("Browser") if isinstance(info.get("Browser"), str) else None
    protocol = info.get("Protocol-Version") if isinstance(info.get("Protocol-Version"), str) else None
    ws_present = isinstance(info.get("webSocketDebuggerUrl"), str) and bool(info["webSocketDebuggerUrl"])
    return PreflightResult(ok=ws_present, cdp_endpoint=self._endpoint, browser=browser, protocol_version=protocol, websocket_url_present=ws_present, error_code=None if ws_present else "CDP_UNREACHABLE", error=None if ws_present else "websocket_url_missing")
```

Map HTTP errors, timeout, connection-refused, invalid JSON, and missing websocket URL to `PreflightResult(ok=False, error_code="CDP_UNREACHABLE")`, with only redacted categorical `error` strings. Login/Cloudflare is not a preflight fact; it is classified later from own-tab navigation/status checks as `HumanActionNeededError`.

### Allowlist before Playwright and before page use

`open_tab(url)` must call `Allowlist.require_allowed_url(url)` before any lazy import, attach check, `context.new_page()`, navigation, or observer setup. `fetch_in_page(tab, url, ...)` must validate before page lookup/evaluate: allow single-slash same-origin paths such as `/backend-api/conversation/<id>`, reject protocol-relative `//...`, reject non-http schemes, and require the allowlist for absolute URLs. Unit tests should monkeypatch a fake Playwright importer that raises if touched and assert `DomainNotAllowedError` wins first.

### Protocol conformance and own-tabs-only construction

`CdpChannel` must satisfy every `BrowserChannel` method with the same names, keyword-only parameters, and return dataclasses: `TabLease(channel=self)`, `RequestSnapshot`, `FetchResult(status, headers, body_path, body_bytes)`, `TurnDomSnapshot`. Use offline fake pages to test method signatures and return types.

Own-tab discipline is primarily a construction invariant: store pages only in `self._pages` keyed by generated private tab ids; `open_tab` uses only `self._context.new_page()` and registers that returned page; `close_tab` looks up the lease id and closes only that page; `detach` disconnects the Playwright client but must never call `browser.close()` or inspect `context.pages`. Add a fake context whose `pages` property raises if accessed and a fake browser whose `close()` raises; tests should pass through open/close/detach without touching either.

### Pure streaming-decode helper from lens B seam

Factor the Python-side binding sink into a browser-free helper, with UTF-8 handled only after bytes are on disk.

```python
def decode_stream_chunk_base64(chunk: str) -> bytes:
    return base64.b64decode(chunk.encode("ascii"), validate=True)

def append_decoded_stream_chunk(sink: BinaryIO, chunk: str) -> int:
    data = decode_stream_chunk_base64(chunk)
    sink.write(data)
    return len(data)
```

The real `fetch_in_page(..., stream_to=raw_tmp)` should call this helper from its exposed binding and return `FetchResult(status, redacted_response_headers, body_path=raw_tmp, body_bytes=None)`. Non-streaming calls return `body_bytes` and `body_path=None`. Offline tests cover chunk order, invalid base64, split multibyte UTF-8 across chunks, byte count, and no request-header value logging.

### Completion-status vocabulary read mechanism

For M5 step 6, prefer a pure reader over any extra network: catalogue completion vocabulary from the already-captured `raw-mapping.json` after a successful scrape/capture. Implement a small function, e.g. `catalogue_completion_status_vocab(raw_path)`, that reads `async_status` at top level and walks `mapping` to collect enum/type counts for `node.status`, `message.status`, `metadata.is_complete`, `metadata.is_finalizing`, and `metadata.pro_progress`. Keep the report redacted: booleans and short enum-like strings can be counted verbatim; high-cardinality/free-text/object `pro_progress` should be summarized by type, keys, length, and hash rather than full content unless an attended evidence task explicitly approves the value.

Leave `/backend-api/conversation/<id>/stream_status` as a disabled, feature-gated read-only probe. If enabled in the attended leg, it must use freshly acquired one-use headers, record only status code/key names/redacted vocabulary, never persist the body or header values, and fall back to full raw-mapping vocabulary if unverified.

## 2. Alternatives considered and rejected

- Top-level Playwright imports: rejected because M4’s offline invariant is that public imports and mock tests never import Playwright.
- Preflight by `connect_over_cdp`: rejected because it would touch the operator browser and cannot be unit-tested offline; `/json/version` via injectable HTTP is sufficient.
- Allowlist after attach/new-page/evaluate: rejected because a bad URL must fail offline before Playwright import or page side effects.
- Unit tests that use real CDP/Chromium: rejected for T2; all browser/CDP behavior belongs to the attended real leg.
- Completion vocabulary by repeated full backend polling or default `stream_status`: rejected as expensive/empirical; raw-mapping cataloguing is simpler and already available after capture.

## 3. Offline-testable vs real-leg-only split

Offline-unit-tested: import/lazy-import invariants; `Session(channel="cdp")` construction and `status(probe_browser=False)` without Playwright; `preflight()` mapping via injected getter; allowlist failures before import; Protocol signatures/return types against fake pages; private page registry and no `context.pages`; close only known own pages; request-buffer predicate behavior with fake `RequestSnapshot`s; `fetch_in_page` return shape with fake evaluate/binding; base64 chunk decode/append; redaction/canary absence in repr/logged details; completion vocabulary reader over fixture raw mappings; optional `stream_status` flag routes to the expected mock path only when enabled.

Real-leg-verified-only: `sync_playwright().start()`; `chromium.connect_over_cdp`; choosing/using the existing CDP context without enumerating pages; `context.new_page()` against operator Chromium; real `page.goto`/reload/load-state behavior; live request observation and whether `request.all_headers()` contains `authorization`/`oai-*`; same-page raw CDP fallback; login/Cloudflare/rate marker classification; live in-page streaming bridge and 17 MB memory/RSS; actual `stream_status` existence, auth, response shape, and semantics.

## 4. Redaction points

Request header values may live only in memory: Playwright request object → short-lived lower-cased required-header dict in a private request buffer → `RequestSnapshot.headers` returned to `capture.acquire_backend_headers` → `HeaderBundle._headers` → one `fetch_in_page` argument. They must not appear in `repr`, `MockCall`/Cdp call logs, exceptions, status reports, fixtures, raw mapping, transcript JSONL, or evidence reports. Drop irrelevant request headers, especially cookies, before constructing `RequestSnapshot` unless a future contract explicitly needs them.

`fetch_in_page` must delete/local-drop its request header dict after evaluation returns/raises. `FetchResult.headers` are response headers only; redact/omit `set-cookie`, `authorization`, `cookie`, and `oai-*` defensively. Preflight errors store only categorical reasons. Completion vocabulary reports come from raw response content, not request metadata; optional `stream_status` probes must log only redacted status/key/vocab facts.

## 5. Uncertainties the attended real leg must confirm

- Whether Playwright 1.60.0 `request.all_headers()` exposes all eight required live request headers on the tool-owned page.
- Whether the raw CDP `Network.requestWillBeSentExtraInfo` fallback is needed and correlates cleanly by request id.
- Whether login/Cloudflare/rate-limit markers are detectable from own diagnostic tabs without reading operator tabs.
- Whether the exposed-binding streaming path stays within the memory budget on the smoke conversation and later the ~17 MB target.
- Which real `async_status`, node/message `status`, `is_complete`, `is_finalizing`, and `pro_progress` values occur during active/finalizing/complete states.
- Whether `/backend-api/conversation/<id>/stream_status` exists, requires the same headers, and returns a useful lightweight shape.

## 6. Editor checklist

- Add `channels/cdp.py` with no top-level Playwright import and wire `Session._channel()` for `channel="cdp"` only.
- Add injected `http_get_json` preflight tests for ok, HTTP error, timeout, connection refused, invalid JSON, and missing websocket URL.
- Add allowlist-before-import tests for `open_tab` and `fetch_in_page`, including `//evil`, `javascript:`, and absolute disallowed hosts.
- Add fake context/page tests proving `context.pages` and `browser.close()` are never touched and only private pages are closed.
- Add Protocol/signature and return-shape tests for `TabLease`, `RequestSnapshot`, and streamed/non-streamed `FetchResult`.
- Add canary redaction tests for request headers, response headers, errors, reprs, and status output.
- Add pure chunk decode/append tests and keep decoding as bytes until JSON parsing from disk.
- Add `catalogue_completion_status_vocab(raw_path)` tests over fixtures and keep `stream_status` disabled behind an explicit feature flag until attended verification.
