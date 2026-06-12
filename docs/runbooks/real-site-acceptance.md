# Real-site acceptance for ask-chatgpt (operator-run, consent-gated)

## Consent + safety preamble — read before any command

This runbook drives the operator's REAL `chatgpt.com` session in the operator's own visible browser profile. It can consume the operator's ChatGPT quota, create or modify disposable conversations in the operator's account, and expose any uploaded synthetic bundle content to ChatGPT. It is the human/operator half of acceptance; automated acceptance uses the loopback mock only.

NEVER run this runbook from CI, pytest, cron, a bot, or unattended automation. No test, script, or mission worker is allowed to execute these real-site steps. The operator must be hands-on-keyboard, watching the browser, and must type the consent token required by each command block immediately before that command contacts `chatgpt.com`.

The tool must never read, store, print, screenshot, commit, or log credentials, cookies, auth headers, session tokens, browser local storage, or browser-profile contents. The real channel takes an opaque browser profile directory path only so Chromium can open the operator's own logged-in profile; the tool treats that path as configuration and must not inspect the profile directory.

If the browser shows a login screen, the operator may sign in manually through the visible browser UI only. Do not paste passwords, cookies, tokens, account emails, workspace names, private conversation URLs, or private content into terminals, reports, issues, commits, or this repository.

All prompts and files in this runbook are synthetic. Do not upload private source, secrets, personal data, proprietary files, or the predecessor archive. Keep scratch files under this repository's `tmp/real-site-acceptance/` unless the operator deliberately chooses another disposable local root.

Typed consent is required per UC. If you are not the consenting account/profile owner, stop. If any command would contact `chatgpt.com` before a typed-consent check passes, stop and fix the command.

## What is and is not proven before this runbook

Automated tests and mock acceptance prove behavior only against a local loopback mock ChatGPT fixture. They never contact `chatgpt.com`, OpenAI, or any external network service.

Every real-site behavior below is expected but unproven until the operator executes this runbook: real selectors, completion signals, DOM text extraction, copy fallback behavior, upload/download affordances, file size limits, session pinning, model selection, artifact-to-turn identity, and failure-message detectability.

D-001 is the binding design posture for these observations: UC1 text reading is DOM-primary with copy-button fallback; UC2 bundle retrieval is download-capture-primary with a checksummed fenced-base64url fallback; selector maps are operator-versioned data and stale/missing selectors fail closed; no transcript-wide scraping is allowed.

## Prerequisite — resolve real-site unknowns and fill `real.json` first

Do not run UC1, UC2, or UC3 real-site acceptance until `docs/runbooks/observe-chatgpt-unknowns.md` has been completed by the operator on the operator's own account/profile, and `src/ask_chatgpt/selector_maps/real.json` has been filled from those observations.

If `real.json` is still the all-empty template, the real channel is supposed to fail closed with `SelectorUnavailableError`. That is correct and is not a failed acceptance run; it means the observation prerequisite is incomplete.

Confirm the prerequisite locally before any real-site contact:

```bash
cd /home/abhmul/dev/ask-chatgpt
uv sync --all-groups
mkdir -p tmp/real-site-acceptance/state
export ASK_CHATGPT_STATE_DIR="$PWD/tmp/real-site-acceptance/state"
export ASK_CHATGPT_PROFILE_PATH="/absolute/path/to/operator-owned/chatgpt-browser-profile"
# Optional, only if the observed real UI exposes a stable model label and you want to select it from Python UC1:
# export ASK_CHATGPT_MODEL="observed model label from the real UI"
uv run python - <<'PY'
import json
from pathlib import Path
p = Path("src/ask_chatgpt/selector_maps/real.json")
data = json.loads(p.read_text(encoding="utf-8"))
missing = []
for section in ("selectors", "attributes"):
    values = data.get(section, {})
    if not isinstance(values, dict):
        missing.append(section)
        continue
    for key, value in values.items():
        if not isinstance(value, str) or not value.strip():
            missing.append(f"{section}.{key}")
if missing:
    raise SystemExit("real.json is not populated; run docs/runbooks/observe-chatgpt-unknowns.md first. Empty keys: " + ", ".join(missing))
print("real.json appears populated for real-site acceptance. Review it manually for secrets before proceeding.")
PY
uv run ask-chatgpt --help
```

