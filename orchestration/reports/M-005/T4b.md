START_TIMESTAMP: 2026-06-12T11:47:53Z
ESTIMATE: T4b 30m

# T4b independent docs-lens verification

Scope: I re-read `orchestration/tasks/M-005/T4b-docs-lens.md`, the current `docs/runbooks/real-site-acceptance.md`, `src/ask_chatgpt/cli.py`, `src/ask_chatgpt/errors.py`, D-001 docs/code samples, and `tmp/verify-m005/` evidence. I ran only lightweight preflight: `uv sync --all-groups && uv run ask-chatgpt --help`; I did not rerun the heavy suite.

Evidence runner artifacts considered: `tmp/verify-m005/clone_head.txt` says clone/head matched `261a16b...` and contains `0179400`; `clone_uv_sync.txt` confirms editable install under the clone; `clone_pytest.txt` records `121 passed` from the authoritative run; `accept_uc1_results.json`, `accept_uc2_results.json`, and `accept_uc3_results.json` all record `overall: pass`.

## D1 conformance table

Extraction scope for the conformance table is the D1-relevant ask-chatgpt CLI surface plus exception class names. Shell/uv helper tokens are accounted for separately below because they are not ask-chatgpt flags/subcommands.

| Token | Kind | Exists? | Evidence |
| --- | --- | --- | --- |
| `uv sync --all-groups` | external setup command/flag | yes | Executed successfully in this verification; also present in captured `tmp/verify-m005/clone_uv_sync.txt`. |
| `uv run ask-chatgpt` | external runner + console command | yes | `uv run ask-chatgpt --help` executed and printed `usage: ask-chatgpt ...`; `cli.py:97` sets `prog="ask-chatgpt"`. |
| `uv run python` | external runner for API proof blocks | yes | Used only for prereq/UC1 API blocks; not an ask-chatgpt subcommand. |
| shell helpers (`cd`, `mkdir`, `export`, `printf`, `read`, `if`, `echo`, `exit`, `rm`, `tee`, `grep`, `date`) | POSIX/bash helpers | yes | Standard shell utility/builtin usage; not part of ask-chatgpt surface. |
| positional `prompt` | ask-chatgpt positional | yes | Help output lists positional `prompt`; `cli.py:100` has `parser.add_argument("prompt", ...)`. |
| `--help` / `-h` | ask-chatgpt argparse help | yes | Help output lists `-h, --help`. |
| `--prompt` | ask-chatgpt flag | yes | Help output lists `--prompt PROMPT_OPTION`; `cli.py:101`. |
| `--session` | ask-chatgpt flag | yes | Help output lists `--session ID`; `cli.py:102`. |
| `--model-settings` | ask-chatgpt flag | yes | Help output lists `--model-settings JSON`; `cli.py:103`. |
| `--files` | ask-chatgpt flag | yes | Help output lists `--files PATH`; `cli.py:104`. |
| `--dirs` | ask-chatgpt flag | yes | Help output lists `--dirs PATH`; `cli.py:105`. |
| `--out` | ask-chatgpt flag | yes | Help output lists `--out FILE`; `cli.py:106`. |
| `--apply` | ask-chatgpt flag | yes | Help output lists `--apply`; `cli.py:108`. |
| `--dry-run` | ask-chatgpt flag | yes | Help output lists `--dry-run`; `cli.py:109`. |
| `--root` | ask-chatgpt flag | yes | Help output lists `--root DIR`; `cli.py:110`. |
| `--channel` | ask-chatgpt flag | yes | Help output lists `--channel {real,mock}`; `cli.py:111`. |
| `--base-url` | ask-chatgpt flag | yes | Help output lists `--base-url URL`; `cli.py:112`. |
| `--profile-path` | ask-chatgpt flag | yes | Help output lists `--profile-path PATH`; `cli.py:113`. |
| `--timeout` | ask-chatgpt flag | yes | Help output lists `--timeout SECONDS`; `cli.py:114`. |
| ask-chatgpt subcommands | subcommand | yes, absent as claimed | Help output shows a single command with options and no subcommand section; `_build_parser()` defines no subparsers. |
| `LoginRequiredError` | exception | yes | `errors.py:18`; also exported in `errors.py:124`. |
| `SessionNotFoundError` | exception | yes | `errors.py:25`; also exported in `errors.py:125`. |
| `ModelUnavailableError` | exception | yes | `errors.py:33`; also exported in `errors.py:126`. |
| `ResponseTruncatedError` | exception | yes | `errors.py:40`; also exported in `errors.py:127`. |
| `RateLimitedError` | exception | yes | `errors.py:48`; also exported in `errors.py:128`. |
| `SelectorUnavailableError` | exception | yes | `errors.py:55`; also exported in `errors.py:129`. |
| `UploadUnsupportedError` | exception | yes | `errors.py:63`; also exported in `errors.py:130`. |
| `DownloadUnsupportedError` | exception | yes | `errors.py:71`; also exported in `errors.py:131`. |
| `PatchBundleValidationError` | exception | yes | `errors.py:79`; also exported in `errors.py:132`. |
| `PatchMalformedError` | exception | yes | `errors.py:87`; also exported in `errors.py:133`. |
| `BundleIntegrityError` | exception | yes | `errors.py:94`; also exported in `errors.py:134`. |
| `OversizedPayloadError` | exception | yes | `errors.py:101`; also exported in `errors.py:135`. |
| `PathEscapeError` | exception | yes | `errors.py:108`; also exported in `errors.py:136`. |
| `PatchApplyError` | exception | yes | `errors.py:115`; also exported in `errors.py:137`. |

