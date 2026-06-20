# M3 Verify — Dimension 3: Occam simplicity + implementability + falsifiability (DESIGN ONLY, independent verification)

**Read first, in full:** `team/contracts/M3-common-constraints.md`, then the design under verification `team/evidence/reports/M3-detailed-design.md`, then `docs/REWRITE-SPEC.md` (esp. §18 testing, §19 mission sequence) and `.claude/skills/manager/references/agent-rigor.md` (Occam + measure-empirically + falsifiability).

**You are an INDEPENDENT verifier.** You did NOT produce this design. Your single dimension: **is it the SIMPLEST correct design, is it actually implementable as written, and are its tests falsifiable?** Be adversarial — find over-engineering, gaps, internal contradictions, and untestable claims.

**Write your verdict to:** `team/evidence/reports/M3-work/verify-3-occam-impl.md` (begin with `STATUS:` then `VERDICT: PASS | PASS-WITH-NOTES | FAIL`).

## What to check
1. **Occam / no accreted complexity.** Is anything more complex than it needs to be? Specifically check: no daemon/IPC re-introduced; no speculative abstraction layers; the channel/mock abstraction is the minimum needed for offline tests; the attachment/citation schema has no over-engineered fields; the v1 bundle/patch/apply round-trip is NOT resurrected (out of scope). Name each thing that should be **cut** and why. Conversely, flag any place that is **too thin** to implement.
2. **Implementability.** Could an engineer build M4/M5 from this without re-designing? Check that: every module has concrete typed signatures; the JSONL schema is fully specified (types, optionality); the linearization algorithm is unambiguous; the capture pipeline's steps are concrete (real Playwright/CDP calls or close); the error taxonomy maps to real raise sites. List anything still vague/hand-wavy that a builder would have to invent.
3. **Internal consistency (seams).** Cross-check the seams: does the `Session` result object expose exactly the JSONL fields? Does the visible-vs-hidden classification used by the linearizer match the capture extraction rule? Do CLI verbs map to real `Session` methods? Does the concurrency budget owner match the architecture? Report any contradiction between sections.
4. **Falsifiability of the acceptance/tests.** REWRITE-SPEC §18: a test that cannot fail proves nothing. Check the design's proposed M4/M5 acceptance: can the capture-fidelity check actually fail (it must compare against the web-UI copy as ground truth, not self-report)? Can the completion check fail (gated on a real new-turn baseline)? Is the mock channel rich enough to make offline tests meaningful but not so self-describing that tests are circular? Flag any circular/unfalsifiable test.
5. **Build sequence soundness.** Is the recommended M4/M5 ordering correct (offline core before the attended cdp capture; dependencies respected; the pressing scrape deliverable (M6) reachable)? Any missing prerequisite step?
6. **Empirical grounding.** Are scale/memory claims grounded in the **measured** ~17MB/~5k-node figure (or flagged as needing measurement), rather than hand-guessed?

End with: a prioritized list of **must-fix** vs **nice-to-have** findings, the single **biggest risk to implementability**, and your `VERDICT`. A design that is unimplementable-as-written in a load-bearing area, or whose core tests are unfalsifiable, cannot be `PASS`.