Also confirm by manual review that `real.json` contains only selector strings, attribute names, stable visible labels, and nonsecret behavior mappings. It must not contain credentials, cookies, auth tokens, account emails, workspace names, private conversation refs, private transcript content, screenshots, or browser-profile contents.

## Committed CLI surface used by UC2 and UC3

The committed CLI is a single command, `ask-chatgpt`, with no subcommands. Confirm the local install before any CLI command contacts the real site by running `uv run ask-chatgpt --help` and checking for these operator-facing flags: positional `prompt`, `--prompt`, `--session`, `--model-settings`, `--files`, `--dirs`, `--out`, `--apply`, `--dry-run`, `--root`, `--channel`, `--base-url`, `--profile-path`, and `--timeout`.

For patch workflows, the current CLI retrieves a returned patch bundle inside the same real-site invocation that sent `--files` or `--dirs`. `--dry-run` validates and summarizes the returned patch without writing to `--root`; `--apply` validates and then mutates only under the explicit `--root`. The current CLI does not provide a separate operator-facing saved-bundle input/output; if you need to preserve evidence, keep the assistant text written by `--out` and the JSON summary printed to stdout.

## Acceptance record template

Record only nonsecret facts. Keep raw browser details local unless redacted. A minimal acceptance note should include: date/time, operator consent typed locally yes/no, browser/profile owned by operator yes/no, `real.json` populated yes/no, `ask-chatgpt --help` command shape confirmed yes/no, UC1 result PASS/FAIL/BLOCKED, UC2 result PASS/FAIL/BLOCKED, UC3 result PASS/FAIL/BLOCKED, observed named errors, whether DOM-primary was materially flakier than copy fallback, whether bundle retrieval used download capture or fenced fallback, and any selector/protocol updates needed.

## NEVER AUTOMATED BANNER FOR ALL RUN STEPS

The following UC steps are not tests. Do not add them to pytest, CI, shell scripts, make targets, pre-commit hooks, or unattended acceptance scripts. The operator copies each command block by hand, reads the prompt, types the required token, watches the visible browser, and stops on any unexpected private-data exposure.

## UC1 — `ask_chatgpt(prompt, session_identifier, model_settings) -> text`

### UC1 command: real-site function call with typed consent

This command contacts `chatgpt.com` only after the operator types `I-CONSENT-REAL-CHATGPT-UC1`. It uses a disposable session identifier and writes the session registry under `tmp/real-site-acceptance/state`.

```bash
cd /home/abhmul/dev/ask-chatgpt
mkdir -p tmp/real-site-acceptance/state
export ASK_CHATGPT_STATE_DIR="$PWD/tmp/real-site-acceptance/state"
: "${ASK_CHATGPT_PROFILE_PATH:?Set ASK_CHATGPT_PROFILE_PATH to an operator-owned browser profile path before proceeding}"
printf 'UC1 will contact REAL chatgpt.com using your browser profile and quota. Type I-CONSENT-REAL-CHATGPT-UC1 to proceed: '
read -r ACCEPT_REAL_SITE
if [ "$ACCEPT_REAL_SITE" != "I-CONSENT-REAL-CHATGPT-UC1" ]; then echo 'Consent token mismatch; stopping before real-site contact.' >&2; exit 2; fi
uv run python - <<'PY'
import os
import time
from ask_chatgpt import ask_chatgpt
profile = os.environ["ASK_CHATGPT_PROFILE_PATH"]
nonce = "UC1-" + time.strftime("%Y%m%dT%H%M%S")
model = os.environ.get("ASK_CHATGPT_MODEL")
model_settings = {"model": model} if model else None
prompt = f"Real-site acceptance UC1. Reply with exactly this single line and no extra words: REAL-SITE-UC1-PASS {nonce}"
print("UC1_NONCE", nonce)
text = ask_chatgpt(prompt, session_identifier="real-site-acceptance-uc1", model_settings=model_settings, channel="real", profile_path=profile, timeout_s=90.0)
print("ASSISTANT_TEXT_BEGIN")
print(text)
print("ASSISTANT_TEXT_END")
expected = f"REAL-SITE-UC1-PASS {nonce}"
if expected not in text:
    raise SystemExit(f"UC1 INCONCLUSIVE/FAIL: expected {expected!r} in assistant text")
print("UC1 PASS: expected nonce observed in returned assistant text")
PY
```

