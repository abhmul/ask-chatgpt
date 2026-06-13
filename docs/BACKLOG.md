# Backlog — ask-chatgpt (future work)

The core directive (M-001..M-007) is complete: all three README use cases are mock- and real-proven. These are operator-flagged enhancements, not yet scheduled.

## B-1 — General ChatGPT add-on / tools support (operator, 2026-06-13)

Support ChatGPT's add-ons/tools (Deep Research, and others) via **ONE general, extensible mechanism — not a Deep-Research-specific feature.** Deep Research is the first consumer; the abstraction is "select a ChatGPT tool/mode, run it, then read its possibly-differently-formatted, possibly-long-running, possibly-multi-phase output." Operator rationale: a general tool interface is cleaner and more robust than N special cases — do not over-engineer for Deep Research.

Design notes when scoped:
- Map the composer tools/"+" menu into `real.json` (no tool selectors exist today). This also unblocks **real model-selection** (B-2), which shares the same menu-mapping work.
- A tool/mode abstraction: select tool → handle an optional **clarifying-question round** (Deep Research often asks one before starting) → **long/multi-phase completion detection** (runs minutes, with its own progress UI) → read output (report + **citations/sources** may warrant structured extraction beyond `-> text`).
- Keep `-> text` as the base return; richer structured returns are per-tool extensions.
- Occam: build the general tool interface, not a Deep-Research branch.

## B-2 — Real model-selection wiring

`model_settings` is built + mock-proven but **fail-closed on real** (`real.json` `model_menu`/`model_option` are empty; M-006 left them unmapped). Folds into B-1's menu mapping.

## B-3 — Real UC2 matrix breadth

Real UC2 is proven for the **modified-single-file** round-trip; **added/deleted/multi-file are mock-proven only.** Extend to real if desired (the README obligation is already satisfied).

## B-4 — Launcher singleton guard (apparatus)

The triple-launch bug recurred in M-006 (absorbed each time by the manager-side atomic lock). Durable fix: a per-mission `flock` in `orchestration/bin/claude-orchestrator-watch.sh`.
