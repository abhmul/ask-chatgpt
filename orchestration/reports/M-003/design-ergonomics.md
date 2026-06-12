ESTIMATE: T1c 45m
START_TIMESTAMP: 2026-06-12T02:04:33-05:00
LENS: ergonomics

## Current `ask_chatgpt` anchor

`src/ask_chatgpt/api.py:16-27` currently defines:

```python
def ask_chatgpt(
    prompt: str,
    *,
    session_identifier: str | None = None,
    model_settings: dict[str, Any] | None = None,
    channel: str = "real",
    base_url: str | None = None,
    profile_path: str | Path | None = None,
    registry: SessionRegistry | None = None,
    reader_order: Iterable[ResponseReader] | None = None,
    timeout_s: float = 30.0,
) -> str:
```

Back-compat anchor: UC1 callers get a plain `str`; `session_identifier` is looked up and persisted through `SessionRegistry`, `model_settings` is passed to `session.select_model(...)` and stored by deep copy in `ConversationRef`, and `channel`/`base_url`/`profile_path` are passed directly to `BrowserSession`. `src/ask_chatgpt/__init__.py` currently exports `ask_chatgpt` plus named errors from `errors.py`.

## Proposed `ask_chatgpt(...)` extension for UC2

Add keyword-only UC2 path arguments at the end of the existing signature to minimize call-site and introspection churn:

```python
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Pathish = str | Path

@dataclass(frozen=True, slots=True)
class PatchBundle:
    filename: str
    content: bytes
    sha256: str
    byte_count: int

@dataclass(frozen=True, slots=True)
class AskChatGPTResult:
    text: str
    patch_bundle: PatchBundle | None


def ask_chatgpt(
    prompt: str,
    *,
    session_identifier: str | None = None,
    model_settings: dict[str, Any] | None = None,
    channel: str = "real",
    base_url: str | None = None,
    profile_path: str | Path | None = None,
    registry: SessionRegistry | None = None,
    reader_order: Iterable[ResponseReader] | None = None,
    timeout_s: float = 30.0,
    files: Sequence[Pathish] | None = None,
    dirs: Sequence[Pathish] | None = None,
) -> str | AskChatGPTResult:
```

Return rule: if no file/dir path is supplied, runtime behavior remains exactly UC1 and the function returns `str`; if at least one path is supplied through `files` or `dirs`, the function returns `AskChatGPTResult(text=..., patch_bundle=...)`. Empty sequences are equivalent to omission.

Choice rationale: returning `str` for UC1 preserves all existing callers, while returning a richer result for UC2 is necessary because there are two caller-facing outputs: assistant text and an optional retrieved changed-files-only patch bundle. Returning only text would hide the patch handle; returning a result object for all calls would be a breaking UC1 API change.

`PatchBundle` is intentionally an opaque, unapplied handle accepted by `apply_patch(...)`. It carries bytes plus stable metadata, avoiding caller-visible temp-file lifetime issues; if implementation stores downloads on disk internally, that remains an implementation detail. `patch_bundle is None` means the assistant produced text but no retrievable patch bundle.

Public export additions recommended in `ask_chatgpt.__init__`: `AskChatGPTResult`, `PatchBundle`, `apply_patch`, `DiffSummary`, `FileDiff`, and any UC2 patch errors finalized by synthesis.

## `apply_patch(...)` API and diff summary

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PatchBundleSource = PatchBundle | bytes | str | Path
ChangeKind = Literal["added", "modified", "deleted"]

@dataclass(frozen=True, slots=True)
class FileDiff:
    path: str                 # POSIX-style path relative to root; never absolute
    change_kind: ChangeKind
    old_sha256: str | None
    new_sha256: str | None
    old_bytes: int | None
    new_bytes: int | None
    byte_delta: int           # new_bytes - old_bytes, treating missing side as 0
    lines_added: int | None   # None for binary/unknown
    lines_deleted: int | None # None for binary/unknown

@dataclass(frozen=True, slots=True)
class DiffSummary:
    root: Path
    dry_run: bool
    files: tuple[FileDiff, ...]
    added: int
    modified: int
    deleted: int
    total_files: int
    total_byte_delta: int
    total_bytes_changed: int  # sum(abs(file.byte_delta))


def apply_patch(
    bundle: PatchBundleSource,
    root: str | Path,
    *,
    dry_run: bool = True,
) -> DiffSummary:
    ...
