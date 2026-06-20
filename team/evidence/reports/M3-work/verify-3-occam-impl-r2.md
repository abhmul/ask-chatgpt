STATUS: DONE
VERDICT: PASS-WITH-NOTES

Re-verified the revised `team/evidence/reports/M3-detailed-design.md` for Occam simplicity, implementability, internal seams, falsifiability, build sequence, empirical grounding, and revision regressions against `docs/REWRITE-SPEC.md`, `team/evidence/handoffs/M2-ground-truth-probe.md`, `team/charter.md`, `.claude/skills/manager/references/agent-rigor.md`, and the M3 contracts. No browser/CDP/network leg was run.

## Findings

1. **MUST-FIX before M5 real completion: header lifetime is still too broad for the hard single-fetch rule.** `team/contracts/M3-common-constraints.md §2/§3` requires the Authorization/OAI headers to be obtained transiently from the page's own request, forwarded for the single fetch, and discarded. The revised design's capture path has `HeaderBundle.for_single_fetch()` and a single capture fetch (`team/evidence/reports/M3-detailed-design.md §2.3, §4.2`), but completion explicitly allows a `HeaderBundle` to live for one whole `wait_for_completion` call and to be used by sparse backend checks (`§2.3, §5`). For a minutes-long Pro/DR wait, that can mean retaining bearer/OAI headers across multiple polls. Fix: make `HeaderBundle` consumed per backend request/fetch, or explicitly reacquire and discard per sparse poll; keep only redacted progress state across the wait. This is the only load-bearing note preventing a clean PASS.

2. **NICE-TO-HAVE implementability cleanup: a few helper types remain referenced but unspecified.** The main prior seam regression is fixed: `TabLease` is channel-bound and the missing public seam types (`Transcript`, `SelectorMap`, `SendTimeouts`, `AttachmentSpec`, `PreflightResult`, `StatusReport`) are now defined (`M3-detailed-design.md §2.1–§2.10`). Remaining signatures still mention `BackendFetchMeta`, `BackendTopLevel`, `SendContext`, and `ConversationPaths` without field definitions (`§2.3, §2.7`). These are not re-design blockers because surrounding sections define the algorithms, but M4 scaffolding should add minimal dataclasses/aliases.

3. **NICE-TO-HAVE store semantics: pending eager-write stubs need an explicit status convention.** The design allows `message_id="local:<client_send_id>"` only for pending stubs and says `turn_index` is null only for pending stubs (`§2.1, §3.3`), but `TurnStatus` has only `complete|partial|error` and read semantics hide superseded stubs, not unsuperseded pending ones (`§3.3`). Specify whether an unsubmitted pending prompt is `partial`, `error`, or hidden by default until canonicalized.

4. **PASS: Occam choices remain sound and no daemon/IPC or v1 bundle/patch/apply path regressed in.** The design keeps `library-core + thin CLI + persistent Session; no daemon` (`M3-detailed-design.md §1`, matching `docs/REWRITE-SPEC.md §2`), keeps `mock`/`cdp` as the minimum useful channels (`§2.9`, `REWRITE-SPEC §14`), cuts the unmeasured six-tab cache to modest defaults (`§7`), and does not resurrect the out-of-scope v1 bundle/patch/apply workflow (`REWRITE-SPEC §15`; design `§3.7, §11`).

5. **PASS: core implementation seams are now coherent.** `Session.ask` returns the same `TurnRecord` serialized to JSONL (`M3-detailed-design.md §2.1–§2.2`); capture emits `TurnRecord` and store serializes it (`§2.1, §2.3, §2.7, §3.3`); visible classification (`user:text`/`assistant:text` only) matches M2's observed content shapes (`M2-ground-truth-probe.md "Backend-api verdict"; design `§3.5, §4.3`); CLI verbs map to actual `Session` methods (`§8`); and `Session` owns the tab pool and send budget (`§1, §7`).

6. **PASS: linearization, capture, and JSONL are implementable as written.** Current-branch linearization follows parent links from `current_node` to root and reverses (`M3-detailed-design.md §3.5`), matching M2's message-tree fact. JSONL fields, nullability, supersession, last-writer-wins reads, raw mapping atomic replace, and stdout+`--out` behavior are specified (`§3.1–§3.4, §8`). Capture uses own-tab header observation, in-page streaming fetch, shape validation, and fail-closed fallback triggers (`§4.1–§4.4`).

7. **PASS: tests/acceptance are falsifiable rather than circular.** The design requires fidelity comparison against web-UI copy for heavy math/DR samples and checks `\widehat`, `\ne`/`\neq`, and `\frac{}{}` (`M3-detailed-design.md §4.4, §10 M5/M6`; `REWRITE-SPEC §18`). Send/completion acceptance is gated on real/mock baseline changes and can fail via no-op send and newer-assistant checks (`design §6, §10 M4/M5`). The mock is rich enough to falsify core behavior: 404-without-headers, required-header success, selector drift, no-op send, composer unmount, long progress, clipboard prompt, and ~5k-node mapping (`§2.9, §10 M4`).

8. **PASS: build sequence and empirical grounding are now aligned.** M4 is offline core/mock; M5 is CDP capability/smoke; M6 is the target scrape; M7 is menus/loop/tab-pool/rate (`M3-detailed-design.md §10`), matching `REWRITE-SPEC §19`. Scale claims use M2's measured ~17.1 MB/~5k nodes and explicitly defer RSS/tracemalloc and polling-cadence measurement to M5/M6 (`M2-ground-truth-probe.md "Backend-api verdict"; design `§4.2, §10 M5/M6`; agent-rigor "Measure complexity empirically").

## Revision regression check

No regression found in the prior round's channel/tab seam, M4/M5/M6/M7 ordering, or model-picker executable algorithm: those are materially improved (`M3-detailed-design.md revision log M1/N1/N2; verified against `§2.1–§2.10, §6, §10`). The one regression/unfinished fix is the revised `HeaderBundle` lifetime wording: it turns the previous ambiguity into an explicit per-`wait_for_completion` retention rule, which conflicts with the single-fetch safety invariant.

## Prioritized must-fix vs nice-to-have

**Must-fix:** consume/reacquire/discard Authorization/OAI headers per backend request, not per whole completion wait.

**Nice-to-have:** define the remaining helper dataclasses/aliases; specify pending-stub status/read semantics.

**Single biggest risk to implementability:** unsafe or ambiguous header lifetime during sparse backend completion polling, because it spans the safety and completion seams.

Final verdict: **PASS-WITH-NOTES**.
