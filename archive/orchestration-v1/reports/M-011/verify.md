# M-011 verification

## Producer-side verification — what was REALLY observed vs not

- **VERIFIED (real, self-derived from our own CDP tab):** tools-menu trigger + 7 options + kinds + the Deep Research option + the armed-chip behavior + "Escape keeps armed" (T1, reproduced in the T2 open); DR select + submit + arm; a completed turn at ≈ +8s carrying a `button[data-testid="copy-turn-action-button"]` but NO `[data-message-author-role="assistant"]` (the turn-selector finding); PARTIAL-TIMEOUT at the 2400s ceiling (300 polls).
- **NOT verified / UNKNOWN (load-bearing for M-012):** the clarifying-question TEXT and exact structure (turn not captured); a genuine research/activity progress UI (only a false-positive chip match); the FINAL REPORT structure + CITATION rendering (run never reached the report). The DR completion signal is therefore only partially characterized: we know a turn's copy-marker appears, and that DR turns are NOT author-role-tagged, but we did NOT observe the *final-report* completion.
- **UNVERIFIED LEAD (provenance-disclosed, do NOT treat as evidence):** during the run a since-deleted inspector incidentally (and wrongly — see INCIDENT) observed that a *completed* Deep Research report can render as `section[data-testid="conversation-turn-N"]` containing a nested `[data-message-author-role="assistant"]` with a "Thought for Xm Ys" header and multiple headings/list-items. This was from a MIS-TARGETED tab, its content was scrubbed, and it is NOT verified on our own run — M-012 must verify the report+citation structure directly. No operator content is reproduced here; only the generic structural shape is noted as a lead.

## INCIDENT — operator-content leak (caught + scrubbed)

> During T2, the manager wrote a read-only CDP inspector (`scripts/_m011_inspect.py`) to diagnose why the recorder saw `assistant_turn_count=0`. To find the Deep Research tab among the browser's open tabs, the inspector matched on loose substrings (`lfp` / `nmc`) and the Deep Research chip. The operator was **concurrently** running their own, unrelated Deep Research conversation, and that loose match selected the OPERATOR's tab instead of ours. The inspector captured ~5 gated lines of the operator's conversation (an unrelated research topic) into `orchestration/reports/M-011/T2-dr-inspect-initial.json`. This was a leak of operator-private (non-PII) content. It was caught on the FIRST (read-only) inspector run — no second run, and `--answer-clarify` was NOT used, so the operator's session was never modified. Remediation, same step: both `T2-dr-inspect-initial.json` and `scripts/_m011_inspect.py` were DELETED; `git log` confirmed HEAD was unchanged (still the dispatch commit), so the leaked content NEVER entered git history; a full leak scan (operator terms + `/c/<id>` + token patterns) over all M-011 artifacts returned CLEAN. The captured lines were printed to the manager's transient session log (not a repo artifact). ROOT CAUSE: loose-substring tab identification. LESSON: only inspect the recorder's OWN owned tab; never enumerate the operator's tabs; if a tab must be identified by content, use a precise verbatim phrase, never loose substrings.

## Leak scan (record the commands + the CLEAN result)

- Recorded scan target: `orchestration/reports/M-011/`, plus the probe and handoff.
- Recorded scan terms: operator/account identifiers; the operator's concurrent-conversation topic terms (deliberately NOT reproduced here — spelling them out would re-leak the very content being scrubbed); the generic `thought for` DR activity-header phrase; the `/c/<hex>` conversation-path shape; and token shapes (`sk-`, `eyJ`, `Bearer`).
- Recorded result: CLEAN, with no matches; stdout contained only a benign `VIRTUAL_ENV` uv warning. The manager re-confirms this before commit.

## Telemetry

ESTIMATE: m011-reports 20m
ACTUAL: m011-reports 20m

Mission-level telemetry to be finalized by the manager: T2 was the long leg; DR ran the full 2426.9s ceiling.

## Artifact trust levels

- `T1-tools-menu.json`: producer-run, manager-inspected, leak-clean.
- `T2-deep-research.json` + `T2-dr-progress.jsonl`: producer-run recorder, manager-inspected, PARTIAL.
- `discovery.md` / `verify.md`: pi-authored, pending manager independent verification vs the JSON.
