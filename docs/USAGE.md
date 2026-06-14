# Using `ask-chatgpt` from another agent

`ask-chatgpt` drives a **real, human-launched ChatGPT browser session** to send a prompt and read the
assistant's reply as text, and (optionally) to ship a small file bundle and get back an applied patch.
It is a library + CLI, not a daemon and not an API client — it has no API key and reads ChatGPT's web
UI through a versioned selector map.

This guide is for an **agent consuming the tool**. It states honestly what is real-proven, what is
mock-proven only, and what fails closed. Status claims tie to `VERIFICATION.md` and the cited mission
reports under `orchestration/reports/`.

## TL;DR
```python
from ask_chatgpt import ask_chatgpt

# UC1 — plain text (returns str)
text = ask_chatgpt("Reply with just the word: pong", channel="cdp")

# UC2 — send files, get an applied-patch bundle back (returns AskChatGPTResult)
from ask_chatgpt import apply_patch
result = ask_chatgpt("In example.txt, change favorite_color red->blue.",
                     files=["example.txt"], bundle_root=".", channel="cdp")
if result.patch_bundle is not None:
    summary = apply_patch(result.patch_bundle, root=".", dry_run=True)   # preview
    apply_patch(result.patch_bundle, root=".", dry_run=False)            # write
```
```bash
ask-chatgpt --channel cdp "Reply with just the word: pong"
```

## Prerequisite: an operator-launched, signed-in CDP browser (ATTENDED)
The tool **never launches a browser for real use and never automates login.** Cloudflare hard-blocks
Playwright-*launched* browsers on chatgpt.com before auth (D-002 addendum). The working real path is
**CDP attach** to a browser the operator started and signed into:

```bash
# Operator runs this in a run window (localhost-only debug port):
chromium --profile-directory='Profile 1' --remote-debugging-port=9222
# ...then signs into chatgpt.com in that window.
```
The tool then attaches with `channel="cdp"` (CLI `--channel cdp`), default endpoint
`http://127.0.0.1:9222` (override with `cdp_endpoint=` / `--cdp-endpoint`). It opens its **own new tab**,
never touches operator tabs, and on close detaches the tab (never quits the browser).

Preflight before relying on it: `curl -s http://127.0.0.1:9222/json/version`. If that fails the tool
raises `CDPUnreachableError` — ask the operator to launch the browser.

> The CLI default is `--channel real`, which *launches* a persistent-context browser and is Cloudflare-
> blocked on chatgpt.com — **do not use it for real work; always pass `--channel cdp`.** `--channel mock`
> is the test-only loopback fixture (see "Default tier" below).

## Library API
`ask_chatgpt(prompt, *, channel="real", cdp_endpoint=None, session_identifier=None, model_settings=None,
files=None, dirs=None, bundle_root=None, timeout_s=30.0, base_url=None, profile_path=None, ...)`

