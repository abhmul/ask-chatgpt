from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid

import pytest

from ask_chatgpt import (
    AskChatGPTError,
    BundleIntegrityError,
    DownloadUnsupportedError,
    LoginRequiredError,
    ModelUnavailableError,
    OversizedPayloadError,
    PatchApplyError,
    PatchBundle,
    PatchBundleValidationError,
    PatchMalformedError,
    PathEscapeError,
    RateLimitedError,
    ResponseTruncatedError,
    SelectorUnavailableError,
    SessionNotFoundError,
    UploadUnsupportedError,
)
import ask_chatgpt.cli as cli

ROOT = Path(__file__).resolve().parents[1]
PATCH_CHANGED_FILES = {
    "src/app.txt": "new app contents\nsecond line\n",
    "src/added.txt": "brand new file\n",
}
PATCH_DELETED_FILES = ("docs/delete-me.txt",)
PATCH_OPERATIONS = {"src/app.txt": "modified", "src/added.txt": "added"}
UNCHANGED_BYTES = b"leave this file unchanged\n"


@pytest.fixture
def cli_project_root(request):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.node.name)[:80]
    root = ROOT / "tmp" / "test_cli" / f"{safe_name}-{uuid.uuid4().hex}"
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


def _script_patch_response(mock_chatgpt, *, response_text: str = "PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip", **fields) -> None:
    mock_chatgpt.script_next_response(
        response_text,
        patch_changed_files=PATCH_CHANGED_FILES,
        patch_deleted_files=PATCH_DELETED_FILES,
        patch_operations=PATCH_OPERATIONS,
        **fields,
    )


def _user_texts(snapshot, ref):
    return [t["text"] for t in snapshot["conversations"][ref]["turns"] if t["role"] == "user"]


def _assert_expected_summary(payload: dict[str, object], *, dry_run: bool) -> None:
    assert payload["dry_run"] is dry_run
    assert payload["added"] == 1
    assert payload["modified"] == 1
    assert payload["deleted"] == 1
    assert payload["total_files"] == 3
    files = payload["files"]
    assert isinstance(files, list)
    assert [item["path"] for item in files] == ["docs/delete-me.txt", "src/added.txt", "src/app.txt"]
    assert {item["path"]: item["change_kind"] for item in files} == {
        "docs/delete-me.txt": "deleted",
        "src/added.txt": "added",
        "src/app.txt": "modified",
    }


def _assert_project_applied(root: Path) -> None:
    assert (root / "src" / "app.txt").read_text(encoding="utf-8") == PATCH_CHANGED_FILES["src/app.txt"]
    assert (root / "src" / "added.txt").read_text(encoding="utf-8") == PATCH_CHANGED_FILES["src/added.txt"]
    assert not (root / "docs" / "delete-me.txt").exists()
    assert (root / "README.md").read_bytes() == UNCHANGED_BYTES


def test_main_prompt_writes_only_response_stdout(mock_chatgpt, capsys):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("CLI text answer")

    code = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--model-settings",
        '{"model":"mock-default"}',
        "hello from cli",
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "CLI text answer"
    assert captured.err == ""


def test_main_session_reuses_same_conversation_through_cli(mock_chatgpt, tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("ASK_CHATGPT_STATE_DIR", str(state_dir))
    mock_chatgpt.reset()

    mock_chatgpt.script_next_response("first answer")
    code1 = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--session",
        "sess-A",
        "first prompt",
    ])
    captured = capsys.readouterr()
    assert code1 == 0
    assert captured.out == "first answer"
    assert captured.err == ""

    mock_chatgpt.script_next_response("second answer")
    code2 = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--session",
        "sess-A",
        "second prompt",
    ])
    captured = capsys.readouterr()
    assert code2 == 0
    assert captured.out == "second answer"
    assert captured.err == ""

    snapshot = mock_chatgpt.inspect()
    conversations = snapshot["conversations"]
    assert len(conversations) == 1
    sess_a_ref = next(iter(conversations))
    assert _user_texts(snapshot, sess_a_ref) == ["first prompt", "second prompt"]

    registry_path = state_dir / "sessions.json"
    assert registry_path.exists()

    mock_chatgpt.script_next_response("different answer")
    code3 = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--session",
        "sess-B",
        "different prompt",
    ])
    captured = capsys.readouterr()
    assert code3 == 0
    assert captured.out == "different answer"
    assert captured.err == ""

    snapshot = mock_chatgpt.inspect()
    conversations = snapshot["conversations"]
    assert len(conversations) == 2
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    sess_a_ref = registry["sessions"]["sess-A"]["conversation_ref"]
    sess_b_ref = registry["sessions"]["sess-B"]["conversation_ref"]
    assert sess_a_ref != sess_b_ref
    assert _user_texts(snapshot, sess_a_ref) == ["first prompt", "second prompt"]
    assert _user_texts(snapshot, sess_b_ref) == ["different prompt"]