Stale-token check: grep found no `--profile` stale flag, no `--patch-out`, no `--bundle`, no `apply-patch`, and none of `PatchBundleMalformedError`, `PatchBundleIntegrityError`, `PatchBundleTooLargeError`, or `PatchPathEscapeError` in `docs/runbooks/real-site-acceptance.md`.

## Operator-runnability findings

PASS. UC1 is one consent-gated API command block after setup; it uses the public `ask_chatgpt(...)` API with `channel="real"`, `profile_path`, `session_identifier`, optional `model_settings`, and `timeout_s`, so no bogus CLI flag is involved. UC2 has setup plus exactly two real-site CLI proofs, dry-run and apply, using only real ask-chatgpt flags: `--channel real`, `--profile-path`, `--session`, `--prompt`, `--files`, `--root`, `--dry-run`/`--apply`, `--out`, and `--timeout`. UC3 has two real-site CLI proofs, stdout and `--out`, using only real flags: `--channel`, `--profile-path`, `--session`, `--prompt`, `--out`, and `--timeout`.

PASS. Typed-consent gates remain present before real-site contact: global preamble lines 7 and 15, UC1 lines 82 and 89-91, UC2 dry-run lines 153 and 160-162, UC2 apply lines 181 and 188-193, UC3 stdout lines 252 and 260-262, and UC3 out lines 275 and 283-285. UC2 apply also has a separate local mutation token before the command.

PASS. Honest mock-vs-real interpretation remains present: runbook lines 19-21 state automated/mock acceptance proves only loopback behavior and real-site behavior is unproven until operator execution; lines 23, 214, and 216 keep D-001 fallback/revisit notes. The prereq section lines 25-29 requires `observe-chatgpt-unknowns.md` and populated `real.json`; its `SelectorUnavailableError` fail-closed statement matches `errors.py:55` and captured D2 evidence in `tmp/verify-m005/d2_demo.txt`.

PASS. Prerequisites match the real CLI surface: runbook line 66 enumerates exactly the ask-chatgpt flags seen in `--help` and `cli.py:100-114`, including `--profile-path` rather than stale `--profile`; line 68 accurately says there is no saved-bundle input/output and patch apply/dry-run occurs in the same invocation, matching `api.py:107`/`api.py:123` and `cli.py:76-83`.

D1-VERDICT: PASS

## Spot recheck 1 — D-001 conformance

PASS. `docs/DECISIONS.md:13-16` states DOM-primary/copy fallback, download-primary/fenced fallback, selector-map fail-closed, loopback-only automation, library-first/no-daemon posture, and no transcript-wide scraping. Code samples match: `readers.py:26-87` implements `DomReader`, `CopyButtonReader`, and default order `(DomReader(), CopyButtonReader())` scoped to a supplied latest-turn locator; `selector_map.py:20-38` fails closed on empty/missing selector data; `patch.py:186-238` tries latest-turn download artifacts before fenced fallback; `cli.py:61-87` wraps the library result and only applies through `apply_patch` in explicit patch modes.

## Spot recheck 2 — bundle/patch protocol sampling

PASS. Claim sampled: changed-files-only patch bundles with manifest. Runbook UC2 prompts require only changed files; bundle instructions enforce “only changed/deleted paths and `manifest.json`” at `bundle.py:137` and schema at `bundle.py:151-165`; validator enforces manifest keys/statuses at `patch.py:709-767` and payload set exactly equals changed paths at `patch.py:619-620`.

PASS. Claim sampled: fenced fallback is checksummed base64url with `BEGIN_PATCH_BUNDLE`/`END_PATCH_BUNDLE`, `MANIFEST_JSON`, byte count, and SHA-256. Bundle instructions state this at `bundle.py:175-189`; parser/validator enforces marker counts, base64url caps, zip byte count, SHA-256, and manifest envelope consistency at `patch.py:419-492`.

PASS. Claim sampled: path safety/no absolute paths/no `..`/no symlink or out-of-root writes. Bundle instructions state path rules at `bundle.py:101` and `bundle.py:198`; lexical validation rejects backslashes/absolute/drive/traversal at `bundle.py:413-432`; apply validation rejects escapes/symlinks/special targets at `patch.py:851-896` and later apply-time checks.

## Spot recheck 3 — mock-vs-real honesty

PASS. `README.md:18` still says automated acceptance is against local mock ChatGPT and real-site proof is operator-gated with explicit consent. The real-site runbook header/preamble says automated tests prove only loopback mock and real behavior is expected but unproven until operator execution (`docs/runbooks/real-site-acceptance.md:19-21`). `docs/runbooks/observe-chatgpt-unknowns.md:5`, `:11`, `:54`, and `:267` keep the manual/unknown/Playwright-not-proven distinctions.

T4b-VERDICT: PASS
END_TIMESTAMP: 2026-06-12T11:50:14Z
T4b-STATUS: DONE