### UC1 expected observations

Expected, to be confirmed on the real site: a headed Chromium window opens on the operator's profile; if the profile is already logged in, the tool opens or creates the disposable session, sends the prompt, waits for completion using the observed real selectors, reads only the latest completed assistant turn, and prints assistant text containing `REAL-SITE-UC1-PASS <nonce>`.

A PASS means the function returned the latest assistant response text for the known prompt, session pinning did not prevent the disposable session from opening, and the model selection was either not requested or selected from the observed real UI. This does not prove UC2 upload/download and does not prove every future ChatGPT UI rollout.

If the visible browser answer contains the nonce but the returned text does not, report a D-001 reader issue: DOM-primary may be stale, partial, wrong-turn, virtualized, or otherwise flakier than expected. If copy-button fallback succeeds more reliably during a supervised diagnostic run, report that as an empirical-revisit trigger to consider flipping reader order.

### UC1 honest-failure interpretations

| What the operator sees | Named error expected from tool | Meaning and action |
| --- | --- | --- |
| Browser shows a login wall, or stderr names a login condition without printing credentials. | `LoginRequiredError` | The profile is not logged in or the session expired. Sign in manually in the visible browser if you consent, then rerun; the tool must not read/store credentials. |
| Browser or stderr indicates the stored disposable conversation cannot be opened. | `SessionNotFoundError` | The session ref in `ASK_CHATGPT_STATE_DIR` is stale, deleted, archived incompatibly, or unmapped. Delete/recreate the disposable `real-site-acceptance-uc1` entry or use a new session identifier. |
| Browser lacks an observed selector or stderr says a selector-map key is unavailable. | `SelectorUnavailableError` | `real.json` is empty, stale, incomplete, or mismatched to this rollout. Stop, rerun/update `observe-chatgpt-unknowns.md`, and do not broaden selectors ad hoc. |
| Requested model label is absent, disabled, upgraded away, or not selectable. | `ModelUnavailableError` | The optional `ASK_CHATGPT_MODEL` does not match the real UI/account. Clear it or set it to an observed available label. |
| Browser shows rate limit/backoff/capacity message. | `RateLimitedError` | Quota or rate limit is hit. Wait per UI guidance and rerun only if the operator consents. |
| The assistant visibly continues, asks to continue generating, lacks a completion marker, or stderr says truncation/timeout. | `ResponseTruncatedError` | The completion signal or output completeness failed. Retry with a shorter prompt/longer timeout after updating selectors if needed. |
| Upload unsupported, download unsupported, patch malformed, hash/byte-count mismatch, oversized payload, or path escape appears during this plain UC1 command. | `UploadUnsupportedError`, `DownloadUnsupportedError`, `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, or `PathEscapeError` as applicable | These are not expected in plain UC1. Treat as wrong command path, stale invocation, or cross-feature bug; stop and record the named error before any local mutation. |

## UC2 — bundle workflow: send files/dirs, retrieve changed-files-only patch bundle, apply locally

### UC2 non-contact setup and CLI confirmation

These setup commands do not contact the real site. They create a disposable scratch root, confirm the committed CLI help, and intentionally use paths relative to the later `--root` when invoking `--files`.

```bash
cd /home/abhmul/dev/ask-chatgpt
uv sync --all-groups
uv run ask-chatgpt --help
rm -rf tmp/real-site-acceptance/uc2
mkdir -p tmp/real-site-acceptance/uc2/root
printf 'favorite_color = "red"\n' > tmp/real-site-acceptance/uc2/root/example.txt
printf 'Expected UC2 edit: change favorite_color from red to blue in example.txt only.\n' > tmp/real-site-acceptance/uc2/expected.txt
```

If `uv run ask-chatgpt --help` is unavailable, or if it does not show `--files`, `--dirs`, `--root`, `--dry-run`, `--apply`, `--out`, `--channel`, `--profile-path`, and `--session`, do not run UC2 real-site acceptance. Record UC2 as blocked pending the CLI/UC2 implementation, not as a real-site failure.

### UC2 command 1: contact real site, upload synthetic bundle, retrieve and validate patch bundle without writes

This command contacts `chatgpt.com` only after the operator types `I-CONSENT-REAL-CHATGPT-UC2-DRY-RUN`. It uploads the synthetic `example.txt`, asks for a changed-files-only patch, writes the assistant text to `assistant-response-dry-run.txt`, and prints a JSON dry-run summary to stdout; it must not write to the scratch root.

```bash
cd /home/abhmul/dev/ask-chatgpt
mkdir -p tmp/real-site-acceptance/state tmp/real-site-acceptance/uc2
export ASK_CHATGPT_STATE_DIR="$PWD/tmp/real-site-acceptance/state"
: "${ASK_CHATGPT_PROFILE_PATH:?Set ASK_CHATGPT_PROFILE_PATH to an operator-owned browser profile path before proceeding}"
printf 'UC2 dry-run will upload a synthetic bundle to REAL chatgpt.com and consume quota. Type I-CONSENT-REAL-CHATGPT-UC2-DRY-RUN to proceed: '
read -r ACCEPT_REAL_SITE
if [ "$ACCEPT_REAL_SITE" != "I-CONSENT-REAL-CHATGPT-UC2-DRY-RUN" ]; then echo 'Consent token mismatch; stopping before real-site contact.' >&2; exit 2; fi
uv run ask-chatgpt \
  --channel real \
  --profile-path "$ASK_CHATGPT_PROFILE_PATH" \
  --session real-site-acceptance-uc2-dry-run \
  --prompt 'Real-site acceptance UC2 dry-run. You are editing a synthetic file. Change favorite_color from "red" to "blue" in example.txt. Return a patch bundle containing ONLY changed files, with repo-root-relative forward-slash paths, no absolute paths, no .. traversal, and no unchanged files. Prefer a downloadable .zip; if no download artifact is available, use the exact fenced patch-bundle fallback required by the bundle protocol.' \
  --files example.txt \
  --root tmp/real-site-acceptance/uc2/root \
  --dry-run \
  --out tmp/real-site-acceptance/uc2/assistant-response-dry-run.txt \
  --timeout 120 \
  | tee tmp/real-site-acceptance/uc2/dry-run-summary.json
