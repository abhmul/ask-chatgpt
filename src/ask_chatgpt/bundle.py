"""Outgoing bundle construction, catalogue generation, prompt instructions, and upload."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PureWindowsPath
import stat
import time
from typing import Any
import zipfile

from playwright.sync_api import Error as PlaywrightError

from ask_chatgpt.errors import (
    AskChatGPTError,
    BundleIntegrityError,
    OversizedPayloadError,
    PathEscapeError,
    SelectorUnavailableError,
    UploadUnsupportedError,
)

ASK_CHATGPT_BUNDLE_README = "ASK_CHATGPT_BUNDLE_README.md"
UPLOAD_BUNDLE_MAX_FILE_BYTES = 5 * 1024 * 1024
UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES = 50 * 1024 * 1024
UPLOAD_BUNDLE_MAX_ZIP_BYTES = 25 * 1024 * 1024
UPLOAD_BUNDLE_MAX_FILE_COUNT = 1000

_CREATED_AT_ISO8601 = "1970-01-01T00:00:00Z"
_ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_UPLOAD_STATUS_SELECTOR = '[data-testid="mock-upload-status"]'

Pathish = str | os.PathLike[str]


@dataclass(frozen=True, slots=True)
class UploadBundleCaps:
    """Build-time caps for outgoing upload bundles."""

    max_file_bytes: int = UPLOAD_BUNDLE_MAX_FILE_BYTES
    max_total_file_bytes: int = UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES
    max_zip_bytes: int = UPLOAD_BUNDLE_MAX_ZIP_BYTES
    max_file_count: int = UPLOAD_BUNDLE_MAX_FILE_COUNT


@dataclass(frozen=True, slots=True)
class BundleEntry:
    """Inventory metadata for one included project file."""

    path: str
    kind: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class OutgoingBundle:
    """A deterministic outgoing bundle zip ready for UI upload."""

    filename: str
    content: bytes
    sha256: str
    byte_count: int
    readme: str
    entries: tuple[BundleEntry, ...]
    bundle_id: str
    project_root_name: str
    created_at_iso8601: str


@dataclass(frozen=True, slots=True)
class UploadConfirmation:
    """Credential-free upload confirmation returned by the mock affordance."""

    filename: str
    size: int
    sha256: str
    content_type: str
    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class _PreparedEntry:
    path: str
    data: bytes
    public: BundleEntry


_CATALOGUE_TEMPLATE = """# ask-chatgpt bundle instructions

Read this file first. This zip is a project-context bundle prepared by `ask-chatgpt` so you can answer the user using local files and, if needed, return edits as a machine-readable patch bundle.

## Project root and path rules

The archive root represents the project root named `{{PROJECT_ROOT_NAME}}`. Every project file path below is repo-root-relative. Use forward slashes only. Never use absolute paths, drive letters, leading `/`, backslashes, empty path segments, or `..`. Treat paths as case-sensitive. Patch bundles may contain only regular file entries plus `manifest.json`; do not create symlinks or special files.

## Bundle identity

- Bundle id: `{{BUNDLE_ID}}`
- Created at: `{{CREATED_AT_ISO8601}}`
- Project root display name: `{{PROJECT_ROOT_NAME}}`
- Included file count: `{{FILE_COUNT}}`
- Included payload bytes: `{{TOTAL_BYTES}}`

## Included file inventory

Directories supplied by the caller were expanded recursively. The table lists every included project file; empty directories are not represented. `Path` is the canonical path to use in discussion and patch bundles. `Zip entry` is where the file appears inside this archive. `Kind` is `text` or `binary` by conservative local detection. `Size` is decimal bytes. `SHA-256` is lowercase hex of the included file bytes.

| Path | Zip entry | Kind | Size bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
{{INVENTORY_ROWS}}

Inventory row template:

| `src/example.py` | `src/example.py` | text | 1234 | `0123456789abcdef...` |

If a file you need is not in this inventory, say what is missing in your ordinary answer. Do not invent unseen file contents. You may create a new repo-root-relative file when the user task clearly requires it.

## If no edits are needed

If the correct response requires no file changes, reply exactly:

