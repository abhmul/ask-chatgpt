START_TIMESTAMP: 2026-06-12T00:05:17-05:00
ESTIMATE: T8 20m
END_TIMESTAMP: 2026-06-12T00:08:40-05:00

Deliverable written:
- docs/runbooks/observe-chatgpt-unknowns.md

Ten memo §7 unknown sections covered:
1. Zip attachment upload size/type limits
2. Whether/when ChatGPT offers file downloads from responses
3. Session pinning via URL/conversation ref
4. Model-selection UI hooks
5. Copy-button/clipboard behavior
6. Assistant completion signal
7. File upload UI hooks
8. Text-channel size/truncation limits
9. Artifact↔turn identity and wrong-turn risk
10. Operator UX/failure messaging

Safety/telemetry confirmation:
- Documentation-only runbook created with prominent safety preamble.
- Manual operator steps only; no automation against chatgpt.com/openai was run or described as being run by this worker.
- No uv, pytest, Playwright, build, git commit, or git push was run.
- Touched no src/, tests/, pyproject.toml, or uv.lock; only the runbook deliverable and this report were written.
- Included M-003-consumable results template and cross-references to memo §6 mock assumptions plus later real selector map/tool config.

Deviations: none.
T8-STATUS: DONE