# Design decisions — ask-chatgpt

## D-002 (2026-06-12): Real-site automated testing enabled by operator consent — tiered, bounded, audited

**Status:** DECIDED (team lead), on explicit operator grant 2026-06-12: "It is okay to do automated tests with the real chatgpt account. I am signed into both chromium and firefox currently." Supersedes the absolute "automated tests NEVER contact chatgpt.com" rule (README, charter, seed) with the following bounded posture:

1. **Two test tiers.** The DEFAULT suite (`uv run pytest`) remains loopback-mock-only — deterministic, zero quota. Real-site tests live behind a `real_site` pytest marker, deselected by default, and additionally gated on `ASK_CHATGPT_REAL=1` — both conditions required; CI-style runs can never hit the real site accidentally.
2. **Bounded consumption.** Any real-site run has a HARD message budget (≤30 messages per full run; per-phase sub-budgets), every message logged with purpose to an audit artifact. Stop at budget → honest PARTIAL, never silent overrun. Rate-limit signals are honored as named failures, not retried through.
3. **Headed, operator-session, login never automated.** Real runs use the operator's signed-in Chromium profile, headed (no headless on a personal account); the profile path is opaque config — contents never read/stored/logged; if logged out or the profile is locked by a running browser, raise the named actionable error and stop. Firefox sign-in is noted as a fallback lane only.
4. **Network discipline inverts, not disappears.** The default tier keeps the socket guard; the `real_site` tier replaces it with a browser-level domain allowlist (chatgpt.com + empirically-discovered asset domains), so real tests still cannot wander.
5. **What this unlocks:** the previously operator-manual runbooks (observe-unknowns selector discovery; UC1–3 real-site acceptance) may now be agent-driven, same bounds. Operator retains: signing in, closing the browser for run windows, and `git push`.

**Rejected:** making the default suite contact the real site (non-deterministic, quota-burning, no upside); copying/exporting cookies into an automation profile (violates credential non-reading); headless real-account automation (worst anti-bot posture for no benefit).



## D-001 (2026-06-11): Response & file return channels — bounded extraction, departing Level B deliberately

**Status:** DECIDED (team lead), recorded before any implementation. Informed by `orchestration/reports/M-001/decision-memo.md` (independently verified, `VERDICT: PASS`); archive rationale read first per operator instruction.

### Context

The predecessor control-plane's Level B contract allowed only seeding prompts into the chat UI and forbade extracting assistant output; results returned through an MCP connector. This repo's spec (`README.md`) makes `ask_chatgpt(...) -> text` and patch-bundle retrieval core acceptance obligations — without the connector. The M-001 memo established (with citations, independently verified) that the archive's prohibition was an architecture choice serving the events-canonical connector product — selector fragility was anticipated not measured, adversarial assistant-DOM risk was proven only as a mock tripwire, and **no resolved ToS/ban-risk claim against bounded DOM reading exists in the archive**. The product definition changed; pure Level B cannot implement this spec.

### Decision

1. **Plain text (`-> text`): PRIMARY = bounded DOM extraction; FALLBACK = copy-button/clipboard.** Both implemented behind one `ResponseReader` interface with configurable order; both must pass the same adversarial mock fixtures. The bounded reader is NOT a generic scraper: latest completed assistant turn only, selector-map-scoped, explicit completion detection, no history sweep, fail-closed with actionable errors (`RESPONSE_TRUNCATED`, selector-unavailable).
2. **Patch bundle (zip): PRIMARY = Playwright file-download capture; FALLBACK = checksummed fenced base64url zip over the text channel** (BEGIN/END markers, manifest, byte count, SHA-256 validated before apply). Any claim of *real-site* download support is gated on the operator observation runbook; the fallback keeps the design from depending on an unproven affordance and keeps mock acceptance deterministic.
3. **Connector-style callback: not shipped as default.** Reserved as a possible later structured/audited mode; heavyweight and contrary to the library-first, no-daemon posture.
4. **Level B disciplines that survive unchanged:** operator-owned profile and credentials (tool never reads/stores/logs them); automated tests loopback-only (never chatgpt.com); selector maps as operator-versioned data; fail-closed on stale selectors (stop, never guess or broaden); adversarial-fixture testing against prompt-injection/booby-trap DOM; no transcript-wide scraping ever.

### Why DOM-primary (team-lead deviation from the memo's copy-primary recommendation)

The memo preferred copy-button first for UI-owned Markdown serialization. Overriding considerations:

- **Clipboard side effects:** real-site runs are headed on the operator's profile; every copy-click overwrites the operator's OS clipboard mid-work. A tool that clobbers the user's clipboard on every call is bad desktop citizenship. (Reasoning, not measured — the runbook observes actual behavior.)
- **Fewer moving parts (Occam):** copy needs the same latest-turn targeting as DOM reading PLUS a (possibly hover-hidden) button PLUS clipboard permission machinery. Bounded DOM read is strictly simpler.
- **Fidelity is acceptable:** the spec returns "the assistant's response text"; rendered-text extraction preserves content (including code text). Markdown-source fidelity is a nice-to-have, available via the copy fallback.
- **Empirical revisit trigger:** if the operator runbook shows real-site DOM extraction materially flakier than copy-click, flip the default order (a constant, not a redesign).

### Rejected

- Pure Level B (no reader) — cannot implement the spec.
- Copy/clipboard for binary bundles — text-only, truncation-prone.
- Downloads for ordinary text — artifact-heavy, unproven affordance.
- Connector as default — heavy, server-visible, approval/tunnel-dependent.
- Fenced base64 as the only bundle path — unknown response-length limits.

### Deferred to operator-gated runbooks (memo §7, verbatim source of truth)

Zip upload size/type limits; whether/when responses offer file downloads (and Playwright `Download` integrity); session pinning via stored conversation URL/ref; model-selection UI hooks; copy/clipboard behavior and telemetry visibility; completion signals; upload UI hooks; text-channel truncation limits; artifact↔turn identity; honest-failure detectability. Automated tests never touch chatgpt.com; these are resolved only by operator-consented runbook runs.