```text
NO_CHANGES_NEEDED
```

Do not attach a zip and do not emit a fenced patch bundle in that case.

## If edits are needed: return a patch bundle, not the whole tree

Return exactly one patch bundle containing only changed/deleted paths and `manifest.json`. Do not include unchanged files. Do not include this instruction file. Do not include the whole project tree.

Example: if you change `src/app.py`, add `tests/test_app.py`, delete `docs/obsolete.md`, and leave `README.md` unchanged, the patch zip must contain:

```text
manifest.json
src/app.py
tests/test_app.py
```

It must not contain `README.md`, `docs/obsolete.md`, or `ASK_CHATGPT_BUNDLE_README.md`.

## Patch zip manifest

Every patch zip must contain one top-level `manifest.json` encoded as UTF-8 JSON. Use this schema, keeping the fixture-compatible fields `version`, `files`, `total_byte_count`, `path`, `size`, `sha256`, and `status`:

```json
{
  "version": 1,
  "files": [
    {"path": "src/existing.py", "status": "changed", "operation": "modified", "size": 1200, "sha256": "<sha256-of-new-bytes>"},
    {"path": "src/new_file.py", "status": "changed", "operation": "added", "size": 300, "sha256": "<sha256-of-new-bytes>"},
    {"path": "docs/obsolete.md", "status": "deleted", "operation": "deleted", "size": 0, "sha256": null}
  ],
  "total_byte_count": 1500
}
```

For added and modified files, include the new file bytes in the zip at exactly `path`, set `status` to `changed`, set `operation` to `added` or `modified`, set `size` to the byte length, and set `sha256` to the lowercase SHA-256 of the included bytes. For deleted files, do not include a file payload, set `status` and `operation` to `deleted`, set `size` to `0`, and set `sha256` to `null`. `total_byte_count` is the sum of byte sizes for added and modified payloads; deletions contribute zero. Do not use `status: "unchanged"` in real patch bundles.

## Response channel priority

Primary/preferred: produce a downloadable `.zip` file named `patch-bundle.zip` containing the patch zip described above. If you provide a downloadable zip, do not also emit the fallback text block. In the chat message body, write only:

```text
PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip
```

Fallback: if you cannot produce a downloadable `.zip`, emit the same zip bytes as one base64url marker block. The marker block must be the only patch bundle in the response. Do not wrap it in Markdown triple backticks; the `BEGIN_PATCH_BUNDLE` and `END_PATCH_BUNDLE` lines are the fence. Do not put commentary inside the block. Use unpadded base64url (`A-Z`, `a-z`, `0-9`, `-`, `_`), preferably on one line.

Exact fallback format:

```text
BEGIN_PATCH_BUNDLE
MANIFEST_JSON: {"files":[{"operation":"modified","path":"src/example.py","sha256":"<sha256-of-new-bytes>","size":123,"status":"changed"}],"total_byte_count":123,"version":1,"zip_byte_count":456,"zip_sha256":"<sha256-of-zip-bytes>"}
ZIP_BYTE_COUNT: 456
ZIP_SHA256: <sha256-of-zip-bytes>
BASE64URL:
<unpadded-base64url-of-the-zip-bytes>
END_PATCH_BUNDLE
```

`MANIFEST_JSON` must be compact JSON on the same line. Its `zip_byte_count` and `zip_sha256` must match `ZIP_BYTE_COUNT`, `ZIP_SHA256`, and the decoded zip bytes. Emit exactly one `BEGIN_PATCH_BUNDLE` and exactly one `END_PATCH_BUNDLE`.
"""

_PROMPT_INSTRUCTIONS_TEMPLATE = """I uploaded a zip project-context bundle named `{{BUNDLE_FILENAME}}`. First read `ASK_CHATGPT_BUNDLE_README.md` inside the zip. Then complete this task:

{{USER_TASK}}

If no file edits are needed, reply exactly `NO_CHANGES_NEEDED` and nothing else.

If file edits are needed, return exactly one patch bundle. The patch bundle must contain only `manifest.json` plus added or modified file payloads at repo-root-relative paths, with deleted files represented only in `manifest.json`. Do not return the whole tree. Do not include unchanged files. Do not include absolute paths, `..`, backslashes, symlinks, or files outside the project root.

