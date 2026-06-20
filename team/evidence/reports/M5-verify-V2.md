# M5 verification — Lens V2 (Offline falsifiability & correctness)

**Lens verdict:** CONFIRM-WITH-FINDINGS

**Scope executed:** V2 only. I did not touch browser/CDP/network/`:9222` and did not mutate source/tests. Source/tests/scripts were clean against `HEAD`; M5 commits inspected were `5966814` and `09eee7f`.

## Pytest re-derivation

| Item | Verdict | Evidence |
|---|---:|---|
| Full offline suite | PASS | `PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider` collected 205 items and ended `205 passed in 0.45s`. |
| Existing 188 still pass | PASS | Full suite 205 minus `tests/test_cdp_channel.py`'s 17 collected cases (`.................`) = 188 pre-M5 cases still green. |
| No-Playwright pins still exist | PASS | `tests/test_channels_base.py:111-114` asserts public API/session mock import leaves no `playwright*` in `sys.modules`; `tests/test_mock_channel.py:33-43` asserts mock import is offline and context/browser page enumeration guards exist. |

## Acceptance-behavior falsifiability map

| M5 acceptance behavior | Verdict | Public/real behavior exercised? | Could fail? concrete assertion evidence |
|---|---:|---|---|
| Lazy-import boundary | PASS | Yes: imports `ask_chatgpt`, imports `ask_chatgpt.channels.cdp`, constructs `CdpChannel`, and constructs `Session(channel="cdp")` then calls `status(probe_browser=False)` (`tests/test_cdp_channel.py:219-236`). | Yes: `_assert_playwright_not_imported` asserts no `playwright*` modules (`tests/test_cdp_channel.py:215-216`); `report.cdp is None` at `tests/test_cdp_channel.py:236`. |
| Preflight mapping: ok/http-error/timeout/refused/invalid-json/missing-ws | PASS | Yes: calls public `CdpChannel.preflight` with injected `http_get_json` (`tests/test_cdp_channel.py:249-296`). | Yes: error result fields asserted at `tests/test_cdp_channel.py:257-261`; ok result + websocket presence at `tests/test_cdp_channel.py:279-284`; missing websocket at `tests/test_cdp_channel.py:292-296`. |
| Allowlist before Playwright factory/import | PASS* | Mostly: public `open_tab`/`fetch_in_page` reject disallowed URLs with a factory that would fail if touched (`tests/test_cdp_channel.py:299-312`); code performs allowlist checks before tab validation/page work (`src/ask_chatgpt/channels/cdp.py:446-450`, `src/ask_chatgpt/channels/cdp.py:592-603`). | Yes for factory/order: `pytest.raises(DomainNotAllowedError)` at `tests/test_cdp_channel.py:309-312`. Finding F1: no direct post-call `sys.modules` assertion for raw Playwright imports on disallowed paths. |
| Own-tabs-only | PASS | Yes: public `attach/open_tab/close_tab/detach` against fake context whose `.pages` and `.on` raise (`tests/test_cdp_channel.py:154-168`, `tests/test_cdp_channel.py:315-348`). | Yes: two pages/cdp sessions created via `new_page`, no context listeners, own pages closed, browser/playwright disconnected (`tests/test_cdp_channel.py:329-348`). |
| Protocol signatures + `FetchResult` stream/non-stream shapes | PASS | Yes: protocol method names pinned in `tests/test_channels_base.py:83-107`; `CdpChannel.fetch_in_page` returns public `FetchResult` shapes through stream and non-stream calls (`tests/test_cdp_channel.py:390-428`). | Yes: `isinstance(FetchResult)`, status/path/body/header assertions at `tests/test_cdp_channel.py:415-428`. |
| `wait_for_request`: cheap predicate, required-name projection, CDP ExtraInfo fallback by requestId, redacted repr | PASS* | Yes: installs fake page/CDP listeners through public `open_tab`, invokes handlers, then calls public `wait_for_request` (`tests/test_cdp_channel.py:454-500`). | Yes: predicate snapshot has `{}` headers and one header materialization (`tests/test_cdp_channel.py:477-478`); required-header projection and cookie drop (`tests/test_cdp_channel.py:479-481`); CDP fallback (`tests/test_cdp_channel.py:490-493`); redacted repr (`tests/test_cdp_channel.py:482`, `tests/test_cdp_channel.py:493`, `tests/test_cdp_channel.py:500`). Finding F2: no non-matching-request case proves headers are not materialized for rejected predicates. |
| Pure stream decode incl. multibyte UTF-8 split across chunks | PASS | Yes, via exported stream helper `consume_stream_event` rather than a browser/CDP surface (`tests/test_cdp_channel.py:351-387`; exported at `src/ask_chatgpt/channels/cdp.py:790-794`). | Yes: split `π` bytes at `tests/test_cdp_channel.py:354-355`; reconstructed text/asserted state at `tests/test_cdp_channel.py:371-373`; bad events raise at `tests/test_cdp_channel.py:381-386`. |
| Redaction canary | PASS | Yes: canaries are passed through preflight, fetch args/results, request headers, and vocab input while only repr/summaries are allowed. | Yes: canary absence asserted for preflight (`tests/test_cdp_channel.py:261`, `tests/test_cdp_channel.py:284`), `FetchResult` repr (`tests/test_cdp_channel.py:427-428`), evaluate exception sanitization (`tests/test_cdp_channel.py:450-451`), `RequestSnapshot` repr (`tests/test_cdp_channel.py:482`, `tests/test_cdp_channel.py:493`, `tests/test_cdp_channel.py:500`), and vocab summary (`tests/test_cdp_channel.py:626`). |
| `catalogue_completion_status_vocab` | PASS* | Yes: public function consumes a raw mapping fixture and summarizes statuses/progress (`tests/test_cdp_channel.py:575-626`; implementation `src/ask_chatgpt/capture.py:648-675`). | Yes: count assertions at `tests/test_cdp_channel.py:618-623`; object/string progress hashing at `tests/test_cdp_channel.py:624-625`; canary redaction at `tests/test_cdp_channel.py:626`. Finding F3: no short enum-shaped secret token (e.g. `CANARY_SECRET`/`secret_token`) directly tests `_is_short_enum_token`'s secret-substring guard (`src/ask_chatgpt/capture.py:708-713`). |
| Action methods raise | PASS | Yes: public action/clipboard methods are called on `CdpChannel` (`tests/test_cdp_channel.py:503-523`; implementation `src/ask_chatgpt/channels/cdp.py:518-534`, `src/ask_chatgpt/channels/cdp.py:654-662`). | Yes: each action is inside `pytest.raises(HumanActionNeededError, match="M5 is read-only")` (`tests/test_cdp_channel.py:519-520`); clipboard reason asserted at `tests/test_cdp_channel.py:521-523`. |

## Findings / gaps

1. **F1 — Coverage gap: disallowed URL tests do not directly assert no Playwright import side effect.** Add `sys.modules` cleanup + post-call `assert not any(name == "playwright" or name.startswith("playwright.") ...)` around `test_open_tab_and_fetch_reject_disallowed_urls_before_playwright_factory`.
2. **F2 — Coverage gap: cheap-predicate test lacks a rejected-request case.** Add a first observed request whose predicate returns `False`, assert its `all_headers_calls == 0`, then a matching request with the current assertions.
3. **F3 — Coverage gap: short secret-ish `pro_progress` enum tokens.** Add a raw node with `pro_progress: "CANARY_SECRET"` or `"secret_token"` and assert it is summarized as `str:len=...:sha256=...`, not emitted literally.

## Could not verify

- I did not perform mutation testing; I only judged falsifiability from committed tests/source and the green offline run.
- I did not verify V1 safety/leak claims or V3 real-leg conformance; those are outside this lens.
