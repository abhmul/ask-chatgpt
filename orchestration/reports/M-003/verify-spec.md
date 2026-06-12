ESTIMATE: T7c 25m
LENS: spec-conformance
START_TIMESTAMP: 2026-06-12T04:00:31-05:00

CHECK 1: PASS — UC2 round-trip obligation
- Binding: README UC2 requires files/dirs → bundle README → changed-files-only patch bundle → retrieve/apply (`README.md:10-13`) and acceptance requires “bundle out → (mock) GPT edits → patch bundle back → applied locally → diff matches expectation” (`README.md:19`); protocol lifecycle requires download-primary then fenced fallback retrieval and `apply_patch(..., dry_run=True|False)` (`docs/bundle-protocol.md:5-19,163-185`).
- Evidence: newest `tmp/accept-uc2-20260612-034717/results.json` has `overall: pass`; `download-primary-roundtrip` has `patch_bundle.source: download`, `overall_diff_matches: true`, `added_matches: true`, `modified_matches: true`, `deleted_absent: true`, summaries `added=1 modified=1 deleted=1`; `fenced-fallback-roundtrip` has the same diff facts with `patch_bundle.source: fenced`.
- Test/source mapping: `tests/test_uc2_roundtrip.py:17-22` defines one modified, one added, one deleted; `:62-80` asserts diff/summary; `:118-126` dry-runs without mutation then applies; `:131-154` tests both download and fenced paths. API builds/uploads/retrieves/result-wraps at `src/ask_chatgpt/api.py:107-123,136`; apply default/signature is `src/ask_chatgpt/patch.py:258`.

CHECK 2: PASS — catalogue README + prompt-instructions conformance
- Binding: full template and prompt are mandatory (`docs/bundle-protocol.md:31-159`): inventory/path rules, exact `NO_CHANGES_NEEDED`, changed/deleted-only patch zip, manifest schema, download-preferred `PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip`, and exact `BEGIN_PATCH_BUNDLE` fenced fallback.
- Generated README matches: `src/ask_chatgpt/bundle.py:95-190` includes “Read this file first”, root/path rules, identity/inventory table, exact no-edit sentinel, “Return exactly one patch bundle containing only changed/deleted paths and `manifest.json`”, manifest schema, “Primary/preferred” download response, and exact fallback marker block.
- Generated prompt matches: `src/ask_chatgpt/bundle.py:192-224` repeats the upload/readme instruction, task, no-edit sentinel, changed/deleted-only patch bundle, download-preferred channel, and fenced fallback tokens. Tests assert deterministic README/inventory/tokens at `tests/test_bundle_out.py:44-67` and prompt tokens at `tests/test_bundle_out.py:115-123`.

CHECK 3: PASS — §10 public API conformance
- Binding: no-files UC1 path returns plain `str`; UC2 appends keyword-only `files`, `dirs`, `bundle_root` and returns `AskChatGPTResult{text, patch_bundle}` only in bundle mode (`docs/bundle-protocol.md:305-344`); `PatchBundle`, `FileDiff`, `DiffSummary`, and `apply_patch(bundle, root, *, dry_run=True)` are specified at `docs/bundle-protocol.md:319-392`; exports are required at `docs/bundle-protocol.md:392`.
- Source: `AskChatGPTResult` fields are `src/ask_chatgpt/api.py:23-27`; `ask_chatgpt` signature and return annotation match at `src/ask_chatgpt/api.py:30-44`; no-files returns `text` at `src/ask_chatgpt/api.py:74`; bundle mode calls `build_bundle`, upload, retrieve, and returns `AskChatGPTResult` at `src/ask_chatgpt/api.py:107-136`.
- Source: `PatchBundle`, `PatchBundleSource`, `FileDiff`, `DiffSummary`, and `apply_patch(..., dry_run=True)` match at `src/ask_chatgpt/patch.py:88-120,258`; package exports include required API, dataclasses, and named validation/apply errors at `src/ask_chatgpt/__init__.py:27-47`.

CHECK 4: PASS — §11 CLI conformance
- Binding: console script and flags/no-mutate/stdout/exit codes are specified at `docs/bundle-protocol.md:394-424,426-440`.
- Source: `[project.scripts] ask-chatgpt = "ask_chatgpt.cli:main"` is present at `pyproject.toml:11-12`; parser implements positional `prompt`, `--prompt`, `--session`, `--model-settings`, `--files`, `--dirs`, `--out`, mutually exclusive `--apply/--dry-run`, `--root`, `--channel`, `--base-url`, `--profile-path`, `--timeout` at `src/ask_chatgpt/cli.py:100-114`.
- Source/tests: CLI passes args to library including `bundle_root=args.root` (`src/ask_chatgpt/cli.py:65-71`), calls `apply_patch` only in dry-run/apply modes (`:76-87`), requires files/root before side effects (`:126-130`), maps errors to 0/2/3-12/1 (`:35-49,224`). Acceptance `tmp/accept-uc3-20260612-034726/results.json` passes prompt stdout, `--out`, and `--files --dry-run` no-mutation; tests cover default no-mutate/dry-run/apply/usage/errors at `tests/test_cli.py:114-394`.

