# M3 Revision 2 (final, small) — close the last round-2 verifier notes (DESIGN ONLY, single editor)

**Read first, in full:** `team/contracts/M3-common-constraints.md`, then the design you will edit `team/evidence/reports/M3-detailed-design.md` (focus on §2.1, §2.3, §2.5, §2.7, §3.3, §5), then `team/evidence/reports/M3-work/verify-3-occam-impl-r2.md` (the source of these three items). Cross-check `team/charter.md` + `team/evidence/handoffs/M2-ground-truth-probe.md` for the header-handling rule.

**You are the single editor.** Apply EXACTLY these three changes IN PLACE in `team/evidence/reports/M3-detailed-design.md` only. Preserve everything else (the design is otherwise verified PASS on fidelity and gotcha/safety). Append your changes to the existing "## Revision log (M3 panel fixes)" section as a "Revision 2" subsection.

### Fix A — MUST-FIX (V3r2 #1): tighten `HeaderBundle` lifetime to per-request, non-intrusively
The safety rule (`team/charter.md`; `M3 common §2`; M2) is: obtain auth/OAI headers transiently from the page's OWN request, use them, and never persist/log them. The current design lets a `HeaderBundle` live for one whole `wait_for_completion` call, which for a minutes-long Pro/DR wait retains the bearer across many sparse backend polls. Tighten it (state this in §2.3, §2.5, and §5):
- **No long-lived header reference is held across a `wait_for_completion` loop.** Each backend request — the one capture fetch, OR each sparse authoritative backend completion check — acquires the required headers, uses them for that single request, and **discards the local copy immediately after**.
- **Only redacted progress state persists across the wait loop** — ids, text lengths, hashes, status flags — **never** header values.
- **Reacquisition must be NON-INTRUSIVE:** re-read the headers from the tool's OWN already-registered same-tab request observer (the listener that first captured the page's `/backend-api/conversation/<id>` request and refreshes on the app's subsequent same-origin backend calls). Do **NOT** re-navigate or reload the operator's tab merely to refresh headers (that would be intrusive and fragile).
- Keep the existing rules: `repr=False`; values never in logs, exceptions, `raw-mapping.json`, `transcript.jsonl`, status reports, fixtures, or any file on disk. Note that fine-grained progress checks use cheap own-tab DOM signals that need **no** headers, so header-bearing requests are minimized to the sparse backend checks.

### Fix B — NICE (V3r2 #2): define the remaining referenced helper types
The seam types are now mostly defined, but these are still referenced without definitions: `BackendFetchMeta`, `BackendTopLevel`, `SendContext`, `ConversationPaths` (§2.3, §2.7). Add a minimal typed definition (fields + types) for each where first referenced, so M4/M5 scaffolding need not invent them. Keep them minimal (Occam).

### Fix C — NICE (V3r2 #3): specify pending eager-write stub status + read visibility
`TurnStatus` is `complete|partial|error` and reads hide *superseded* stubs but the convention for an *unsuperseded pending* stub (e.g. `message_id="local:<client_send_id>"`, `turn_index=null`, prompt persisted but not yet UI-verified) is unspecified (§2.1, §3.3). Specify it: state the `status`/`partial` value a pending stub carries and that it is **hidden from default `history`/`export` reads** (surfaced only via a `--include-pending`-style flag and in `status` diagnostics) until superseded by the canonical user record — so an unsubmitted prompt never appears as a real turn. Pick the simplest convention and state it.

## Output
Edit only `team/evidence/reports/M3-detailed-design.md` (touch no other file; no production source, no `issues/cdp-send-repro/controller.mjs`, no git commit/push/uv-tool-install, no browser/CDP leg). Keep edits surgical — clarify/complete, do not bloat or restructure. In your stdout, confirm the three fixes applied and that no other section changed materially.