```

`root` is always caller-specified and has no default. `dry_run=True` is the library default: `apply_patch(bundle, root)` validates and computes the same `DiffSummary` an apply would compute, but performs no writes. Local mutation requires the caller to opt in explicitly with `dry_run=False`.

Dry-run contract: parse and validate the entire bundle, compare against the current filesystem under `root`, and return `DiffSummary` without creating, modifying, deleting, chmodding, or replacing any file under `root`.

Mutation contract: before any write with `dry_run=False`, the library MUST validate the entire bundle first, including manifest, hashes, byte counts, and path safety. It MUST reject absolute paths, `..` traversal, and symlink escapes, and it MUST write only under the caller-specified `root`. Exact validation/write mechanics are owned by the integrity/safety lens; this lens fixes the signature and summary shape.

## CLI design for UC3

`pyproject.toml` should add:

```toml
[project.scripts]
ask-chatgpt = "ask_chatgpt.cli:main"
```

CLI mode summary: by default the CLI calls `ask_chatgpt(...)` and emits only assistant response text. With `--dry-run` or `--apply`, it must first retrieve a UC2 patch bundle, then call `apply_patch(...)` and emit only the diff summary on stdout.

| Flag/argument | Type, default, repeatability | Help text and semantics |
|---|---|---|
| `prompt` | optional positional `str`; default none; not repeatable | Prompt text. Mutually exclusive with `--prompt`; one of positional prompt or `--prompt` is required. |
| `--prompt TEXT` | `str`; default none; not repeatable | Prompt text as an option, useful when positional parsing would be awkward. |
| `--session ID` | `str`; default `None`; not repeatable | Persistent conversation identifier; passes `session_identifier=ID`. |
| `--model-settings JSON` | JSON object string; default `None`; not repeatable | Model/options dictionary passed as `model_settings`; invalid JSON or non-object JSON is CLI usage error. |
| `--files PATH` | path; default empty; repeatable | File to include in the upload bundle; each occurrence appends to `files`. |
| `--dirs PATH` | path; default empty; repeatable | Directory to include in the upload bundle; each occurrence appends to `dirs`. |
| `--out FILE` | path; default `None`; not repeatable | Write assistant response text to `FILE` instead of stdout. In `--apply`/`--dry-run` mode, stdout remains reserved for the diff summary, so `--out` is the way to preserve response text. |
| `--dry-run` | boolean flag; default false; mutually exclusive with `--apply` | Retrieve a patch bundle and show the `DiffSummary` without applying it. Requires at least one `--files`/`--dirs` path and an explicit `--root`. |
| `--apply` | boolean flag; default false; mutually exclusive with `--dry-run` | Retrieve a patch bundle and apply it by calling `apply_patch(..., dry_run=False)`. Requires at least one `--files`/`--dirs` path and an explicit `--root`; without `--root`, exit with usage error before any network/browser action. |
| `--root DIR` | path; default `None`; not repeatable | Apply/dry-run root passed to `apply_patch`; never inferred from cwd and required for `--apply` and `--dry-run`. |
| `--channel {real,mock}` | enum; default `real`; not repeatable | Browser channel passed to `ask_chatgpt`; automated tests must use `mock` with loopback `--base-url`. |
| `--base-url URL` | URL string; default `None`; not repeatable | Base URL passed through for mock/local fixtures. |
| `--profile-path PATH` | path; default `None`; not repeatable | Browser profile path passed through; the CLI must never inspect credentials, cookies, or profile contents. |
| `--timeout SECONDS` | float; default `30.0`; not repeatable | Completion timeout passed as `timeout_s`. |

No-mutation default: absent `--apply`, the CLI never calls `apply_patch(..., dry_run=False)`. `--dry-run` calls `apply_patch(..., dry_run=True)` and writes no patch changes. `--apply` without explicit `--root` is a usage error, not a fallback to cwd. `--apply` and `--dry-run` are mutually exclusive; `--dry-run` is not an alias for default ask mode.

Stdout/stderr conventions: default ask mode writes assistant response text, and only that text, to stdout unless `--out` is set; diagnostics and progress go to stderr. In `--apply` or `--dry-run` mode, stdout is a stable JSON object matching `DiffSummary`; assistant text is written only if `--out` is set. All errors write one concise diagnostic to stderr and never print credentials, cookies, session tokens, or browser-profile contents.

Exit-code convention:

| Exit | Failure class |
|---:|---|
| `0` | Success. |
| `2` | CLI usage error: bad flags, both prompt forms, missing prompt, invalid `--model-settings`, `--apply`/`--dry-run` without `--root`, or mutually exclusive flags. |
| `3` | `LoginRequiredError`. |
| `4` | `SessionNotFoundError`. |
| `5` | `ModelUnavailableError`. |
| `6` | `RateLimitedError`. |
| `7` | `ResponseTruncatedError`. |
| `8` | `SelectorUnavailableError`. |
| `9` | `UploadUnsupportedError`. |
| `10` | `DownloadUnsupportedError`. |
| `11` | Proposed UC2 `PatchBundleValidationError` for manifest/hash/byte/path rejection before mutation. |
| `12` | Proposed UC2 `PatchApplyError` for apply I/O failures after validation. |
| `1` | Other `AskChatGPTError` or unexpected uncaught failure after emitting a safe diagnostic. |

## Library-vs-CLI responsibility split

Library responsibilities: bundle construction, README/catalog generation, browser upload/download, prompt/response handling, patch-bundle representation, validation-before-mutate, diff computation, and patch application. The public library API must provide every behavior the CLI exposes.

CLI responsibilities: parse arguments, reject invalid flag combinations before side effects, call `ask_chatgpt(...)` and `apply_patch(...)`, format stdout/stderr, and translate exceptions to exit codes. Avoid putting bundle walking, manifest validation, zip-slip checks, symlink checks, diff computation, or file writes in `ask_chatgpt.cli`.

## Open questions for synthesis

1. Should UC2 add an explicit send-side `bundle_root`/`input_root` to make archive-relative paths deterministic, or should path relativization be owned entirely by the bundle/integrity design?
2. Should `PatchBundle` be bytes-backed as above, path-backed for large bundles, or opaque with both implementations hidden behind the same public type?
3. Should the CLI add `--patch-out FILE` and/or `--bundle FILE` for a two-step save/apply workflow, or is the first UC3 surface limited to same-invocation `--dry-run`/`--apply`?
4. Should `PatchBundleValidationError` and `PatchApplyError` be added to `errors.py`, or should integrity failures collapse into existing `AskChatGPTError` subclasses?

END_TIMESTAMP: 2026-06-12T02:07:54-05:00
T1c-STATUS: DONE
