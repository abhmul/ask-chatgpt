# M10-T1-L1 — Read-path & blast-radius cartographer

**FIRST read `team/contracts/M10-common.md` in full — it is mandatory and part of
these instructions.** Then execute this lens. READ-ONLY, OFFLINE.

## Your lens
You map the COMPLETE surface. Independently trace every public entry point and
classify it by cost, so the implementer knows exactly what a "light read" fix must
touch — and nothing it must not.

## Required work
1. For **every public `Session` method** (`create`, `ask`, `scrape`, `history`,
   `fetch`, `loop`, `status`, and any others) build a table with columns:
   - acquires a pool tab? (which `session.py` line)
   - navigates to `/c/<id>` (heavy render) vs a light page vs no tab at all
   - obtains its data from the DOM, the backend-API fetch, or the local store
   - is it a READ (no message sent) or a SEND (mutates the conversation)?
2. **Confirm or REFUTE** hypotheses **H1** (scrape is the only always-heavy READ),
   **H2** (history & fetch are tab-free local-store reads), and **H3** (ask & loop
   legitimately need `/c/<id>`). Quote the decisive lines.
3. Trace the **CLI layer** (`cli.py`): which subcommands (`scrape`, `history`,
   `fetch`, `export`, `status`, `ask`, `loop`, …) map to which Session methods?
   Does any CLI read path acquire a heavy tab that the Session-level analysis
   missed?
4. Trace the **completion-poll path** (`completion.py` + `_run_send_turn` in
   `session.py`): does completion acquire its own tab, or reuse the send tab? Is
   there any READ-only use of a heavy tab there?
5. Trace `status` (`session.py:604`): does it need the DOM/heavy page, the
   backend-API, or the store? Could it also benefit from a light page?
6. Produce the **exhaustive list of code locations** a light-read fix would touch
   (file:line), separating MUST-CHANGE (read ops paying for a heavy render) from
   MUST-NOT-CHANGE (sends that legitimately need `/c/<id>`).

## Deliverable
Write your handoff to **`team/evidence/handoffs/M10-T1-L1-readpath.md`** following
the handoff protocol in the common file. Lead with the method-classification table.
