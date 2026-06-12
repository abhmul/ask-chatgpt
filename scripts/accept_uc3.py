#!/usr/bin/env python3
"""Scripted UC3 CLI acceptance against the loopback mock ChatGPT server."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import traceback
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.fixtures.mock_chatgpt import MockChatGPTServer  # noqa: E402

PATCH_CHANGED_FILES = {
    "src/app.txt": "new app contents\nsecond line\n",
    "src/added.txt": "brand new file\n",
}
PATCH_DELETED_FILES = ("docs/delete-me.txt",)
PATCH_OPERATIONS = {"src/app.txt": "modified", "src/added.txt": "added"}
UNCHANGED_BYTES = b"leave this file unchanged\n"


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "step"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seed_project(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "src" / "app.txt").write_bytes(b"old app contents\nsecond line\n")
    (root / "docs" / "delete-me.txt").write_bytes(b"delete this file\n")
    (root / "README.md").write_bytes(UNCHANGED_BYTES)


def _snapshot_tree(root: Path) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            snapshot[rel] = {"type": "symlink", "target": os.readlink(path)}
        elif stat.S_ISREG(mode):
            data = path.read_bytes()
            item: dict[str, Any] = {"type": "file", "byte_count": len(data), "sha256": _sha(data)}
            try:
                item["text"] = data.decode("utf-8")
            except UnicodeDecodeError:
                item["text"] = None
            snapshot[rel] = item
        elif stat.S_ISDIR(mode):
            snapshot[rel] = {"type": "dir"}
        else:
            snapshot[rel] = {"type": "other"}
    return snapshot


def _script_patch_response(handle, *, response_text: str = "PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip", **fields: Any) -> None:
    handle.script_next_response(
        response_text,
        patch_changed_files=PATCH_CHANGED_FILES,
        patch_deleted_files=PATCH_DELETED_FILES,
        patch_operations=PATCH_OPERATIONS,
        **fields,
    )


def _run_cli(out_dir: Path, name: str, args: list[str], *, timeout: float = 45.0) -> dict[str, Any]:
    command = ["uv", "run", "ask-chatgpt", *args]
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    safe = _safe_name(name)
    stdout_path = out_dir / f"{safe}-stdout.txt"
    stderr_path = out_dir / f"{safe}-stderr.txt"
    command_path = out_dir / f"{safe}-command.json"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    command_data = {
        "command": command,
        "cwd": str(ROOT),
        "returncode": proc.returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    command_path.write_text(json.dumps(command_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**command_data, "stdout": proc.stdout, "stderr": proc.stderr, "command_path": str(command_path)}


def _assert_expected_summary(summary: dict[str, Any], project_root: Path) -> None:
    if summary.get("root") != str(project_root.resolve()):
        raise AssertionError(f"unexpected root in summary: {summary.get('root')!r}")
    expected_counts = {"dry_run": True, "added": 1, "modified": 1, "deleted": 1, "total_files": 3}
    actual_counts = {key: summary.get(key) for key in expected_counts}
    if actual_counts != expected_counts:
        raise AssertionError(f"unexpected diff counts: {actual_counts!r}")
    files = summary.get("files")
    if not isinstance(files, list):
        raise AssertionError(f"summary files was not a list: {type(files).__name__}")
    paths = [item.get("path") for item in files if isinstance(item, dict)]
    if paths != ["docs/delete-me.txt", "src/added.txt", "src/app.txt"]:
        raise AssertionError(f"unexpected diff paths: {paths!r}")
    kinds = {item["path"]: item["change_kind"] for item in files if isinstance(item, dict)}
    expected_kinds = {"docs/delete-me.txt": "deleted", "src/added.txt": "added", "src/app.txt": "modified"}
    if kinds != expected_kinds:
        raise AssertionError(f"unexpected diff kinds: {kinds!r}")


def _run_step(out_dir: Path, steps: list[dict[str, Any]], name: str, func: Callable[[], dict[str, Any]]) -> None:
    print(f"STEP {name}: start", flush=True)
    try:
        data = func()
        step = {"name": name, "status": "pass", "detail": data.get("detail", "ok"), "data": data}
        print(f"STEP {name}: pass", flush=True)
    except Exception as exc:  # noqa: BLE001 - acceptance must preserve raw failure detail.
        step = {
            "name": name,
            "status": "fail",
            "detail": str(exc),
            "error_type": exc.__class__.__name__,
            "traceback": traceback.format_exc(),
        }
        print(f"STEP {name}: fail: {exc.__class__.__name__}: {exc}", flush=True)
    (out_dir / f"{_safe_name(name)}.json").write_text(json.dumps(step, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    steps.append(step)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="artifact output directory")
    args = parser.parse_args(argv)
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    steps: list[dict[str, Any]] = []
    server = MockChatGPTServer().start()
    try:
        handle = server.make_handle()
        print(f"artifact_dir={out_dir}", flush=True)
        print(f"mock_base_url={handle.base_url}", flush=True)
        print(f"mock_port={handle.port}", flush=True)

        def prompt_stdout() -> dict[str, Any]:
            handle.reset()
            expected = "accept UC3 prompt response"
            handle.script_next_response(expected)
            run = _run_cli(
                out_dir,
                "prompt-stdout",
                ["--channel", "mock", "--base-url", handle.base_url, "--timeout", "5", "accept UC3 prompt"],
            )
            if run["returncode"] != 0:
                raise AssertionError(f"CLI returned {run['returncode']}: stderr={run['stderr']!r}")
            if run["stdout"] != expected:
                raise AssertionError(f"unexpected stdout: {run['stdout']!r}")
            if run["stderr"]:
                raise AssertionError(f"unexpected stderr: {run['stderr']!r}")
            return {"detail": "prompt call printed only assistant text", "returned_text": run["stdout"], "subprocess": run}

        def out_file_call() -> dict[str, Any]:
            handle.reset()
            expected = "accept UC3 out-file response"
            out_file = out_dir / "assistant-out.txt"
            handle.script_next_response(expected)
            run = _run_cli(
                out_dir,
                "out-file",
                [
                    "--channel",
                    "mock",
                    "--base-url",
                    handle.base_url,
                    "--timeout",
                    "5",
                    "--prompt",
                    "accept UC3 out prompt",
                    "--out",
                    str(out_file),
                ],
            )
            if run["returncode"] != 0:
                raise AssertionError(f"CLI returned {run['returncode']}: stderr={run['stderr']!r}")
            if run["stdout"] != "":
                raise AssertionError(f"expected empty stdout with --out, got {run['stdout']!r}")
            if run["stderr"]:
                raise AssertionError(f"unexpected stderr: {run['stderr']!r}")
            actual = out_file.read_text(encoding="utf-8")
            if actual != expected:
                raise AssertionError(f"unexpected --out file contents: {actual!r}")
            return {"detail": "--out wrote assistant text and left stdout empty", "out_file": str(out_file), "returned_text": actual, "subprocess": run}

        def files_dry_run() -> dict[str, Any]:
            handle.reset()
            project_root = out_dir / "dry-run-project"
            _seed_project(project_root)
            before = _snapshot_tree(project_root)
            (out_dir / "dry-run-before-tree.json").write_text(json.dumps(before, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            _script_patch_response(handle, download_mode="ok")
            run = _run_cli(
                out_dir,
                "files-dry-run",
                [
                    "--channel",
                    "mock",
                    "--base-url",
                    handle.base_url,
                    "--timeout",
                    "5",
                    "--root",
                    str(project_root),
                    "--files",
                    "README.md",
                    "--dirs",
                    "src",
                    "--dirs",
                    "docs",
                    "--dry-run",
                    "accept UC3 dry-run bundle prompt",
                ],
            )
            if run["returncode"] != 0:
                raise AssertionError(f"CLI returned {run['returncode']}: stderr={run['stderr']!r}")
            if run["stderr"]:
                raise AssertionError(f"unexpected stderr: {run['stderr']!r}")
            summary = json.loads(run["stdout"])
            _assert_expected_summary(summary, project_root)
            after = _snapshot_tree(project_root)
            (out_dir / "dry-run-after-tree.json").write_text(json.dumps(after, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (out_dir / "dry-run-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if after != before:
                raise AssertionError("--dry-run mutated the project tree")
            if (project_root / ".ask-chatgpt-tmp").exists():
                raise AssertionError("--dry-run created a transaction directory")
            return {"detail": "--files --dry-run printed diff summary without mutation", "project_root": str(project_root), "summary": summary, "subprocess": run}

        _run_step(out_dir, steps, "prompt-stdout", prompt_stdout)
        _run_step(out_dir, steps, "out-file", out_file_call)
        _run_step(out_dir, steps, "files-dry-run-no-mutation", files_dry_run)
    finally:
        server.stop()

    overall = "pass" if all(step["status"] == "pass" for step in steps) else "fail"
    result = {"overall": overall, "steps": steps}
    (out_dir / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"overall={overall}", flush=True)
    print(f"results_json={out_dir / 'results.json'}", flush=True)
    return 0 if overall == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
