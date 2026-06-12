ESTIMATE: T6 45m
START_TIMESTAMP: 2026-06-12T02:04:41-05:00
END_TIMESTAMP: 2026-06-12T02:10:19-05:00

Task: T6 real-site acceptance runbook authoring.
Deliverable written: `docs/runbooks/real-site-acceptance.md`.
Report written: `orchestration/reports/M-003/T6-report.md`.

Runbook section outline:
1. Title: real-site acceptance for ask-chatgpt, operator-run and consent-gated.
2. Consent + safety preamble: real account/profile/quota, no automation, no credential/profile reads, typed consent per UC.
3. What is and is not proven before this runbook: mock-proven only; all real-site behavior expected but unproven until operator executes.
4. Prerequisite: operator must complete `docs/runbooks/observe-chatgpt-unknowns.md` and fill `src/ask_chatgpt/selector_maps/real.json` first.
5. `real.json` confirmation command: local-only JSON check for empty selector/attribute strings plus manual secret review.
6. Command freshness check: UC1 Python command matches current API; UC2/UC3 CLI commands marked confirm against `ask-chatgpt --help`.
7. Acceptance record template: nonsecret facts only, with pass/fail/blocked per UC and D-001 revisit notes.
8. Repeated NEVER AUTOMATED banner immediately before UC run steps.
9. UC1 procedure: one typed-consent Python command calling `ask_chatgpt(..., channel="real", profile_path=...)` with a nonce prompt.
10. UC1 expected observations and honest-failure table.
11. UC2 procedure: local synthetic setup, typed-consent CLI command to upload/retrieve patch bundle, local dry-run plus explicit apply to scratch root.
12. UC2 expected observations and honest-failure table.
13. UC3 procedure: CLI stdout command and CLI `--out` command, each with separate typed consent.
14. UC3 expected observations and honest-failure table.
15. Stop conditions and reporting: no private data, stop on failed validation, report facts vs interpretations vs speculation.

Existing docs/source anchored to:
- `orchestration/tasks/M-003/T6-runbook-real-site-acceptance.md`: full task contract, safety block, deliverable paths, telemetry requirements.
- `docs/runbooks/observe-chatgpt-unknowns.md`: matched operator-consent tone, nonsecret observation posture, and prerequisite role for filling `real.json`.
- `README.md`: three use cases, acceptance shape with mock half plus operator-gated real half, and honest failure modes.
- `docs/DECISIONS.md` D-001: DOM-primary text read with copy fallback; download-capture primary plus fenced fallback for bundles; operator-owned profile/credentials; empirical revisit triggers.
- `orchestration/handoffs/MISSION-002-handoff.json`: mock-proven vs real-site-unproven scope and fail-closed `real.json` state.
- `src/ask_chatgpt/api.py`: current public `ask_chatgpt` signature and default real channel.
- `pyproject.toml`: no `[project.scripts]` present at authoring time, so CLI spellings cannot be treated as final.
- `src/ask_chatgpt/errors.py`: current UC1 named errors available in source.
- `src/ask_chatgpt/selector_maps/real.json`: current all-empty fail-closed template shape used for prerequisite confirmation guidance.
- `docs/bundle-protocol.md`: checked by find; it did not exist at authoring time.

Commands marked "CONFIRM AGAINST `ask-chatgpt --help`":
- UC2 non-contact setup includes `uv run ask-chatgpt --help` as mandatory CLI freshness check.
- UC2 real-site upload/retrieve command using provisional `--channel`, `--profile`, `--session`, `--prompt`, `--files`, `--out`, and `--patch-out` spellings.
- UC2 local apply command using provisional `ask-chatgpt apply-patch`, `--bundle`, `--root`, `--dry-run`, and `--apply` spellings.
- UC3 stdout command using provisional `--channel`, `--profile`, `--session`, and `--prompt` spellings.
- UC3 `--out` command using provisional `--out` spelling.

Reason commands were marked for help confirmation:
- T5 CLI may still be in progress.
- Current `pyproject.toml` has no `[project.scripts]` entry.
- `docs/bundle-protocol.md` did not exist at authoring time.
- The README defines UC2/UC3 semantics but not final flag spelling.
- The runbook preserves required semantics even if final flag names change.

Named-error mapping notes:
- Existing source names used directly: `LoginRequiredError`, `SessionNotFoundError`, `ModelUnavailableError`, `ResponseTruncatedError`, `RateLimitedError`, `SelectorUnavailableError`, `UploadUnsupportedError`, `DownloadUnsupportedError`.
- Bundle-layer names in the runbook are the expected M-003 public names for the documented failure modes: `PatchBundleMalformedError`, `PatchBundleIntegrityError`, `PatchBundleTooLargeError`, and `PatchPathEscapeError`.
- If final M-003 implementation chooses different bundle error class names, the runbook flags/commands already require help/source confirmation before operator execution; the table should be mechanically updated to the final names before a real run.

Safety/trust notes:
- I did not contact `chatgpt.com`, OpenAI, or any external network service.
- I did not run the real channel.
- I did not run pytest or acceptance scripts.
- I did not read credentials, cookies, tokens, browser-profile contents, or private session data.
- I did not write outside `/home/abhmul/dev/ask-chatgpt`.
- I did not touch `.claude/`, `.agents/`, the shared agent venv, or the predecessor archive.
- The only shell commands executed were `date -Iseconds` for required telemetry.
- The runbook commands themselves are for a future consenting operator, not for automation.

Safety block reflection in the runbook:
- Top preamble states real-site/account/quota effects and typed consent requirement.
- Prerequisite section states real channel fails closed with `SelectorUnavailableError` until `real.json` is filled.
- Run steps repeat NEVER AUTOMATED banner.
- UC2 apply step requires dry-run, explicit root, local apply token, and explicit `--apply` before mutation.
- UC2/UC3 failure tables state malformed/hash/oversize/path-escape failures must prevent mutation.
- Multiple sections state no credential/cookie/token/profile-content reads/logging.

Unproven-scope honesty included:
- Runbook states every real-site behavior is expected but unproven until executed.
- UC1 does not claim to prove UC2 upload/download.
- UC2 distinguishes download-capture pass from fenced-fallback pass and records absent/inconclusive download support.
- UC3 distinguishes CLI preflight block from real-site failure when console script is unavailable.
- D-001 revisit triggers are listed for DOM-vs-copy reliability, download affordance, artifact wrong-turn risk, fenced truncation, and CLI output fidelity.

Deliverable status:
- `docs/runbooks/real-site-acceptance.md` created.
- `orchestration/reports/M-003/T6-report.md` created.
- No blockers for doc authoring.
T6-STATUS: DONE
