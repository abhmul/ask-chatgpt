# M15 store inventory + rotation-lineage verification

Scope: local files only; no network. Metadata-only. Task-1 inventory below is pre-consolidation; Task-3 records cache mutations.

## Task 1 — latest-content inventory

### OLD `6a387270-c3b0-83ea-991f-81085a2eeb9b`

Verdict: saved TRUE. The OLD-anchor is present in non-cache stores, freshest evidence `tmp/weak-simplex-push/driver/rotate-scrape-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/raw-mapping.json`, mtime `2026-06-23 05:39:22.969693359 -0500`, user turns `30`, nodes `4494`.

Files checked:
- `cache/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/raw-mapping.json`: size `12970982`, mtime `2026-06-23 04:30:26.831043932 -0500`, user turns `30`, nodes `4368`, OLD-anchor present `FALSE`.
- `cache/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/transcript.jsonl`: size `46569837`, mtime `2026-06-23 02:16:15.127460252 -0500`, user records `106`, records `412`, OLD-anchor present `FALSE`.
- `tmp/weak-simplex-push/ask-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/raw-mapping.json`: size `13342322`, mtime `2026-06-23 05:36:53.870129565 -0500`, user turns `30`, nodes `4494`, OLD-anchor present `TRUE`.
- `tmp/weak-simplex-push/ask-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/transcript.jsonl`: size `12071373`, mtime `2026-06-23 05:36:54.041899960 -0500`, user records `29`, records `113`, OLD-anchor present `TRUE`.
- `tmp/weak-simplex-push/driver/rotate-scrape-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/raw-mapping.json`: size `13342322`, mtime `2026-06-23 05:39:22.969693359 -0500`, user turns `30`, nodes `4494`, OLD-anchor present `TRUE`.
- `tmp/weak-simplex-push/driver/rotate-scrape-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/transcript.jsonl`: size `12071373`, mtime `2026-06-23 05:39:23.136633322 -0500`, user records `29`, records `113`, OLD-anchor present `TRUE`.
- `tmp/weak-simplex-push/driver/rotate-seed-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/raw-mapping.json`: size `638045`, mtime `2026-06-21 18:45:39.467240090 -0500`, user turns `2`, nodes `190`, OLD-anchor present `FALSE`.
- `tmp/weak-simplex-push/driver/rotate-seed-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/transcript.jsonl`: size `1272605`, mtime `2026-06-21 18:45:39.477695810 -0500`, user records `4`, records `10`, OLD-anchor present `FALSE`.

### NEW `6a3a6268-da78-83ea-9b23-7dc1731976ac`

Verdict: saved FALSE by exact NEW-anchor criterion. MILESTONE marker present TRUE in cache and rotate-seed stores, but NEW-anchor present FALSE in every checked `raw-mapping.json` and `transcript.jsonl`; the freshest NEW local files in ask-data contain neither.

Files checked:
- `cache/conversations/6a3a6268-da78-83ea-9b23-7dc1731976ac/raw-mapping.json`: size `1958157`, mtime `2026-06-23 08:36:40.009441916 -0500`, user turns `5`, nodes `578`, NEW-anchor present `FALSE`, MILESTONE present `TRUE`.
- `cache/conversations/6a3a6268-da78-83ea-9b23-7dc1731976ac/transcript.jsonl`: size `169019`, mtime `2026-06-23 08:33:15.387264535 -0500`, user records `4`, records `10`, NEW-anchor present `FALSE`, MILESTONE present `TRUE`.
- `tmp/weak-simplex-push/ask-data/conversations/6a3a6268-da78-83ea-9b23-7dc1731976ac/raw-mapping.json`: size `0`, mtime `2026-06-23 10:58:37.003666814 -0500`, user turns `NA`, nodes `NA`, NEW-anchor present `FALSE`, MILESTONE present `FALSE`.
- `tmp/weak-simplex-push/ask-data/conversations/6a3a6268-da78-83ea-9b23-7dc1731976ac/transcript.jsonl`: size `1277`, mtime `2026-06-23 10:59:05.225358918 -0500`, user records `2`, records `2`, NEW-anchor present `FALSE`, MILESTONE present `FALSE`.
- `tmp/weak-simplex-push/driver/rotate-seed-data/conversations/6a3a6268-da78-83ea-9b23-7dc1731976ac/raw-mapping.json`: size `572228`, mtime `2026-06-23 05:53:57.281353561 -0500`, user turns `2`, nodes `66`, NEW-anchor present `FALSE`, MILESTONE present `TRUE`.
- `tmp/weak-simplex-push/driver/rotate-seed-data/conversations/6a3a6268-da78-83ea-9b23-7dc1731976ac/transcript.jsonl`: size `169019`, mtime `2026-06-23 05:53:57.289272648 -0500`, user records `4`, records `10`, NEW-anchor present `FALSE`, MILESTONE present `TRUE`.

Note: the contract-listed top-level `tmp/weak-simplex-push/rotate-scrape-data/...` and `tmp/weak-simplex-push/rotate-seed-data/...` stores were absent; matching stores under `tmp/weak-simplex-push/driver/` were present and checked.

## Task 2 — rotation lineage

Verdict: TRUE, NEW is the recorded rotation of OLD.

Rotation-log evidence: `tmp/weak-simplex-push/driver/rotation-log.jsonl` has one matching entry: event `rotation-completed`, old_conv `6a387270-c3b0-83ea-991f-81085a2eeb9b`, new_conv `6a3a6268-da78-83ea-9b23-7dc1731976ac`, new_model `gpt-5-5-pro`, ts `2026-06-23T05:53:57-05:00`.

Archive corroboration: `tmp/weak-simplex-push/reseed/ARCHIVE-current.md` exists, size `53888`, mtime `2026-06-23 05:39:23.492790790 -0500`, rotation-carry marker present `TRUE` with count `1`. NEW seed corroboration in `tmp/weak-simplex-push/driver/rotate-seed-data/conversations/6a3a6268-da78-83ea-9b23-7dc1731976ac/`: seed user material references the archive/proof-tree `TRUE`; exact OLD id string in seed user material `FALSE`.

## Task 3 — consolidation into cache

Copied for OLD because best non-cache raw was newer and larger than cache:
- `tmp/weak-simplex-push/driver/rotate-scrape-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/raw-mapping.json` → `cache/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/raw-mapping.json`; source size/mtime `13342322` / `2026-06-23 05:39:22.969693359 -0500`; dest size/mtime after copy `13342322` / `2026-06-23 12:06:45.421398673 -0500`.
- `tmp/weak-simplex-push/driver/rotate-scrape-data/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/transcript.jsonl` → `cache/conversations/6a387270-c3b0-83ea-991f-81085a2eeb9b/transcript.jsonl`; source size/mtime `12071373` / `2026-06-23 05:39:23.136633322 -0500`; dest size/mtime after copy `12071373` / `2026-06-23 12:06:45.430398731 -0500`.

No copy for NEW: cache raw size/mtime `1958157` / `2026-06-23 08:36:40.009441916 -0500`; largest non-cache raw size/mtime `572228` / `2026-06-23 05:53:57.281353561 -0500`; freshest ask-data raw was size `0` and therefore not larger.

## Operator questions

Q1: Is the latest content of each conversation scraped/saved? OLD yes; NEW no by exact NEW-anchor criterion, although a MILESTONE marker is present in older cache/seed stores.

Q2: Is `6a3a6268` the rotation of `6a387270`? Yes.

STATUS: DONE
