"""Patch-bundle retrieval, validation, diffing, and zip-slip-safe application."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import time
from typing import Any, Literal
import uuid
import zipfile
import zlib

from playwright.sync_api import Error as PlaywrightError, Locator, TimeoutError as PlaywrightTimeoutError

from ask_chatgpt.bundle import ASK_CHATGPT_BUNDLE_README, validate_posix_relative_path
from ask_chatgpt.errors import (
    AskChatGPTError,
    BundleIntegrityError,
    DownloadUnsupportedError,
    OversizedPayloadError,
    PatchApplyError,
    PatchMalformedError,
    PathEscapeError,
    ResponseTruncatedError,
    SelectorUnavailableError,
)
from ask_chatgpt.readers import ResponseReader, read_response

PATCH_BUNDLE_MAX_ZIP_BYTES = 25 * 1024 * 1024
PATCH_BUNDLE_MAX_FILE_BYTES = 5 * 1024 * 1024
PATCH_BUNDLE_MAX_EXPANDED_BYTES = 50 * 1024 * 1024
PATCH_MANIFEST_MAX_BYTES = 1024 * 1024
PATCH_BUNDLE_MAX_FILE_COUNT = 1000
PATCH_BUNDLE_MAX_BASE64URL_CHARS = math.ceil(PATCH_BUNDLE_MAX_ZIP_BYTES * 4 / 3) + 4

Pathish = str | Path
PatchSource = Literal["download", "fenced"]
ChangeKind = Literal["added", "modified", "deleted"]

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL_RE = re.compile(r"^[0-9]+$")
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]*$")
_BEGIN_PATCH_BUNDLE = "BEGIN_PATCH_BUNDLE"
_END_PATCH_BUNDLE = "END_PATCH_BUNDLE"
_MANIFEST_LINE_PREFIX = "MANIFEST_JSON:"
_ZIP_BYTE_COUNT_PREFIX = "ZIP_BYTE_COUNT:"
_ZIP_SHA256_PREFIX = "ZIP_SHA256:"
_BASE64URL_LINE = "BASE64URL:"
_PATCH_RESERVED_PATHS = ("manifest.json", ASK_CHATGPT_BUNDLE_README)
_PATCH_RESERVED_PREFIXES = (".ask-chatgpt-tmp", "manifest.json", ASK_CHATGPT_BUNDLE_README)
_DOWNLOAD_DELAYED_SELECTOR = '[data-testid="download-delayed"]'
_DOWNLOAD_UNSUPPORTED_SELECTOR = '[data-testid="download-unsupported"]'
_TRANSACTION_DIRNAME = ".ask-chatgpt-tmp"
_JOURNAL_NAME = "journal.json"


@dataclass(frozen=True, slots=True)
class PatchBundleCaps:
    """Validation and retrieval caps for incoming patch bundles."""

    max_zip_bytes: int = PATCH_BUNDLE_MAX_ZIP_BYTES
    max_file_bytes: int = PATCH_BUNDLE_MAX_FILE_BYTES
    max_expanded_bytes: int = PATCH_BUNDLE_MAX_EXPANDED_BYTES
    max_manifest_bytes: int = PATCH_MANIFEST_MAX_BYTES
    max_file_count: int = PATCH_BUNDLE_MAX_FILE_COUNT
    max_base64url_chars: int | None = None

    @property
    def resolved_max_base64url_chars(self) -> int:
        if self.max_base64url_chars is not None:
            return self.max_base64url_chars
        return math.ceil(self.max_zip_bytes * 4 / 3) + 4


@dataclass(frozen=True, slots=True)
class PatchBundle:
    filename: str
    content: bytes
    sha256: str
    byte_count: int
    source: PatchSource


PatchBundleSource = PatchBundle | bytes | str | Path


@dataclass(frozen=True, slots=True)
class FileDiff:
    path: str
    change_kind: ChangeKind
    old_sha256: str | None
    new_sha256: str | None
    old_bytes: int | None
    new_bytes: int | None
    byte_delta: int
    lines_added: int | None
    lines_deleted: int | None


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
    total_bytes_changed: int


@dataclass(frozen=True, slots=True)
class _DownloadCandidate:
    locator: Locator
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _DownloadScan:
    candidate: _DownloadCandidate | None
    stale_artifact_seen: bool
    delayed: bool
    unsupported: bool


@dataclass(frozen=True, slots=True)
class _FencedParseResult:
    zip_bytes: bytes
    manifest: dict[str, Any]
    byte_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _PatchFile:
    path: str
    status: Literal["changed", "deleted"]
    operation: str | None
    size: int
    sha256: str | None
    data: bytes | None = None


@dataclass(frozen=True, slots=True)
class _ValidatedPatch:
    filename: str
    content: bytes
    sha256: str
    byte_count: int
    source: PatchSource | Literal["raw", "path"]
    manifest: dict[str, Any]
    files: tuple[_PatchFile, ...]


@dataclass(frozen=True, slots=True)
class _TargetPlan:
    entry: _PatchFile
    target: Path
    existed: bool
    old_sha256: str | None
    old_bytes: int | None
    old_data: bytes | None


@dataclass(frozen=True, slots=True)
class _PreparedApply:
    summary: DiffSummary
    plans: tuple[_TargetPlan, ...]


def retrieve_patch_bundle(
    session: Any,
    *,
    timeout_s: float = 5.0,
    download_wait_s: float = 1.0,
    caps: PatchBundleCaps | None = None,
    reader_order: Sequence[ResponseReader] | None = None,
) -> tuple[bytes, PatchBundle] | None:
    """Retrieve and validate the latest-turn patch bundle from download primary or fenced fallback."""

    resolved_caps = _validate_caps(caps or PatchBundleCaps())
    page = getattr(session, "page", None)
    selectors = getattr(session, "selectors", None)
    if page is None or selectors is None:
        raise DownloadUnsupportedError("browser session is not started; no local files were changed")

    turn = _latest_completed_turn(session, timeout_s=timeout_s)
    stale_artifact_seen = False
    unsupported_seen = False
    deadline = time.monotonic() + max(0.0, float(download_wait_s))

    while True:
        scan = _scan_download_artifacts(turn, selectors)
        stale_artifact_seen = stale_artifact_seen or scan.stale_artifact_seen
        unsupported_seen = unsupported_seen or scan.unsupported
        if scan.candidate is not None:
            zip_bytes, bundle = _download_candidate_bytes(page, scan.candidate, resolved_caps, timeout_s=timeout_s)
            _validate_zip_bytes(
                zip_bytes,
                filename=bundle.filename,
                source=bundle.source,
                expected_byte_count=bundle.byte_count,
                expected_sha256=bundle.sha256,
                caps=resolved_caps,
            )
            return zip_bytes, bundle

        if not scan.delayed or time.monotonic() >= deadline:
            break
        _reload_current_page(page, timeout_s=timeout_s)
        turn = _latest_completed_turn(session, timeout_s=timeout_s)

    text = read_response(turn, page, selectors, order=reader_order)
    if text.strip() == "NO_CHANGES_NEEDED":
        return None
    fenced = _parse_fenced_patch_bundle(text, resolved_caps)
    if fenced is not None:
        bundle = PatchBundle(
            filename="patch-bundle.zip",
            content=fenced.zip_bytes,
            sha256=fenced.sha256,
            byte_count=fenced.byte_count,
            source="fenced",
        )
        _validate_zip_bytes(
            fenced.zip_bytes,
            filename=bundle.filename,
            source=bundle.source,
            expected_byte_count=fenced.byte_count,
            expected_sha256=fenced.sha256,
            caps=resolved_caps,
            expected_fenced_manifest=fenced.manifest,
        )
        return fenced.zip_bytes, bundle

    if stale_artifact_seen:
        raise PatchMalformedError("stale or wrong-turn download artifact was present without a valid latest-turn fallback")
    if unsupported_seen:
        raise DownloadUnsupportedError("download affordance unsupported and no fenced patch-bundle fallback was present")
    raise DownloadUnsupportedError("no eligible latest-turn download artifact and no fenced patch-bundle fallback were present")


def apply_patch(bundle: PatchBundle | bytes | str | Path, root: str | Path, *, dry_run: bool = True) -> DiffSummary:
    """Validate a patch bundle, compute a diff, and optionally apply it under ``root``."""

    caps = _validate_caps(PatchBundleCaps())
    content, filename, source, expected_count, expected_digest = _coerce_patch_source(bundle, caps)
    validated = _validate_zip_bytes(
        content,
        filename=filename,
        source=source,
        expected_byte_count=expected_count,
        expected_sha256=expected_digest,
        caps=caps,
    )
    root_real = _resolve_apply_root(root)
    prepared = _prepare_apply(validated, root_real=root_real, dry_run=bool(dry_run))
    if dry_run:
        return prepared.summary
    _recover_incomplete_transactions(root_real)
    return _apply_transaction(root_real, prepared)


def _validate_caps(caps: PatchBundleCaps) -> PatchBundleCaps:
    fields = {
        "PATCH_BUNDLE_MAX_ZIP_BYTES": caps.max_zip_bytes,
        "PATCH_BUNDLE_MAX_FILE_BYTES": caps.max_file_bytes,
        "PATCH_BUNDLE_MAX_EXPANDED_BYTES": caps.max_expanded_bytes,
        "PATCH_MANIFEST_MAX_BYTES": caps.max_manifest_bytes,
        "PATCH_BUNDLE_MAX_FILE_COUNT": caps.max_file_count,
        "PATCH_BUNDLE_MAX_BASE64URL_CHARS": caps.resolved_max_base64url_chars,
    }
    for name, value in fields.items():
        if not isinstance(value, int) or value < 0:
            raise OversizedPayloadError(f"{name} must be a non-negative integer")
    return caps


def _latest_completed_turn(session: Any, *, timeout_s: float) -> Locator:
    try:
        return session.wait_for_completion(timeout_s=timeout_s)
    except AttributeError as exc:
        raise DownloadUnsupportedError("browser session cannot identify the latest completed assistant turn") from exc


def _scan_download_artifacts(turn: Locator, selectors: Any) -> _DownloadScan:
    try:
        turn_id_attr = selectors.attribute("turn_id")
        latest_turn_id = turn.get_attribute(turn_id_attr)
        if not latest_turn_id:
            raise PatchMalformedError("latest assistant turn is missing a turn id")
        links = turn.locator(selectors.selector("download_artifact"))
        count = links.count()
    except PatchMalformedError:
        raise
    except (PlaywrightError, SelectorUnavailableError) as exc:
        raise DownloadUnsupportedError("download artifact selector unavailable for latest assistant turn") from exc

    stale_artifact_seen = False
    eligible: list[_DownloadCandidate] = []
    filenames: set[str] = set()
    for index in range(count):
        link = links.nth(index)
        source_turn_id = link.get_attribute("data-source-turn-id")
        if not source_turn_id:
            raise PatchMalformedError("download artifact metadata is missing data-source-turn-id")
        if source_turn_id != latest_turn_id:
            stale_artifact_seen = True
            continue
        filename = link.get_attribute("data-filename") or link.get_attribute("download") or "patch-bundle.zip"
        if not _is_safe_download_filename(filename):
            raise PatchMalformedError("download artifact filename metadata is unsafe")
        byte_count_text = link.get_attribute("data-byte-count")
        digest = link.get_attribute("data-sha256")
        if byte_count_text is None or not _DECIMAL_RE.fullmatch(byte_count_text):
            raise PatchMalformedError("download artifact byte-count metadata is malformed")
        if digest is None or not _HEX64_RE.fullmatch(digest):
            raise PatchMalformedError("download artifact SHA-256 metadata is malformed")
        byte_count = int(byte_count_text)
        if filename in filenames:
            raise PatchMalformedError("duplicate latest-turn download artifact filename collision")
        filenames.add(filename)
        eligible.append(_DownloadCandidate(locator=link, filename=filename, byte_count=byte_count, sha256=digest))

    if len(eligible) > 1:
        raise PatchMalformedError("multiple latest-turn download artifacts are ambiguous")

    delayed = _turn_has_selector(turn, _DOWNLOAD_DELAYED_SELECTOR)
    unsupported = _turn_has_selector(turn, _DOWNLOAD_UNSUPPORTED_SELECTOR)
    return _DownloadScan(
        candidate=eligible[0] if eligible else None,
        stale_artifact_seen=stale_artifact_seen,
        delayed=delayed,
        unsupported=unsupported,
    )


def _turn_has_selector(turn: Locator, selector: str) -> bool:
    try:
        return turn.locator(selector).count() > 0
    except PlaywrightError:
        return False


def _is_safe_download_filename(filename: str) -> bool:
    return filename not in {"", ".", ".."} and "/" not in filename and "\\" not in filename


def _download_candidate_bytes(
    page: Any,
    candidate: _DownloadCandidate,
    caps: PatchBundleCaps,
    *,
    timeout_s: float,
) -> tuple[bytes, PatchBundle]:
    if candidate.byte_count > caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by declared download metadata: {candidate.byte_count} > {caps.max_zip_bytes}"
        )
    try:
        with page.expect_download(timeout=_timeout_ms(timeout_s)) as download_info:
            candidate.locator.click(timeout=_timeout_ms(timeout_s))
        download = download_info.value
        failure = download.failure()
        if failure:
            raise DownloadUnsupportedError(f"download failed before validation: {failure}")
        download_path = download.path()
        if download_path is None:
            raise DownloadUnsupportedError("download body path unavailable after capture")
        zip_bytes = Path(download_path).read_bytes()
    except DownloadUnsupportedError:
        raise
    except PlaywrightTimeoutError as exc:
        raise DownloadUnsupportedError("download did not start before the bounded timeout") from exc
    except PlaywrightError as exc:
        raise DownloadUnsupportedError("Playwright download capture failed for the selected artifact") from exc
    except OSError as exc:
        raise DownloadUnsupportedError("download body could not be read after capture") from exc

    if len(zip_bytes) != candidate.byte_count:
        raise BundleIntegrityError(
            f"download byte count mismatch: expected {candidate.byte_count}, got {len(zip_bytes)}"
        )
    digest = sha256(zip_bytes).hexdigest()
    if digest != candidate.sha256:
        raise BundleIntegrityError("download SHA-256 mismatch against artifact metadata")
    bundle = PatchBundle(
        filename=candidate.filename,
        content=zip_bytes,
        sha256=digest,
        byte_count=len(zip_bytes),
        source="download",
    )
    return zip_bytes, bundle


def _reload_current_page(page: Any, *, timeout_s: float) -> None:
    try:
        page.reload(wait_until="load", timeout=_timeout_ms(timeout_s))
    except PlaywrightError as exc:
        raise DownloadUnsupportedError("download artifact polling reload failed") from exc


def _parse_fenced_patch_bundle(text: str, caps: PatchBundleCaps) -> _FencedParseResult | None:
    begin_count = text.count(_BEGIN_PATCH_BUNDLE)
    end_count = text.count(_END_PATCH_BUNDLE)
    if begin_count == 0 and end_count == 0:
        return None
    if begin_count == 1 and end_count == 0:
        raise ResponseTruncatedError("missing END_PATCH_BUNDLE marker in latest assistant turn")
    if begin_count != 1 or end_count != 1:
        raise PatchMalformedError("expected exactly one complete BEGIN_PATCH_BUNDLE/END_PATCH_BUNDLE block")
    try:
        after_begin = text.split(_BEGIN_PATCH_BUNDLE, 1)[1]
        block = after_begin.split(_END_PATCH_BUNDLE, 1)[0]
    except IndexError as exc:
        raise PatchMalformedError("patch-bundle fence markers are malformed") from exc

    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if len(lines) < 5:
        raise PatchMalformedError("fenced patch bundle is missing required lines")
    if not lines[0].startswith(_MANIFEST_LINE_PREFIX):
        raise PatchMalformedError("fenced patch bundle is missing MANIFEST_JSON line")
    if not lines[1].startswith(_ZIP_BYTE_COUNT_PREFIX):
        raise PatchMalformedError("fenced patch bundle is missing ZIP_BYTE_COUNT line")
    if not lines[2].startswith(_ZIP_SHA256_PREFIX):
        raise PatchMalformedError("fenced patch bundle is missing ZIP_SHA256 line")
    if lines[3] != _BASE64URL_LINE:
        raise PatchMalformedError("fenced patch bundle is missing standalone BASE64URL line")

    manifest_text = lines[0].removeprefix(_MANIFEST_LINE_PREFIX).strip()
    if len(manifest_text.encode("utf-8")) > caps.max_manifest_bytes:
        raise OversizedPayloadError(
            f"PATCH_MANIFEST_MAX_BYTES exceeded by fenced MANIFEST_JSON: {len(manifest_text.encode('utf-8'))} > {caps.max_manifest_bytes}"
        )
    byte_count_text = lines[1].removeprefix(_ZIP_BYTE_COUNT_PREFIX).strip()
    if not _DECIMAL_RE.fullmatch(byte_count_text):
        raise PatchMalformedError("fenced ZIP_BYTE_COUNT is not a decimal byte count")
    byte_count = int(byte_count_text)
    digest = lines[2].removeprefix(_ZIP_SHA256_PREFIX).strip()
    if not _HEX64_RE.fullmatch(digest):
        raise PatchMalformedError("fenced ZIP_SHA256 is not lowercase 64-hex")
    encoded = "".join(line.strip() for line in lines[4:] if line.strip())

    if byte_count > caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by fenced ZIP_BYTE_COUNT: {byte_count} > {caps.max_zip_bytes}"
        )
    if len(encoded) > caps.resolved_max_base64url_chars:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_BASE64URL_CHARS exceeded: {len(encoded)} > {caps.resolved_max_base64url_chars}"
        )
    if not _BASE64URL_RE.fullmatch(encoded):
        raise PatchMalformedError("fenced BASE64URL payload uses an invalid alphabet")

    try:
        padding = "=" * (-len(encoded) % 4)
        zip_bytes = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
    except (binascii.Error, ValueError) as exc:
        raise PatchMalformedError("fenced BASE64URL payload could not be decoded") from exc

    if len(zip_bytes) != byte_count:
        raise BundleIntegrityError(f"fenced zip byte count mismatch: expected {byte_count}, got {len(zip_bytes)}")
    actual_digest = sha256(zip_bytes).hexdigest()
    if actual_digest != digest:
        raise BundleIntegrityError("fenced ZIP_SHA256 does not match decoded zip bytes")

    try:
        manifest_obj = json.loads(manifest_text)
    except json.JSONDecodeError as exc:
        raise PatchMalformedError("fenced MANIFEST_JSON is not valid JSON") from exc
    if not isinstance(manifest_obj, dict):
        raise PatchMalformedError("fenced MANIFEST_JSON must be a JSON object")
    if manifest_obj.get("zip_byte_count") != byte_count:
        raise BundleIntegrityError("fenced MANIFEST_JSON.zip_byte_count does not match ZIP_BYTE_COUNT")
    if manifest_obj.get("zip_sha256") != digest:
        raise BundleIntegrityError("fenced MANIFEST_JSON.zip_sha256 does not match ZIP_SHA256")
    embedded_manifest = dict(manifest_obj)
    embedded_manifest.pop("zip_byte_count", None)
    embedded_manifest.pop("zip_sha256", None)
    return _FencedParseResult(zip_bytes=zip_bytes, manifest=embedded_manifest, byte_count=byte_count, sha256=digest)


def _coerce_patch_source(
    bundle: PatchBundle | bytes | str | Path,
    caps: PatchBundleCaps,
) -> tuple[bytes, str, PatchSource | Literal["raw", "path"], int, str]:
    if isinstance(bundle, PatchBundle):
        return bundle.content, bundle.filename, bundle.source, bundle.byte_count, bundle.sha256
    if isinstance(bundle, bytes):
        content = bytes(bundle)
        digest = sha256(content).hexdigest()
        return content, "patch-bundle.zip", "raw", len(content), digest
    try:
        path = Path(os.fspath(bundle))
    except TypeError as exc:
        raise PatchMalformedError("patch bundle source must be PatchBundle, bytes, str, or Path") from exc
    try:
        st = path.stat()
    except OSError as exc:
        raise PatchMalformedError("patch bundle path could not be statted before validation") from exc
    if not stat.S_ISREG(st.st_mode):
        raise PatchMalformedError("patch bundle path must be a regular file")
    if st.st_size > caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by patch bundle file: {st.st_size} > {caps.max_zip_bytes}"
        )
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise PatchMalformedError("patch bundle path could not be read") from exc
    digest = sha256(content).hexdigest()
    return content, path.name or "patch-bundle.zip", "path", len(content), digest


def _validate_zip_bytes(
    content: bytes,
    *,
    filename: str,
    source: PatchSource | Literal["raw", "path"],
    expected_byte_count: int,
    expected_sha256: str,
    caps: PatchBundleCaps,
    expected_fenced_manifest: Mapping[str, Any] | None = None,
) -> _ValidatedPatch:
    if expected_byte_count > caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by declared patch zip bytes: {expected_byte_count} > {caps.max_zip_bytes}"
        )
    if len(content) > caps.max_zip_bytes:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_ZIP_BYTES exceeded by actual patch zip bytes: {len(content)} > {caps.max_zip_bytes}"
        )
    if len(content) != expected_byte_count:
        raise BundleIntegrityError(f"patch zip byte count mismatch: expected {expected_byte_count}, got {len(content)}")
    actual_digest = sha256(content).hexdigest()
    if actual_digest != expected_sha256:
        raise BundleIntegrityError("patch zip SHA-256 mismatch against integrity envelope")

    try:
        with zipfile.ZipFile(BytesIO(content), mode="r") as archive:
            return _validate_open_zip(
                archive,
                content=content,
                filename=filename,
                source=source,
                digest=actual_digest,
                caps=caps,
                expected_fenced_manifest=expected_fenced_manifest,
            )
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise PatchMalformedError("patch zip central directory is invalid") from exc


def _validate_open_zip(
    archive: zipfile.ZipFile,
    *,
    content: bytes,
    filename: str,
    source: PatchSource | Literal["raw", "path"],
    digest: str,
    caps: PatchBundleCaps,
    expected_fenced_manifest: Mapping[str, Any] | None,
) -> _ValidatedPatch:
    infos = archive.infolist()
    if len(infos) > caps.max_file_count + 1:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_FILE_COUNT exceeded by zip entries: {len(infos) - 1} > {caps.max_file_count}"
        )
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise PatchMalformedError("patch zip contains duplicate member names")
    manifest_infos = [info for info in infos if info.filename == "manifest.json"]
    if len(manifest_infos) > 1:
        raise PatchMalformedError("patch zip contains duplicate manifest.json entries")
    if not manifest_infos:
        raise PatchMalformedError("patch zip is missing top-level manifest.json")

    file_infos: dict[str, zipfile.ZipInfo] = {}
    directory_infos: list[zipfile.ZipInfo] = []
    for info in infos:
        _validate_zip_info_basic(info, caps=caps, is_manifest=info.filename == "manifest.json")
        if info.is_dir():
            directory_infos.append(info)
            continue
        if info.filename != "manifest.json":
            file_infos[info.filename] = info
    if len(file_infos) > caps.max_file_count:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_FILE_COUNT exceeded by payload entries: {len(file_infos)} > {caps.max_file_count}"
        )

    manifest_info = manifest_infos[0]
    if manifest_info.file_size > caps.max_manifest_bytes:
        raise OversizedPayloadError(
            f"PATCH_MANIFEST_MAX_BYTES exceeded: {manifest_info.file_size} > {caps.max_manifest_bytes}"
        )
    manifest_obj = _read_manifest_json(archive, manifest_info)
    entries = _validate_manifest_schema(manifest_obj, caps)
    if expected_fenced_manifest is not None and manifest_obj != dict(expected_fenced_manifest):
        raise PatchMalformedError("embedded manifest.json does not match fenced MANIFEST_JSON")

    changed_paths = {entry.path for entry in entries if entry.status == "changed"}
    payload_paths = set(file_infos)
    if payload_paths != changed_paths:
        missing = sorted(changed_paths - payload_paths)
        extra = sorted(payload_paths - changed_paths)
        detail = []
        if missing:
            detail.append(f"missing payloads={missing}")
        if extra:
            detail.append(f"extra payloads={extra}")
        raise PatchMalformedError("patch zip payload entry set does not match manifest changed paths; " + "; ".join(detail))

    for entry in entries:
        _validate_patch_rel_path(entry.path)
    for name in file_infos:
        _validate_patch_rel_path(name)
    _validate_directory_entries(directory_infos, changed_paths)

    payloads: dict[str, bytes] = {}
    expanded = 0
    for entry in entries:
        if entry.status != "changed":
            continue
        info = file_infos[entry.path]
        if info.file_size != entry.size:
            raise BundleIntegrityError(f"payload size mismatch for {entry.path}: central directory {info.file_size} != manifest {entry.size}")
        expanded += info.file_size
        if expanded > caps.max_expanded_bytes:
            raise OversizedPayloadError(
                f"PATCH_BUNDLE_MAX_EXPANDED_BYTES exceeded while reading payloads: {expanded} > {caps.max_expanded_bytes}"
            )
        data = _read_zip_payload(archive, info, cap=caps.max_file_bytes)
        if len(data) != entry.size:
            raise BundleIntegrityError(f"payload byte count mismatch for {entry.path}: expected {entry.size}, got {len(data)}")
        actual = sha256(data).hexdigest()
        if actual != entry.sha256:
            raise BundleIntegrityError(f"payload SHA-256 mismatch for {entry.path}")
        payloads[entry.path] = data

    files = tuple(replace(entry, data=payloads.get(entry.path)) if entry.status == "changed" else entry for entry in entries)
    return _ValidatedPatch(
        filename=filename,
        content=content,
        sha256=digest,
        byte_count=len(content),
        source=source,
        manifest=manifest_obj,
        files=files,
    )


def _zip_file_type(info: zipfile.ZipInfo) -> int:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_IFMT(mode)


def _validate_zip_info_basic(info: zipfile.ZipInfo, *, caps: PatchBundleCaps, is_manifest: bool) -> None:
    if info.flag_bits & 0x1:
        raise PatchMalformedError(f"encrypted zip entry rejected: {info.filename}")
    file_type = _zip_file_type(info)
    if file_type == stat.S_IFLNK:
        raise PathEscapeError(f"symlink zip entry rejected: {info.filename}")
    if file_type and file_type not in {stat.S_IFREG, stat.S_IFDIR}:
        raise PatchMalformedError(f"special zip entry rejected: {info.filename}")
    if info.is_dir():
        if info.file_size != 0:
            raise PatchMalformedError(f"directory zip entry has a payload: {info.filename}")
        return
    cap = caps.max_manifest_bytes if is_manifest else caps.max_file_bytes
    cap_name = "PATCH_MANIFEST_MAX_BYTES" if is_manifest else "PATCH_BUNDLE_MAX_FILE_BYTES"
    if info.file_size > cap:
        raise OversizedPayloadError(f"{cap_name} exceeded by zip entry {info.filename}: {info.file_size} > {cap}")


def _read_manifest_json(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> dict[str, Any]:
    try:
        raw = archive.read(info)
    except (RuntimeError, zipfile.BadZipFile, zlib.error, OSError) as exc:
        raise PatchMalformedError("manifest.json could not be read from patch zip") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise PatchMalformedError("manifest.json is not UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise PatchMalformedError("manifest.json is not valid JSON") from exc
    if not isinstance(value, dict):
        raise PatchMalformedError("manifest.json must be a JSON object")
    return value


def _validate_manifest_schema(manifest: Mapping[str, Any], caps: PatchBundleCaps) -> tuple[_PatchFile, ...]:
    allowed_top = {"version", "files", "total_byte_count"}
    unknown_top = set(manifest) - allowed_top
    if unknown_top:
        raise PatchMalformedError(f"manifest.json contains unknown top-level keys: {sorted(unknown_top)}")
    if type(manifest.get("version")) is not int or manifest.get("version") != 1:
        raise PatchMalformedError("manifest.json version must equal 1")
    files_value = manifest.get("files")
    if not isinstance(files_value, list):
        raise PatchMalformedError("manifest.json files must be an array")
    if len(files_value) > caps.max_file_count:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_FILE_COUNT exceeded by manifest files: {len(files_value)} > {caps.max_file_count}"
        )
    total_byte_count = manifest.get("total_byte_count")
    if type(total_byte_count) is not int or total_byte_count < 0:
        raise PatchMalformedError("manifest.json total_byte_count must be a non-negative integer")

    seen_paths: set[str] = set()
    entries: list[_PatchFile] = []
    changed_total = 0
    for raw_entry in files_value:
        if not isinstance(raw_entry, dict):
            raise PatchMalformedError("manifest file entries must be JSON objects")
        allowed_file = {"path", "status", "operation", "size", "sha256"}
        unknown_file = set(raw_entry) - allowed_file
        if unknown_file:
            raise PatchMalformedError(f"manifest file entry contains unknown keys: {sorted(unknown_file)}")
        path = raw_entry.get("path")
        if not isinstance(path, str):
            raise PatchMalformedError("manifest file entry path must be a string")
        if path in seen_paths:
            raise PatchMalformedError(f"manifest contains duplicate path: {path}")
        seen_paths.add(path)
        status = raw_entry.get("status")
        if status not in {"changed", "deleted"}:
            raise PatchMalformedError(f"manifest path {path} has unsupported status: {status!r}")
        operation = raw_entry.get("operation")
        if operation is not None and not isinstance(operation, str):
            raise PatchMalformedError(f"manifest path {path} operation must be a string when present")
        size = raw_entry.get("size")
        if type(size) is not int:
            raise PatchMalformedError(f"manifest path {path} size must be an integer")
        sha_value = raw_entry.get("sha256")
        if status == "changed":
            if operation not in {None, "added", "modified"}:
                raise PatchMalformedError(f"manifest path {path} changed operation must be absent, added, or modified")
            if size < 0:
                raise PatchMalformedError(f"manifest path {path} changed size must be non-negative")
            if size > caps.max_file_bytes:
                raise OversizedPayloadError(
                    f"PATCH_BUNDLE_MAX_FILE_BYTES exceeded by manifest path {path}: {size} > {caps.max_file_bytes}"
                )
            if not isinstance(sha_value, str) or not _HEX64_RE.fullmatch(sha_value):
                raise PatchMalformedError(f"manifest path {path} sha256 must be lowercase 64-hex")
            changed_total += size
            entries.append(_PatchFile(path=path, status="changed", operation=operation, size=size, sha256=sha_value))
            continue
        if operation != "deleted":
            raise PatchMalformedError(f"manifest path {path} deleted operation must be deleted")
        if size != 0:
            raise PatchMalformedError(f"manifest path {path} deleted size must be 0")
        if sha_value is not None:
            raise PatchMalformedError(f"manifest path {path} deleted sha256 must be null")
        entries.append(_PatchFile(path=path, status="deleted", operation="deleted", size=0, sha256=None))

    if changed_total != total_byte_count:
        raise PatchMalformedError(
            f"manifest total_byte_count mismatch: expected changed-size sum {changed_total}, got {total_byte_count}"
        )
    if changed_total > caps.max_expanded_bytes:
        raise OversizedPayloadError(
            f"PATCH_BUNDLE_MAX_EXPANDED_BYTES exceeded by manifest total_byte_count: {changed_total} > {caps.max_expanded_bytes}"
        )
    return tuple(entries)


def _validate_patch_rel_path(path: str) -> str:
    return validate_posix_relative_path(
        path,
        reserved_paths=_PATCH_RESERVED_PATHS,
        reserved_prefixes=_PATCH_RESERVED_PREFIXES,
    )


def _validate_directory_entries(directory_infos: Sequence[zipfile.ZipInfo], changed_paths: set[str]) -> None:
    for info in directory_infos:
        raw = info.filename.rstrip("/")
        if not raw:
            raise PatchMalformedError("root directory zip entry is not allowed")
        rel = _validate_patch_rel_path(raw)
        if not any(path.startswith(rel + "/") for path in changed_paths):
            raise PatchMalformedError(f"directory zip entry is not a parent of any changed payload: {info.filename}")


def _read_zip_payload(archive: zipfile.ZipFile, info: zipfile.ZipInfo, *, cap: int) -> bytes:
    try:
        with archive.open(info, mode="r") as handle:
            data = handle.read(cap + 1)
    except (RuntimeError, zipfile.BadZipFile, zlib.error, OSError) as exc:
        raise PatchMalformedError(f"zip payload could not be decompressed or failed CRC: {info.filename}") from exc
    if len(data) > cap:
        raise OversizedPayloadError(f"PATCH_BUNDLE_MAX_FILE_BYTES exceeded while reading payload {info.filename}")
    return data


def _resolve_apply_root(root: str | Path) -> Path:
    try:
        root_path = Path(os.fspath(root))
    except TypeError as exc:
        raise PathEscapeError("apply root must be a string or path-like directory") from exc
    try:
        root_real = root_path.resolve(strict=True)
    except OSError as exc:
        raise PathEscapeError("apply root must exist as a directory") from exc
    if not root_real.is_dir():
        raise PathEscapeError("apply root must be an existing directory")
    return root_real


def _prepare_apply(validated: _ValidatedPatch, *, root_real: Path, dry_run: bool) -> _PreparedApply:
    plans: list[_TargetPlan] = []
    diffs: list[FileDiff] = []
    for entry in sorted(validated.files, key=lambda item: item.path):
        plan = _resolve_target_plan(root_real, entry)
        plans.append(plan)
        diffs.append(_diff_for_plan(plan))
    files = tuple(diffs)
    summary = DiffSummary(
        root=root_real,
        dry_run=dry_run,
        files=files,
        added=sum(1 for diff in files if diff.change_kind == "added"),
        modified=sum(1 for diff in files if diff.change_kind == "modified"),
        deleted=sum(1 for diff in files if diff.change_kind == "deleted"),
        total_files=len(files),
        total_byte_delta=sum(diff.byte_delta for diff in files),
        total_bytes_changed=sum(_bytes_changed(diff) for diff in files),
    )
    return _PreparedApply(summary=summary, plans=tuple(plans))


def _resolve_target_plan(root_real: Path, entry: _PatchFile) -> _TargetPlan:
    rel = _validate_patch_rel_path(entry.path)
    parts = rel.split("/")
    lexical_target = Path(os.path.normpath(os.path.join(str(root_real), *parts)))
    if not _is_contained(root_real, lexical_target):
        raise PathEscapeError(f"path escapes apply root: {entry.path}")

    current = root_real
    missing_parent = False
    for part in parts[:-1]:
        candidate = current / part
        if missing_parent:
            current = candidate
            continue
        try:
            st = candidate.lstat()
        except FileNotFoundError:
            if entry.status == "changed":
                missing_parent = True
                current = candidate
                continue
            return _TargetPlan(entry=entry, target=lexical_target, existed=False, old_sha256=None, old_bytes=None, old_data=None)
        except OSError as exc:
            raise PatchApplyError(f"could not inspect parent path for {entry.path}") from exc
        if stat.S_ISLNK(st.st_mode):
            raise PathEscapeError(f"symlink parent component rejected: {entry.path}")
        if not stat.S_ISDIR(st.st_mode):
            raise PathEscapeError(f"non-directory parent component rejected: {entry.path}")
        if not _is_contained(root_real, candidate.resolve(strict=True)):
            raise PathEscapeError(f"parent path escapes apply root: {entry.path}")
        current = candidate

    target = lexical_target
    try:
        st = target.lstat()
    except FileNotFoundError:
        return _TargetPlan(entry=entry, target=target, existed=False, old_sha256=None, old_bytes=None, old_data=None)
    except OSError as exc:
        raise PatchApplyError(f"could not inspect target path for {entry.path}") from exc
    if stat.S_ISLNK(st.st_mode):
        raise PathEscapeError(f"symlink final target rejected: {entry.path}")
    if stat.S_ISDIR(st.st_mode):
        raise PathEscapeError(f"directory target rejected for file operation: {entry.path}")
    if not stat.S_ISREG(st.st_mode):
        raise PathEscapeError(f"special file target rejected: {entry.path}")
    if not _is_contained(root_real, target.resolve(strict=True)):
        raise PathEscapeError(f"target path escapes apply root: {entry.path}")
    old_data = _read_regular_file_no_follow(target, entry.path)
    return _TargetPlan(
        entry=entry,
        target=target,
        existed=True,
        old_sha256=sha256(old_data).hexdigest(),
        old_bytes=len(old_data),
        old_data=old_data,
    )


def _read_regular_file_no_follow(path: Path, rel: str) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if getattr(exc, "errno", None) in {40, 62}:  # ELOOP on Linux/BSD without importing platform-specific constants.
            raise PathEscapeError(f"symlink target rejected while reading {rel}") from exc
        raise PatchApplyError(f"could not open existing file for diff: {rel}") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise PathEscapeError(f"target is not a regular file while reading {rel}")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            return handle.read()
    except (OSError, RuntimeError) as exc:
        raise PatchApplyError(f"could not read existing file for diff: {rel}") from exc
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def _diff_for_plan(plan: _TargetPlan) -> FileDiff:
    entry = plan.entry
    old_data = plan.old_data
    new_data = entry.data if entry.status == "changed" else None
    if entry.status == "deleted":
        change_kind: ChangeKind = "deleted"
    else:
        change_kind = "modified" if plan.existed else "added"
    old_sha_value = plan.old_sha256
    new_sha_value = sha256(new_data).hexdigest() if new_data is not None else None
    old_size = plan.old_bytes
    new_size = len(new_data) if new_data is not None else None
    old_for_delta = old_size or 0
    new_for_delta = new_size or 0
    lines_added, lines_deleted = _line_delta(old_data, new_data)
    return FileDiff(
        path=entry.path,
        change_kind=change_kind,
        old_sha256=old_sha_value,
        new_sha256=new_sha_value,
        old_bytes=old_size,
        new_bytes=new_size,
        byte_delta=new_for_delta - old_for_delta,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
    )


def _line_delta(old_data: bytes | None, new_data: bytes | None) -> tuple[int | None, int | None]:
    try:
        old_lines = [] if old_data is None else old_data.decode("utf-8").splitlines()
        new_lines = [] if new_data is None else new_data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None, None
    added = 0
    deleted = 0
    for tag, old_start, old_end, new_start, new_end in SequenceMatcher(None, old_lines, new_lines).get_opcodes():
        if tag == "insert":
            added += new_end - new_start
        elif tag == "delete":
            deleted += old_end - old_start
        elif tag == "replace":
            added += new_end - new_start
            deleted += old_end - old_start
    return added, deleted


def _bytes_changed(diff: FileDiff) -> int:
    if diff.change_kind == "deleted":
        return diff.old_bytes or 0
    return diff.new_bytes or 0


def _recover_incomplete_transactions(root_real: Path) -> None:
    tmp_root = root_real / _TRANSACTION_DIRNAME
    if not tmp_root.exists():
        return
    try:
        st = tmp_root.lstat()
    except OSError as exc:
        raise PatchApplyError("could not inspect patch transaction directory") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise PathEscapeError("patch transaction directory is not a real directory")
    for child in sorted(tmp_root.iterdir()):
        if not child.name.startswith("apply-"):
            continue
        journal = child / _JOURNAL_NAME
        if journal.exists():
            _rollback_journal(root_real, child)
        else:
            shutil.rmtree(child, ignore_errors=True)
    _remove_empty_transaction_root(tmp_root)


def _apply_transaction(root_real: Path, prepared: _PreparedApply) -> DiffSummary:
    tmp_root = _ensure_transaction_root(root_real)
    tx_dir = tmp_root / f"apply-{uuid.uuid4().hex}"
    staged_root = tx_dir / "staged"
    backup_root = tx_dir / "backup"
    try:
        staged_root.mkdir(parents=True, mode=0o700)
        backup_root.mkdir(parents=True, mode=0o700)
        journal_entries: list[dict[str, Any]] = []
        for plan in prepared.plans:
            rel = plan.entry.path
            staged_rel = None
            backup_rel = None
            if plan.entry.status == "changed":
                if plan.entry.data is None:
                    raise PatchApplyError(f"validated changed payload missing in transaction: {rel}")
                staged_path = staged_root / rel
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                staged_path.write_bytes(plan.entry.data)
                staged_rel = str(staged_path.relative_to(tx_dir).as_posix())
            if plan.existed:
                current = _read_regular_file_no_follow(plan.target, rel)
                current_hash = sha256(current).hexdigest()
                if current_hash != plan.old_sha256:
                    raise PatchApplyError(f"local conflict detected before applying {rel}")
                backup_path = backup_root / rel
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                backup_path.write_bytes(current)
                backup_rel = str(backup_path.relative_to(tx_dir).as_posix())
            else:
                if plan.target.exists() or plan.target.is_symlink():
                    raise PatchApplyError(f"local conflict detected before creating {rel}")
            journal_entries.append(
                {
                    "path": rel,
                    "operation": plan.entry.status,
                    "old_sha256": plan.old_sha256,
                    "new_sha256": plan.entry.sha256,
                    "staged": staged_rel,
                    "backup": backup_rel,
                }
            )
        journal = {"version": 1, "files": journal_entries}
        (tx_dir / _JOURNAL_NAME).write_text(json.dumps(journal, sort_keys=True, separators=(",", ":")), encoding="utf-8")

        for plan in prepared.plans:
            _commit_plan(root_real, tx_dir, plan)
        shutil.rmtree(tx_dir)
        _remove_empty_transaction_root(tmp_root)
        return prepared.summary
    except (AskChatGPTError, OSError) as exc:
        rollback_error: BaseException | None = None
        try:
            if tx_dir.exists():
                _rollback_plans(root_real, tx_dir, prepared.plans)
                shutil.rmtree(tx_dir, ignore_errors=True)
                _remove_empty_transaction_root(tmp_root)
        except BaseException as rollback_exc:  # noqa: BLE001 - preserve rollback failure detail safely.
            rollback_error = rollback_exc
        if isinstance(exc, AskChatGPTError):
            if rollback_error is not None:
                raise PatchApplyError("apply failed and rollback also failed; inspect transaction journal") from rollback_error
            raise
        if rollback_error is not None:
            raise PatchApplyError("apply I/O failed and rollback also failed; inspect transaction journal") from rollback_error
        raise PatchApplyError("apply I/O failed; rollback completed") from exc


def _ensure_transaction_root(root_real: Path) -> Path:
    tmp_root = root_real / _TRANSACTION_DIRNAME
    if tmp_root.exists() or tmp_root.is_symlink():
        try:
            st = tmp_root.lstat()
        except OSError as exc:
            raise PatchApplyError("could not inspect patch transaction directory") from exc
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise PathEscapeError("patch transaction directory is not a real directory")
    else:
        tmp_root.mkdir(mode=0o700)
    return tmp_root


def _commit_plan(root_real: Path, tx_dir: Path, plan: _TargetPlan) -> None:
    rel = plan.entry.path
    _ensure_parent_dirs_no_follow(root_real, plan.target, rel)
    _assert_target_state_for_mutation(plan)
    if plan.entry.status == "changed":
        staged_path = tx_dir / "staged" / rel
        os.replace(staged_path, plan.target)
        return
    if plan.existed:
        os.unlink(plan.target)


def _ensure_parent_dirs_no_follow(root_real: Path, target: Path, rel: str) -> None:
    relative = target.relative_to(root_real).as_posix()
    parts = relative.split("/")[:-1]
    current = root_real
    for part in parts:
        candidate = current / part
        try:
            st = candidate.lstat()
        except FileNotFoundError:
            candidate.mkdir(mode=0o755)
            st = candidate.lstat()
        if stat.S_ISLNK(st.st_mode):
            raise PathEscapeError(f"symlink parent component rejected during apply: {rel}")
        if not stat.S_ISDIR(st.st_mode):
            raise PathEscapeError(f"non-directory parent component rejected during apply: {rel}")
        if not _is_contained(root_real, candidate.resolve(strict=True)):
            raise PathEscapeError(f"parent path escapes apply root during apply: {rel}")
        current = candidate


def _assert_target_state_for_mutation(plan: _TargetPlan) -> None:
    rel = plan.entry.path
    try:
        st = plan.target.lstat()
    except FileNotFoundError:
        if plan.existed:
            raise PatchApplyError(f"local conflict detected before applying {rel}: target disappeared") from None
        return
    if stat.S_ISLNK(st.st_mode):
        raise PathEscapeError(f"symlink final target rejected during apply: {rel}")
    if stat.S_ISDIR(st.st_mode):
        raise PathEscapeError(f"directory final target rejected during apply: {rel}")
    if not stat.S_ISREG(st.st_mode):
        raise PathEscapeError(f"special final target rejected during apply: {rel}")
    current = _read_regular_file_no_follow(plan.target, rel)
    current_hash = sha256(current).hexdigest()
    if plan.existed:
        if current_hash != plan.old_sha256:
            raise PatchApplyError(f"local conflict detected before applying {rel}: content changed")
    else:
        raise PatchApplyError(f"local conflict detected before creating {rel}: target appeared")


def _rollback_plans(root_real: Path, tx_dir: Path, plans: Sequence[_TargetPlan]) -> None:
    for plan in reversed(plans):
        rel = plan.entry.path
        backup_path = tx_dir / "backup" / rel
        if plan.existed:
            if backup_path.exists():
                _ensure_parent_dirs_no_follow(root_real, plan.target, rel)
                os.replace(backup_path, plan.target)
        else:
            _unlink_regular_if_exists(plan.target)


def _rollback_journal(root_real: Path, tx_dir: Path) -> None:
    try:
        payload = json.loads((tx_dir / _JOURNAL_NAME).read_text(encoding="utf-8"))
        files = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(files, list):
            raise ValueError("journal files missing")
        for item in reversed(files):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("journal path missing")
            rel = _validate_patch_rel_path(item["path"])
            target = Path(os.path.normpath(os.path.join(str(root_real), *rel.split("/"))))
            if not _is_contained(root_real, target):
                raise PathEscapeError("journal path escapes apply root")
            backup_rel = item.get("backup")
            if isinstance(backup_rel, str):
                backup = tx_dir / backup_rel
                if backup.exists():
                    _ensure_parent_dirs_no_follow(root_real, target, rel)
                    os.replace(backup, target)
                    continue
            _unlink_regular_if_exists(target)
        shutil.rmtree(tx_dir, ignore_errors=True)
    except AskChatGPTError:
        raise
    except Exception as exc:  # noqa: BLE001 - recovery maps arbitrary local failures to PatchApplyError.
        raise PatchApplyError("incomplete patch transaction could not be rolled back") from exc


def _unlink_regular_if_exists(path: Path) -> None:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
        path.unlink()


def _remove_empty_transaction_root(tmp_root: Path) -> None:
    try:
        tmp_root.rmdir()
    except OSError:
        pass


def _is_contained(root_real: Path, path: Path) -> bool:
    try:
        return os.path.commonpath([str(root_real), str(path)]) == str(root_real)
    except ValueError:
        return False


def _timeout_ms(timeout_s: float) -> int:
    return max(0, int(float(timeout_s) * 1000))


__all__ = [
    "PATCH_BUNDLE_MAX_ZIP_BYTES",
    "PATCH_BUNDLE_MAX_FILE_BYTES",
    "PATCH_BUNDLE_MAX_EXPANDED_BYTES",
    "PATCH_MANIFEST_MAX_BYTES",
    "PATCH_BUNDLE_MAX_BASE64URL_CHARS",
    "PATCH_BUNDLE_MAX_FILE_COUNT",
    "Pathish",
    "PatchSource",
    "PatchBundleSource",
    "ChangeKind",
    "PatchBundleCaps",
    "PatchBundle",
    "FileDiff",
    "DiffSummary",
    "retrieve_patch_bundle",
    "apply_patch",
]
