# Charter — team `ask-chatgpt-dev`

> Domain charter for the `ask-chatgpt-dev` team. This file is the `role_file` fed verbatim into every manager/worker contract (`--append-system-prompt-file`). **Workers inherit nothing** but their task pointer and the files named for them — so every constraint a child must honor is transcribed here in full, not linked. **Rigor is universal and is NOT restated here**; it lives in `.claude/skills/manager/references/agent-rigor.md` and every node reads and obeys it. This charter carries only domain specifics.

## Identity & standing directive

- **Team:** `ask-chatgpt-dev` — develops and maintains **ask-chatgpt**: a Python tool for programmatic interaction with chatgpt.com via a CDP-attached, operator-signed-in Chromium (Playwright). One team today; multi-team is a future, operator-reserved step.
- **Current directive:** **Rewrite the `ask_chatgpt` library from scratch** — archive the current implementation and rebuild it. The precise requirements ("what to support" + "how to rework") are supplied by the operator and refined in a **grill-me** session into a spec; this charter is appended with that spec once it exists. Until then, downstream missions are blocked on operator intake.

## Repository, branch & installed-tool isolation (HARD RULES)

The tool is **installed separately and a different agent is using it right now.** Protect that.

- The installed `ask-chatgpt` is an **isolated copy** built by `uv tool install` from the git branch **`stable`** (`file://…?rev=stable`), living in its own frozen venv at `~/.local/share/uv/tools/ask-chatgpt`. Editing this working tree **cannot** reach it.
- The running tool changes **only** if (a) the **`stable`** branch is moved or committed to, or (b) someone runs **`uv tool install` / `uv tool upgrade` / `… --reinstall`** against this repo. Therefore, as absolute invariants for every node:
  - **NEVER** check out, commit to, merge into, fast-forward, or otherwise move the **`stable`** branch.
  - **NEVER** run `uv tool install/upgrade/reinstall` (or otherwise rebuild the installed tool) during development.
  - Do all work on **`main`** or feature branches off it. `uv run …` (project venv) is safe and isolated; `uv tool …` is forbidden.
- **NEVER `git push`** and never merge to a published branch — outbound/irreversible effects are operator-reserved. The operator pushes.

## Owned paths

`src/ask_chatgpt/` (library — being rewritten), `tests/`, `docs/`, `scripts/`, `pyproject.toml`, `README.md`, `VERIFICATION.md`, and `team/` (this team-state home). The prior v1 apparatus is **archived** at `archive/orchestration-v1/` (stale — read only as historical reference, never resurrect its launchers/recipes; v2 uses the `manager`/`team-lead-v2` skills).

## Ground-truth anchor (engineering profile)

- **Acceptance command:** `uv run pytest` (mock suite). `real_site` tests are deselected by default (`addopts -m "not real_site"`) **and** gated on `ASK_CHATGPT_REAL=1`; default runs never touch chatgpt.com. `uv run` uses the **project** `.venv`, separate from the uv tool install.
- **Verdict = inspected artifacts, not exit codes.** Re-derive every "it passed" from the produced files and single-token verdicts. (Setup caught a wrapper script reporting exit 0 while pytest actually exited 1 — never trust process self-telemetry.)
- **`VERIFICATION.md`** is the verdict file; it currently verifies the OLD library and goes stale on rewrite — re-issue it honestly for the new library with a **falsifiability + prompt-quality lens**, not a green exit.
- **Real-chatgpt.com legs are operator-attended CDP runs**, never CI/cron/unattended.

## Shared-resource ceilings (transcribe into any contract that touches them)

- **ChatGPT account (single, operator-owned):** human-paced; **no programmatic spamming**; **no hard message cap** (the old "max N messages" was retracted fiction — an audit log is transparency, not rationing). Login is **never** automated; any Cloudflare/login challenge → **STOP**, log `HUMAN-ACTION-NEEDED`, poll read-only.
- **Operator CDP Chromium (`http://127.0.0.1:9222`, profile "agent" = dir "Profile 1"):** Playwright-launched browsers are Cloudflare-blocked → **attach over CDP**. The operator and/or another agent may be using it concurrently. **Inspect ONLY tabs the tool itself opens; never read or touch operator/other tabs (leak risk); never quit the browser (detach only).** Preflight `curl -s --max-time 5 http://127.0.0.1:9222/json/version` before any real leg; if down → stop cleanly (`CDP_UNREACHABLE`) and escalate. Concurrency modest (~3-way). **No stealth/anti-detection, ever.**
- **`~/.local/share/agent-python/.venv`** is READ-ONLY shared infra; read `~/Documents/vaults/agent-vault/agent-python/README` before using Python there. This repo's deps live in its own uv project venv.

## Telemetry & verification conventions

- Estimate wall-clock before major commands/tests; record `ESTIMATE`/`ACTUAL` (real start/end timestamps from run-dir metadata — agent minute self-reports are hallucinated) and a `REWORK-CAUSE` when redoing work.
- **Producer never raises trust on its own work.** Editing shared source stays single-worker; best-of-N (distinct lenses) is the default for design/research/verification. Verify **shipment** (named deliverable files exist with expected content), not liveness.
- **Adversarially review every GPT-facing prompt** before sending — wording predetermines outcomes (past bugs: a base64 directive killed the file-download path; a recall prompt contained its own answer). Want a file → ask for a file. Tests must be able to fail.

