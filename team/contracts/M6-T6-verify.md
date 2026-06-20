# M6-T6 — Independent verification panel (3 distinct READ-ONLY lenses)

You are a **pi verifier** for the `ask-chatgpt-dev` team, mission M6 task T6. Repo `/home/abhmul/dev/ask-chatgpt`, branch `rewrite-v2`. You inherit **nothing** but this contract and the files it names. Read `.claude/skills/manager/references/agent-rigor.md` and obey it. You are **independent of the producers** — re-derive everything from ground truth; do NOT trust prior reports' claims.

**Your dispatch tells you which LENS to execute (L1, L2, or L3). Execute ONLY that lens.** This is an **OFFLINE, READ-ONLY** verification: do NOT touch the browser, the network beyond uv/PyPI, or chatgpt.com. Do NOT edit source, do NOT commit, do NOT run any git *write* (read-only `git log`/`git show`/`git diff`/`git check-ignore` are fine). Never run `uv tool` or move `stable`.

## Shared context (what M6 did — VERIFY, do not assume)
M6 made `cache/` (repo-local, gitignored) the default data-dir, scraped the target `6a316aa8-5dc8-83ea-9014-b8ea38dabc31` into the cache (transcript + raw-mapping), confirmed math fidelity, and implemented + ran attachment byte-download. Commits under review: `f469f44` (cache default + tests), `9648c68` (transcript report), `adfee14` (routes + scripts), `a03a814` (attachment download). Producer reports: `team/evidence/reports/M6-T1-cache-default.md`, `M6-T2-transcript.md`, `M6-T3-attachment-routes.md`, `M6-T4-attachments.md`.

**Hard leak rules (apply to your OWN report too):** never print/persist `authorization`/`oai-*`/`cookie` header VALUES, signed `download_url`s, operator file-ids, attachment filenames, or conversation content. Report counts/booleans/paths/keys only. The cache holds the operator's content and is gitignored — that is BY DESIGN; the violation would be content/headers in **git** or outside the gitignored cache.

---
## LENS L1 — Safety / leak / no-send / own-tab audit
Re-derive these from git + the working tree + the source (NOT from prior reports):
1. **No content/secret in git.** Inspect the four M6 commits (`git show`/`git diff`) and the tracked tree: confirm NO conversation content, NO header VALUES, NO signed URLs, NO operator file-ids, NO attachment filenames are committed. Confirm `cache/` is gitignored (`git check-ignore cache cache/conversations`) and that **no `cache/` content is tracked/staged** (`git status`, `git ls-files cache/` must be empty). Confirm `issues/cdp-send-repro/controller.mjs` (pre-existing dirty) and `human/` were NOT staged by M6.
2. **Header/url non-persistence in code.** In `src/ask_chatgpt/capture.py` download path (`download_attachments`, `_download_one_attachment`, `_fetch_attachment_descriptor`) confirm header values and `download_url` are used only as in-memory fetch args — never written to disk, logs, exceptions, `AttachmentRef.metadata`, or the transcript. Confirm the store's sensitive-key drop still strips `authorization`/`cookie`/`oai-*` (`src/ask_chatgpt/store.py`). Spot-check the cached `transcript.jsonl`/`raw-mapping.json` (programmatically, counts only) for `authorization`/`download_url`/`cookie`/`oai-` substrings → must be 0.
3. **ZERO-send / own-tab-only invariants.** Confirm the CDP channel cannot send: `src/ask_chatgpt/channels/cdp.py` `fill`/`click`/`press`/`upload_files`/`read_clipboard` raise `HumanActionNeededError` (read the methods). Confirm production never enumerates `context.pages` (grep src). These are the standing safety guarantees; confirm M6 did not weaken them.
Single-token verdict per check + an overall `L1: PASS/FAIL`.

---
## LENS L2 — Offline correctness + falsifiability
1. **Authoritative suite.** Run `uv run pytest` yourself; record the exact summary line (expect ≥ 212 passed). (Harmless `VIRTUAL_ENV ... ignored` warning expected.)
2. **No-playwright/offline.** Confirm the suite needs no browser/network (it is the default `-m "not real_site"` run); confirm mock tests don't import/require Playwright.
3. **Falsifiability (the core duty).** For the M6-added tests, prove they CAN fail — pick the most load-bearing and demonstrate by *temporary* mutation: revert/break the behavior, show the test goes RED, then **restore exactly** (leave the tree as you found it; you may use a scratch copy to avoid touching tracked files, or mutate-then-restore and verify `git diff` is empty afterward). Cover at least: (a) cache default = repo `cache/` (`tests/test_cache_default.py` / `tests/test_store_layout.py`); (b) history/export read cache with NO browser; (c) attachment **200-error-JSON-without-download_url => not_downloadable** (the gotcha) and **dedup** (`tests/test_capture.py`). If you cannot safely mutate, give a precise falsifiability argument citing the asserting lines. End with `L2: PASS/FAIL` + the pytest summary + which tests you proved falsifiable and how.

---
## LENS L3 — Acceptance / cache-as-cache / fidelity / attachment shipment conformance
Re-derive from the cache + code (NOT prior reports):
1. **Default data-dir = repo cache.** `Store().resolve_data_dir()` resolves to `<repo>/cache`; `--data-dir` and `ASK_CHATGPT_DATA_DIR` still override. (Pure resolution; no writes.)
2. **Cache acts as a cache (read without browser).** Confirm `Session.history`/CLI `history`/`export` read the cached transcript with NO browser/CDP (code path: `Session.history -> Store.load_transcript`, no `attach()`/preflight). Confirm the target cache holds `transcript.jsonl` + `raw-mapping.json` + a rendered markdown + `index.json`; report byte sizes.
3. **Math fidelity (falsifiable, content-free).** Over the cached markdown export, re-derive: `\widehat` present; `\ne`/`\neq` present; `\frac` present (count); **`\frac` immediately followed by `/` (flattened-fraction corruption signature) == 0**; **literal `≠` (U+2260) == 0**. State `FIDELITY CONFIRMED` or the failing signal. (Note brace-less `\frac12`/`\widehat p` are valid LaTeX — do NOT require braces.) Print counts only, never content.
4. **Attachment shipment.** From the cached `transcript.jsonl` with **last-writer-wins by `message_id`** (dedupe records, keep last — the append-only log contains superseded all-`pending` records from the first scrape; counting all lines is WRONG), report per `source_kind` the `download_state` distribution, the number of distinct downloaded `local_path`s, and confirm **every downloaded `local_path` exists on disk** (0 missing). Confirm `code_execution_output` is `unsupported` (fail-closed). Confirm all attachment bytes live under the gitignored `cache/conversations/<id>/attachments/`.
End with `L3: PASS/FAIL` and the re-derived numbers.

---
## Report (write your handoff here)
Write your report to **`team/evidence/reports/M6-T6-<LENS>.md`** (e.g. `M6-T6-L1.md` for lens L1). Structure: `STATUS` token; per-check evidence (commands run, counts, single-token verdicts); the overall `L#: PASS/FAIL`; any findings/risks; confirm you made no edits/commits and left the tree unchanged (`git diff` empty). Counts/keys/paths/booleans ONLY — never header values, signed urls, file-ids, filenames, or conversation content.
