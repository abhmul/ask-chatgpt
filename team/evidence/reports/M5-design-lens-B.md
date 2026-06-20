# M5 design — Lens B: streaming in-page fetch to disk

## 1. Recommendation

Primary mechanism: implement `CdpChannel.fetch_in_page(..., stream_to=raw_tmp)` with same-page `fetch()` plus `ReadableStreamDefaultReader`, pumping base64-encoded byte chunks through a page-scoped Playwright binding into a Python binary file handle. Use `page.expose_binding`, not `expose_function`, because the binding callback receives `source` and can assert the call came from the expected own page. Offline introspection of Playwright 1.60.0 sync API found: `Page.expose_binding(self, name: str, callback: Callable) -> SyncContextManager`, `Page.expose_function(self, name: str, callback: Callable) -> SyncContextManager`, `Page.evaluate(self, expression: str, arg: Optional[Any] = None) -> Any`, `APIRequestContext.get(...) -> APIResponse`, and `APIResponse.body(self) -> bytes`; docs for `APIResponse.dispose` say the response body stays in memory until disposed, so APIRequestContext is not a streaming solution.

Call sequence for `stream_to`:

```python
# after tab/page validation and before any network action
absolute = resolve_relative_to_tab_url(tab.url, url)
allowlist.require_allowed_url(absolute)
stream_to.parent.mkdir(parents=True, exist_ok=True)
stream_id = uuid.uuid4().hex
binding_name = f"__ask_chatgpt_stream_{stream_id}"
state = StreamState(stream_id=stream_id, next_seq=0)

with stream_to.open("xb") as out:
    def sink(source, event):
        if source.get("page") != page:  # real leg confirms wrapper equality/identity behavior
            raise RuntimeError("stream binding called from unexpected page")
        return consume_stream_event(state, event, out.write)  # pure tested helper

    binding = page.expose_binding(binding_name, sink)
    try:
        meta = page.evaluate(JS_STREAM_FETCH, {
            "bindingName": binding_name,
            "streamId": stream_id,
            "url": url,                 # relative path is OK after absolute allowlist check
            "method": method,
            "headers": dict(headers or {}),
            "bodyText": body if isinstance(body, str) else None,
            "bodyB64": base64.b64encode(body).decode("ascii") if isinstance(body, bytes) else None,
            "chunkBytes": 128 * 1024,
            "timeoutMs": None if timeout_s is None else int(timeout_s * 1000),
        })
    finally:
        binding.close()
    out.flush()

if not state.done:
    raise BackendCaptureShapeError("backend stream ended without done marker")
return FetchResult(status=int(meta["status"]), headers=safe_response_headers(meta["headers"]), body_path=stream_to, body_bytes=None)
```

The in-page JS should use `credentials: "include"`, `cache: "no-store"`, the forwarded one-use request headers, and an `AbortController` when `timeout_s` is not `None` because `Page.evaluate` has no timeout parameter in the sync signature. It should return only `{status, headers}` and never the body. Sketch:

```javascript
async ({bindingName, streamId, url, method, headers, bodyText, bodyB64, chunkBytes, timeoutMs}) => {
  const controller = new AbortController();
  const timer = timeoutMs == null ? null : setTimeout(() => controller.abort(), timeoutMs);
  try {
    const init = {method, headers, credentials: "include", cache: "no-store", signal: controller.signal};
    if (bodyText != null) init.body = bodyText;
    if (bodyB64 != null) init.body = Uint8Array.from(atob(bodyB64), c => c.charCodeAt(0));
    const response = await fetch(url, init);
    if (!response.body) throw new Error("response.body stream unavailable");
    const reader = response.body.getReader();
    let seq = 0;
    for (;;) {
      const {done, value} = await reader.read();
      if (done) break;
      for (let off = 0; off < value.length; off += chunkBytes) {
        const part = value.subarray(off, off + chunkBytes);
        await window[bindingName]({kind: "chunk", streamId, seq: seq++, dataB64: bytesToBase64(part)});
      }
    }
    await window[bindingName]({kind: "done", streamId, seq});
    return {status: response.status, headers: Object.fromEntries(response.headers.entries())};
  } finally {
    if (timer !== null) clearTimeout(timer);
  }
}
```

Encoding: base64 per chunk. It has predictable 4/3 bridge overhead but keeps Python writes as bytes and avoids UTF-8 boundary bugs; decode only later when `capture.py` parses JSON from disk. Reject array-of-ints for this path because it expands each byte into JSON numbers plus Python list/int objects. With `chunkBytes = 128 KiB`, a 17.1 MB response is about 131 bridge calls if MB is decimal, or about 137 calls if the sample was 17.1 MiB; each base64 payload is about 171 KiB. This is a good first point: low per-call memory, acceptable round-trip count, and easy to lower to 64 KiB if the attended run shows callback latency/RSS spikes.

Backpressure: every chunk call is `await window[bindingName](...)`; Playwright resolves that promise only after the sync Python callback returns, so the reader loop does not pull the next chunk until the previous chunk is written. The attended leg must confirm no sync-API deadlock, but this is the intended exposed-binding control flow.

`consume_stream_event` should be pure/offline-testable except for the injected `write_bytes` callable: validate `streamId`, monotonically increasing `seq`, `kind`, and base64 with `validate=True`; write decoded `bytes`; increment `bytes_written`; mark `done`; never decode text. Unit-test it with multibyte UTF-8 split across chunks, invalid base64, wrong stream id, out-of-order sequence, duplicate done, and a bytes sink.

