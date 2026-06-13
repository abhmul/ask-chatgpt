import base64
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from ask_chatgpt.driver import BrowserSession
from ask_chatgpt.errors import (
    BundleIntegrityError,
    DownloadUnsupportedError,
    OversizedPayloadError,
    PatchMalformedError,
    PathEscapeError,
    ResponseTruncatedError,
)
from ask_chatgpt.patch import PatchBundleCaps, _parse_fenced_patch_bundle, apply_patch, retrieve_patch_bundle
from ask_chatgpt.selector_map import SelectorMap


_ZIP_DATE_TIME = (2024, 1, 1, 0, 0, 0)
_REAL_M006_BUNDLE = """BEGIN_PATCH_BUNDLE
MANIFEST_JSON {"version":1,"change":"example.txt favorite_color red to blue"}
ZIP_BYTE_COUNT 144
ZIP_SHA256 3dce3bc5690138135aca9a04e04973c7f75f36e337e1579bf63230a69fbbd050
BASE64URL UEsDBBQAAAAAAAAAIQCdm2LOGAAAABgAAAALAAAAZXhhbXBsZS50eHRmYXZvcml0ZV9jb2xvciA9ICJibHVlIgpQSwECFAMUAAAAAAAAACEAnZtizhgAAAAYAAAACwAAAAAAAAAAAAAApIEAAAAAZXhhbXBsZS50eHRQSwUGAAAAAAEAAQA5AAAAQQAAAAAA
END_PATCH_BUNDLE"""
_REAL_M006_SHA = "3dce3bc5690138135aca9a04e04973c7f75f36e337e1579bf63230a69fbbd050"
_REAL_M006_BASE64URL = "UEsDBBQAAAAAAAAAIQCdm2LOGAAAABgAAAALAAAAZXhhbXBsZS50eHRmYXZvcml0ZV9jb2xvciA9ICJibHVlIgpQSwECFAMUAAAAAAAAACEAnZtizhgAAAAYAAAACwAAAAAAAAAAAAAApIEAAAAAZXhhbXBsZS50eHRQSwUGAAAAAAEAAQA5AAAAQQAAAAAA"


@pytest.fixture
def apply_root(request):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.node.name)[:80]
    root = Path("tmp") / "test_patch" / f"{safe_name}-{uuid.uuid4().hex}"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _zip_info(path: str, *, file_type: int = stat.S_IFREG, mode: int = 0o644) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=_ZIP_DATE_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (file_type | mode) << 16
    return info


