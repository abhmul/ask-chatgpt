# M5 — Live CdpChannel + backend-api capture + scrape capability — handoff

STATUS: **DONE** (substantively complete + verified-safe). The M5 Opus manager completed T2 (build) + T3 (real-leg) + dispatched the T5 verify panel, but its session exited before T6. The **team lead** collected the panel verdicts, independently leak-audited the committed real-site artifacts, and wrote this handoff. (The V3 acceptance lens was still completing at write time — collect `team/evidence/reports/M5-verify-V3.md` when written; the gate below stands on V1 safety + V2 falsifiability + the real-leg confirmation + the lead audit.)

## Verdict — real backend-api capture + scrape CONFIRMED end-to-end, leak-clean
- **T2** (commit `5966814`): `CdpChannel` read-path — lazy Playwright import, `/json/version` preflight, own-tab attach + detach-without-quitting; own-page request header acquisition (auth/OAI headers, **never persisted/logged**); streaming backend fetch; capture parser wired to REAL backend JSON; `scrape` over CDP. Offline suite green (**205 passed**, incl. 17 new `test_cdp_channel.py`; no-playwright pins hold).
- **T3** (commit `09eee7f`; `team/evidence/reports/M5-T3-real-leg.md`):
  - **Smoke `6a3483b3`: scrape CONFIRMED end-to-end** (7 turns, 10,608 chars markdown, 87 nodes).
  - **Target `6a316aa8` read-only scale:** 481 turns, **2,031,266 chars markdown, 6,124 nodes, 20.19 MB** raw-mapping (transcript.jsonl ~5.2 MB, markdown export ~2 MB). Written to OUT-OF-REPO tmp (nothing scraped committed).
  - **Fidelity on REAL data:** `\widehat`=true, `\ne`=true, `\frac`=true, no literal `≠`, no flattened fractions → **gotcha-#1 solved at the source on the real target**.
  - **Memory:** target end-to-end RSS ~354 MB / tracemalloc peak ~254 MB (near 256) → keep whole-file `json.load` for M6.
  - **Completion vocab catalogued:** `async_status`, `message.status` (finished_successfully/in_progress), `is_complete`, `is_finalizing`, `pro_progress`. `/stream_status` not probed.
  - All 8 required header NAMES present (names/booleans only).

## Verification (independent of the producer)
- **V1 safety/leak** (`M5-verify-V1.md`): **PASS** (CONFIRM-WITH-FINDINGS) — no header-value leak, no conversation-content leak (no transcript/raw-mapping/`data/` committed), redaction proven with file:line + canary tests, **ZERO-send** (CDP `fill`/`click`/`press`/`upload`/`read_clipboard` raise `HumanActionNeededError`), **own-tab-only** (no `context.pages`), isolation hygiene. 2 LOW: (1) dirty worktree pre-existed (external `controller.mjs` + lead `live-state.json`); (2) hardening — route non-`pro_progress` status-vocab strings through the secret-guard.
- **V2 offline falsifiability/correctness** (`M5-verify-V2.md`): **PASS** — 205 passed; 188 pre-M5 cases still green; no-playwright pins hold; falsifiability map.
- **V3 acceptance-conformance:** lens completing at write time (corroborated by the demonstrably-working end-to-end scrape); fold in when written.
- **Lead independent leak audit:** CLEAN — confirmed no auth tokens, no cookies, no conversation content, no conversation IDs in git; redaction held (canary-proven).

## Safety held
own-tab-only; **ZERO sends/new-turns**; browser left running; out-of-repo tmp artifacts (nothing scraped committed); no auth/OAI/cookie values or conversation content in any committed file; `stable` `779eb40` unmoved; no `uv tool`; no push.

## Blockers / recommended next
- **None blocking.** **M6 = run the TARGET scrape `6a316aa8` WITH attachments** into the operator's chosen `--data-dir` + final fidelity confirmation + deliver. The capture/scrape path is PROVEN; M6 must additionally **discover the attachment BYTE-download routes** (deferred from M5 — M2/T3 saw ids/pointers/asset_pointers, no literal `/files/` URLs), fetching into the gitignored `attachments/` dir. Attended, own-tab-only, still ZERO sends.
- Open-Qs resolved by live data: completion vocab; memory budget (whole-file OK); math fidelity (intact). Still needing live: **attachment byte routes**; `stream_status` (not probed); multi-part join (not stressed on real data).
- LOW hardening: status-vocab secret-guard (V1 finding #2) — fold into a later pass.

## Send path note
Real-CDP SEND mechanics were NOT built in M5 (read-only phase, deferred). M4's send/completion is mock-proven; a real send-smoke is a later mission before M7's keep-pushing loop.
