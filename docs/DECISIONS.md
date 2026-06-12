# Design decisions — ask-chatgpt

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
