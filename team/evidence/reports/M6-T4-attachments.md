# M6-T4 attachments

## 1. STATUS: DONE

## 2. Phase A

Files changed:

- `src/ask_chatgpt/capture.py` — wires `with_attachments=True` into backend capture, resolves supported refs, fetches descriptors/bytes through `fetch_in_page`, verifies size, re-upserts updated attachment states, and keeps header/download URL values in memory only.
- `src/ask_chatgpt/channels/mock.py` — adds mock descriptor and byte routes plus redacted counters for offline attachment tests.
- `tests/test_capture.py` — adds falsifiable mock coverage for download success, 200 error JSON, unsupported refs, dedup, and default no-op.
- `scripts/m6_download_attachments.py` — counts-only real-download harness; emits states/sizes/mime/counts only.

Required tests:

1. Downloadable mock ref: fails if `with_attachments=True` remains a no-op, bytes are not streamed, `download_state` is not `downloaded`, or `local_path` does not point to an existing cached file.
2. HTTP-200 error-shaped JSON with no `download_url`: fails if code trusts status 200 alone, writes bytes, or marks anything other than `not_downloadable`.
3. Unsupported run/bare sediment refs: fails if unsupported refs issue descriptor/byte fetches or are not marked `unsupported`.
4. Dedup: fails if two refs resolving to the same backend token cause more than one descriptor/byte fetch or do not both receive a local path.
5. Default no-op: fails if `with_attachments=False` triggers descriptor/byte fetches or mutates pending attachment refs.

Pytest: `212 passed in 0.96s`.

## 3. Phase B

Preflight before final real run: `CDP_OK`. Re-preflight after final real run: `CDP_OK`.

Counts-only final transcript summary: 501 turns; attachment dir exists under `cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/attachments/`; 10 regular attachment files on disk; 55,168,133 bytes on disk; 10 unique local paths referenced in the transcript. The per-kind byte totals below are unique local paths within each kind, so overlapping backend tokens can be counted under multiple kinds.

| source_kind | refs | distinct source refs | distinct backend tokens | states | total bytes | mime types |
|---|---:|---:|---:|---|---:|---|
| `user_upload` | 10 | 10 | 10 | `downloaded=10` | 55,168,133 | `<missing>=9`, `application/zip=1` |
| `file_reference` | 209 | 9 | 9 | `downloaded=209` | 13,600,357 | `<missing>=209` |
| `generated_asset` | 140 | 47 | 6 | `downloaded=140` | 12,693,181 | `image_asset_pointer=140` |
| `code_execution_output` | 125 | 113 | 0 | `unsupported=125` | 0 | `application/json=125` |

Transcript reflects attachment states/local paths: all supported refs are `downloaded`; unsupported run outputs are `unsupported`; sensitive-key scan of transcript found `download_url=0`, `authorization=0`, `cookie=0`, `oai-*=0`. Conversation-local `.gitignore` contains `attachments/`, and all attachment bytes are under the cache attachment directory.

## 4. Safety audit

Own-tab-only via `Session`/`TabPool`; no browser/context page enumeration. READ-ONLY GET fetches only; ZERO sends, new turns, typing, clicks, uploads, model selection, or tool selection. Browser alive after run (`CDP_OK`). No header values, cookie values, signed URLs, file-id values, attachment filenames, or conversation content are included in this report. No `git`, no `uv tool`, and no `stable` actions were run.

## 5. Blockers / fail-closed notes

`code_execution_output` is intentionally unsupported. Bare sediment refs without an embedded backend token are unsupported. The target’s generated assets have 47 distinct source refs but 6 distinct embedded backend tokens under the M6-T3-confirmed route; counts above report both to make the contract-number mismatch falsifiable without exposing IDs. A stricter interpretation of sediment fragments produced errors, so the final implementation uses the M6-T3 route and fail-closes unsupported/undownloadable shapes.