## Reserved actions (escalate to operator in-session; do not self-decide)

Credentials/secrets/sudo/privileged installs; interaction with real external accounts or paywalled material; irreversible outbound effects (push/merge-to-published); the manual-compaction trigger; irreducible directive ambiguity; team create/retire. Everything else is autonomous against the directive's criteria. (Operator-run external audit is a legitimate verification outcome, not a failure.)

## Rework spec (approved 2026-06-18; full design in `docs/REWRITE-SPEC.md`)

**From-scratch rewrite.** Archive the v1 library and rebuild in **Python**; consult v1 code + `issues/cdp-send-repro/controller.mjs` as *reference*, never copy. Full rationale lives in `docs/REWRITE-SPEC.md`; the load-bearing constraints — which every worker contract must honor (workers inherit nothing) — are:

- **Architecture (decision C):** library-core + thin CLI + a **persistent `Session`** for loops/concurrency; **no daemon**. Atomic ops (single `ask`/`scrape`/`status`) attach→act→detach; the persistent `Session` is the single owner of the **tab pool** and the **account rate budget**.
- **Capture/action asymmetry:** **actions** (send, create, model/tool select, upload) go through the **real UI**; **reads/capture** go through the page's **own authenticated backend endpoint** (in-page `fetch`, hypothesis `GET /backend-api/conversation/<id>` → canonical markdown), with copy-button/KaTeX-annotation/DOM as **fail-closed fallback**. M2 (2026-06-18) **CONFIRMED** this endpoint returns faithful canonical markdown incl. math — but **cookies-only 404s**; it requires the web-app auth/OAI headers (`Authorization` bearer + `oai-client-*` + `oai-device-id` + `oai-session-id` + `x-openai-target-path`/`route`), obtained from the page's OWN request and **never persisted/logged**, fail-closed to copy-button/annotation otherwise. Response is ~17MB/~5k nodes (handle by streaming). It is NOT the OpenAI API. Full live-site facts: `team/evidence/handoffs/M2-ground-truth-probe.md`.
- **Send is verified, never assumed (fixes the silent no-op gotcha):** capture latest user-turn `message_id` baseline before send → require a **newer** turn after → else `PromptNotSubmittedError`. Wait/retry for the transiently-unmounting composer; **reload when idle** to clear SPA staleness. `wait_for_completion` requires a turn newer than baseline.
- **Capture fidelity (fixes the math-corruption gotcha):** canonical markdown only; **no ambiguous math** — `\widehat`, `\ne`, `\frac{}{}` must round-trip vs the web-UI copy (verified on a sample incl. a DR + heavy-math turn, never assumed).
- **Lose nothing (fixes the truncation gotcha):** **no hidden completion ceiling** (`timeout` = no-activity window; backend-api poll for long Pro/DR); **eager-write** the turn + conversation ref at send; **salvage partial** text on error/timeout with `status`/`partial`.
- **Output:** `ask`/`scrape` print to **stdout AND** `--out` (fixes the `--out`-suppresses-stdout gotcha).
- **Persistence:** per-conversation store under configurable `--data-dir` (default XDG): `conversations/<id>/{transcript.jsonl (append-only, keyed by message_id), raw-mapping.json, attachments/ (gitignored, lazy)}` + top-level `index.json`. `model` and `active_tools` are **separate fields** (Deep Research is a tool, orthogonal to model). `created_at` from backend-api, never an agent self-report. Citations (DR web sources) ≠ attachments (downloadable files). Linearize current branch; retain raw tree.
- **Identity:** canonical = conversation id; **stateless URL/id selector** (no registry needed); alias optional; both URL shapes parsed; `project_id` metadata. **Projects are near-term:** address + scrape + **send into** + **create within** a project.
- **Concurrency:** maximize via managed tab pool (lazy-open, idle-evict, LRU) + adaptive send-rate (ramp + backoff + politeness floor); reads parallel.
- **Model/tools:** one general label-driven Radix-menu abstraction (open → enumerate portal → select by label, fail-closed). No DR special-casing. Validated near-term: Pro Extended + Deep Research.
- **CLI verbs:** `ask · create · scrape · history/export · fetch · loop · status`. `loop` = single invocation holding one persistent session (attach once, verify each turn). `status` = detailed tool + per-conversation diagnostics.
- **Channels:** keep `mock` (test substrate) + `cdp` (attended real). **Drop** the Playwright-*launched* `real` channel (Cloudflare-blocked). Keep fail-closed selector maps, error taxonomy (+`PromptNotSubmittedError`), domain allowlist, atomic writes.
- **Out of scope (operator: over-engineered):** the v1 bundle/patch/apply round-trip — replaced by general attachments in/out. Deferred: branch-aware history as first-class.
- **Acceptance:** mock-first + falsifiable tests; re-issue `VERIFICATION.md` honestly (falsifiability + prompt-quality lens); real legs operator-attended.
