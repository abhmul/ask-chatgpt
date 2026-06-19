# M6-T4 — Implement lazy attachment byte-download + run the real `--with-attachments` download

You are a **pi worker** for the `ask-chatgpt-dev` team, mission M6 task T4. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit **nothing** but this contract and the files it names. Read `.claude/skills/manager/references/agent-rigor.md` and obey it. **Follow strict TDD** (one falsifiable test → minimal impl → repeat) for the implementation.

Two phases in ONE worker: **(A) OFFLINE implementation + mock tests** (edit source, single editor), then **(B) ONE attended READ-ONLY real download leg** against the target. Do them in order; do NOT start B until A is green.

## Confirmed byte route (from M6-T3, live-verified — transcribe; do NOT re-derive)
The capture layer already normalizes 4 attachment shapes into `AttachmentRef(source_kind, source_ref, raw_path, filename, mime, bytes, sha256, local_path, download_state, metadata)` (see `src/ask_chatgpt/capture.py` `_attachments_for_message`). `capture_conversation(..., with_attachments=...)` currently does `del with_attachments` (a NO-OP at line ~299) — your job is to wire the real download.

**General resolver: `AttachmentRef` → file id → bytes.**
1. **Normalize `source_ref` to a file id** (`file_…` or `file-…`):
   - `user_upload`, `file_reference`: `source_ref` **is** the `file_…` id — use directly.
   - `generated_asset`: if `source_ref` starts `file-service://` → strip the scheme, use the remainder; if `sediment://…` → extract an embedded `file_…`/`file-…` token if present; **otherwise mark `unsupported`** (no live-confirmed route).
   - `code_execution_output`: `source_ref` is a `run_id` (UUID-like) — **`unsupported`** (no byte route; confirmed: `/download` returns HTTP 200 *error-shaped* JSON, metadata variant 404).
2. **Fetch the download descriptor**: in-page `GET https://chatgpt.com/backend-api/files/<urlencoded_file_id>/download` with `accept: application/json` **plus the web-app auth/OAI headers** (same `HeaderBundle` the conversation capture already acquires — names: `authorization`, `oai-client-build-number`, `oai-client-version`, `oai-device-id`, `oai-language`, `oai-session-id`, `x-openai-target-path`, `x-openai-target-route`). Response is JSON with keys `creation_time, download_url, file_name, file_size_bytes, metadata, mime_type, no_auth_user_upload, status`.
   - **CRITICAL GOTCHA (must be a falsifiable test):** HTTP **200 alone is NOT success** — a `run_id` returns HTTP 200 with an **error-shaped** JSON (`error_code, error_message, error_type, status`, **no `download_url`**). Treat as downloadable **only if** the JSON has a non-empty `download_url`. Success-shaped JSON **without** a `download_url` → `download_state="not_downloadable"`.
