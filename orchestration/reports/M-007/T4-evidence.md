START_TIMESTAMP: 2026-06-13T00:55:17-05:00

# M-007 T4 evidence summary

Raw evidence directory: `tmp/verify-m007/`

## Dependency/test evidence
- Fresh deps: PASS — `uv sync --all-groups` exit `0`; raw `tmp/verify-m007/sync.txt`.
- Full serialized suite: PASS — `====================== 198 passed, 1 deselected in 51.08s ======================`; `PYTEST_EXIT_CODE: 0`; raw `tmp/verify-m007/pytest-full.txt`.

## Tier purity
- PASS — default config deselects `real_site`: `pyproject.toml:20` has `addopts = ["-m", "not real_site"]`; `tests/conftest.py:17-20` skips `real_site` unless `ASK_CHATGPT_REAL=1`; raw `tmp/verify-m007/tier-config.txt`.
- PASS — `uv run pytest -m "not real_site" --collect-only -q | tail -3`: `198/199 tests collected (1 deselected) in 0.08s`; raw `tmp/verify-m007/collect-not-real.txt`.
- PASS — `uv run pytest -m real_site --collect-only -q | tail -5`: `1/199 tests collected (198 deselected) in 0.09s`; raw `tmp/verify-m007/collect-real.txt`.

## Safety checks
- No-stealth grep: PASS — searched `src/` and `tests/` for stealth/fingerprint/UA-spoof/AutomationControlled tokens; `RESULT: NO_MATCHES`; raw `tmp/verify-m007/grep-stealth.txt`.
- Socket guard: PASS — autouse loopback/AF_UNIX guard active at `tests/conftest.py:36-60`; default-tier assertions at `tests/test_network_guard.py:9-12` and `tests/test_smoke.py:23-31`; raw `tmp/verify-m007/grep-socket-guard.txt`.
- CDP safety: PASS — cdp attach uses `src/ask_chatgpt/driver.py:481 connect_over_cdp`; cdp close path at `src/ask_chatgpt/driver.py:162-168` closes only owned pages, while `context.close()`/`browser.close()` are in the non-cdp branch at `src/ask_chatgpt/driver.py:176-184`; detach-preservation test pointers `tests/test_driver_cdp_attach.py:285-317`; raw `tmp/verify-m007/grep-cdp.txt`.
- Leak grep: PASS — no `/c/<hexish>` or email matches in last-8 commit messages or M-007 reports; raw `tmp/verify-m007/grep-leak.txt`.

## Git provenance
- PASS — recent M-007 commits present: `5c26977` T1 fenced patch bundle format, `90e4f86` T2 GAP-15 persistence, T3 drift/runbook commits `9b7fd30` and `4a68100`; raw `tmp/verify-m007/git-provenance.txt`.
- Working tree before this T4 report had only untracked M-007 orchestration artifacts; no staged entries, no staged secrets/venvs/`*.db`/account identifiers observed; raw `tmp/verify-m007/git-provenance.txt`.

## T3 real artifacts (redacted summary only)
- T3 report: `orchestration/reports/M-007/T3.md`; `MESSAGES_USED: 8`; `UC2_DIFF_OK` and `GAP15_CONTINUITY_OK` both present; raw summary `tmp/verify-m007/t3-artifacts.txt`.
- Artifact root listed: `tmp/real-accept-m007-20260613T003803-0500/`; audit ledger listed: `tmp/real-audit-20260613T003803-0500/messages.log`.
- UC2 evidence present: raw assistant response file, fenced patch bundle zip, fresh apply root, and apply summary showing exactly `example.txt` modified while other seeded files remained unchanged.
- GAP-15 continuity evidence present: successful retry artifact, seed/recall response files, stable persisted redacted conversation ref, and `same_ref: true` in redacted summary.

END_TIMESTAMP: 2026-06-13T01:01:24-05:00
T4-EVIDENCE-STATUS: DONE