Preferred response channel: attach or produce a downloadable zip named `patch-bundle.zip`. In the message body, write only `PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip`. Do not also include the base64 fallback if a downloadable zip is available.

Fallback response channel, only if no downloadable zip can be produced: emit exactly this marker-block shape and no other patch bundle. Do not wrap it in triple backticks. Do not add commentary inside the block.

BEGIN_PATCH_BUNDLE
MANIFEST_JSON: {"files":[{"operation":"modified","path":"src/example.py","sha256":"<sha256-of-new-bytes>","size":123,"status":"changed"}],"total_byte_count":123,"version":1,"zip_byte_count":456,"zip_sha256":"<sha256-of-zip-bytes>"}
ZIP_BYTE_COUNT: 456
ZIP_SHA256: <sha256-of-zip-bytes>
BASE64URL:
<unpadded-base64url-of-the-zip-bytes>
END_PATCH_BUNDLE

For added files use `status: "changed"` and `operation: "added"`; for modified files use `status: "changed"` and `operation: "modified"`; for deletions use `status: "deleted"`, `operation: "deleted"`, `size: 0`, `sha256: null`, and omit the deleted file payload from the zip. Compute sizes and hashes from the actual bytes in the patch zip. Emit exactly one bundle per response.
"""


def build_bundle(
    files: Sequence[Pathish] | Pathish | None = None,
    dirs: Sequence[Pathish] | Pathish | None = None,
    *,
    root: Pathish | None = None,
    caps: UploadBundleCaps | None = None,
) -> OutgoingBundle:
    """Build a deterministic outgoing bundle zip from regular files under ``root``."""

    resolved_caps = caps or UploadBundleCaps()
    _validate_caps(resolved_caps)
    root_real = _resolve_root(root)
    selected = _select_regular_files(root_real, _as_path_list(files), _as_path_list(dirs))
    if len(selected) > resolved_caps.max_file_count:
        raise OversizedPayloadError(
            f"UPLOAD_BUNDLE_MAX_FILE_COUNT exceeded: {len(selected)} > {resolved_caps.max_file_count}"
        )

    prepared = _read_prepared_entries(root_real, selected, resolved_caps)
    public_entries = tuple(entry.public for entry in prepared)
    total_bytes = sum(entry.size for entry in public_entries)
    project_root_name = root_real.name or str(root_real)
    bundle_id = _derive_bundle_id(project_root_name, public_entries)
    readme = generate_catalogue_readme(
        public_entries,
        project_root_name=project_root_name,
        bundle_id=bundle_id,
        created_at_iso8601=_CREATED_AT_ISO8601,
    )
    zip_bytes = _write_zip(readme, prepared)
    if len(zip_bytes) > resolved_caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"UPLOAD_BUNDLE_MAX_ZIP_BYTES exceeded: {len(zip_bytes)} > {resolved_caps.max_zip_bytes}"
        )
    digest = sha256(zip_bytes).hexdigest()
    return OutgoingBundle(
        filename=f"ask-chatgpt-bundle-{bundle_id[:16]}.zip",
        content=zip_bytes,
        sha256=digest,
        byte_count=len(zip_bytes),
        readme=readme,
        entries=public_entries,
        bundle_id=bundle_id,
        project_root_name=project_root_name,
        created_at_iso8601=_CREATED_AT_ISO8601,
    )


def generate_catalogue_readme(
    entries: Sequence[BundleEntry],
    *,
    project_root_name: str,
    bundle_id: str,
    created_at_iso8601: str = _CREATED_AT_ISO8601,
) -> str:
    """Generate the protocol catalogue README for the supplied inventory."""

    sorted_entries = tuple(sorted(entries, key=lambda entry: entry.path))
    rows = "\n".join(
        f"| `{entry.path}` | `{entry.path}` | {entry.kind} | {entry.size} | `{entry.sha256}` |"
        for entry in sorted_entries
    )
    total_bytes = sum(entry.size for entry in sorted_entries)
    return (
        _CATALOGUE_TEMPLATE.replace("{{PROJECT_ROOT_NAME}}", str(project_root_name))
        .replace("{{BUNDLE_ID}}", str(bundle_id))
        .replace("{{CREATED_AT_ISO8601}}", str(created_at_iso8601))
        .replace("{{FILE_COUNT}}", str(len(sorted_entries)))
        .replace("{{TOTAL_BYTES}}", str(total_bytes))
        .replace("{{INVENTORY_ROWS}}", rows)
    )


def generate_prompt_instructions(user_task: str, *, bundle_filename: str) -> str:
    """Generate the imperative prompt text sent alongside the uploaded zip."""

    return _PROMPT_INSTRUCTIONS_TEMPLATE.replace("{{BUNDLE_FILENAME}}", str(bundle_filename)).replace(
        "{{USER_TASK}}", str(user_task)
    )


def upload_bundle(
    session: Any,
    bundle: OutgoingBundle | bytes,
    *,
    filename: str | None = None,
    caps: UploadBundleCaps | None = None,
    timeout_s: float = 5.0,
) -> UploadConfirmation:
    """Upload an outgoing bundle through a started ``BrowserSession`` upload input."""

    resolved_caps = caps or UploadBundleCaps()
    _validate_caps(resolved_caps)
    content, upload_name, expected_sha = _coerce_upload_payload(bundle, filename=filename)
    if len(content) > resolved_caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"UPLOAD_BUNDLE_MAX_ZIP_BYTES exceeded before upload: {len(content)} > {resolved_caps.max_zip_bytes}"
        )
    page = getattr(session, "page", None)
    if page is None:
        raise UploadUnsupportedError("browser session is not started; upload basename unavailable")
    try:
        selector = session.selectors.selector("upload_input")
    except (AttributeError, SelectorUnavailableError) as exc:
        raise UploadUnsupportedError("selector 'upload_input' unavailable for upload") from exc

    try:
        upload_input = page.locator(selector)
        if upload_input.count() < 1:
            raise UploadUnsupportedError(f"upload input absent; upload basename={upload_name}")
        upload_input.first.set_input_files(
            {"name": upload_name, "mimeType": "application/zip", "buffer": content},
            timeout=_timeout_ms(timeout_s),
        )
    except UploadUnsupportedError:
        raise
    except PlaywrightError as exc:
        raise UploadUnsupportedError(f"upload input rejected file; upload basename={upload_name}") from exc

    status, reason = _wait_for_upload_status(page, timeout_s=timeout_s)
    if status == "ok":
        return UploadConfirmation(
            filename=upload_name,
            size=len(content),
            sha256=expected_sha,
            content_type="application/zip",
            status="ok",
            reason=reason,
        )
    if status == "rejected":
        detail = f"reason={reason or 'file size/type rejected by UI'}; upload basename={upload_name}"
        raise UploadUnsupportedError(detail)
    if status == "corrupt":
        detail = f"upload SHA-256 mismatch for upload basename={upload_name}; expected_sha256={expected_sha}"
        raise BundleIntegrityError(detail)
    if status == "unsupported":
        raise UploadUnsupportedError(f"upload unsupported; upload basename={upload_name}")
    raise UploadUnsupportedError(f"unexpected upload status={status!r}; upload basename={upload_name}")


def _as_path_list(value: Sequence[Pathish] | Pathish | None) -> tuple[Pathish, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, os.PathLike)):
        return (value,)  # type: ignore[return-value]
    return tuple(value)


def _validate_caps(caps: UploadBundleCaps) -> None:
    fields = {
        "UPLOAD_BUNDLE_MAX_FILE_BYTES": caps.max_file_bytes,
        "UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES": caps.max_total_file_bytes,
        "UPLOAD_BUNDLE_MAX_ZIP_BYTES": caps.max_zip_bytes,
        "UPLOAD_BUNDLE_MAX_FILE_COUNT": caps.max_file_count,
    }
    for name, value in fields.items():
        if not isinstance(value, int) or value < 0:
            raise OversizedPayloadError(f"{name} must be a non-negative integer")


def _resolve_root(root: Pathish | None) -> Path:
    raw_root = Path.cwd() if root is None else Path(os.fspath(root))
    try:
        root_real = raw_root.resolve(strict=True)
    except OSError as exc:
        raise PathEscapeError("bundle root must exist and be readable") from exc
    if not root_real.is_dir():
        raise PathEscapeError("bundle root must be a directory")
    return root_real


def _select_regular_files(root_real: Path, files: tuple[Pathish, ...], dirs: tuple[Pathish, ...]) -> dict[str, Path]:
    selected: dict[str, Path] = {}
    for file_value in files:
        rel = _validate_input_path(file_value)
        path, st_mode = _resolve_existing_under_root(root_real, rel)
        if stat.S_ISDIR(st_mode):
            raise OversizedPayloadError(f"selected file path is not a regular file: {rel}")
        if not stat.S_ISREG(st_mode):
            raise OversizedPayloadError(f"selected path is not a regular file: {rel}")
        _add_selected(selected, rel, path)
    for dir_value in dirs:
        rel = _validate_input_path(dir_value)
        path, st_mode = _resolve_existing_under_root(root_real, rel)
        if not stat.S_ISDIR(st_mode):
            raise OversizedPayloadError(f"selected directory path is not a directory: {rel}")
        for child_rel, child_path in _walk_regular_files(root_real, path):
            _add_selected(selected, child_rel, child_path)
    return dict(sorted(selected.items()))


def validate_posix_relative_path(
    value: Pathish,
    *,
    reserved_paths: Iterable[str] = (),
    reserved_prefixes: Iterable[str] = (),
) -> str:
    """Validate and normalize one repo-root-relative POSIX path.

    This is the single lexical path-safety helper shared by outgoing bundles and incoming patch bundles. It intentionally performs only lexical checks; callers that touch the filesystem must additionally enforce realpath containment and no-follow symlink rules for their root.
    """

    try:
        raw = os.fspath(value)
    except TypeError as exc:
        raise PathEscapeError("path value must be a string or path-like object") from exc
    if isinstance(raw, bytes):
        raise PathEscapeError("bytes paths are rejected; use a repo-root-relative text path")
    text = str(raw)
    if text == "":
        raise PathEscapeError("empty paths are rejected")
    if "\x00" in text:
        raise PathEscapeError("NUL bytes are rejected in bundle paths")
    if "\\" in text:
        raise PathEscapeError("backslashes are rejected in bundle paths")
    if Path(text).is_absolute() or PureWindowsPath(text).drive:
        raise PathEscapeError("absolute paths and drive/UNC paths are rejected")
    parts = text.split("/")
    if any(part == "" or part == "." for part in parts):
        raise PathEscapeError("empty or '.' path segments are rejected")
    if any(part == ".." for part in parts):
        raise PathEscapeError("path traversal '..' is rejected")
    normalized = "/".join(parts)
    reserved_path_set = {str(path) for path in reserved_paths}
    if normalized in reserved_path_set:
        raise PathEscapeError(f"reserved metadata path collision: {normalized}")
    for prefix in reserved_prefixes:
        clean_prefix = str(prefix).rstrip("/")
        if normalized == clean_prefix or normalized.startswith(clean_prefix + "/"):
            raise PathEscapeError(f"reserved metadata path collision: {normalized}")
    return normalized


def _validate_input_path(value: Pathish) -> str:
    return validate_posix_relative_path(value)


def _validate_archive_path(rel: str) -> str:
    return validate_posix_relative_path(rel, reserved_paths=(ASK_CHATGPT_BUNDLE_README,))


def _resolve_existing_under_root(root_real: Path, rel: str) -> tuple[Path, int]:
    parts = rel.split("/")
    current = root_real
    for index, part in enumerate(parts):
        candidate = current / part
        try:
            st = candidate.lstat()
        except OSError as exc:
            raise PathEscapeError(f"selected path is unavailable under bundle root: {rel}") from exc
        if stat.S_ISLNK(st.st_mode):
            raise PathEscapeError(f"symlink path component rejected: {rel}")
        if index < len(parts) - 1:
            if not stat.S_ISDIR(st.st_mode):
                raise PathEscapeError(f"non-directory parent component rejected: {rel}")
            current = candidate
            continue
        if not _is_contained(root_real, candidate):
            raise PathEscapeError(f"path escapes bundle root: {rel}")
        return candidate, st.st_mode
    raise PathEscapeError("empty paths are rejected")


def _walk_regular_files(root_real: Path, directory: Path) -> Iterable[tuple[str, Path]]:
    def onerror(error: OSError) -> None:
        raise AskChatGPTError("Directory traversal failed while building upload bundle. Operator action: inspect permissions and retry.") from error

    for dirpath_text, dirnames, filenames in os.walk(directory, topdown=True, followlinks=False, onerror=onerror):
        dirpath = Path(dirpath_text)
        for dirname in sorted(tuple(dirnames)):
            child = dirpath / dirname
            try:
                mode = child.lstat().st_mode
            except OSError as exc:
                raise PathEscapeError(f"directory entry became unavailable: {_safe_rel(root_real, child)}") from exc
            rel = _safe_rel(root_real, child)
            _validate_archive_path(rel)
            if stat.S_ISLNK(mode):
                raise PathEscapeError(f"symlink directory rejected: {rel}")
            if not stat.S_ISDIR(mode):
                raise OversizedPayloadError(f"directory entry is not a regular file or directory: {rel}")
        dirnames.sort()
        for filename in sorted(filenames):
            child = dirpath / filename
            try:
                mode = child.lstat().st_mode
            except OSError as exc:
                raise PathEscapeError(f"file entry became unavailable: {_safe_rel(root_real, child)}") from exc
            rel = _safe_rel(root_real, child)
            rel = _validate_archive_path(rel)
            if stat.S_ISLNK(mode):
                raise PathEscapeError(f"symlink file rejected: {rel}")
            if not stat.S_ISREG(mode):
                raise OversizedPayloadError(f"directory entry is not a regular file: {rel}")
            if not _is_contained(root_real, child):
                raise PathEscapeError(f"path escapes bundle root: {rel}")
            yield rel, child


def _safe_rel(root_real: Path, path: Path) -> str:
    try:
        return path.relative_to(root_real).as_posix()
    except ValueError as exc:
        raise PathEscapeError("path escapes bundle root") from exc


def _is_contained(root_real: Path, path: Path) -> bool:
    try:
        return os.path.commonpath([str(root_real), str(path)]) == str(root_real)
    except ValueError:
        return False


def _add_selected(selected: dict[str, Path], rel: str, path: Path) -> None:
    rel = _validate_archive_path(rel)
    if rel in selected:
        raise PathEscapeError(f"duplicate normalized path in upload bundle: {rel}")
    selected[rel] = path


def _read_prepared_entries(root_real: Path, selected: dict[str, Path], caps: UploadBundleCaps) -> tuple[_PreparedEntry, ...]:
    preflight: list[tuple[str, Path, int]] = []
    total_size = 0
    for rel, path in sorted(selected.items()):
        try:
            st = path.lstat()
        except OSError as exc:
            raise PathEscapeError(f"selected path became unavailable: {rel}") from exc
        if stat.S_ISLNK(st.st_mode):
            raise PathEscapeError(f"symlink file rejected: {rel}")
        if not stat.S_ISREG(st.st_mode):
            raise OversizedPayloadError(f"selected path is not a regular file: {rel}")
        if not _is_contained(root_real, path):
            raise PathEscapeError(f"path escapes bundle root: {rel}")
        size = int(st.st_size)
        if size > caps.max_file_bytes:
            raise OversizedPayloadError(f"UPLOAD_BUNDLE_MAX_FILE_BYTES exceeded for {rel}: {size} > {caps.max_file_bytes}")
        total_size += size
        if total_size > caps.max_total_file_bytes:
            raise OversizedPayloadError(
                f"UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES exceeded: {total_size} > {caps.max_total_file_bytes}"
            )
        preflight.append((rel, path, size))

    entries: list[_PreparedEntry] = []
    actual_total_size = 0
    for rel, path, expected_size in preflight:
        try:
            with path.open("rb") as handle:
                data = handle.read(caps.max_file_bytes + 1)
        except OSError as exc:
            raise AskChatGPTError(f"Selected file could not be read: {rel}") from exc
        if len(data) > caps.max_file_bytes:
            raise OversizedPayloadError(f"UPLOAD_BUNDLE_MAX_FILE_BYTES exceeded while reading {rel}")
        actual_total_size += len(data)
        if actual_total_size > caps.max_total_file_bytes:
            raise OversizedPayloadError(
                f"UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES exceeded while reading: {actual_total_size} > {caps.max_total_file_bytes}"
            )
        size = len(data) if len(data) != expected_size else expected_size
        digest = sha256(data).hexdigest()
        public = BundleEntry(path=rel, kind=_detect_kind(data), size=size, sha256=digest)
        entries.append(_PreparedEntry(path=rel, data=data, public=public))
    return tuple(entries)


def _detect_kind(data: bytes) -> str:
    if b"\x00" in data:
        return "binary"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "binary"
    return "text"


def _derive_bundle_id(project_root_name: str, entries: Sequence[BundleEntry]) -> str:
    payload = {
        "created_at": _CREATED_AT_ISO8601,
        "files": [
            {"kind": entry.kind, "path": entry.path, "sha256": entry.sha256, "size": entry.size}
            for entry in sorted(entries, key=lambda item: item.path)
        ],
        "project_root_name": project_root_name,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _write_zip(readme: str, entries: Sequence[_PreparedEntry]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(_zip_info(ASK_CHATGPT_BUNDLE_README), readme.encode("utf-8"))
        for entry in sorted(entries, key=lambda item: item.path):
            archive.writestr(_zip_info(entry.path), entry.data)
    return buffer.getvalue()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_ZIP_DATE_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def _coerce_upload_payload(bundle: OutgoingBundle | bytes, *, filename: str | None) -> tuple[bytes, str, str]:
    if isinstance(bundle, OutgoingBundle):
        content = bundle.content
        upload_name = filename or bundle.filename
        expected_sha = bundle.sha256
    else:
        content = bytes(bundle)
        upload_name = filename or "ask-chatgpt-bundle.zip"
        expected_sha = sha256(content).hexdigest()
    if "/" in upload_name or "\\" in upload_name or upload_name in {"", ".", ".."}:
        raise PathEscapeError("upload filename must be a safe basename")
    if not upload_name.lower().endswith(".zip"):
        raise UploadUnsupportedError("upload filename must end with .zip")
    return content, upload_name, expected_sha


def _timeout_ms(timeout_s: float) -> int:
    return max(0, int(float(timeout_s) * 1000))


def _wait_for_upload_status(page: Any, *, timeout_s: float) -> tuple[str, str | None]:
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    last_error: Exception | None = None
    while True:
        try:
            status_locator = page.locator(_UPLOAD_STATUS_SELECTOR).first
            if status_locator.count() > 0:
                status = status_locator.get_attribute("data-upload-status", timeout=250) or ""
                reason = status_locator.get_attribute("data-reason", timeout=250)
                if status and status != "idle":
                    return status, reason
        except PlaywrightError as exc:
            last_error = exc
        if time.monotonic() >= deadline:
            detail = "upload did not confirm before timeout"
            if last_error is not None:
                detail += "; status locator unavailable"
            raise UploadUnsupportedError(detail)
        page.wait_for_timeout(50)


__all__ = [
    "ASK_CHATGPT_BUNDLE_README",
    "UPLOAD_BUNDLE_MAX_FILE_BYTES",
    "UPLOAD_BUNDLE_MAX_TOTAL_FILE_BYTES",
    "UPLOAD_BUNDLE_MAX_ZIP_BYTES",
    "UPLOAD_BUNDLE_MAX_FILE_COUNT",
    "UploadBundleCaps",
    "BundleEntry",
    "OutgoingBundle",
    "UploadConfirmation",
    "build_bundle",
    "generate_catalogue_readme",
    "generate_prompt_instructions",
    "upload_bundle",
    "validate_posix_relative_path",
]
