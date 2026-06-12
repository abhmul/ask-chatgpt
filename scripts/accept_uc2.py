#!/usr/bin/env python3
"""Scripted UC2 round-trip acceptance against the loopback mock ChatGPT server."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import traceback
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ask_chatgpt import AskChatGPTResult, DiffSummary, PatchBundle, apply_patch, ask_chatgpt  # noqa: E402
from tests.fixtures.mock_chatgpt import MockChatGPTServer  # noqa: E402

PATCH_CHANGED_FILES = {
    "src/app.txt": "new app contents\nsecond line\n",
    "src/added.txt": "brand new file\n",
}
PATCH_DELETED_FILES = ("docs/delete-me.txt",)
PATCH_OPERATIONS = {"src/app.txt": "modified", "src/added.txt": "added"}
UNCHANGED_BYTES = b"leave this file unchanged\n"
PROMPT = "Acceptance UC2: update the sample project using the returned patch bundle."


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


def _summary_json(summary: DiffSummary) -> dict[str, Any]:
    return {
        "root": str(summary.root),
        "dry_run": summary.dry_run,
        "files": [
            {
                "path": item.path,
                "change_kind": item.change_kind,
                "old_sha256": item.old_sha256,
                "new_sha256": item.new_sha256,
                "old_bytes": item.old_bytes,
                "new_bytes": item.new_bytes,
                "byte_delta": item.byte_delta,
                "lines_added": item.lines_added,
                "lines_deleted": item.lines_deleted,
            }
            for item in summary.files
        ],
        "added": summary.added,
        "modified": summary.modified,
        "deleted": summary.deleted,
        "total_files": summary.total_files,
        "total_byte_delta": summary.total_byte_delta,
        "total_bytes_changed": summary.total_bytes_changed,
    }


def _assert_expected_summary(summary: DiffSummary) -> None:
    if (summary.added, summary.modified, summary.deleted, summary.total_files) != (1, 1, 1, 3):
        raise AssertionError(f"unexpected diff counts: {_summary_json(summary)!r}")
    paths = [item.path for item in summary.files]
    if paths != ["docs/delete-me.txt", "src/added.txt", "src/app.txt"]:
        raise AssertionError(f"unexpected diff paths: {paths!r}")
    by_path = {item.path: item for item in summary.files}
    expected_kinds = {"docs/delete-me.txt": "deleted", "src/added.txt": "added", "src/app.txt": "modified"}
    actual_kinds = {path: by_path[path].change_kind for path in expected_kinds}
    if actual_kinds != expected_kinds:
        raise AssertionError(f"unexpected diff kinds: {actual_kinds!r}")


def _diff_match_evidence(root: Path) -> dict[str, Any]:
    modified = (root / "src" / "app.txt").read_text(encoding="utf-8")
    added = (root / "src" / "added.txt").read_text(encoding="utf-8")
    deleted_exists = (root / "docs" / "delete-me.txt").exists()
    unchanged = (root / "README.md").read_bytes()
    evidence = {
        "modified_path": "src/app.txt",
        "modified_matches": modified == PATCH_CHANGED_FILES["src/app.txt"],
        "modified_text": modified,
        "added_path": "src/added.txt",
        "added_matches": added == PATCH_CHANGED_FILES["src/added.txt"],
        "added_text": added,
        "deleted_path": "docs/delete-me.txt",
        "deleted_absent": not deleted_exists,
        "unchanged_path": "README.md",
        "unchanged_matches": unchanged == UNCHANGED_BYTES,
        "unchanged_sha256": _sha(unchanged),
    }
    evidence["overall_diff_matches"] = all(
        bool(evidence[key])
        for key in ("modified_matches", "added_matches", "deleted_absent", "unchanged_matches")
    )
    if not evidence["overall_diff_matches"]:
        raise AssertionError(f"applied tree diff did not match expected edit: {evidence!r}")
    return evidence


def _run_roundtrip(out_dir: Path, handle, *, name: str, expected_source: str, response_text: str, **script_fields: Any) -> dict[str, Any]:
    project_root = out_dir / f"{name}-project"
    _seed_project(project_root)
    handle.reset()
    handle.script_next_response(
        response_text,
        patch_changed_files=PATCH_CHANGED_FILES,
        patch_deleted_files=PATCH_DELETED_FILES,
        patch_operations=PATCH_OPERATIONS,
        **script_fields,
    )

    result = ask_chatgpt(
        PROMPT,
        channel="mock",
        base_url=handle.base_url,
        timeout_s=5,
        files=["README.md"],
        dirs=["src", "docs"],
        bundle_root=project_root,
    )
    if not isinstance(result, AskChatGPTResult):
        raise AssertionError(f"expected AskChatGPTResult, got {type(result).__name__}")
    if not isinstance(result.patch_bundle, PatchBundle):
        raise AssertionError("expected a patch bundle handle")
    if result.patch_bundle.source != expected_source:
        raise AssertionError(f"expected source={expected_source!r}, got {result.patch_bundle.source!r}")

    assistant_path = out_dir / f"{name}-assistant.txt"
    assistant_path.write_text(result.text, encoding="utf-8")
    patch_path = out_dir / f"{name}-patch-bundle.zip"
    patch_path.write_bytes(result.patch_bundle.content)
    inspect_after_api = handle.inspect()
    (out_dir / f"{name}-inspect-after-api.json").write_text(
        json.dumps(inspect_after_api, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    before_dry_run = _snapshot_tree(project_root)
    (out_dir / f"{name}-before-dry-run-tree.json").write_text(
        json.dumps(before_dry_run, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    dry_run_summary = apply_patch(result.patch_bundle, project_root, dry_run=True)
    _assert_expected_summary(dry_run_summary)
    after_dry_run = _snapshot_tree(project_root)
    if after_dry_run != before_dry_run:
        raise AssertionError("dry_run=True mutated the project tree")
    if (project_root / ".ask-chatgpt-tmp").exists():
        raise AssertionError("dry_run=True created a transaction directory")

    applied_summary = apply_patch(result.patch_bundle, project_root, dry_run=False)
    _assert_expected_summary(applied_summary)
    if applied_summary != replace(dry_run_summary, dry_run=False):
        raise AssertionError("dry_run and apply summaries differ beyond the dry_run flag")
    evidence = _diff_match_evidence(project_root)
    after_apply = _snapshot_tree(project_root)
    (out_dir / f"{name}-after-apply-tree.json").write_text(
        json.dumps(after_apply, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "detail": f"{name} round-trip returned, dry-ran, applied, and matched expected tree diff",
        "mock_base_url": handle.base_url,
        "mock_port": handle.port,
        "project_root": str(project_root),
        "assistant_text_path": str(assistant_path),
        "patch_bundle_path": str(patch_path),
        "patch_bundle": {
            "filename": result.patch_bundle.filename,
            "source": result.patch_bundle.source,
            "byte_count": result.patch_bundle.byte_count,
            "sha256": result.patch_bundle.sha256,
        },
        "upload": inspect_after_api.get("last_upload"),
        "dry_run_summary": _summary_json(dry_run_summary),
        "applied_summary": _summary_json(applied_summary),
        "diff_match_evidence": evidence,
    }


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

        _run_step(
            out_dir,
            steps,
            "download-primary-roundtrip",
            lambda: _run_roundtrip(
                out_dir,
                handle,
                name="download-primary",
                expected_source="download",
                response_text="PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip",
                download_mode="ok",
            ),
        )
        _run_step(
            out_dir,
            steps,
            "fenced-fallback-roundtrip",
            lambda: _run_roundtrip(
                out_dir,
                handle,
                name="fenced-fallback",
                expected_source="fenced",
                response_text="",
                download_mode="missing",
                fenced_mode="ok",
            ),
        )
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