CHECK 5: PASS — honest-failure-mode coverage table
| Mode | Protocol taxonomy | Error class | Raise/test evidence | CLI code |
| --- | --- | --- | --- | --- |
| upload unsupported / UI rejects size-type after preflight | `docs/bundle-protocol.md:272,302` | `UploadUnsupportedError` (`src/ask_chatgpt/errors.py:63`) | source `src/ask_chatgpt/bundle.py:315-317,345-352`; tests `tests/test_bundle_out.py:153-171` including `unsupported` and `reject_size_type` | 9 (`src/ask_chatgpt/cli.py:42`; test `tests/test_cli.py:342,353-364`) |
| download unsupported without fallback | `docs/bundle-protocol.md:274,294` | `DownloadUnsupportedError` (`src/ask_chatgpt/errors.py:71`) | source `src/ask_chatgpt/patch.py:253-255`; test `tests/test_patch.py:196-198` | 10 (`src/ask_chatgpt/cli.py:43`; test `tests/test_cli.py:343,353-364`) |
| patch malformed | `docs/bundle-protocol.md:276` | `PatchMalformedError` (`src/ask_chatgpt/errors.py:87`) | source malformed cases `src/ask_chatgpt/patch.py:567-628,676-704,712-775`; tests `tests/test_patch.py:169-185,211-213` | 11 (`src/ask_chatgpt/cli.py:44-48`; test `tests/test_cli.py:344-348,353-364`) |
| hash/byte-count mismatch | `docs/bundle-protocol.md:277` | `BundleIntegrityError` (`src/ask_chatgpt/errors.py:94`) | source `src/ask_chatgpt/patch.py:396-401,478-492,550-553,643-654`; tests `tests/test_patch.py:206-208,277-287`; upload corrupt `tests/test_bundle_out.py:153-171` | 11 (`src/ask_chatgpt/cli.py:45,48`; test `tests/test_cli.py:346,353-364`) |
| oversized payload | `docs/bundle-protocol.md:278` | `OversizedPayloadError` (`src/ask_chatgpt/errors.py:101`) | source `src/ask_chatgpt/bundle.py:310-312,552-572`; `src/ask_chatgpt/patch.py:461-465,542-546,758-779`; tests `tests/test_patch.py:216-219`, `tests/test_bundle_out.py:109-111,175-179` | 11 (`src/ask_chatgpt/cli.py:46,48`; test `tests/test_cli.py:347,353-364`) |
| path-escape / zip-slip | `docs/bundle-protocol.md:279` and apply rules `docs/bundle-protocol.md:226-244` | `PathEscapeError` (`src/ask_chatgpt/errors.py:108`) | source `src/ask_chatgpt/bundle.py:420-452`; `src/ask_chatgpt/patch.py:785-800,855-896`; tests `tests/test_patch.py:222-273` | 11 (`src/ask_chatgpt/cli.py:47-48`; test `tests/test_cli.py:348,353-364`) |
| response truncated | `docs/bundle-protocol.md:275,185` | `ResponseTruncatedError` (`src/ask_chatgpt/errors.py:40`) | source `src/ask_chatgpt/patch.py:419-427`; test `tests/test_patch.py:201-203` | 7 (`src/ask_chatgpt/cli.py:40`; test `tests/test_cli.py:340,353-364`) |
- Note: protocol intentionally groups validation subclasses under exit code 11 (`docs/bundle-protocol.md:437`); the table is distinct at the protocol’s exit-code category level.

CHECK 6: PASS — deviation (a) adjudication
- Protocol quote relied on: failure taxonomy says “UI rejects file size/type after local preflight passed” maps to `UploadUnsupportedError` (`docs/bundle-protocol.md:272`), and the adversarial matrix says `upload reject_size_type`: “If local preflight exceeded a configured upload cap, raise `OversizedPayloadError` before UI interaction; otherwise the fixture rejection maps to existing `UploadUnsupportedError` with safe reason” (`docs/bundle-protocol.md:302`).
- Implementation matches: local upload zip cap raises `OversizedPayloadError` before page/UI access (`src/ask_chatgpt/bundle.py:306-317`), while mock/UI status `rejected` raises `UploadUnsupportedError` with safe reason/basename (`src/ask_chatgpt/bundle.py:345-346`). Tests assert `reject_size_type -> UploadUnsupportedError` and local preflight cap -> `OversizedPayloadError` at `tests/test_bundle_out.py:153-179`. Ruling: conformant.

CHECK 7: PASS — D-001 retrieval-channel order
- Binding: D-001 says patch bundle primary is Playwright file-download capture and fallback is checksummed fenced base64url (`docs/DECISIONS.md:14`); protocol repeats “D-001 is binding: Playwright download capture is primary, and a checksummed fenced base64url block is fallback” (`docs/bundle-protocol.md:163`).
- Source: `retrieve_patch_bundle` scans and selects latest-turn download artifacts before reading/parsing text fallback (`src/ask_chatgpt/patch.py:203-228`); only after no candidate remains does it read response text, handle `NO_CHANGES_NEEDED`, and parse fenced fallback (`src/ask_chatgpt/patch.py:229-249`); latest-turn artifact metadata is enforced at `src/ask_chatgpt/patch.py:301-347`.
- Tests/evidence: `tests/test_patch.py:149-166` covers missing-download fallback and delayed-download primary; `tests/test_uc2_roundtrip.py:131-154` covers public API download-primary and fenced-fallback; newest UC2 results show source `download` for primary and `fenced` for fallback.

END_TIMESTAMP: 2026-06-12T04:03:16-05:00
V-SPEC-VERDICT: PASS
T7c-STATUS: DONE