grep -Fx 'favorite_color = "red"' tmp/real-site-acceptance/uc2/root/example.txt
```

Before applying, manually inspect `tmp/real-site-acceptance/uc2/dry-run-summary.json`. It must show `"dry_run": true`, exactly one modified path `example.txt`, and the explicit scratch root. The JSON summary may report hashes/counts rather than a content diff; use it to confirm scope, then use the final file check after apply to confirm the red-to-blue content. If the summary is empty, names any other path, reports a delete/add you did not intend, or reports any validation error, stop before local mutation.

### UC2 command 2: contact real site again, validate, then apply only to the explicit scratch root

The current CLI applies only the patch bundle returned by the same invocation, so this command requires both renewed real-site consent and a separate local mutation token before it runs. It repeats the same synthetic task, writes the assistant text to `assistant-response-apply.txt`, validates the returned patch bundle, applies only after validation, and prints a JSON apply summary to stdout.

```bash
cd /home/abhmul/dev/ask-chatgpt
mkdir -p tmp/real-site-acceptance/state tmp/real-site-acceptance/uc2
export ASK_CHATGPT_STATE_DIR="$PWD/tmp/real-site-acceptance/state"
: "${ASK_CHATGPT_PROFILE_PATH:?Set ASK_CHATGPT_PROFILE_PATH to an operator-owned browser profile path before proceeding}"
printf 'UC2 apply will contact REAL chatgpt.com again using synthetic data. Type I-CONSENT-REAL-CHATGPT-UC2-APPLY to proceed: '
read -r ACCEPT_REAL_SITE
if [ "$ACCEPT_REAL_SITE" != "I-CONSENT-REAL-CHATGPT-UC2-APPLY" ]; then echo 'Consent token mismatch; stopping before real-site contact.' >&2; exit 2; fi
printf 'UC2 apply may mutate only tmp/real-site-acceptance/uc2/root/example.txt after validation. Type APPLY-UC2-SYNTHETIC-PATCH to mutate that scratch root: '
read -r ACCEPT_APPLY
if [ "$ACCEPT_APPLY" != "APPLY-UC2-SYNTHETIC-PATCH" ]; then echo 'Apply token mismatch; stopping before real-site contact and before local mutation.' >&2; exit 2; fi
uv run ask-chatgpt \
  --channel real \
  --profile-path "$ASK_CHATGPT_PROFILE_PATH" \
  --session real-site-acceptance-uc2-apply \
  --prompt 'Real-site acceptance UC2 apply. You are editing a synthetic file. Change favorite_color from "red" to "blue" in example.txt. Return a patch bundle containing ONLY changed files, with repo-root-relative forward-slash paths, no absolute paths, no .. traversal, and no unchanged files. Prefer a downloadable .zip; if no download artifact is available, use the exact fenced patch-bundle fallback required by the bundle protocol.' \
  --files example.txt \
  --root tmp/real-site-acceptance/uc2/root \
  --apply \
  --out tmp/real-site-acceptance/uc2/assistant-response-apply.txt \
  --timeout 120 \
  | tee tmp/real-site-acceptance/uc2/apply-summary.json