3. **Follow the `download_url`** with a second in-page fetch, **streaming bytes to disk** (`stream_to=`). Observed byte host is **`chatgpt.com`** (same-origin, cookie-bound: `credentials: omit` → 403, so the in-page fetch's `credentials: include` is required; backend auth/OAI headers are NOT needed for this follow). Keep the existing allowlist (`chatgpt.com` + `oaiusercontent.com` retained for future variants — `src/ask_chatgpt/allowlist.py`).
4. **Store**: stream to `store.attachment_path(conversation_id, ref)` (already path-safe, under `cache/conversations/<id>/attachments/`). On success set `download_state="downloaded"` and `local_path` (relative to the conversation root). Verify the written size against `file_size_bytes`/`bytes` when known. Use `not_downloadable` (success JSON, no url), `unsupported` (kind/scheme), `error` (fetch/stream failure) — these are the allowed `download_state` literals (`pending|downloaded|not_downloadable|unsupported|error`, see `src/ask_chatgpt/models.py`).
5. **DEDUP by resolved file-id within one scrape run** (REQUIRED — account politeness): the target has ~449 attachment refs but only ~66 distinct file ids (10 user_upload + 9 distinct file_reference + 47 distinct generated_asset). Download each **distinct file id once**; other refs to the same id reuse the same `local_path` without re-fetching. Do NOT issue ~449 backend file requests.

## Where to wire it (single editor — keep edits minimal + cohesive)
- In `src/ask_chatgpt/capture.py` `capture_conversation`, when `with_attachments=True`: after `store.upsert_many(records)`, run a download pass over the records' `AttachmentRef`s reusing the `headers` HeaderBundle already acquired at line ~304, then re-emit each affected `TurnRecord` via `dataclasses.replace(record, attachments=<updated tuple>)` and `store.upsert_many(updated)` (transcript.jsonl is append-only + last-writer-wins by `message_id`, so re-upsert reflects `download_state`/`local_path` on read — no schema change).
- Prefer a small new helper (e.g. `download_attachments(tab, conv, headers, records, store)` in `capture.py`, or a focused `attachments.py`) so the logic is testable. Reuse the channel seam only: `tab.channel.fetch_in_page(...)` (see `channels/cdp.py` `fetch_in_page` — it streams via `stream_to=` and allowlist-checks). Do NOT call Playwright directly.
- **NEVER persist or log** header values or signed `download_url`s anywhere (no prints, no files, no exceptions carrying them). The `AttachmentRef.metadata` must stay sanitized (no auth/url).

## Phase A — OFFLINE TDD (mock; no browser/network)
Extend `MockChannel`/`MockScenario` (`src/ask_chatgpt/channels/mock.py`; see `_scripted_fetch_response` and how `fetch_in_page` resolves URLs — it already streams bytes via `stream_to`) to serve:
- `GET /backend-api/files/<id>/download` → success JSON with a `download_url` (for a downloadable id), AND a separate id whose `/download` returns **HTTP 200 error-shaped JSON without `download_url`** (the gotcha), AND the `download_url` → some bytes.
Write falsifiable tests (each MUST be able to fail):
1. `scrape(with_attachments=True)` over mock → for a downloadable ref: bytes written under `cache/.../attachments/`, `download_state=="downloaded"`, `local_path` set and the file exists with expected bytes. (Fails if no-op / bytes missing.)
2. The **200-error-JSON-without-`download_url`** ref → `download_state=="not_downloadable"`, NO bytes written. (Pins the gotcha; fails if 200 is naively trusted.)
3. Unsupported kind/scheme (`code_execution_output` run_id; bare `sediment://` w/o token) → `download_state=="unsupported"`, no fetch attempted.
4. **Dedup**: two refs with the same resolved file id → the descriptor/byte fetch happens **once** (assert via the mock's fetch counter), both refs get a `local_path`.
5. `with_attachments=False` (default) remains a no-op (no download fetches) — regression guard.
Run `uv run pytest` to full green (≥ the current 207 + your new tests). A harmless `VIRTUAL_ENV ... ignored` warning is expected (`uv run` uses the project `.venv`).

**STOP after Phase A.** In your report, mark Phase A complete with the pytest summary. (The manager will independently re-run pytest + inspect the diff + commit the code BEFORE you proceed — but since you are one worker, proceed to Phase B only after A is green; the manager commits afterward. Do NOT run git yourself.)

## Phase B — ATTENDED REAL DOWNLOAD (READ-ONLY) ░░ SAFETY (OBEY EXACTLY) ░░
The browser at `127.0.0.1:9222` is **SHARED with another ACTIVE agent**.
- **own-tab-only**; never read/iterate foreign tabs; never `context.pages`.
- **READ-ONLY**: attachment downloads are GET reads. **ZERO sends / new turns / model or tool selection / typing / clicks / Enter / uploads.**
- **never quit the browser** (detach only). **preflight** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` first; fail → STOP `CDP_UNREACHABLE`. login/Cloudflare → STOP `HUMAN-ACTION-NEEDED`.
- **NEVER persist/log** `authorization`/`oai-*`/`cookie` values or signed `download_url`s. read ONLY target `6a316aa8-5dc8-83ea-9014-b8ea38dabc31`.
- **modest pacing**: small delay (~0.2–0.5s) between distinct-file downloads; dedup so only ~66 distinct files are fetched. Reads, not sends — but stay polite on the shared account.
- **never commit cache content** (gitignored). No git, no `uv tool`, no `stable` movement. Branch `rewrite-v2` only.
- **stdout-mirroring lesson (from T2):** `scrape`/`history --out` mirror payload to **stdout AND** file by design. Run the real download via a counts-only harness OR redirect stdout to `/dev/null`, so conversation content does NOT land in logs. Prefer a small `scripts/m6_download_attachments.py` that calls `Session(channel="cdp", data_dir="cache").scrape(<url>, with_attachments=True)` and prints **only counts/states/sizes/mime** (never content, never urls/ids/filenames).

Steps: preflight curl → run the real `--with-attachments` scrape of the target into `cache/` → confirm files appear under `cache/conversations/6a316aa8-…/attachments/` → re-preflight (browser alive). Report per `source_kind`: distinct ids, #downloaded / #not_downloadable / #unsupported / #error, total bytes, mime types seen (counts only). Confirm `git status` shows NO attachment bytes staged (cache is gitignored) — but do NOT run git; instead confirm via `git check-ignore cache` is not your job — just confirm the attachments are under the gitignored `cache/` path.

## Acceptance
- Phase A: `uv run pytest` fully green incl. the 5 falsifiable tests above (esp. the 200-error gotcha + dedup).
- Phase B: real attachments downloaded into `cache/conversations/<id>/attachments/`; honest per-kind counts incl. unsupported; transcript.jsonl reflects `download_state`/`local_path`; ZERO sends; own-tab-only; browser alive; no header values / signed urls / file-ids / filenames / content in the committed report; cache content uncommitted.

## Report (write your handoff here)
Write `team/evidence/reports/M6-T4-attachments.md`, in order:
1. **STATUS:** `DONE` / `PARTIAL` / `BLOCKED`.
2. **Phase A:** files changed (paths) + 1-line each; the 5 tests and how each can fail; the `uv run pytest` summary line.
3. **Phase B:** preflight before/after; per-`source_kind` distinct-id counts + download_state distribution + total bytes + mime types (counts only); confirmation attachments are under the gitignored cache attachments dir and transcript reflects them.
4. **Safety audit:** own-tab-only; ZERO sends; browser alive; no header values/signed-urls/file-ids/filenames/content committed or printed; no git/`uv tool`/`stable` actions.
5. **Blockers / fail-closed notes** (e.g. unsupported kinds, any HTTP errors).
Counts/sizes/states/mime ONLY — never header values, signed URLs, file-ids, filenames, or conversation content.