- **No `files`/`dirs`** → returns `str` (the assistant's reply text). This is UC1.
- **With `files`/`dirs`** → returns `AskChatGPTResult(text: str, patch_bundle: PatchBundle | None)`. This
  is UC2: the prompt is wrapped with instructions asking ChatGPT to return one downloadable `.zip` patch;
  `patch_bundle` is the validated, unapplied bundle (or `None` if ChatGPT replied `NO_CHANGES_NEEDED`).
- Apply a bundle with `apply_patch(bundle, root, *, dry_run=True) -> DiffSummary`. `dry_run=True` previews
  the diff without writing; `dry_run=False` writes under `root` (changed-files-only, path-escape-guarded).

### Session continuity (`session_identifier` / `--session`)
Pass a stable `session_identifier="my-key"` to make follow-up calls land in the **same ChatGPT
conversation** (the tool stores the conversation reference in a local registry and reopens it). Omit it
for a fresh conversation each call. Continuity is real-proven conversation-scoped (M-008b: a planted
nonce is recalled in the same conversation; a fresh conversation does not recall it).

### Bundles (UC2 flags)
- Library: `files=[...]`, `dirs=[...]`, `bundle_root="."` (root the paths are relative to).
- CLI: `--files PATH` (repeatable), `--dirs PATH` (repeatable), `--root DIR` (apply + bundle root),
  `--apply` (write) or `--dry-run` (preview; mutually exclusive), `--out FILE` (write reply text).
  `--apply`/`--dry-run` require at least one `--files`/`--dirs` and an explicit `--root`. In patch mode
  the CLI prints a JSON `DiffSummary` to stdout.

### `model_settings` — honest status
`model_settings={"model": "<label>"}` now selects a top-level model option on the **real** site (M-010), proven over CDP by the composer trigger's visible label changing after selection. The picker is the **composer-toolbar dropdown** (`model_menu`); on the test account its observed, enabled top-level options were `Instant`, `Medium`, `High`, `Extra High`, and `Pro Extended`.

Important scope: these labels are GPT-5.5 **reasoning/throughput tiers** in the composer picker — mode/tier labels, **not base model families**. Base model families live behind a separate `GPT-5.5` submenu (`role="menuitem"` with `aria-haspopup`), and that submenu is **not wired** in this pass; requesting a base-model-family name fails closed.

Availability is account/plan-dependent. The exact labels depend on the signed-in account, and the tool fails closed on any requested label not present in the open menu. M-010 switch proof exercised UI-state switches `Extra High` → `Instant` and `Instant` → `Medium`, with `Extra High` also restored as the starting selection; end-to-end `ask_chatgpt(..., model_settings={"model": "Instant"}, channel="cdp")` returned. `High` and `Pro Extended` were observed available/enabled but were not switch- or send-proven.

Requesting an available top-level composer-picker label now works. Requesting an absent label (typo, unavailable account/plan label, or base-model-family name) raises `ModelUnavailableError` before any send — it never silently sends on the wrong model. Evidence: `orchestration/reports/M-010/discovery.md`, `orchestration/reports/M-010/T3-switch-proof.json`; see also `VERIFICATION.md`.

## Named error modes (all subclass `AskChatGPTError`)
Each is actionable and fails closed. The CLI maps the exit codes shown in parentheses below; errors
with no code shown fall through to the generic `AskChatGPTError` exit code `1`, and the bundle-
validation group intentionally shares code `11`. All error classes are importable from `ask_chatgpt.errors` (e.g. `from ask_chatgpt.errors import DownloadUnsupportedError`); the common ones are also re-exported from the top-level `ask_chatgpt`.

| Error | Means | Operator action |
|---|---|---|
| `CDPUnreachableError` (1) | CDP endpoint down (no browser to attach). | Launch `chromium --remote-debugging-port=9222`, sign in, retry. |
| `LoginRequiredError` (3) | Browser is logged out / redirected to auth. | Sign in via the browser UI and retry (tool never reads credentials). |
| `ChallengePresentError` (1) | Cloudflare / human-verification challenge is showing. | Clear it manually in the browser, then retry. Automation stops, never clicks through. |
| `ProfileLockedError` (1) | Profile in use / lock held. | Close the conflicting browser, retry. |
| `SessionNotFoundError` (4) | Stored conversation ref no longer opens. | Delete/recreate that `session_identifier`, retry. |
| `ModelUnavailableError` (5) | A mapped menu lacks the requested model. | Choose an available model setting, retry. |
| `ResponseTruncatedError` (7) | Reply looks incomplete / end-marker missing. | Retry or reduce payload. (Short replies are handled — see caveats.) |
| `RateLimitedError` (6) | ChatGPT signaled a rate limit. | Wait the indicated window, slow down, retry. |
| `SelectorUnavailableError` (8) | A required selector-map key is missing/stale (fail closed, never guesses). | Update the selector map / the feature is unmapped. |
| `UploadUnsupportedError` (9) | Upload affordance absent/rejected. | Disable the upload workflow or retry later. |
| `DownloadUnsupportedError` (10) | No downloadable patch file in the reply (and no fenced fallback). | Use the text channel, or retry — ChatGPT may have answered in prose instead of a file. |
| `PatchMalformedError` / `BundleIntegrityError` / `OversizedPayloadError` / `PathEscapeError` (11) | Returned bundle failed validation. | Request a fresh changed-files-only bundle; no local files were changed. |
| `PatchApplyError` (12) | Apply failed after validation. | Inspect the filesystem / transaction journal; local mutation may need recovery. |

## What is real-proven vs not (read before relying on it)
- **UC1 text (`-> str`): real-PROVEN.** Completeness on long replies (M-008b: 180-line elicitation returned
  exact + complete) and short replies (M-009 T2: `PING`/`hi`/`7`/`OK` each returned, **0 spurious
  truncations**, `orchestration/reports/M-009/T2-short-response.json`).
- **UC2 round-trip (`files=` → capture → apply + diff + content): real-PROVEN for a SINGLE modified-file bundle.** M-009 T1 closed this end-to-end over CDP: upload → real `.zip` captured via the production path (`source=download`, 161 bytes) → applied → `favorite_color` red→blue with the sibling line unchanged (`content_correct=true`, `orchestration/reports/M-009/T1-uc2-roundtrip.json`). **Scope:** only the single modified-file round-trip is real-proven; **added, deleted, and multi-file bundles are mock-proven only** (`VERIFICATION.md` M-007 scope), not yet validated against the real download path. The real ChatGPT download control carries no integrity metadata, so the captured zip is validated **structurally** (zip-slip + caps + structure), not against a model-declared SHA.
- **Continuity: real-PROVEN (conversation-scoped, memory-immune).** M-008b temp-chat probe 3/3.
- **Real model selection: real-PROVEN (M-010)** — composer-picker reasoning/throughput tiers; UI-state switch + fail-closed proven; base-model-family submenu not wired. See `model_settings` above.

## Caveats (do not over-rely)
- **Attended + human browser required.** Real use needs an operator-launched, signed-in CDP browser in a
  run window. There is no headless/unattended real mode (Cloudflare + login-never-automated).
- **Consumes the operator's ChatGPT quota** and runs on their account. Human-paced; do not spam (no
  rapid-fire loops). Honor `RateLimitedError` as a stop, not a retry-through.
- **Non-deterministic surface.** UC2 depends on ChatGPT choosing to emit a downloadable file; if it
  answers in prose, expect `DownloadUnsupportedError`. The download selector is text-dependent
  (`button:has-text("Download the patch bundle")`) and fails closed if the UI text drifts.
- **Default test tier is mock-only.** `uv run pytest` is loopback-mock-only (213 passed / 4 deselected),
  contacts neither chatgpt.com nor any API, and burns no quota. Real-site tests are double-gated behind a
  `real_site` marker **and** `ASK_CHATGPT_REAL=1`; they never run by accident.
- **Fail-closed everywhere.** On any stale selector, challenge, logout, or ambiguous bundle the tool
  raises a named error and changes nothing — it never guesses, broadens selectors, or sends on the wrong
  model. Treat a raised error as "stop and tell the operator," not "retry blindly."