def _build_patch_zip(
    *,
    changed: dict[str, bytes | str] | None = None,
    deleted: tuple[str, ...] = (),
    operations: dict[str, str] | None = None,
    sha_overrides: dict[str, str | None] | None = None,
    size_overrides: dict[str, int] | None = None,
    status_overrides: dict[str, str] | None = None,
    extra_entries: dict[str, bytes | str] | None = None,
    entry_file_types: dict[str, int] | None = None,
) -> bytes:
    changed = {} if changed is None else changed
    operations = {} if operations is None else operations
    sha_overrides = {} if sha_overrides is None else sha_overrides
    size_overrides = {} if size_overrides is None else size_overrides
    status_overrides = {} if status_overrides is None else status_overrides
    extra_entries = {} if extra_entries is None else extra_entries
    entry_file_types = {} if entry_file_types is None else entry_file_types
    normalized_changed = {
        path: data if isinstance(data, bytes) else data.encode("utf-8")
        for path, data in changed.items()
    }
    files = []
    for path, data in sorted(normalized_changed.items()):
        files.append(
            {
                "path": path,
                "status": status_overrides.get(path, "changed"),
                "operation": operations.get(path, "modified"),
                "size": size_overrides.get(path, len(data)),
                "sha256": sha_overrides.get(path, hashlib.sha256(data).hexdigest()),
            }
        )
    for path in sorted(deleted):
        files.append(
            {
                "path": path,
                "status": status_overrides.get(path, "deleted"),
                "operation": operations.get(path, "deleted"),
                "size": size_overrides.get(path, 0),
                "sha256": sha_overrides.get(path, None),
            }
        )
    manifest = {
        "version": 1,
        "files": files,
        "total_byte_count": sum(item["size"] for item in files if item["status"] == "changed"),
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(_zip_info("manifest.json"), json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        for path, data in sorted(normalized_changed.items()):
            archive.writestr(_zip_info(path, file_type=entry_file_types.get(path, stat.S_IFREG)), data)
        for path, data in sorted(extra_entries.items()):
            payload = data if isinstance(data, bytes) else data.encode("utf-8")
            archive.writestr(_zip_info(path, file_type=entry_file_types.get(path, stat.S_IFREG)), payload)
    return buffer.getvalue()


def _build_bare_patch_zip(
    members: dict[str, bytes | str],
    *,
    entry_file_types: dict[str, int] | None = None,
) -> bytes:
    entry_file_types = {} if entry_file_types is None else entry_file_types
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for path, data in sorted(members.items()):
            payload = data if isinstance(data, bytes) else data.encode("utf-8")
            archive.writestr(_zip_info(path, file_type=entry_file_types.get(path, stat.S_IFREG)), payload)
    return buffer.getvalue()


def _with_encrypted_member_flag(zip_bytes: bytes, member: str) -> bytes:
    target = member.encode("utf-8")
    data = bytearray(zip_bytes)
    found = False

    def set_flag(offset: int) -> None:
        flags = int.from_bytes(data[offset : offset + 2], "little") | 0x1
        data[offset : offset + 2] = flags.to_bytes(2, "little")

    index = 0
    while True:
        index = data.find(b"PK\x03\x04", index)
        if index < 0:
            break
        compressed_size = int.from_bytes(data[index + 18 : index + 22], "little")
        name_len = int.from_bytes(data[index + 26 : index + 28], "little")
        extra_len = int.from_bytes(data[index + 28 : index + 30], "little")
        name = bytes(data[index + 30 : index + 30 + name_len])
        if name == target:
            set_flag(index + 6)
            found = True
        index += 30 + name_len + extra_len + compressed_size

    index = 0
    while True:
        index = data.find(b"PK\x01\x02", index)
        if index < 0:
            break
        name_len = int.from_bytes(data[index + 28 : index + 30], "little")
        extra_len = int.from_bytes(data[index + 30 : index + 32], "little")
        comment_len = int.from_bytes(data[index + 32 : index + 34], "little")
        name = bytes(data[index + 46 : index + 46 + name_len])
        if name == target:
            set_flag(index + 8)
            found = True
        index += 46 + name_len + extra_len + comment_len

    assert found, f"member not found in zip: {member}"
    return bytes(data)


def _snapshot_tree(root: Path):
    snapshot = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        st_mode = path.lstat().st_mode
        if stat.S_ISLNK(st_mode):
            snapshot[rel] = ("symlink", os.readlink(path))
        elif stat.S_ISREG(st_mode):
            snapshot[rel] = ("file", path.read_bytes())
        elif stat.S_ISDIR(st_mode):
            snapshot[rel] = ("dir", None)
        else:
            snapshot[rel] = ("other", None)
    return snapshot


def _download_unavailable_map(selectors: SelectorMap) -> SelectorMap:
    real_like_selectors = dict(selectors.selectors)
    real_like_selectors["download_artifact"] = ""
    return SelectorMap(
        channel="mock-download-unavailable",
        selectors=real_like_selectors,
        attributes=dict(selectors.attributes),
        version=selectors.version,
    )


def _retrieve_scripted(
    mock_chatgpt,
    *,
    text: str = "patch response",
    download_mode: str | None = None,
    fenced_mode: str | None = None,
    caps: PatchBundleCaps | None = None,
    download_wait_s: float = 1.0,
):
    mock_chatgpt.reset()
    fields = {}
    if download_mode is not None:
        fields["download_mode"] = download_mode
    if fenced_mode is not None:
        fields["fenced_mode"] = fenced_mode
    mock_chatgpt.script_next_response(text, **fields)
    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        session.send_prompt("return a patch bundle")
        session.wait_for_completion(timeout_s=3)
        return retrieve_patch_bundle(session, timeout_s=3, download_wait_s=download_wait_s, caps=caps)


def test_parse_real_m006_space_keys_inline_base64_decodes():
    result = _parse_fenced_patch_bundle(_REAL_M006_BUNDLE, PatchBundleCaps())

    assert result is not None
    assert result.byte_count == 144
    assert result.sha256 == _REAL_M006_SHA
    padding = "=" * (-len(_REAL_M006_BASE64URL) % 4)
    assert result.zip_bytes == base64.urlsafe_b64decode((_REAL_M006_BASE64URL + padding).encode("ascii"))


def test_parse_real_m006_softwrapped_payload_is_whitespace_tolerant():
    wrapped_payload = _REAL_M006_BASE64URL[:72] + "\n  " + _REAL_M006_BASE64URL[72:]
    text = _REAL_M006_BUNDLE.replace(_REAL_M006_BASE64URL, wrapped_payload)

    result = _parse_fenced_patch_bundle(text, PatchBundleCaps())

    assert result is not None
    assert result.byte_count == 144
    assert result.sha256 == _REAL_M006_SHA


def test_parse_real_m006_truncated_missing_end_raises_truncated():
    text = _REAL_M006_BUNDLE.replace("\nEND_PATCH_BUNDLE", "")

    with pytest.raises(ResponseTruncatedError):
        _parse_fenced_patch_bundle(text, PatchBundleCaps())


@pytest.mark.parametrize("drift_marker", ["END_PATCH_BUNDL", "END_PATCH_BUND"])
def test_parse_real_drift_end_marker_prefix_decodes_verified_payload(drift_marker):
    text = _REAL_M006_BUNDLE.replace("END_PATCH_BUNDLE", drift_marker)

    result = _parse_fenced_patch_bundle(text, PatchBundleCaps())

    assert result is not None
    assert result.byte_count == 144
    assert result.sha256 == _REAL_M006_SHA


def test_parse_real_m006_bad_sha_raises_integrity():
    text = _REAL_M006_BUNDLE.replace(_REAL_M006_SHA, "0" * 64)

    with pytest.raises(BundleIntegrityError):
        _parse_fenced_patch_bundle(text, PatchBundleCaps())


def test_parse_real_m006_bad_byte_count_raises_integrity():
    text = _REAL_M006_BUNDLE.replace("ZIP_BYTE_COUNT 144", "ZIP_BYTE_COUNT 145")

    with pytest.raises(BundleIntegrityError):
        _parse_fenced_patch_bundle(text, PatchBundleCaps())


def test_parse_real_m006_bad_alphabet_raises_malformed():
    bad_payload = _REAL_M006_BASE64URL[:20] + "+" + _REAL_M006_BASE64URL[21:]
    text = _REAL_M006_BUNDLE.replace(_REAL_M006_BASE64URL, bad_payload)

    with pytest.raises(PatchMalformedError):
        _parse_fenced_patch_bundle(text, PatchBundleCaps())


def test_parse_colon_form_still_supported_backward_compat():
    zip_bytes = _build_patch_zip(changed={"src/example.txt": b"new\n"})
    digest = hashlib.sha256(zip_bytes).hexdigest()
    manifest = {
        "files": [
            {
                "operation": "modified",
                "path": "src/example.txt",
                "sha256": hashlib.sha256(b"new\n").hexdigest(),
                "size": 4,
                "status": "changed",
            }
        ],
        "total_byte_count": 4,
        "version": 1,
        "zip_byte_count": len(zip_bytes),
        "zip_sha256": digest,
    }
    encoded = base64.urlsafe_b64encode(zip_bytes).decode("ascii").rstrip("=")
    text = "\n".join(
        [
            "BEGIN_PATCH_BUNDLE",
            "MANIFEST_JSON: " + json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            f"ZIP_BYTE_COUNT: {len(zip_bytes)}",
            f"ZIP_SHA256: {digest}",
            "BASE64URL:",
            encoded,
            "END_PATCH_BUNDLE",
        ]
    )

    result = _parse_fenced_patch_bundle(text, PatchBundleCaps())

    assert result is not None
    assert result.zip_bytes == zip_bytes
    assert result.byte_count == len(zip_bytes)
    assert result.sha256 == digest


def test_bare_zip_without_manifest_reconstructs_and_applies_modified_and_added(apply_root):
    (apply_root / "src").mkdir()
    (apply_root / "src" / "existing.txt").write_text("old\n", encoding="utf-8")
    bundle = _build_bare_patch_zip({"src/existing.txt": b"new\n", "src/added.txt": b"added\n"})

    summary = apply_patch(bundle, apply_root, dry_run=False)

    assert summary.modified == 1
    assert summary.added == 1
    assert summary.deleted == 0
    assert (apply_root / "src" / "existing.txt").read_text(encoding="utf-8") == "new\n"
    assert (apply_root / "src" / "added.txt").read_text(encoding="utf-8") == "added\n"


def test_bare_zip_real_m006_payload_roundtrips(apply_root):
    padding = "=" * (-len(_REAL_M006_BASE64URL) % 4)
    zip_bytes = base64.urlsafe_b64decode((_REAL_M006_BASE64URL + padding).encode("ascii"))
    (apply_root / "example.txt").write_text('favorite_color = "red"\n', encoding="utf-8")

    summary = apply_patch(zip_bytes, apply_root, dry_run=False)

    assert summary.modified == 1
    assert (apply_root / "example.txt").read_text(encoding="utf-8") == 'favorite_color = "blue"\n'


@pytest.mark.parametrize("member", ["../escape.txt", "/absolute.txt"])
def test_bare_zip_unsafe_member_paths_rejected_before_write(apply_root, member):
    bundle = _build_bare_patch_zip({member: b"escape\n"})
    before = _snapshot_tree(apply_root)

    with pytest.raises(PathEscapeError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert _snapshot_tree(apply_root) == before


def test_bare_zip_member_symlink_entry_rejected_before_write(apply_root):
    bundle = _build_bare_patch_zip({"link": b"../outside"}, entry_file_types={"link": stat.S_IFLNK})
    before = _snapshot_tree(apply_root)

    with pytest.raises(PathEscapeError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert _snapshot_tree(apply_root) == before


def test_bare_zip_symlink_parent_escape_rejected_before_write(apply_root):
    outside_dir = apply_root.parent / f"{apply_root.name}-bare-outside-dir"
    shutil.rmtree(outside_dir, ignore_errors=True)
    outside_dir.mkdir(parents=True)
    try:
        (apply_root / "link").symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    bundle = _build_bare_patch_zip({"link/evil.txt": b"escape\n"})
    before = _snapshot_tree(apply_root)

    with pytest.raises(PathEscapeError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert not (outside_dir / "evil.txt").exists()
    assert _snapshot_tree(apply_root) == before
    shutil.rmtree(outside_dir, ignore_errors=True)


@pytest.mark.parametrize("member", ["ASK_CHATGPT_BUNDLE_README.md", ".ask-chatgpt-tmp/x"])
def test_bare_zip_reserved_member_rejected_before_write(apply_root, member):
    bundle = _build_bare_patch_zip({member: b"reserved\n"})
    before = _snapshot_tree(apply_root)

    with pytest.raises(PathEscapeError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert _snapshot_tree(apply_root) == before


def test_bare_zip_encrypted_member_rejected_before_write(apply_root):
    bundle = _with_encrypted_member_flag(_build_bare_patch_zip({"src/secret.txt": b"secret\n"}), "src/secret.txt")
    before = _snapshot_tree(apply_root)

    with pytest.raises(PatchMalformedError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert _snapshot_tree(apply_root) == before


def test_bare_zip_member_over_file_cap_rejected_before_write(apply_root):
    bundle = _build_bare_patch_zip({"big.bin": b"x" * (5 * 1024 * 1024 + 1)})
    before = _snapshot_tree(apply_root)

    with pytest.raises(OversizedPayloadError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert _snapshot_tree(apply_root) == before


def test_bare_zip_empty_no_manifest_no_members_fails_closed(apply_root):
    bundle = _build_bare_patch_zip({})

    with pytest.raises(PatchMalformedError):
        apply_patch(bundle, apply_root, dry_run=False)


def test_bare_zip_dry_run_writes_nothing(apply_root):
    (apply_root / "src").mkdir()
    (apply_root / "src" / "existing.txt").write_text("old\n", encoding="utf-8")
    before = _snapshot_tree(apply_root)
    bundle = _build_bare_patch_zip({"src/existing.txt": b"new\n", "src/added.txt": b"added\n"})

    summary = apply_patch(bundle, apply_root, dry_run=True)

    assert summary.dry_run is True
    assert summary.modified == 1
    assert summary.added == 1
    assert _snapshot_tree(apply_root) == before
    assert not (apply_root / ".ask-chatgpt-tmp").exists()


def test_manifest_present_still_enforces_declared_sha_mismatch(apply_root):
    bundle = _build_patch_zip(changed={"src/bad.txt": b"new\n"}, sha_overrides={"src/bad.txt": "0" * 64})
    before = _snapshot_tree(apply_root)

    with pytest.raises(BundleIntegrityError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert _snapshot_tree(apply_root) == before


def test_manifest_present_still_supports_deletions(apply_root):
    (apply_root / "docs").mkdir()
    (apply_root / "docs" / "obsolete.md").write_text("obsolete\n", encoding="utf-8")
    bundle = _build_patch_zip(deleted=("docs/obsolete.md",))

    summary = apply_patch(bundle, apply_root, dry_run=False)

    assert summary.deleted == 1
    assert not (apply_root / "docs" / "obsolete.md").exists()


def test_fenced_real_bare_format_roundtrips_via_reconstruction(mock_chatgpt, apply_root):
    result = _retrieve_scripted(mock_chatgpt, download_mode="missing", fenced_mode="ok")

    assert result is not None
    zip_bytes, bundle = result
    assert bundle.source == "fenced"
    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        assert "manifest.json" not in archive.namelist()
    summary = apply_patch(bundle, apply_root, dry_run=False)
    assert summary.added == 2


def test_download_missing_falls_back_to_valid_fenced_bundle(mock_chatgpt):
    result = _retrieve_scripted(mock_chatgpt, download_mode="missing", fenced_mode="ok")

    assert result is not None
    zip_bytes, bundle = result
    assert bundle.source == "fenced"
    assert bundle.content == zip_bytes
    assert bundle.byte_count == len(zip_bytes)
    assert bundle.sha256 == hashlib.sha256(zip_bytes).hexdigest()


def test_unmapped_download_artifact_selector_falls_back_to_valid_fenced_bundle(mock_chatgpt):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("patch response", download_mode="missing", fenced_mode="ok")
    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        session.send_prompt("return a patch bundle")
        session.wait_for_completion(timeout_s=3)
        session.selectors = _download_unavailable_map(session.selectors)

        result = retrieve_patch_bundle(session, timeout_s=3, download_wait_s=1.0)

    assert result is not None
    zip_bytes, bundle = result
    assert bundle.source == "fenced"
    assert bundle.content == zip_bytes
    assert bundle.byte_count == len(zip_bytes)
    assert bundle.sha256 == hashlib.sha256(zip_bytes).hexdigest()


def test_download_delayed_is_polled_with_bounded_wait_and_uses_download(mock_chatgpt):
    result = _retrieve_scripted(mock_chatgpt, download_mode="delayed", download_wait_s=2.0)

    assert result is not None
    _zip_bytes, bundle = result
    assert bundle.source == "download"
    assert bundle.filename.endswith(".zip")


def test_download_wrong_older_rejects_stale_artifact_and_uses_fallback_or_fails(mock_chatgpt):
    result = _retrieve_scripted(mock_chatgpt, download_mode="wrong_older", fenced_mode="ok")
    assert result is not None
    assert result[1].source == "fenced"

    with pytest.raises(PatchMalformedError):
        _retrieve_scripted(mock_chatgpt, download_mode="wrong_older")


@pytest.mark.parametrize("mode", ["corrupt", "truncated"])
def test_download_corrupt_and_truncated_artifacts_raise_patch_malformed(mock_chatgpt, mode):
    with pytest.raises(PatchMalformedError):
        _retrieve_scripted(mock_chatgpt, download_mode=mode)


def test_download_collision_is_ambiguous_and_does_not_choose_or_fallback(mock_chatgpt):
    with pytest.raises(PatchMalformedError):
        _retrieve_scripted(mock_chatgpt, download_mode="collision", fenced_mode="ok")


def test_download_unsupported_uses_valid_fenced_fallback_when_present(mock_chatgpt):
    result = _retrieve_scripted(mock_chatgpt, download_mode="unsupported", fenced_mode="ok")

    assert result is not None
    assert result[1].source == "fenced"


def test_download_unsupported_without_fallback_raises_download_unsupported(mock_chatgpt):
    with pytest.raises(DownloadUnsupportedError):
        _retrieve_scripted(mock_chatgpt, download_mode="unsupported")


def test_fenced_missing_end_raises_response_truncated_before_decode(mock_chatgpt):
    with pytest.raises(ResponseTruncatedError):
        _retrieve_scripted(mock_chatgpt, download_mode="missing", fenced_mode="missing_end")


def test_fenced_bad_hash_raises_bundle_integrity(mock_chatgpt):
    with pytest.raises(BundleIntegrityError):
        _retrieve_scripted(mock_chatgpt, download_mode="missing", fenced_mode="bad_hash")


def test_fenced_changed_and_unchanged_manifest_is_rejected(mock_chatgpt):
    with pytest.raises(PatchMalformedError):
        _retrieve_scripted(mock_chatgpt, download_mode="missing", fenced_mode="changed_and_unchanged")


def test_fenced_oversized_refuses_before_decode_with_test_cap(mock_chatgpt):
    caps = PatchBundleCaps(max_zip_bytes=64)
    with pytest.raises(OversizedPayloadError):
        _retrieve_scripted(mock_chatgpt, download_mode="missing", fenced_mode="oversized", caps=caps)


def test_zip_slip_absolute_path_raises_path_escape_and_writes_nothing_outside(apply_root):
    outside = apply_root.parent / f"{apply_root.name}-absolute-outside.txt"
    outside.unlink(missing_ok=True)
    bundle = _build_patch_zip(changed={str(outside.resolve()): b"escape\n"})
    before = _snapshot_tree(apply_root)

    with pytest.raises(PathEscapeError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert not outside.exists()
    assert _snapshot_tree(apply_root) == before


def test_zip_slip_parent_traversal_raises_path_escape_and_writes_nothing_outside(apply_root):
    outside = apply_root.parent / f"{apply_root.name}-traversal-outside.txt"
    outside.unlink(missing_ok=True)
    bundle = _build_patch_zip(changed={f"../{outside.name}": b"escape\n"})
    before = _snapshot_tree(apply_root)

    with pytest.raises(PathEscapeError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert not outside.exists()
    assert _snapshot_tree(apply_root) == before


def test_zip_slip_symlink_parent_escape_raises_path_escape_and_writes_nothing_outside(apply_root):
    outside_dir = apply_root.parent / f"{apply_root.name}-outside-dir"
    shutil.rmtree(outside_dir, ignore_errors=True)
    outside_dir.mkdir(parents=True)
    try:
        (apply_root / "link").symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    bundle = _build_patch_zip(changed={"link/evil.txt": b"escape\n"})
    before = _snapshot_tree(apply_root)

    with pytest.raises(PathEscapeError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert not (outside_dir / "evil.txt").exists()
    assert _snapshot_tree(apply_root) == before
    shutil.rmtree(outside_dir, ignore_errors=True)


def test_zip_symlink_entry_raises_path_escape_and_writes_nothing(apply_root):
    bundle = _build_patch_zip(changed={"link": b"../outside"}, entry_file_types={"link": stat.S_IFLNK})
    before = _snapshot_tree(apply_root)

    with pytest.raises(PathEscapeError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert _snapshot_tree(apply_root) == before


def test_late_validation_failure_leaves_apply_root_byte_for_byte_unchanged(apply_root):
    (apply_root / "src").mkdir()
    (apply_root / "src" / "first.txt").write_text("old first\n", encoding="utf-8")
    before = _snapshot_tree(apply_root)
    bundle = _build_patch_zip(
        changed={"src/first.txt": b"new first\n", "src/second.txt": b"new second\n"},
        sha_overrides={"src/second.txt": "0" * 64},
    )

    with pytest.raises(BundleIntegrityError):
        apply_patch(bundle, apply_root, dry_run=False)

    assert _snapshot_tree(apply_root) == before


def test_dry_run_returns_diff_summary_and_writes_nothing(apply_root):
    (apply_root / "src").mkdir()
    (apply_root / "docs").mkdir()
    (apply_root / "src" / "existing.txt").write_text("old\nline\n", encoding="utf-8")
    (apply_root / "docs" / "delete.txt").write_text("gone\n", encoding="utf-8")
    before = _snapshot_tree(apply_root)
    bundle = _build_patch_zip(
        changed={"src/existing.txt": b"new\nline\n", "src/added.txt": b"added\n"},
        deleted=("docs/delete.txt",),
        operations={"src/added.txt": "added", "src/existing.txt": "modified"},
    )

    summary = apply_patch(bundle, apply_root)

    assert summary.dry_run is True
    assert summary.root == apply_root.resolve()
    assert summary.added == 1
    assert summary.modified == 1
    assert summary.deleted == 1
    assert summary.total_files == 3
    assert [item.path for item in summary.files] == ["docs/delete.txt", "src/added.txt", "src/existing.txt"]
    by_path = {item.path: item for item in summary.files}
    assert by_path["src/added.txt"].change_kind == "added"
    assert by_path["src/added.txt"].old_sha256 is None
    assert by_path["src/added.txt"].new_sha256 == hashlib.sha256(b"added\n").hexdigest()
    assert by_path["docs/delete.txt"].change_kind == "deleted"
    assert by_path["docs/delete.txt"].new_sha256 is None
    assert _snapshot_tree(apply_root) == before
    assert not (apply_root / ".ask-chatgpt-tmp").exists()


def test_happy_path_valid_bundle_applies_modified_added_and_deleted_files(apply_root):
    (apply_root / "src").mkdir()
    (apply_root / "docs").mkdir()
    (apply_root / "src" / "existing.txt").write_text("old\n", encoding="utf-8")
    (apply_root / "docs" / "delete.txt").write_text("remove me\n", encoding="utf-8")
    bundle = _build_patch_zip(
        changed={"src/existing.txt": b"new\n", "src/added.txt": b"added\n"},
        deleted=("docs/delete.txt",),
        operations={"src/added.txt": "added", "src/existing.txt": "modified"},
    )

    summary = apply_patch(bundle, apply_root, dry_run=False)

    assert summary.dry_run is False
    assert summary.added == 1
    assert summary.modified == 1
    assert summary.deleted == 1
    assert (apply_root / "src" / "existing.txt").read_text(encoding="utf-8") == "new\n"
    assert (apply_root / "src" / "added.txt").read_text(encoding="utf-8") == "added\n"
    assert not (apply_root / "docs" / "delete.txt").exists()