grep -Fx 'favorite_color = "blue"' tmp/real-site-acceptance/uc2/root/example.txt
```

### UC2 expected observations

Expected, to be confirmed on the real site: the real UI accepts the synthetic uploaded bundle, ChatGPT reads the catalogue/file, returns a patch bundle containing only the changed `example.txt`, and the tool retrieves that patch bundle either via Playwright download capture or via the checksummed fenced base64url fallback.

A PASS requires all of the following: the dry-run command exits zero, writes `assistant-response-dry-run.txt`, prints a dry-run JSON summary showing only `example.txt`, and leaves the scratch file red; the apply command exits zero after both consent tokens, writes `assistant-response-apply.txt`, prints an apply JSON summary showing only `example.txt`, and changes only `tmp/real-site-acceptance/uc2/root/example.txt`; the final file contains exactly `favorite_color = "blue"`; no absolute path, `..`, symlink escape, unchanged-file overwrite, or out-of-root write occurs.

If download capture succeeds, record that the real site offered a usable download affordance for this prompt/model/account and note suggested filename/MIME if visible. If download capture is absent but fenced fallback succeeds and validates, UC2 can still pass via D-001 fallback, but record that real-site download support was absent or inconclusive. If both paths fail, UC2 real-site acceptance fails or blocks depending on the named error.

Watch D-001 revisit triggers: if real artifacts are not scoped to the latest assistant turn, if the latest visible download retrieves an older file, if the real site provides downloads only under model/account conditions not captured by `real.json`, or if fenced payloads are truncated near observed limits, record this and update the observation results/protocol before claiming broad support.

### UC2 honest-failure interpretations

| What the operator sees | Named error expected from tool | Meaning and action |
| --- | --- | --- |
| Browser shows login wall or CLI exits with login-required text. | `LoginRequiredError` | The real profile is not authenticated. Sign in manually in the visible browser if you consent; do not expose credentials to the tool or logs. |
| The stored UC2 session URL/ref no longer opens the intended disposable chat. | `SessionNotFoundError` | The local session registry has a stale or deleted conversation ref. Delete/recreate the disposable session or choose a new session identifier. |
| Upload control is absent, rejects `.zip`, rejects size/type, scanning fails, or the tool cannot attach the outgoing bundle. | `UploadUnsupportedError` | Real upload support is absent, disabled, over limit, or selector/config is stale. Stop UC2; update observation limits/selectors or reduce synthetic payload if the UI says size/type is the issue. |
| No downloadable artifact appears, Playwright download capture does not fire, or the artifact is unavailable; fenced fallback then succeeds. | `DownloadUnsupportedError` may be logged/handled internally before fallback, final command may still pass | Download-capture primary is unsupported or inconclusive for this real run; acceptance may pass via fenced fallback, but record the real download behavior. |
| No downloadable artifact appears and the fenced fallback also cannot be parsed. | `DownloadUnsupportedError` or `ResponseTruncatedError` depending on visible/fenced symptoms | Retrieval failed. Record whether the model never produced a bundle, produced text only, or truncated; revise prompt/protocol or real capability config before retry. |
| Patch zip is corrupt, manifest missing/invalid, required fields missing, multiple bundles are returned, unchanged files are included when forbidden, or fence markers are malformed/missing. | `PatchMalformedError` | The bundle is not structurally valid. No apply may mutate anything; save only nonsecret diagnostics and update prompt/protocol. |
| Whole-zip byte count, whole-zip SHA-256, per-file byte count, or per-file SHA-256 does not match. | `BundleIntegrityError` | The retrieved bytes are incomplete, altered, or not the declared bundle. No apply; retry with smaller payload or alternate retrieval path after recording the mismatch. |
| Upload or returned fenced payload exceeds configured caps, UI reports size limit, or parser rejects payload as too large. | `OversizedPayloadError` for retrieved patch payload, or `UploadUnsupportedError` for outgoing upload rejection | Payload is over safe/observed limits. Reduce bundle size, split files, or update observed limits only after rerunning the observation runbook. |
| Manifest or zip entry uses an absolute path, contains `..`, targets outside `--root`, or would follow/write through a symlink escape. | `PathEscapeError` | Treat as unsafe or adversarial output. No file may be written; report the prompt/model behavior and preserve only redacted diagnostics. |
| A patch validates but local write, rollback, filesystem, or transaction-journal handling fails. | `PatchApplyError` | Local mutation failed after validation. Stop, inspect only the synthetic scratch root and transaction detail, and do not retry on private data. |
| Generic patch or upload validation fails without a more specific subclass. | `PatchBundleValidationError` | The bundle was rejected before any write. Treat the detail as safe diagnostic input and rerun only after reducing payload or fixing the prompt/protocol. |
| Assistant response visibly stops early, asks to continue, lacks `END_PATCH_BUNDLE`, lacks final markers, or times out. | `ResponseTruncatedError` | The text channel or completion signal was insufficient. Prefer download capture, reduce payload, or update real truncation limits before retry. |
| Model option unavailable, rate limit banner, or selector unavailable appears. | `ModelUnavailableError`, `RateLimitedError`, or `SelectorUnavailableError` | Not a bundle-format failure. Resolve account/model/quota/selector condition first, then rerun UC2 only with renewed consent. |

## UC3 — `ask-chatgpt` CLI wrapping the function

### UC3 CLI confirmation

Run the following non-contact confirmation before real-site contact. The commands below use only committed CLI flags and keep real-channel explicitness, session explicitness, and no-mutation-by-default posture.

```bash
cd /home/abhmul/dev/ask-chatgpt
uv sync --all-groups
uv run ask-chatgpt --help
```

If the help output is unavailable, or if it does not show `--channel`, `--profile-path`, `--session`, `--prompt`, `--out`, and `--timeout`, do not run UC3 real-site acceptance. If model selection is required for a later CLI run, express it with the real `--model-settings JSON` flag after confirming the observed model label; do not proceed on guesses.

### UC3 command 1: CLI prints response to stdout

This command contacts `chatgpt.com` only after the operator types `I-CONSENT-REAL-CHATGPT-UC3-STDOUT`.

```bash
cd /home/abhmul/dev/ask-chatgpt
mkdir -p tmp/real-site-acceptance/state tmp/real-site-acceptance/uc3
export ASK_CHATGPT_STATE_DIR="$PWD/tmp/real-site-acceptance/state"
: "${ASK_CHATGPT_PROFILE_PATH:?Set ASK_CHATGPT_PROFILE_PATH to an operator-owned browser profile path before proceeding}"
NONCE="UC3-STDOUT-$(date +%Y%m%dT%H%M%S)"
printf 'UC3 stdout will contact REAL chatgpt.com using your browser profile and quota. Type I-CONSENT-REAL-CHATGPT-UC3-STDOUT to proceed: '
read -r ACCEPT_REAL_SITE
if [ "$ACCEPT_REAL_SITE" != "I-CONSENT-REAL-CHATGPT-UC3-STDOUT" ]; then echo 'Consent token mismatch; stopping before real-site contact.' >&2; exit 2; fi
uv run ask-chatgpt \
  --channel real \
  --profile-path "$ASK_CHATGPT_PROFILE_PATH" \
  --session real-site-acceptance-uc3-stdout \
  --prompt "Real-site acceptance UC3 stdout. Reply with exactly this single line and no extra words: REAL-SITE-UC3-STDOUT-PASS $NONCE" \
  --timeout 90 \
  | tee tmp/real-site-acceptance/uc3/stdout.txt
