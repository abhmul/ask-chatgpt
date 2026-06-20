# M6-T3 attachment byte routes

## 1. STATUS: DONE

## 2. Phase A enumeration

Offline source: cached `raw-mapping.json`, current branch only. All four normalized source kinds are present.

| source_kind | count | distinct nonempty refs | ref/pointer format examples | bytes present | mime present | filename present |
|---|---:|---:|---|---:|---:|---:|
| `user_upload` | 10 | 10 | `file_…` length 37 | 10 | 1 | 10 |
| `file_reference` | 270 | 9 | `file_…` length 37 | 0 | 0 | 270 |
| `generated_asset` | 169 | 47 | `sediment://…` length 72/73; representative contains an embedded `file_…` token | 169 | 169 | 0 |
| `code_execution_output` | 216 | 115 | UUID-like length 36; some missing run id | 0 | 216 | 115 |

Phase A helper added: `scripts/m6_attachment_enumerate.py` (offline-only; prints shapes/counts only; full representative refs only to `/tmp` when requested).

## 3. Phase B route findings

Live method: own newly opened target tab only; in-page read-only `GET`/`HEAD`; one representative ref per present kind. Header values and signed URLs were kept in memory only. Phase B helper added: `scripts/m6_attachment_route_probe.py` (sanitized stdout only).

Required backend header names observed/sent to `/backend-api/files/...`: `accept`, `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, `x-openai-target-route`.

### `user_upload`

- Route: `GET /backend-api/files/<file_id>/download` where `source_ref` is the `file_…` id.
- Download endpoint status/content-type: HTTP 200, `application/json`.
- Download JSON keys: `creation_time`, `download_url`, `file_name`, `file_size_bytes`, `metadata`, `mime_type`, `no_auth_user_upload`, `status`.
- Metadata variant: `GET /backend-api/files/<file_id>` returned HTTP 200 with keys `creation_time`, `expiration_time`, `file_extension`, `file_size_tokens`, `id`, `metadata`, `mime_type`, `name`, `no_auth_user_upload`, `owner_id`, `ready_time`, `retrieval_index_status`, `size`, `state`, `use_case`, `variants`.
- Byte follow: `HEAD <download_url>` returned HTTP 200 from host `chatgpt.com`, content-type `application/pdf`, content-length `413577`.
- Auth on byte follow: no backend auth/OAI headers supplied, but `credentials: omit` returned HTTP 403; treat the observed URL as cookie-bound same-origin, not public cookie-free pre-signed.

### `file_reference`

- Route: `GET /backend-api/files/<file_id>/download` where `source_ref` is the `file_…` id.
- Download endpoint status/content-type: HTTP 200, `application/json`.
- Download JSON keys: `creation_time`, `download_url`, `file_name`, `file_size_bytes`, `metadata`, `mime_type`, `no_auth_user_upload`, `status`.
- Metadata variant: `GET /backend-api/files/<file_id>` returned HTTP 200 with keys `creation_time`, `expiration_time`, `file_extension`, `file_size_tokens`, `id`, `metadata`, `mime_type`, `name`, `no_auth_user_upload`, `owner_id`, `ready_time`, `retrieval_index_status`, `size`, `state`, `use_case`, `variants`.
- Byte follow: `HEAD <download_url>` returned HTTP 200 from host `chatgpt.com`, content-type `application/pdf`, content-length `784867`.
- Auth on byte follow: no backend auth/OAI headers supplied, but `credentials: omit` returned HTTP 403; treat as cookie-bound same-origin.

### `generated_asset`

- Representative pointer format: `sediment://…`, with an embedded `file_…` token.
- Confirmed route: extract embedded `file_…` token, then `GET /backend-api/files/<file_id>/download`.
- Download endpoint status/content-type: HTTP 200, `application/json`.
- Download JSON keys: `creation_time`, `download_url`, `file_name`, `file_size_bytes`, `metadata`, `mime_type`, `no_auth_user_upload`, `status`.
- Metadata variant: `GET /backend-api/files/<file_id>` returned HTTP 200 with keys `creation_time`, `expiration_time`, `file_extension`, `file_size_tokens`, `id`, `metadata`, `mime_type`, `name`, `no_auth_user_upload`, `owner_id`, `ready_time`, `retrieval_index_status`, `size`, `state`, `use_case`, `variants`.
- Byte follow: `HEAD <download_url>` returned HTTP 200 from host `chatgpt.com`, content-type `application/pdf`, content-length `762215`.
- Auth on byte follow: no backend auth/OAI headers supplied, but `credentials: omit` returned HTTP 403; treat as cookie-bound same-origin.
- Caveat: only the embedded-file-token sediment shape was live-confirmed; sediment pointers without an embedded `file_…`/`file-…` token should fail closed until separately confirmed.

### `code_execution_output`

- Representative run id format: UUID-like length 36.
- Probe: `GET /backend-api/files/<run_id>/download` returned HTTP 200 but error-shaped JSON only, keys `error_code`, `error_message`, `error_type`, `status`; no `download_url`.
- Metadata variant: `GET /backend-api/files/<run_id>` returned HTTP 404 with key `detail`.
- Byte route: unsupported/fail-closed on this target.

## 4. Recommended T4 implementation shape

- Normalize to a file id before fetching bytes:
  - `user_upload` and `file_reference`: use `AttachmentRef.source_ref` when it matches `file_…` or `file-…`.
  - `generated_asset`: if `file-service://...`, strip the scheme and use the payload; if `sediment://...`, extract an embedded `file_…`/`file-…` token when present; otherwise mark unsupported/fail-closed.
  - `code_execution_output`: do not treat `run_id` as byte-downloadable unless a future route is discovered.
- In the logged-in page, call `GET /backend-api/files/<urlencoded_file_id>/download` with `accept: application/json` plus the required web-app header names above. Require a success-shaped JSON containing `download_url`; do not trust HTTP 200 alone because run ids can return HTTP 200 error JSON.
- Follow `download_url` from the same page/session. Observed byte host is `chatgpt.com`; keep the allowlist check for `chatgpt.com` and retain existing `oaiusercontent.com` allowance for future variants. The observed follow step needs cookies (`credentials: omit` was 403) but not backend auth/OAI headers.
- For storage: stream bytes to a cache-local attachment path, then set `AttachmentRef.download_state="downloaded"` and `local_path` after successful byte write; use `not_downloadable` for success-shaped metadata with no `download_url`, and `unsupported` for unsupported source kinds/schemes.

## 5. Safety audit

- CDP preflight before attach: reachable. CDP re-check after live probes: reachable.
- Own-tab-only: used one newly opened target tab per probe run; did not iterate existing/operator tabs.
- READ-ONLY: only in-page `GET`/`HEAD`; no UI download button, no clicks, no typing, no sends, no model/tool selection, no uploads.
- Login/Cloudflare: not encountered.
- Secrets/data hygiene: no header values, cookie values, signed URLs, file ids, filenames, or conversation content in this report; full refs stayed in `/tmp` scratch/in memory only.
- Repo hygiene: no git commands, no `uv tool`, no `stable` movement, no cache content committed or copied into the report.

## 6. Blockers

None for T4’s general file-id/pointer-to-bytes resolver. Remaining caveat: this target confirmed cookie-bound `chatgpt.com` download URLs; it did not confirm a cookie-free `oaiusercontent.com` variant.
