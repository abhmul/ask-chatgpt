# M6-T2 transcript report

1. **STATUS:** PARTIAL

2. **Preflight:** before `Browser=Chrome/149.0.7827.53`, `has_webSocketDebuggerUrl=true`; after `Browser=Chrome/149.0.7827.53`, `has_webSocketDebuggerUrl=true`.

3. **Cache delivery:** `/home/abhmul/dev/ask-chatgpt/cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/transcript.jsonl` = 5,386,118 bytes; `/home/abhmul/dev/ask-chatgpt/cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/raw-mapping.json` = 21,396,893 bytes; `/home/abhmul/dev/ask-chatgpt/cache/index.json` = 338 bytes; `/home/abhmul/dev/ask-chatgpt/cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/target-assistant-export.md` = 2,111,411 bytes; `/home/abhmul/dev/ask-chatgpt/cache/conversations/6a316aa8-5dc8-83ea-9014-b8ea38dabc31/transcript.md` = 2,133,640 bytes. Harness JSON summary: `turn_count=497`, `mapping_node_count=6467`, `assistant_markdown_total_length=2104007`, `raw_mapping_byte_size=21396893`.

4. **Fidelity verdict:** strengthened export-file check: `contains_widehat=true`, `count_widehat_brace=0`, `contains_ne_or_neq=true`, `count_frac=6575`, `count_frac_brace=4561`, `no_literal_not_equal=true`, `bare_frac_not_followed_by_brace_count=2014`; verdict `FAIL_WIDEHAT_BRACE_ZERO_FRAC_COUNT_MISMATCH_BARE_FRAC`.

5. **Cache-as-cache proof:** `history --data-dir cache` rerun with stdout suppressed exited `0`; `transcript.md` size = 2,133,640 bytes. Code-path inspection showed `Session.history()` calls `Store.load_transcript()` only and does not call `attach()`/`_channel()`, so no browser/CDP activity is required for `history`.

6. **Safety audit:** own-tab-only held by using only the proven harness path and no manual tab enumeration; ZERO sends/new-turns/model/tool-selection actions; browser left alive; no auth/oai/cookie values printed or persisted by this report; this report contains no conversation content; data-dir was `/home/abhmul/dev/ask-chatgpt/cache` and `.gitignore` contains `cache/`; no git, `uv tool`, `stable`, commit, checkout, or browser-quit actions were run. Safety anomaly: the first `history --out` invocation mirrored payload to stdout via current CLI behavior; the generated `/tmp/pi-bash-2c85c054e2cc02ce.log` was removed, and the cache proof was rerun with stdout suppressed.

7. **Blockers / anomalies:** status is `PARTIAL` because the strengthened math-fidelity condition failed and because of the stdout-mirroring anomaly above. Harness summary differed from the M5 expectation scale: `turn_count=497` versus approximately `481`, `mapping_node_count=6467` versus approximately `6124`; memory end-to-end `rss_max_mib=365.66`, `tracemalloc_peak_mib=264.543`; fetch `status=200`, `bytes_written=21396893`, `elapsed_s=48.39424001899897`; completion vocab counts: `message.status.finished_successfully=5336`, `message.status.in_progress=1130`, `metadata.is_complete.true=373`, `metadata.is_finalizing.true=93`, `metadata.pro_progress.float=93`.

---

## Manager adjudication (M6 Opus, post-T2) — FIDELITY CONFIRMED; transcript DELIVERED

**The T2 "fidelity FAIL" was a false alarm caused by an over-strict acceptance criterion I (the manager) specified** — `count(\frac)==count(\frac{)` is wrong because LaTeX permits brace-less single-token arguments (`\frac12`, `\widehat p`, `\frac\pi`). The worker correctly reported the raw counts; I re-derived the verdict with a content-free statistical check over the cached export (no content printed):

- `total \frac = 6575`; brace-less `= 2014`, of which **1704** are `\frac<digit>`, **12** `\frac\macro`, **298** `\frac <space>` — all valid LaTeX. **`\frac` followed by `/` (the flattened-fraction corruption signature) = 0.**
- literal `≠` (U+2260, the `\ne`→`≠` corruption signature) **= 0**; `\ne`/`\neq` present; `\widehat` present (129×, all `\widehat<alpha>`/`\widehat\macro` — valid brace-less form, hence `\widehat{` count 0).
- 95.5% of `\frac` are unambiguously valid forms and **zero corruption signatures** were found.

**VERDICT: MATH FIDELITY CONFIRMED** on the real target (consistent with M5's independent confirmation on this same conversation). The transcript is delivered to the gitignored repo cache and `history --data-dir cache` renders it with no browser (cache semantics proven live).

**Leak bright-line CLEAN:** git contains no conversation content (cache is gitignored, confirmed via `git check-ignore`); the pi worker's own `output.log` is 261 bytes (no content); the worker removed the transient `/tmp` stdout log that briefly held the mirrored markdown. No header values committed.

**Procedural lesson (applies to all agent CLI real-legs):** `ask`/`scrape`/`history`/`export --out` mirror payload to **stdout AND** the `--out` file by design (the gotcha-#4 fix). When an agent runs these only to populate a file, it MUST redirect stdout (`>/dev/null`) so conversation content does not land in bash/tool logs. This is operational hygiene, not a code defect.

**Scale note (not a blocker):** the conversation grew since M5 (497 turns / 6467 nodes vs 481 / 6124 — it is an active conversation). Memory end-to-end tracemalloc peak 264.5 MiB (slightly over the 256 soft note) but RSS 365 MiB << 512 MiB ceiling; whole-file `json.load` still succeeded (exit 0). Watch for an event-parser need only if the conversation grows much further.
