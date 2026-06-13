# NEXT SESSION (post-compaction) — ask-chatgpt team lead resume handoff

Authoritative pickup for a compacted/fresh team-lead agent. Read this FIRST, then re-verify every live claim from ground truth before acting (you inherit nothing but what you read).

## Read order
1. THIS file. 2. `orchestration/team.json` (identity). 3. `orchestration/state/lead.state.json` (ledger + apparatus_lessons). 4. `VERIFICATION.md` — especially the **CORRECTION** section. 5. `docs/DECISIONS.md` (D-001 channels, D-002 real-site/CDP). 6. `docs/BACKLOG.md`. 7. `README.md` (spec).
Then GROUND-TRUTH probe: `git log --oneline -8`; `tmux ls | grep -E 'pi-worker|claude-orch'` (expect none); `uv run pytest -q` (expect `198 passed, 1 deselected`); `curl -s http://127.0.0.1:9222/json/version` (operator's CDP browser — only up during a run window).

## Where we are
Directive M-001..M-007 built all 3 README use cases — library `ask_chatgpt()->text`, zip bundle-out + patch-bundle apply, `ask-chatgpt` CLI — MOCK-proven (198 tests) and independently verified on the mock. Real-site claims were **PARTIALLY RETRACTED 2026-06-13** after the operator reviewed the actual chat transcript (`VERIFICATION.md` CORRECTION). Do NOT trust the old real-site "PASS".

### Proven vs NOT (real site)
- PROVEN: mock half (all 3 UCs, 198 tests, tier-purity, no-stealth, patch-apply validate-before-mutate); STRUCTURAL continuity (2nd turn reused the same `/c/<id>` thread via the JSON registry); tiny single-file UC2 **content** correctness (decoded zip = correct edit).
- NOT PROVEN (need corrected tests): SEMANTIC continuity (GPT actually using prior-turn context); robust/real-size bundle return; complete (non-truncated) `->text` for long responses.

## THE KEY INSIGHT (operator, 2026-06-13) — the prompts were the bug
The M-006 conclusion "real site fires no Playwright Download event → base64 is the real bundle path" was **CIRCULAR/WRONG**. We told ChatGPT to return a fenced **base64url TEXT** blob, so it returned text, so no download affordance appeared — there is no file to download when the model only emits text. **To get a real downloadable bundle FILE, the prompt must instruct ChatGPT to create/return the changed files as an actual downloadable zip file (it can via its tools), with NO base64 wording in the primary path.** base64-in-chat stays only as a genuine fallback.
GENERAL MANDATE (operator): my GPT-facing prompts were "horrible for testing." **Adversarially review EVERY prompt** — the bundle catalogue instructions (`src/ask_chatgpt/bundle.py:generate_prompt_instructions`) AND every real-site test prompt — for how a chatbot could misread it / what outcome the wording predetermines. Two known-bad examples: (a) continuity recall prompt CONTAINED the answer (`"Reply exactly: GAP15_RECALL N5C85C"`); (b) bundle prompt asked for base64 → sabotaged the download path. (Memory: `prompt-design-adversarial-review`, `tests-must-be-falsifiable`.)

## WORKSTREAM A — fix prompts + corrected real-site verification (call it M-008)
1. **Rewrite the patch-bundle return instructions** (`bundle.py:generate_prompt_instructions` + `docs/bundle-protocol.md` + the catalogue README) to ask ChatGPT to return the changed files as a **downloadable ZIP FILE** (changed-files-only; `manifest.json` preferred-but-OPTIONAL — operator decision #1 = keep the current manifest-or-reconstruct fallback). NO base64 in the primary path; base64 remains a labeled fallback. Adversarially review the wording.
2. **Re-test UC2 over CDP:** confirm a real download affordance now appears and Playwright captures the actual file; validate content + changed-files-only. (Mock fixture: add a download-file variant that mirrors the real affordance.)
3. **Falsifiable continuity test:** plant a nonce ONLY in turn 1; in turn 2 (same `session_identifier`, nonce ABSENT from the prompt) ask GPT to recall it; assert it returns the nonce. CONTROL: identical turn-2 against a FRESH conversation must FAIL (proves the test can fail). CROSS-PROCESS variant: turn-1 via one CLI invocation, turn-2 via a SEPARATE process (proves the JSON registry carries continuity across invocations). Use full-length nonces (also exercises truncation).
4. **Response-truncation test (UC1 CORE):** elicit a long, deterministically-verifiable response and assert it returns COMPLETE. If the reader clips (a short seeded nonce came back clipped in M-007 — `…1F3845_`), FIX the driver/reader completion+read logic. This affects `->text` generally, not just UC2.
5. Re-issue an HONEST `VERIFICATION.md` verdict. The best-of-N panel MUST include a falsifiability + prompt-quality lens (can each test fail? could the prompt be misread?), not just green-exit.
Real-site-gated (needs the operator's CDP browser up). Human-paced, audited, NO message cap.

## WORKSTREAM B — general ChatGPT add-on support, Deep Research first (backlog B-1)
Operator wants ONE general add-on/tools mechanism (NOT deep-research-specific — cleaner, more robust; memory `operator-prefers-general-abstractions`). Deep Research = first consumer. Steps: map the composer tools/"+" menu into `real.json` (no tool selectors today; this ALSO unblocks real model-selection B-2, currently fail-closed) → a select-tool/mode abstraction → handle the **clarifying-question round** Deep Research asks before starting → **long/multi-phase completion** detection (runs minutes, own progress UI) → read the report output (citations/sources may need structured extraction beyond `->text`). Keep `->text` as the base return.

## Apparatus (carry forward — all verified this directive)
- **Team-lead loop:** author self-contained mission contracts in `orchestration/tasks/`; dispatch each detached manager via a **Sonnet ops-runner** (background `Agent`, `model: sonnet`) that loops `bash orchestration/bin/claude-orchestrator-watch.sh --wait-seconds 480 [--watch <run-dir>]` (Bash timeout 600000ms), verifies SHIPMENT (deliverable files + handoff STATUS + verify VERDICT, never exit codes alone), returns a compact digest; bounded auto-recovery (max 2 relaunch on missing-handoff). **Singleton discipline:** launch once; re-check `tmux ls | grep claude-orch` before any retry (triple-launch bug B-4).
- **Managers** are headless `claude -p` (Opus): they DIE at turn end → NEVER background a watch; hold foreground `--wait-seconds 480` loops; write the handoff before ending. Charter `orchestration/roles/manager-role.md` carries the recipe + the no-message-cap + CDP rules.
- **Workers:** pi (GPT-5.5) via `.claude/skills/orchestration/references/pi-worker-watch.sh --wait-seconds 480`. pi minute self-reports are HALLUCINATED — derive ACTUAL from run-dir metadata. NO pi concurrency cap. Editing legs serialize (single editor); non-editing best-of-N lenses can run as parallel `claude Plan` subagents (cheaper than pi).
- **Real-site (D-002):** CDP attach to the operator's signed-in Chromium — profile "agent" = dir `Profile 1` — at `--remote-debugging-port=9222`. Cloudflare blocks Playwright-LAUNCHED browsers (hence CDP attach). Work ONLY in tabs the tool opens; never touch the operator's tabs; never quit the browser (detach only); login NEVER automated; any challenge → STOP + log `HUMAN-ACTION-NEEDED` + poll read-only 10 min; NO stealth/anti-detection ever. NO message cap (human-paced, no programmatic spamming; audit log = transparency only).
- NEVER `git push` (operator pushes). Telemetry: `ESTIMATE`/`ACTUAL` + `REWORK-CAUSE`. Keep team-lead context lean — delegate everything except judgement.

## Operator prerequisite for real-site legs
Operator launches, during a run window: `chromium --profile-directory='Profile 1' --remote-debugging-port=9222` (the "agent" profile, signed into chatgpt.com), then tells the team lead it's up. The team lead must preflight `127.0.0.1:9222` before any real leg and stop cleanly (`CDP_UNREACHABLE`) if it's down.

## Do NOT
- Do not dispatch M-008 or the add-on mission until the operator confirms (they paused real-site work pending this compaction). Re-verify the browser is up first.
- Do not trust the retracted real-site "PASS". Do not reuse the old continuity/bundle prompts — rewrite them.
