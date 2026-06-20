# M3 Lens 5 — CLI / loop ergonomics + error taxonomy + status (DESIGN ONLY)

**Read first, in full:** `team/contracts/M3-common-constraints.md`, then `docs/REWRITE-SPEC.md` (esp. §4 CLI, §12 status, §13 safety, §17 gotcha traceability), `team/evidence/handoffs/M2-ground-truth-probe.md`, `team/charter.md`, `.claude/skills/manager/references/agent-rigor.md`.

**Your lens:** design the **thin CLI verb surface, the keep-pushing loop, the named error taxonomy, and the `status` command** — the agent-facing ergonomics. The primary consumer is **autonomous agents** (scripted, not interactive), so verbs must be composable and outputs machine-friendly.

**Write your deliverable to:** `team/evidence/reports/M3-work/lens-5-cli.md` (begin with `STATUS:`).

## Produce these sections
1. **Verb surface.** For each verb give: arguments, flags, behavior, browser-or-not, and the `Session` method it maps to. Verbs (REWRITE-SPEC §4):
   - `ask <conv?> "<prompt>"` — send → verify new turn → wait → capture → append transcript → print to **stdout** (and `--out` if given). Flags: `--model LABEL`, `--tool LABEL` (repeatable), `--attach FILE` (repeatable), `--project ID`, `--timeout S` (no-activity window), `--max-total-wait S`, `--out FILE`, `--data-dir`.
   - `create` — start a conversation (optional `--project ID`); print URL/id.
   - `scrape <conv>` — populate JSONL store + render one markdown export; `--with-attachments`, `--out`, `--data-dir`. Read-only.
   - `history <conv>` / `export <conv>` — render local transcript to markdown, **no browser**.
   - `fetch <conv> <attachment>` — lazily download a referenced attachment.
   - `loop <conv> --message "keep pushing!!" [--max-iterations N]` — single invocation holding one persistent session.
   - `status [<conv>]` — diagnostics (§4 below).
2. **Output rule (gotcha #4).** `ask`/`scrape` **always** print to stdout **and additionally** write `--out` when given (never let `--out` suppress stdout). Specify the stdout format (e.g. the canonical markdown of the new/scraped turn(s)) so it's a usable fallback and machine-parseable.
3. **Keep-pushing loop.** Two forms: (a) **primary, agent-driven** — because addressing is stateless-by-URL and `ask` appends, an agent just calls `ask <url> "keep pushing!!"` repeatedly and supplies its own "is it solved?" judgement; (b) **`loop` convenience** — one invocation holds one persistent `Session`: attach once → idle-reload → send → verify-new-turn → wait-for-completion → append → repeat, bounded by `--max-iterations`. Design the loop control flow + how it surfaces each turn (stdout per turn) + stop conditions. **Adversarially note:** the loop message ("keep pushing!!") must not encode its own answer; want a file → ask for a file (charter prompt-design rule).
4. **Error taxonomy (named, actionable).** Design the exception hierarchy and which errors are **retryable**. Must include at least: `PromptNotSubmittedError` (send produced no new turn — loud + retryable), `CdpUnreachableError` (`CDP_UNREACHABLE` — preflight failed → escalate), a login-wall error (`HUMAN-ACTION-NEEDED` — STOP + poll read-only, never automate login), `DisallowedDomainError` (allowlist violation), a capture fail-closed error (auth headers unobtainable / backend shape unrecognised → fall back, flag), `CompletionTimeoutError` (no-activity window elapsed — carries salvaged partial text, `partial=true`), model/tool selection-not-reflected error, `ConversationNotFoundError`. Map each to an actionable message + exit code.
5. **`status` command contents (REWRITE-SPEC §12).** **Global:** version; CDP endpoint reachable (preflight `curl -s --max-time 5 http://127.0.0.1:9222/json/version`); browser attached + profile; **signed-in vs login-wall**; selector-map channel + validity; data-dir + #conversations + total turns + pending attachment downloads; concurrency/rate state; last error. **Per-conversation (`status <conv>`):** model, active tools, #turns, last-turn time/role, pending attachments, branch info. Specify a machine-readable output option (e.g. `--json`) since the consumer is an agent.
6. **Atomic-verb plumbing.** How each atomic verb constructs a short-lived `Session` internally (attach→act→detach), and how `loop`/concurrent agents hold one open (defer pool/rate internals to lens 4; just show the wiring).

End with **"Cross-cluster interfaces & dependencies"** (verbs → `Session` API/lens-1; errors used across all modules; `status` reads store/lens-2 + rate state/lens-4 + CDP/capture state/lens-3) and **"Open questions / assumptions"**. Occam: the CLI is **thin** — logic lives in the library; verbs just parse args, call a `Session` method, and format output.
