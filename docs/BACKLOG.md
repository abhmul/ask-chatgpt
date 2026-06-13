# Backlog — ask-chatgpt (future work)

The core directive (M-001..M-007) is mock-proven (198 tests); some real-site claims were RETRACTED 2026-06-13 (see `VERIFICATION.md` CORRECTION + `orchestration/NEXT-SESSION-compacted.md`). Next session picks up A (prompt fixes + corrected real-site verification M-008) and B-1 (add-ons).

## A — Corrected real-site verification (M-008) — PRIORITY (operator, 2026-06-13)

Root cause of the bad real-site results was prompt design, not the site:
- **"Downloads don't work" was circular.** The patch-bundle prompt asked for a base64url TEXT blob → GPT returned text → no download affordance (there's no file to download). FIX: rewrite the prompt to ask ChatGPT to return changed files as a **downloadable ZIP FILE** (no base64 in the primary path; base64 = fallback). Then capture the real file via Playwright.
- **Continuity test was circular** (recall prompt contained the answer) → redo falsifiable: nonce in turn 1 only; turn 2 asks with it absent; fresh-conversation control must FAIL; cross-process CLI variant.
- **Response truncation:** a short nonce came back clipped — test that `->text` returns long responses COMPLETE (affects UC1 core); fix the reader if it clips.
- Adversarially review EVERY GPT-facing prompt. Full plan in `orchestration/NEXT-SESSION-compacted.md` Workstream A.


## B-1 — General ChatGPT add-on / tools support (operator, 2026-06-13) — SCHEDULED for next session

Support ChatGPT's add-ons/tools (Deep Research, and others) via **ONE general, extensible mechanism — not a Deep-Research-specific feature.** Deep Research is the first consumer; the abstraction is "select a ChatGPT tool/mode, run it, then read its possibly-differently-formatted, possibly-long-running, possibly-multi-phase output." Operator rationale: a general tool interface is cleaner and more robust than N special cases — do not over-engineer for Deep Research.

Design notes when scoped:
- Map the composer tools/"+" menu into `real.json` (no tool selectors exist today). This also unblocks **real model-selection** (B-2), which shares the same menu-mapping work.
- A tool/mode abstraction: select tool → handle an optional **clarifying-question round** (Deep Research often asks one before starting) → **long/multi-phase completion detection** (runs minutes, with its own progress UI) → read output (report + **citations/sources** may warrant structured extraction beyond `-> text`).
- Keep `-> text` as the base return; richer structured returns are per-tool extensions.
- Occam: build the general tool interface, not a Deep-Research branch.

## B-2 — Real model-selection wiring

`model_settings` is built + mock-proven but **fail-closed on real** (`real.json` `model_menu`/`model_option` are empty; M-006 left them unmapped). Folds into B-1's menu mapping.

## B-3 — Real UC2 matrix breadth

Real UC2 **content** is proven only for the **modified-single-file** round-trip via base64 (now superseded — see A: re-prove via a real downloadable file). Added/deleted/multi-file are mock-proven only. Extend to real after A lands.

## B-4 — Launcher singleton guard (apparatus)

The triple-launch bug recurred in M-006 (absorbed each time by the manager-side atomic lock). Durable fix: a per-mission `flock` in `orchestration/bin/claude-orchestrator-watch.sh`.
