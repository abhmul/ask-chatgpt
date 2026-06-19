# M6-T3 — Discover the attachment BYTE-download routes (ATTENDED REAL-LEG, READ-ONLY investigation)

You are a **pi worker** for the `ask-chatgpt-dev` team, mission M6 task T3. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit **nothing** but this contract and the files it names. Read `.claude/skills/manager/references/agent-rigor.md` and obey it.

## Goal
M2/M5 saw attachment **references** (ids / pointers / metadata) but **no literal download URLs**. Discover **how the web app turns a referenced file/asset into bytes** — the endpoint(s), auth, and download host — so M6-T4 can implement a **general** byte-download resolver. Confirm it **live, read-only**, on the authorized target's own tab. Deliver a precise route-findings report.

## ░░ SAFETY — real-site, SHARED browser (OBEY EXACTLY; transcribed verbatim) ░░
The browser at `127.0.0.1:9222` is **SHARED with another ACTIVE agent**.
- **own-tab-only**: never read/iterate foreign/operator tabs (prior leak incident). Only tabs the tool itself opens. Never `context.pages`.
- **READ-ONLY**: an in-page `GET` to a files endpoint is a read. **ZERO sends / new turns / model or tool selection / typing / clicks-that-mutate / Enter / uploads.** Do NOT click UI download buttons (state risk); use in-page `fetch` GETs only.
- **never quit the browser** (detach only).
- **preflight** `curl -s --max-time 5 http://127.0.0.1:9222/json/version` BEFORE attaching; if it fails → STOP `CDP_UNREACHABLE`.
- **login / Cloudflare / "Just a moment…"** → STOP `HUMAN-ACTION-NEEDED`; never solve/login.
- **no stealth**; domain allowlist stays enforced (the channel enforces it: chatgpt.com, openai.com, oaiusercontent.com, oaistatic.com + subdomains).
- **NEVER persist or log** `authorization` / `oai-*` / `cookie` values — names/booleans only.
- read **ONLY** the authorized target `6a316aa8-5dc8-83ea-9014-b8ea38dabc31`.
- **Never commit cache content** (gitignored). **Never** `git add/commit/push` or any git command. Branch `rewrite-v2` only; never move/commit `stable`; never `uv tool install/upgrade/reinstall` (use `uv run`/`uv sync`).
- **Do NOT put operator file-ids, filenames, or any conversation content in the committed report** — those can leak operator data. Report formats/shapes/counts and the ROUTE, not the specific ids/names. Keep any full id you need for probing in memory or a /tmp scratch file only.

## Phase A — OFFLINE: enumerate the target's actual attachment refs (no network)
The target is already cached (from T2) at `cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/raw-mapping.json`. The capture layer already normalizes 4 attachment shapes — read `src/ask_chatgpt/capture.py` `_attachments_for_message` (≈lines 429–487) to see exactly how `AttachmentRef` is built:
- `source_kind="user_upload"` ← `message.metadata.attachments[]`, `source_ref = id` (a `file-…`/`file_…` id), `filename`, `bytes`.
- `source_kind="file_reference"` ← `message.metadata.content_references[]` where `type=="file"`, `source_ref = id`, plus `cloud_doc_url`, `library_file_id`, `input_pointer`, …
- `source_kind="generated_asset"` ← `message.content.assets[]`, `source_ref = asset_pointer` (often `file-service://file-…` or `sediment://…`), `mime`, `bytes`.
- `source_kind="code_execution_output"` ← `message.metadata.aggregate_result`, `source_ref = run_id`.

Write a tiny **offline** script (e.g. `scripts/m6_attachment_enumerate.py`, no network) that loads the cached `raw-mapping.json` and reports, per `source_kind`: **count**, and for a few examples the **id/pointer FORMAT** (prefix + length, NOT the full id) and whether `bytes`/`mime`/`filename` are present. This tells us which kinds actually exist on this target and gives you representative refs to probe. (If a kind has count 0, you cannot live-confirm its route on this target — say so.)

## Phase B — LIVE (attended, read-only): confirm the byte route(s)
Candidate routes to TEST (these are HYPOTHESES from the known ChatGPT backend; CONFIRM, do not assume):
1. **File id → signed URL → bytes** (primary hypothesis): in-page `GET https://chatgpt.com/backend-api/files/<file_id>/download` with the page's own web-app auth/OAI headers (cookies-only 404s, exactly like the conversation endpoint — reuse the proven header-acquisition mechanism). Expect JSON whose KEYS may include a download URL (e.g. `download_url`, `url`, `status`). Then `GET <that url>` (likely host `*.oaiusercontent.com`, allowlisted) → the actual bytes. Confirm with a **HEAD or a tiny ranged GET** (`Range: bytes=0-0` or a small read) — get status / content-type / content-length **without downloading the whole file and without printing bytes**.
2. **Metadata variant**: `GET /backend-api/files/<file_id>` (no `/download`) — note if it returns metadata/url.
3. **asset_pointer**: if `file-service://file-XXXX`, extract `file-XXXX` and try route 1. If `sediment://…` or other scheme, document what resolves (or that it does not).
4. **file_reference / code_execution_output**: test route 1 with their ids; if not byte-downloadable (likely for `run_id`), document **fail-closed** ("unsupported — no byte route").

Mechanics: reuse the channel `fetch_in_page` (see `src/ask_chatgpt/channels/cdp.py` `fetch_in_page`, and how `scripts/m5_capture_measure.py` / `src/ask_chatgpt/capture.py` acquire the own-page headers via the request observer). Easiest: write a small attended probe script `scripts/m6_attachment_route_probe.py` that takes the target conversation, acquires headers from the own tab, and does the read-only GET(s) for ONE representative ref per present kind. **Never** log header values; print only status codes, response JSON KEYS, resolved download HOST, content-type, content-length.

Probe **one representative ref per present kind** (not every file) to keep browser load minimal on the shared browser. Preflight curl first; re-check the browser is alive after.

## Acceptance
- A clear, reproducible **route per source_kind** that exists on the target: exact endpoint, required auth (header NAMES only), the download host, the response-shape KEYS, and a confirmed byte-serving status (200 + content-type/length) for at least the primary `file-id → /download → signed url` path **if** any such ref exists on the target.
- Honest **fail-closed** notes for kinds with no byte route (e.g. `code_execution_output`).
- ZERO sends; own-tab-only; browser left alive; no header values / file-ids / filenames / content in the committed report.

## Report (write your handoff here)
Write `team/evidence/reports/M6-T3-attachment-routes.md`, in order:
1. **STATUS:** `DONE` / `PARTIAL` / `BLOCKED`.
2. **Phase A enumeration:** per `source_kind` count on the target + id/pointer FORMAT (shape only). Which kinds are present.
3. **Phase B route findings:** for each present kind — endpoint, method, required header NAMES, response JSON KEYS, resolved download HOST, byte-serving status/content-type/content-length (from HEAD/ranged GET), and whether the download_url needs auth or is pre-signed. Mark unsupported kinds fail-closed.
4. **Recommended T4 implementation shape:** the general `file-id/pointer → bytes` resolver (endpoint + signed-url follow), what to set on `AttachmentRef.download_state`/`local_path`, and the allowlist host to confirm.
5. **Safety audit:** own-tab-only; ZERO sends; browser alive before+after; no header values/ids/filenames/content committed; no git/`uv tool`/`stable` actions.
6. **Blockers** (e.g. target has zero downloadable refs → route unconfirmable live; needs an operator-approved conversation with a known file upload).
Report shapes/keys/status codes ONLY — never header values, file-ids, filenames, or conversation content.
