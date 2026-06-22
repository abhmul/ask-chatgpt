# M10-T4 — Attended real-site confirmation (ATTENDED, ZERO-SEND, own-tab-only)

**FIRST read `team/contracts/M10-common.md` in full (safety + ground truth).** This
is the TERMINAL verification of the M10 fix: prove that reading a LARGE conversation
via the new light-page `scrape` no longer crashes the renderer, returns correct
data, and that the ambient header-harvest works on the real site. The operator is
attended and the CDP browser is UP. Branch `fix/m10-light-read-scrape` is checked out.

## TARGET
`TARGET_URL = https://chatgpt.com/c/6a387270-c3b0-83ea-991f-81085a2eeb9b`

## Preconditions (re-check; STOP if any fail)
1. CDP preflight: `curl -s --max-time 5 http://127.0.0.1:9222/json/version` must
   return a Browser/version JSON. If it fails → STOP, write a BLOCKED handoff with
   `HUMAN-ACTION-NEEDED: bring the signed-in Chromium up on CDP :9222`. Do NOT call
   `/json/list` or any other `/json/*` endpoint (it lists ALL tabs incl. the
   operator's — LEAK risk).
2. Confirm `git rev-parse --abbrev-ref HEAD` = `fix/m10-light-read-scrape` and
   `uv run ask-chatgpt --version` = `0.2.0` (this runs the PROJECT venv = the fix;
   NEVER use the bare installed `ask-chatgpt` — that is the separate stable copy
   another agent uses).

## The run (a SINGLE read; ZERO sends)
Run exactly one scrape, redirecting the leak-prone stdout to /dev/null and stderr to
a local temp file, and capture exit code + elapsed seconds:

```
START=$(date +%s)
uv run ask-chatgpt scrape "$TARGET_URL" --data-dir cache >/dev/null 2>/tmp/m10-t4-stderr.log
CODE=$?
END=$(date +%s); echo "exit=$CODE elapsed=$((END-START))s"
```

- `--data-dir cache` (gitignored cache; do NOT scrape with `--with-attachments` —
  attachments are a separate concern; keep this to the core transcript read).
- Do NOT loop or retry-spam. At most ONE retry if the first attempt fails for a
  transient reason. Adding extra scrapes/restarts risks the rate limiter (see
  `issues/2026-06-21-...`). No `ask`/`loop`/`create` — this is read-only, zero-send.

## Interpret the outcome
- **exit 0 + transcript present = NO renderer crash → the bug is FIXED for this
  conversation.** (The pre-fix behavior on this conv was INTERNAL_ERROR / exit 99 /
  EPIPE / 10-min hang.)
- exit 99 / INTERNAL_ERROR / EPIPE / a multi-minute hang = the renderer still
  crashed → FIX FAILED for this conv (report it; do NOT aggressively retry).
- Because `scrape` now uses the light page + ambient harvest, a SUCCESS also proves:
  - **U1**: the root `https://chatgpt.com/` page emitted a `/backend-api/*` request
    carrying all 8 required headers (else `BackendAuthUnavailableError`).
  - **U2**: the conversation fetch accepted the VERBATIM `x-openai-target-route`
    (else a fetch/HTTP error). If it FAILED specifically with
    `BackendAuthUnavailableError` → U1 negative; if a fetch/HTTP 4xx/route error →
    U2 negative (route must be reconstructed). Report the EXACT error CLASS NAME
    only (from the stderr log) — never paste tokens/urls-with-ids/content.

## Verify fidelity FROM THE CACHE (local; counts/booleans only — NO content dumps)
From `cache/conversations/<id>/` (resolve `<id>` from TARGET_URL):
- transcript.jsonl + transcript.md + raw-mapping.json exist.
- Turn count (dedupe transcript.jsonl by `message_id` — keep last per id), total
  char/byte size, mapping node count, and that capture `source` is `backend_api`.
- Math-fidelity sample (report COUNTS only): occurrences of `\widehat`, `\ne`,
  `\frac` (>0 expected if this is a math conversation); flattened-frac signature
  count (expect 0); literal U+2260 `≠` count in canonical text (expect 0).
- Report RSS/elapsed if available as a rough cost signal (the fix should be fast vs
  the prior 10-min hang).

## Safety (NON-NEGOTIABLE — operator's real account)
- own-tab-only: only the tab the tool itself opens. NEVER read/inspect/close the
  operator's tabs; NEVER quit the browser (detach only); NEVER `/json/list`.
- ZERO sends. Never print/log/persist auth tokens, OAI header VALUES, cookies,
  conversation content, file ids, or attachment bytes. Header NAMES ok.
- NEVER commit cache content (`git add cache` forbidden); never move/commit `stable`;
  never `uv tool install/upgrade/reinstall`; no push/merge.
- login wall / Cloudflare "Just a moment" → STOP, report `HUMAN-ACTION-NEEDED`.

## Deliverable + handoff
Write **`team/evidence/handoffs/M10-T4-realsite.md`**: STATUS token; exit code +
elapsed; CRASH yes/no; the fidelity counts; U1 + U2 verdicts; exact error class if
any; and a safety attestation (zero sends; own-tab-only; no `/json/list`; no leak;
`git rev-parse stable` unchanged = bbbe027; cache not committed). Then verify
`git status` shows no staged cache/source changes.
