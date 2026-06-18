# Worker contract — M-009 T5 independent verification (read-mostly; NO edits to src/docs)

You are an INDEPENDENT non-producer verifier. You did NOT write any of this. Be adversarial. Your job
is to find OVERCLAIM and inaccuracy, not to rubber-stamp. Do NOT edit any source/doc/selector file. You
MAY run read-only commands (`uv run pytest`, `git log`, read files). Do NOT `git push`. Do NOT contact
chatgpt.com (do not run anything under `scripts/m009_real_probe.py`; the real probes were already run by
the manager — reason over their artifacts).

## The MANDATORY lens
Does `docs/USAGE.md` claim anything as real-proven / supported that the ground-truth artifacts and code
do NOT support? Check EACH claim against evidence and report every gap.

## Inputs to read
- `docs/USAGE.md` (the artifact under audit).
- `VERIFICATION.md` (esp. the M-008b section, lines ~161-202) — prior real-proven scope.
- `orchestration/reports/M-009/T1-uc2-roundtrip.json` — UC2 real round-trip evidence.
- `orchestration/reports/M-009/T2-short-response.json` — short-response evidence.
- `orchestration/reports/M-009/T3-model-findings.md` — model-selection fail-closed.
- `orchestration/reports/M-009/discovery.md` — manager's ground-truth read.
- `src/ask_chatgpt/selector_maps/real.json`, `src/ask_chatgpt/errors.py`, `src/ask_chatgpt/cli.py`,
  `src/ask_chatgpt/driver.py` (wait_for_completion), `src/ask_chatgpt/patch.py`
  (_scan_download_artifacts / _download_candidate_bytes), `src/ask_chatgpt/__init__.py`.

## Checks (be specific; cite file:line or artifact field for each verdict)
1. **UC2 real-proven claim.** USAGE says UC2 round-trip (capture+apply+diff+content) is real-PROVEN. Is
   that supported by `T1-uc2-roundtrip.json`? Confirm the fields actually present: `retrieve_outcome`,
   `bundle_source`, `content_correct`, the applied text, `download_selector_injected` (was it the
   SHIPPED config, i.e. null/none, not an injected override?). If content_correct is true AND it used the
   shipped real.json, the claim holds; otherwise flag overclaim.
2. **Short-response claim.** USAGE says short replies return with 0 spurious truncations. Does
   `T2-short-response.json` show `summary.returned == prompts` and `spurious_truncations == []`? Confirm.
3. **Model-selection claim.** USAGE says real model selection FAILS CLOSED (not wired). Verify
   `real.json` has `model_menu`/`model_option` empty, and that `select_model` (driver.py) raises on an
   empty `model_menu`. Confirm USAGE does NOT claim real model selection works.
4. **Download-path honesty.** USAGE says the real download has no integrity metadata and the zip is
   validated structurally. Verify against patch.py `_scan_download_artifacts` opaque branch +
   `_download_candidate_bytes` (byte_count/sha256 None tolerated). Confirm `real.json` download_artifact
   == `button:has-text("Download the patch bundle")`.
5. **Error table.** Cross-check every error in USAGE's table against `errors.py` (exists, subclasses
   AskChatGPTError) and the CLI exit codes against `cli.py` `_ERROR_EXIT_CODES`. Flag any wrong code,
   missing error, or invented error.
6. **Test-tier claim.** USAGE says `uv run pytest` = "212 passed / 4 deselected", mock-only, no quota.
   INDEPENDENTLY RUN `uv run pytest -q` and report the EXACT tail. If it is not 212 passed / 4 deselected,
   flag it. (Run `uv sync --all-groups` first if imports fail.)
7. **Channel honesty.** USAGE says CLI default `--channel real` is Cloudflare-blocked and agents must use
   `--channel cdp`. Confirm `cli.py` default is `real` and the CDP-attach posture matches driver.py.
8. **No-leak spot check.** Grep `orchestration/reports/M-009/` for obvious account identifiers / unredacted
   `/c/<id>` / tokens. Report anything found (do not reproduce the value — just the file+kind).

## Output
Write `orchestration/reports/M-009/T5-usage-overclaim-verify.md`:
- `VERDICT: PASS` (no overclaim; accurate) or `VERDICT: CONCERNS` with a numbered list of each specific
  overclaim/inaccuracy and the exact fix.
- The independent `uv run pytest -q` tail (verbatim).
- A short per-check table (check # -> OK / CONCERN -> evidence).
- Telemetry: `ESTIMATE: T5-verify <m>m`, `ACTUAL: T5-verify <m>m`, end timestamp from `date -Iseconds`.
- Do NOT edit src/docs; do NOT commit; do NOT push.