grep -F "REAL-SITE-UC3-STDOUT-PASS $NONCE" tmp/real-site-acceptance/uc3/stdout.txt
```

### UC3 command 2: CLI writes response to `--out`

This command contacts `chatgpt.com` only after the operator types `I-CONSENT-REAL-CHATGPT-UC3-OUT`.

```bash
cd /home/abhmul/dev/ask-chatgpt
mkdir -p tmp/real-site-acceptance/state tmp/real-site-acceptance/uc3
export ASK_CHATGPT_STATE_DIR="$PWD/tmp/real-site-acceptance/state"
: "${ASK_CHATGPT_PROFILE_PATH:?Set ASK_CHATGPT_PROFILE_PATH to an operator-owned browser profile path before proceeding}"
NONCE="UC3-OUT-$(date +%Y%m%dT%H%M%S)"
printf 'UC3 --out will contact REAL chatgpt.com using your browser profile and quota. Type I-CONSENT-REAL-CHATGPT-UC3-OUT to proceed: '
read -r ACCEPT_REAL_SITE
if [ "$ACCEPT_REAL_SITE" != "I-CONSENT-REAL-CHATGPT-UC3-OUT" ]; then echo 'Consent token mismatch; stopping before real-site contact.' >&2; exit 2; fi
uv run ask-chatgpt \
  --channel real \
  --profile-path "$ASK_CHATGPT_PROFILE_PATH" \
  --session real-site-acceptance-uc3-out \
  --prompt "Real-site acceptance UC3 --out. Reply with exactly this single line and no extra words: REAL-SITE-UC3-OUT-PASS $NONCE" \
  --out tmp/real-site-acceptance/uc3/out.txt \
  --timeout 90
