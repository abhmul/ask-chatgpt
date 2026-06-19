STATUS: DONE

## Files changed
- `src/ask_chatgpt/store.py`: changed only the default fallback in `Store.resolve_data_dir()`; priority remains explicit `data_dir` > `ASK_CHATGPT_DATA_DIR` > default. Default now walks up from `Path.cwd().resolve()` to the nearest `pyproject.toml` and returns `<repo>/cache`; if no marker is found, it returns `<cwd>/cache`. It does not create directories.
- `tests/test_store_layout.py`: updated the old home-default assertion to the repo `cache/` default, while preserving explicit/env override assertions.
- `tests/test_cache_default.py`: added cache semantics tests for browser-free history/export and scrape refresh behavior.
- `team/evidence/reports/M6-T1-cache-default.md`: required handoff report.

## Tests added/changed and falsifiability
- `test_data_dir_resolution_precedence_and_repo_cache_default`: pins explicit override, env override, and repo-root `cache/` default from a nested cwd; fails on the old home-dir fallback or if env/explicit priority changes.
- `test_history_and_export_read_cached_transcript_without_browser`: seeds a temp cache, then verifies `Session.history()` and CLI `export` read it without any browser channel construction/calls; fails if either path attaches, preflights, scrapes, or ignores the cache.
- `test_rescrape_refreshes_cached_transcript_last_writer_wins`: scrapes the same mock conversation twice with changed backend content and verifies the temp cache first populates, then reads the refreshed last-writer-wins transcript without duplicate visible turns; fails if scrape does not persist, refresh, or de-duplicate visible reads.

## Acceptance evidence
- `uv run pytest` summary: `207 passed in 0.43s`.
- Repo cache pollution check after the full run: `ls cache` returned `Path not found: /home/abhmul/dev/ask-chatgpt/cache`; `find .` with pattern `cache/**` returned `No files found matching pattern`.
- `.gitignore` was not modified; it already contains `cache/`.

## Beyond store.py/tests
- Only this required report was written outside `src/ask_chatgpt/store.py` and `tests/`.

## Blockers
- None.