Atomicity: the channel writes only to the caller-provided temp path (`raw-mapping.json.tmp.<pid>...`) and closes/flushes it before returning. It must not promote, rename, parse, or compact the raw JSON. For `stream_to` it returns exactly `FetchResult(status, headers, body_path=raw_tmp, body_bytes=None)`. `capture.stream_backend_conversation` owns the temp path, `_validate_fetch_meta` owns status/content-type rejection, and `Store.write_raw_mapping_atomic` owns final promotion via temp file + `os.replace` + directory fsync. On exceptions, leave cleanup to `capture_conversation`'s existing unlink path.

## 2. Alternatives considered

- Whole-body `page.evaluate` returning `await response.text()` or base64 of `arrayBuffer()`: simplest and same-page, but wrong for the 17 MB target. It materializes the body in the renderer, serializes the whole body through Playwright/CDP in one result, creates a Python string/bytes object, then the current parser materializes it again. A 17.1 MB UTF-8 JSON can transiently become a ~34 MB JS UTF-16 string plus protocol/Python copies before JSON objects are allocated. Keep this only as a small-response diagnostic fallback behind a hard cap such as 2 MiB, never for the target scrape.
- `page.request.get(url, headers=...)` / `APIRequestContext.get`: it may reuse context cookies and explicit harvested headers, but it is not the page's `fetch` path and the sync API exposes `APIResponse.body() -> bytes`, not a streaming file sink. Docs also say the response body remains in memory until `dispose()`. Use only for small/lightweight endpoints after real verification; reject for 17 MB raw capture.
- Primary selected: exposed-binding stream pump. If this fails for the 17 MB path, fail closed and fix the pump rather than silently switching to a materializing fallback.

## 3. Offline-testable vs real-leg-only

Offline-testable: URL allowlist resolution before fetch; `FetchResult` shape for `stream_to`; response-header sanitization; base64 stream event decoder/appender; file open/close behavior with fake page/evaluate doubles; no header values in exceptions/log records; and the contract that `body_bytes is None` when `body_path` is set.

Real-leg-only: actual ChatGPT same-page `fetch` accepts the forwarded required headers; `response.body.getReader()` is available for this response; Playwright sync exposed-binding callbacks make progress while `page.evaluate` is pending; binding close/disposal behavior; throughput and RSS on smoke and ~17 MB conversations; and whether current whole-file parse stays under budget.

## 4. Redaction points

Header values live only in `HeaderBundle.for_single_fetch()`'s returned dict, the local `fetch_headers`, the `page.evaluate` argument, and the browser `fetch` init. They are never sent through the binding, returned in `FetchResult`, written to `raw-mapping.json`, included in exception details, or logged. Delete/let locals die immediately after `page.evaluate`; do not include the evaluate arg in wrapped exceptions. Binding payloads contain only `streamId`, `seq`, and base64 response-body chunks. Return only sanitized response headers needed by capture, at minimum lower-cased `content-type` and optionally `content-length`; drop cookie-like response headers defensively. Body chunks are conversation data and are intentionally persisted only as `raw-mapping.json`/transcript via the store path, never in logs.

## 5. Measurement methodology and decision rule

Run the attended measurement in fresh Python processes so `resource.getrusage(...).ru_maxrss` high-water values are meaningful; on Linux record KiB converted to MiB. Use `tracemalloc` for Python allocations and RSS for actual process memory; note that `tracemalloc` does not include browser/native allocations.

Measure two approved read-only conversations: first a small smoke conversation, then the known ~17 MB target. For each, record baseline after attach/open/header acquisition, fetch-only metrics around `fetch_in_page(stream_to=raw_tmp)`, then parse/store metrics around the current capture path. Current code uses whole-file `Path.read_text()+json.loads` in `capture._load_backend_raw`, repeats loads in `validate_backend_shape`/`iter_current_branch_records`, and `Store.write_raw_mapping_atomic` reads/dumps again, so measure the actual path, not an idealized single `json.load`.

Decision rule: accept the streaming adapter only if the 17 MB fetch writes the expected file, returns `body_path`/`body_bytes=None`, and fetch-only overhead is within 128 MiB RSS over post-attach baseline and 32 MiB `tracemalloc` peak. Keep the current whole-file parse/store path for M5/M6 only if end-to-end fetch+parse+atomic-write stays under 512 MiB process RSS and 256 MiB `tracemalloc` peak on the 17 MB target. If either parse threshold is exceeded, implement an event/streaming parser and a non-recompacting atomic promote before running the long target scrape.

## 6. Uncertainties the attended real leg must confirm

- Exposed-binding chunk pumping does not deadlock under Playwright 1.60.0 sync while `page.evaluate` awaits the JS promise.
- `source["page"]` comparison works as expected for the callback; otherwise rely on page-bound binding plus private tab validation.
- `binding.close()` actually disposes the exposed binding sufficiently; unique UUID names avoid collisions either way.
- ChatGPT's response exposes a non-null `response.body` stream and response headers include usable `content-type`.
- Real RSS/tracemalloc values satisfy the thresholds above; otherwise whole-parse/store must be replaced.

## 7. Editor checklist

- Implement the pure `consume_stream_event` helper first with offline tests.
- In `CdpChannel.fetch_in_page`, validate tab and allowlist before any Playwright action; resolve relative URLs against the tab URL.
- For `stream_to`, open the temp path exclusively, install a UUID page binding, run the JS stream pump, close the binding/file, and return `FetchResult(status, safe_headers, stream_to, None)`.
- Use base64 chunks of 128 KiB raw bytes, sequence numbers, and JS `AbortController` for non-`None` timeouts.
- Do not log/eagerly repr request headers or evaluate args; return response header names/values only after cookie-like filtering.
- Measure smoke then 17 MB in fresh processes with `tracemalloc` and `ru_maxrss`; record the numbers in evidence before declaring the parse path acceptable.
