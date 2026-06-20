STATUS: DONE

Implemented M4-E4 on `rewrite-v2` in three commits: step 0 DECISION-13 seam fix, capture parser/linearizer, and fallback degradation coverage. Did not touch `cli.py`; did not stage unrelated `issues/`, `team/state/`, or `human/` paths.

Verification:

```text
uv run pytest
============================= 152 passed in 0.29s ==============================
```

Step-0 created_at grep:

```text
grep -RInE 'created_at\s*=\s*(datetime\.(now|utcnow)|time\.time)' src/ask_chatgpt || true
(no output)
```

D1-D10 ledger: D1 done — no headers/non-2xx/non-JSON/parse/wrong-id/malformed branches fail closed without canonical transcript or raw promotion. D2 done — authorized 200 with required headers emits complete canonical backend records and promotes validated raw with unknown top-level keys preserved. D3 done — `HeaderBundle` is `repr=False`, one-use, redacted by names only, and header canaries are absent from failure artifacts/objects/files. D4 done — current branch follows parent links iteratively through 5001 nodes, detects cycle/broken parent/invalid current, ignores side branches, and raw remains unpruned. D5 done — message id falls back to node id, parent id is raw parent, turn indexes count visible records only, and missing backend `create_time` stays `created_at=None`. D6 done — only `user:text`/`assistant:text` emit, hidden code/tool/thought text is absent, empty parts are `""`, multi-parts concatenate with no separator, non-list/non-string parts fail closed, and exact math tokens are asserted. D7 done — DR classification requires same-exchange visible user + hidden internals + citation/search metadata + visible final assistant, negatives/synthetic stay normal, hidden refs attach to final report. D8 done — all four attachment shapes normalize with `download_state="pending"`, no local path/hash/downloaded state, and no invented backend file routes. D9 done — citations normalize separately from attachments; file refs remain attachments; bare search queries are not promoted. D10 done — fallback defaults to human action for clipboard permission, explicit copy is `ui_copy` non-canonical, KaTeX/DOM salvage is degraded partial, and empty allowed fallback raises fail-closed.

Falsifiability notes: Step 0 tests were observed RED before implementation: backend `created_at=None` raised, non-empty `record_partial` was `error`, salvage fabricated `datetime.now(UTC)`, and the source grep found `store.py:created_at=datetime.now(UTC)`. Initial capture test was observed RED with `ModuleNotFoundError: No module named 'ask_chatgpt.capture'` before `capture.py` existed. Capture assertions use literal expected values: 5001-node branch length, exact visible message ids, exact `alphabeta\ngamma`, exact `\widehat`/`\ne`/`\neq`/`\frac{}{}` tokens, hidden text absence plus raw presence, DR positive/negative matrix, all four attachment source kinds, citation source kinds, one-use header failure, and header canary scans. Representative wrong mutations that flip tests: join parts with `" "`, emit hidden `assistant:code`, classify synthetic `content_type="deep_research"`, set attachment `download_state="downloaded"`, promote file refs as citations, or include a header value in `HeaderBundle.__repr__`/artifact text.

Commits:

```text
379795a M4 step 4a: relax created_at invariant
3d30e2d M4 step 4b: add offline capture parser
de96e20 M4 step 4c: cover capture fallback degradation
```

`git log --oneline -3`:

```text
de96e20 M4 step 4c: cover capture fallback degradation
3d30e2d M4 step 4b: add offline capture parser
379795a M4 step 4a: relax created_at invariant
```

`git show --stat HEAD`:

```text
commit de96e20cb2622956bcd65d1dbc60a6d3ccbf4354
Author: jetm <abhmul@gmail.com>
Date:   Thu Jun 18 16:58:38 2026 -0500

    M4 step 4c: cover capture fallback degradation

 tests/test_capture.py | 72 ++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 71 insertions(+), 1 deletion(-)
```

Blockers: none. Deferrals: none for M4-E4 offline scope; live Playwright/CDP header acquisition remains M5+ per contract.
