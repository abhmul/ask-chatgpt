FAIL

# M4 verification lens 2 — correctness vs M3 design

Authoritative test evidence used: `team/evidence/reports/M4-pytest-authoritative.txt` reports `183 passed in 0.40s`; I did not re-run tests. Source audited under `src/ask_chatgpt/` against `team/contracts/M4-common.md`, `team/evidence/reports/M4-test-plan.md`, and M3 §§2, 3, 5, 6, 9.

## Load-bearing divergences

1. `completion.salvage_partial` attempts clipboard access without an explicit opt-in. Contract: M4-common decision 2 and M3 §5 require clipboard/copy fallback only with explicit attended permission and default fail-closed behavior; never auto-read the clipboard. Implementation: `src/ask_chatgpt/completion.py:232` unconditionally calls `tab.channel.read_clipboard(tab)` when no backend partial is available. If clipboard raises but a DOM partial exists, the function returns DOM salvage instead of stopping with `HumanActionNeededError`. This violates the fail-closed clipboard safety contract.

2. `--out` handling in the real `Session` path is not stdout-first/failure-independent. Contract: M4-common decision 3 and the M4 test plan require payloads to be written to stdout every time and additionally to `--out`; out-file failure must not suppress stdout. Implementation: `src/ask_chatgpt/session.py:316-317` and `src/ask_chatgpt/session.py:335-336` call `store.emit_payload(..., stdout=_NullStdout())` before returning to the CLI, while `src/ask_chatgpt/cli.py` emits stdout only after the session call returns. If the session-level out write fails, stdout is suppressed; on success the out file is also written twice. This contradicts the stdout-plus-out gotcha fix for real `Session.ask`/`Session.scrape` paths.

## Secondary divergences / notes

- M3 §5 says `/backend-api/conversation/<id>/stream_status` remains a hypothesis until M5 and must not be relied on before evidence. `src/ask_chatgpt/completion.py` defaults `poll_backend_completion(..., prefer_lightweight=True)` to `/stream_status`, and `wait_for_completion` uses that default. This is acceptable for the mock-only tests but is not the conservative design default for a future real channel.

- M3 §3.3 says `model.slug` comes from backend message metadata/default where available. `src/ask_chatgpt/capture.py` uses only top-level `default_model_slug` or the send context and does not inspect per-message metadata, so mixed-model backend records could be serialized with the wrong model slug.

- Completion branch parsing does not implement the same `message.id`-else-mapping-node-id fallback as capture. `src/ask_chatgpt/completion.py` tries `message.id` or `node.get("id")`, but raw mapping node ids are mapping keys, not necessarily node fields. Capture correctly uses the mapping key fallback.

## Contracts with no source-level divergence found

- Public dataclass fields in §2.1 are present for `ModelRef`, `AttachmentRef`, `CitationRef`, `TurnRecord`, `Transcript`, `PreflightResult`, and `StatusReport`; `StatusReport` uses the exact M4-common field names.

- `errors.py` matches the M3 §9 class/code/exit-code table exactly for codes 20, 21, 22, 23, 24, 30, 31, 32, 40, 41, 42, 50, 51, 60, 61, 62, 70, and 99.

- JSONL serialization includes all `TurnRecord` fields, last-writer-wins reads, default hiding of local pending stubs, `include_pending=True`, stable sorting, and the dedicated `StoreWarning`/`StoreError` torn-line split.

- Current-branch linearization follows parent links iteratively, emits only visible `user:text`/`assistant:text`, preserves empty `parts=[]` as `""`, rejects non-list/non-string parts, and concatenates multiple string parts without inserted separators.

- Project-id normalization, selector-map required keys, attachment default `download_state="pending"`, citation/attachment separation, DR evidence grouping with no numeric threshold, timeout split (`CompletionTimeoutError` vs `MaxTotalWaitExceededError`), and verified-send newer-user/newer-assistant gating are implemented consistently with the inspected M4 decisions aside from the divergences above.