grep -F "REAL-SITE-UC3-OUT-PASS $NONCE" tmp/real-site-acceptance/uc3/out.txt
```

### UC3 expected observations

Expected, to be confirmed on the real site: command 1 exits zero and prints the assistant response to stdout; command 2 exits zero and writes the assistant response to the path given by `--out`; both outputs contain the expected nonce; stderr contains no credentials, cookies, tokens, profile contents, private refs, or private transcript text.

A PASS means the installed `ask-chatgpt` console script wraps the public function for the real channel with the operator's explicit consent and preserves stdout/`--out` behavior. UC3 plain prompt acceptance does not by itself prove UC2 file apply; if the CLI also uses file/apply flags, those inherit UC2's patch validation and explicit `--apply --root` requirements.

Watch D-001 revisit triggers from the CLI surface too: if CLI output differs from the visible latest assistant turn, if `--out` writes partial/stale text, if DOM-primary fails while copy fallback would have succeeded, or if CLI error messages include private account/profile details, stop and report before broader use.

### UC3 honest-failure interpretations

| What the operator sees | Named error expected from tool | Meaning and action |
| --- | --- | --- |
| CLI help is unavailable or the `ask-chatgpt` console script is not installed. | No real-site error; UC3 implementation/preflight is blocked | Do not contact the site for UC3. Install/sync the implemented CLI or wait for CLI completion, then rerun help confirmation. |
| Browser shows login wall or CLI exits with login-required text. | `LoginRequiredError` | The real profile is not authenticated. Sign in manually in the visible browser if you consent; the CLI must not request or log credentials. |
| CLI reports the stored session cannot be opened. | `SessionNotFoundError` | The disposable CLI session ref is stale/deleted. Delete/recreate the registry entry under `ASK_CHATGPT_STATE_DIR` or use a new session identifier. |
| CLI reports missing/stale selector-map key or cannot find real UI controls. | `SelectorUnavailableError` | `real.json` is incomplete or stale for this rollout. Stop and update via the observation runbook. |
| Requested model setting is not available in the UI/account. | `ModelUnavailableError` | Remove or correct the model setting using observed labels. |
| Rate/capacity/quota banner appears or stderr reports backoff. | `RateLimitedError` | Wait for the operator's quota/backoff window; rerun only with consent. |
| Output lacks the nonce, includes only partial text, times out, or visible UI asks to continue. | `ResponseTruncatedError` or nonzero CLI exit if nonce check fails | The reader/completion path is incomplete or wrong-turn. Reduce prompt, update selectors, or investigate DOM-vs-copy behavior before accepting. |
| Upload/download unsupported appears when using CLI file flags. | `UploadUnsupportedError` or `DownloadUnsupportedError` | UC3 file mode inherits UC2 real-site capability limits. Record whether fallback succeeded; no local apply unless a valid patch exists. |
| Patch malformed, hash/byte-count mismatch, oversized payload, path escape, validation failure, or apply failure appears when using CLI file/apply flags. | `PatchMalformedError`, `BundleIntegrityError`, `OversizedPayloadError`, `PathEscapeError`, `PatchBundleValidationError`, or `PatchApplyError` | The CLI must stop before mutation unless a valid explicit apply passes full validation. Preserve redacted diagnostics, update prompt/protocol/selectors, and rerun only with consent. |

## Stop conditions and reporting

Stop immediately if any command would contact the real site without a freshly typed consent token, if any output contains credentials/cookies/tokens/profile contents/private refs/private transcripts, if `real.json` is unpopulated, if the visible browser shows an unexpected account/workspace/private conversation, if a patch bundle fails validation, or if an apply would write outside the explicit root.

When reporting results, separate facts from interpretations: fact = exact nonsecret named error/output/visible behavior; interpretation = likely stale selector, unsupported upload, quota, etc.; speculation = account/model/rollout-dependent until repeated. Include whether the run used download capture or fenced fallback, whether DOM-primary matched the visible latest turn, and whether any D-001 revisit trigger fired.

Do not commit raw acceptance artifacts if they contain account-private details. Synthetic files under `tmp/real-site-acceptance/` are disposable; review before sharing. The profile path and local session registry may reveal private conversation refs; keep them local or redact them.
