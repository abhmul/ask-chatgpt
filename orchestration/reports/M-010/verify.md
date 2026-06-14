# M-010 T4 producer-side verification

Producer-side docs verification for T4. Scope: docs edits only (`docs/USAGE.md`, `VERIFICATION.md`) plus this report; no code changes and no real-site interaction.

## Honesty / no-overclaim lens — PASS

Verdict: **PASS, with scoped claims only**.

Evidence checked: `orchestration/reports/M-010/discovery.md` and `orchestration/reports/M-010/T3-switch-proof.json`.

- `docs/USAGE.md` now says `model_settings={"model": "<label>"}` selects a **top-level composer-toolbar picker option** on the real site, not an arbitrary base model. This matches discovery: `model_menu` is `form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])`, and options are `[data-radix-popper-content-wrapper] [role="menuitemradio"]`.
- The docs preserve the mode-vs-base-model-family distinction: `Instant`, `Medium`, `High`, `Extra High`, and `Pro Extended` are described as GPT-5.5 reasoning/throughput tiers in the composer picker, while the `GPT-5.5` submenu is explicitly not wired.
- Proven-label scope is underclaimed: UI-state switching is stated only for `Extra High` → `Instant` and `Instant` → `Medium`, with `Extra High` as start/restore; end-to-end `ask_chatgpt(model_settings)` is stated only for `Instant`; `High` and `Pro Extended` are listed as observed available/enabled only.
- Fail-closed behavior is stated as `ModelUnavailableError` before any send for absent labels, matching the T3 absent-label proof (`message_count` 0→0 and trigger unchanged).

Residual overclaim: **none found** in the new T4 docs text.

## Safety / leak lens — PASS

Verdict: **PASS**.

Evidence checked: `orchestration/reports/M-010/real-audit-log.md`, `orchestration/reports/M-010/discovery.md`, `orchestration/reports/M-010/T3-switch-proof.json`, and the requested grep.

- Leak grep run: `grep -riE "abhmul|gmail|@.*\.(com|org)|profile|signed in|log ?out" orchestration/reports/M-010/ || true` returned **no output**.
- The committed M-010 artifacts contain model labels, selector/trigger text, redacted prompt labels, counts, and timestamps; I found no account/profile/email/name/avatar/plan disclosure in the reviewed artifacts.
- The audit log records attach-only/own-tab behavior (`open own tab conversation`), human-paced timestamped actions rather than a rapid prompt loop, no automated login, discovery actions with `no prompt sent`, and no option selected during discovery. T3 restored the original selection (`Extra High`) after switching.
- The only real send in M-010 was the trivial end-to-end `model_settings` entrypoint check; fail-closed absent-model proof sent nothing.

## Prompt-quality lens — PASS

Verdict: **PASS**.

Evidence checked: `orchestration/reports/M-010/real-audit-log.md` row 63 and `orchestration/reports/M-010/T3-switch-proof.json`.

- Discovery and UI switch/fail-closed legs used no GPT-facing prompts; switches were proven by DOM/UI state, specifically the composer trigger's visible label changing, not by asking the model which selection was active.
- The only GPT-facing prompt was `Reply with only the word OK.` for the end-to-end `ask_chatgpt(model_settings={"model":"Instant"})` smoke check. It is non-leading for model-selection validation and does not predetermine the verification outcome; the model-selection proof rests on UI-state and fail-closed assertions.

## Open follow-ups / brittleness

- Base-model-family selection remains open: the `GPT-5.5` submenu is observed but not wired; requesting submenu/base-family labels should fail closed rather than silently selecting the wrong thing.
- Selector brittleness remains: `model_menu` is attribute/structure-based (`form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])`) and `model_option` depends on Radix popper/role structure (`[data-radix-popper-content-wrapper] [role="menuitemradio"]`). UI drift should fail closed via selector/model-unavailable errors.