def test_main_out_writes_response_file_without_stdout(mock_chatgpt, cli_project_root, capsys):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("file-only response")
    out_path = cli_project_root / "assistant.txt"

    code = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--prompt",
        "write to out",
        "--out",
        str(out_path),
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err == ""
    assert out_path.read_text(encoding="utf-8") == "file-only response"


def test_files_without_apply_does_not_mutate_by_default(mock_chatgpt, cli_project_root, capsys):
    _seed_project(cli_project_root)
    before = _snapshot_tree(cli_project_root)
    mock_chatgpt.reset()
    _script_patch_response(mock_chatgpt, download_mode="ok")
    readme = (cli_project_root / "README.md").relative_to(ROOT).as_posix()
    src_dir = (cli_project_root / "src").relative_to(ROOT).as_posix()

    code = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--files",
        readme,
        "--dirs",
        src_dir,
        "default bundle mode",
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip"
    assert captured.err == ""
    assert _snapshot_tree(cli_project_root) == before
    assert not (cli_project_root / ".ask-chatgpt-tmp").exists()


def test_dry_run_prints_diff_summary_and_writes_nothing(mock_chatgpt, cli_project_root, capsys):
    _seed_project(cli_project_root)
    before = _snapshot_tree(cli_project_root)
    mock_chatgpt.reset()
    _script_patch_response(mock_chatgpt, download_mode="ok")

    code = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--root",
        str(cli_project_root),
        "--files",
        "README.md",
        "--dirs",
        "src",
        "--dirs",
        "docs",
        "--dry-run",
        "dry-run bundle mode",
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["root"] == str(cli_project_root.resolve())
    _assert_expected_summary(payload, dry_run=True)
    assert _snapshot_tree(cli_project_root) == before
    assert not (cli_project_root / ".ask-chatgpt-tmp").exists()


def test_apply_requires_root_before_browser_side_effects(mock_chatgpt, cli_project_root, capsys):
    _seed_project(cli_project_root)
    before = _snapshot_tree(cli_project_root)
    mock_chatgpt.reset()

    code = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--files",
        (cli_project_root / "README.md").relative_to(ROOT).as_posix(),
        "--apply",
        "missing root",
    ])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "--root" in captured.err
    assert _snapshot_tree(cli_project_root) == before
    inspected = mock_chatgpt.inspect()
    assert inspected["last_upload"] is None
    assert inspected["conversations"] == {}


def test_apply_and_dry_run_are_mutually_exclusive(cli_project_root, capsys):
    code = cli.main([
        "--root",
        str(cli_project_root),
        "--files",
        "README.md",
        "--apply",
        "--dry-run",
        "bad flags",
    ])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "not allowed with argument" in captured.err


