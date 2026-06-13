from __future__ import annotations

from dataclasses import replace
import os
import re
import shutil
import stat
import uuid
from pathlib import Path

import pytest

from ask_chatgpt import AskChatGPTResult, apply_patch, ask_chatgpt
from ask_chatgpt.patch import PatchBundle


PATCH_CHANGED_FILES = {
    "src/app.txt": "new app contents\nsecond line\n",
    "src/added.txt": "brand new file\n",
}
PATCH_DELETED_FILES = ("docs/delete-me.txt",)
PATCH_OPERATIONS = {"src/app.txt": "modified", "src/added.txt": "added"}
UNCHANGED_BYTES = b"leave this file unchanged\n"


@pytest.fixture
def uc2_root(request):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.node.name)[:80]
    root = Path("tmp") / "test_uc2_roundtrip" / f"{safe_name}-{uuid.uuid4().hex}"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _seed_project(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "src" / "app.txt").write_bytes(b"old app contents\nsecond line\n")
    (root / "docs" / "delete-me.txt").write_bytes(b"delete this file\n")
    (root / "README.md").write_bytes(UNCHANGED_BYTES)


def _snapshot_tree(root: Path) -> dict[str, tuple[str, bytes | str | None]]:
    snapshot: dict[str, tuple[str, bytes | str | None]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            snapshot[rel] = ("symlink", os.readlink(path))
        elif stat.S_ISREG(mode):
            snapshot[rel] = ("file", path.read_bytes())
        elif stat.S_ISDIR(mode):
            snapshot[rel] = ("dir", None)
        else:
            snapshot[rel] = ("other", None)
    return snapshot


def _assert_diff_match(root: Path) -> None:
    assert (root / "src" / "app.txt").read_text(encoding="utf-8") == PATCH_CHANGED_FILES["src/app.txt"]
    assert (root / "src" / "added.txt").read_text(encoding="utf-8") == PATCH_CHANGED_FILES["src/added.txt"]
    assert not (root / "docs" / "delete-me.txt").exists()
    assert (root / "README.md").read_bytes() == UNCHANGED_BYTES


def _assert_expected_summary(summary) -> None:
    assert summary.added == 1
    assert summary.modified == 1
    assert summary.deleted == 1
    assert summary.total_files == 3
    assert [item.path for item in summary.files] == ["docs/delete-me.txt", "src/added.txt", "src/app.txt"]
    by_path = {item.path: item for item in summary.files}
    assert by_path["src/app.txt"].change_kind == "modified"
    assert by_path["src/added.txt"].change_kind == "added"
    assert by_path["docs/delete-me.txt"].change_kind == "deleted"
    assert by_path["src/added.txt"].old_sha256 is None
    assert by_path["docs/delete-me.txt"].new_sha256 is None


def _run_public_api_roundtrip(mock_chatgpt, root: Path, *, response_text: str, expected_source: str, **script_fields):
    _seed_project(root)
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(
        response_text,
        patch_changed_files=PATCH_CHANGED_FILES,
        patch_deleted_files=PATCH_DELETED_FILES,
        patch_operations=PATCH_OPERATIONS,
        **script_fields,
    )

    result = ask_chatgpt(
        "Update the sample project using the returned patch bundle.",
        channel="mock",
        base_url=mock_chatgpt.base_url,
        timeout_s=5,
        files=["README.md"],
        dirs=["src", "docs"],
        bundle_root=root,
    )

    assert isinstance(result, AskChatGPTResult)
    assert isinstance(result.patch_bundle, PatchBundle)
    assert result.patch_bundle.source == expected_source
    assert result.patch_bundle.byte_count == len(result.patch_bundle.content)

    inspected = mock_chatgpt.inspect()
    assert inspected["last_upload"] is not None
    assert inspected["last_upload"]["filename"].startswith("ask-chatgpt-bundle-")
    conversation = inspected["conversations"][inspected["selected_conversation_ref"]]
    user_prompts = [turn["text"] for turn in conversation["turns"] if turn["role"] == "user"]
    assert "I uploaded a zip project-context bundle" in user_prompts[-1]
    assert "Update the sample project using the returned patch bundle." in user_prompts[-1]

    before_dry_run = _snapshot_tree(root)
    dry_run_summary = apply_patch(result.patch_bundle, root, dry_run=True)
    _assert_expected_summary(dry_run_summary)
    assert dry_run_summary.dry_run is True
    assert _snapshot_tree(root) == before_dry_run
    assert not (root / ".ask-chatgpt-tmp").exists()

    applied_summary = apply_patch(result.patch_bundle, root, dry_run=False)
    _assert_expected_summary(applied_summary)
    assert applied_summary == replace(dry_run_summary, dry_run=False)
    _assert_diff_match(root)
    return result, dry_run_summary, applied_summary


def test_uc2_roundtrip_download_primary_public_api_dry_run_and_apply(mock_chatgpt, uc2_root):
    result, _dry_run, _applied = _run_public_api_roundtrip(
        mock_chatgpt,
        uc2_root,
        response_text="PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip",
        expected_source="download",
        download_mode="ok",
    )

    assert result.text == "PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip"


def test_uc2_roundtrip_opaque_download_public_api_dry_run_and_apply(mock_chatgpt, uc2_root):
    source_text = 'favorite_color = "red"\nsibling_line = "unchanged"\n'
    expected_text = 'favorite_color = "blue"\nsibling_line = "unchanged"\n'
    source_path = uc2_root / "src" / "preferences.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source_text, encoding="utf-8")

    mock_chatgpt.reset()
    mock_chatgpt.script_next_response(
        "PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip",
        download_mode="opaque",
        patch_changed_files={"src/preferences.py": expected_text},
        patch_operations={"src/preferences.py": "modified"},
    )

    result = ask_chatgpt(
        "Update favorite_color using the returned patch bundle.",
        files=["src/preferences.py"],
        channel="mock",
        base_url=mock_chatgpt.base_url,
        timeout_s=5,
        bundle_root=uc2_root,
    )

    assert isinstance(result, AskChatGPTResult)
    assert isinstance(result.patch_bundle, PatchBundle)
    assert result.patch_bundle.source == "download"

    dry_run_summary = apply_patch(result.patch_bundle, root=uc2_root, dry_run=True)
    assert dry_run_summary.modified == 1
    assert source_path.read_text(encoding="utf-8") == source_text

    applied_summary = apply_patch(result.patch_bundle, root=uc2_root, dry_run=False)
    assert applied_summary.modified == 1
    assert source_path.read_text(encoding="utf-8") == expected_text
    assert 'sibling_line = "unchanged"' in source_path.read_text(encoding="utf-8")


def test_uc2_roundtrip_fenced_fallback_public_api_dry_run_and_apply(mock_chatgpt, uc2_root):
    result, _dry_run, _applied = _run_public_api_roundtrip(
        mock_chatgpt,
        uc2_root,
        response_text="",
        expected_source="fenced",
        download_mode="missing",
        fenced_mode="ok",
    )

    assert "BEGIN_PATCH_BUNDLE" in result.text
    assert "END_PATCH_BUNDLE" in result.text