def test_dry_run_requires_files_and_explicit_root(capsys):
    code = cli.main(["--dry-run", "no files"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "--files/--dirs" in captured.err

    code = cli.main(["--files", "README.md", "--dry-run", "no root"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "--root" in captured.err


def test_apply_with_root_prints_json_summary_and_mutates_only_then(mock_chatgpt, cli_project_root, capsys):
    _seed_project(cli_project_root)
    mock_chatgpt.reset()
    _script_patch_response(mock_chatgpt, download_mode="ok")

    code = cli.main([
        "--channel",
        "mock",
        "--base-url",
        mock_chatgpt.base_url,
        "--timeout",
        "5",
        "--root",
        str(cli_project_root),
        "--files",
        "README.md",
        "--dirs",
        "src",
        "--dirs",
        "docs",
        "--apply",
        "apply bundle mode",
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    _assert_expected_summary(payload, dry_run=False)
    _assert_project_applied(cli_project_root)


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--prompt", "option", "positional"], "mutually exclusive"),
        (["--model-settings", "[]", "prompt"], "JSON object"),
        ([], "required"),
    ],
)
def test_usage_errors_return_two_without_browser(argv, message, capsys):
    code = cli.main(argv)
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert message in captured.err


@pytest.mark.parametrize(
    ("error_cls", "exit_code"),
    [
        (LoginRequiredError, 3),
        (SessionNotFoundError, 4),
        (ModelUnavailableError, 5),
        (RateLimitedError, 6),
        (ResponseTruncatedError, 7),
        (SelectorUnavailableError, 8),
        (UploadUnsupportedError, 9),
        (DownloadUnsupportedError, 10),
        (PatchBundleValidationError, 11),
        (PatchMalformedError, 11),
        (BundleIntegrityError, 11),
        (OversizedPayloadError, 11),
        (PathEscapeError, 11),
        (PatchApplyError, 12),
        (AskChatGPTError, 1),
    ],
)
def test_named_errors_map_to_exit_codes(monkeypatch, capsys, error_cls, exit_code):
    def raise_error(*_args, **_kwargs):
        raise error_cls("safe synthetic detail")

    monkeypatch.setattr(cli, "ask_chatgpt", raise_error)

    code = cli.main(["prompt"])

    captured = capsys.readouterr()
    assert code == exit_code
    assert captured.out == ""
    assert error_cls.__name__ in captured.err
    assert "safe synthetic detail" in captured.err
    assert "cookie" not in captured.err.lower()
    assert "token" not in captured.err.lower()


def test_apply_patch_error_maps_to_exit_code(monkeypatch, capsys, cli_project_root):
    bundle = PatchBundle(filename="patch-bundle.zip", content=b"", sha256="0" * 64, byte_count=0, source="fenced")

    def fake_ask(*_args, **_kwargs):
        return cli.AskChatGPTResult(text="assistant text", patch_bundle=bundle)

    def fake_apply(*_args, **_kwargs):
        raise PatchApplyError("safe apply failure")

    monkeypatch.setattr(cli, "ask_chatgpt", fake_ask)
    monkeypatch.setattr(cli, "apply_patch", fake_apply)

    code = cli.main([
        "--root",
        str(cli_project_root),
        "--files",
        "README.md",
        "--apply",
        "prompt",
    ])

    captured = capsys.readouterr()
    assert code == 12
    assert captured.out == ""
    assert "PatchApplyError" in captured.err
    assert "safe apply failure" in captured.err


def test_subprocess_module_prompt_stdout_and_out(mock_chatgpt, cli_project_root):
    mock_chatgpt.reset()
    mock_chatgpt.script_next_response("subprocess stdout response")
    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "ask_chatgpt.cli",
            "--channel",
            "mock",
            "--base-url",
            mock_chatgpt.base_url,
            "--timeout",
            "5",
            "subprocess prompt",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert first.returncode == 0
    assert first.stdout == "subprocess stdout response"
    assert first.stderr == ""

    out_path = cli_project_root / "subprocess-out.txt"
    mock_chatgpt.script_next_response("subprocess file response")
    second = subprocess.run(
        [
            sys.executable,
            "-m",
            "ask_chatgpt.cli",
            "--channel",
            "mock",
            "--base-url",
            mock_chatgpt.base_url,
            "--timeout",
            "5",
            "--prompt",
            "subprocess out prompt",
            "--out",
            str(out_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert second.returncode == 0
    assert second.stdout == ""
    assert second.stderr == ""
    assert out_path.read_text(encoding="utf-8") == "subprocess file response"
