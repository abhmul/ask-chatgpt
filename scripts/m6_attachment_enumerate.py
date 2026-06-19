#!/usr/bin/env python3
"""Offline M6-T3 attachment reference enumerator.

Loads a cached ChatGPT raw-mapping.json and emits only sanitized reference shapes.
No network is used. Full refs can optionally be written to a /tmp scratch file for
attended probing; they are never printed.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

KINDS = ("user_upload", "file_reference", "generated_asset", "code_execution_output")


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _iter_current_branch_node_ids(raw: Mapping[str, Any]) -> list[str]:
    mapping = _mapping(raw.get("mapping"))
    node_id = raw.get("current_node")
    branch: list[str] = []
    seen: set[str] = set()
    while node_id:
        if not isinstance(node_id, str):
            raise ValueError("current branch contains a non-string node id")
        if node_id in seen:
            raise ValueError("cycle in current branch")
        seen.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, Mapping):
            raise ValueError("current branch references a missing node")
        branch.append(node_id)
        parent = node.get("parent")
        if parent is not None and not isinstance(parent, str):
            raise ValueError("node parent must be string or null")
        node_id = parent
    return list(reversed(branch))


def _attachments_for_message(node_id: str, message: Mapping[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    metadata = _mapping(message.get("metadata"))
    for index, item in enumerate(_list(metadata.get("attachments"))):
        if not isinstance(item, Mapping):
            continue
        refs.append(
            {
                "source_kind": "user_upload",
                "source_ref": _optional_str(item.get("id")),
                "raw_path": f"/mapping/{node_id}/message/metadata/attachments/{index}",
                "filename_present": _optional_str(item.get("name")) is not None,
                "mime_present": (_optional_str(item.get("mime_type")) or _optional_str(item.get("mime"))) is not None,
                "bytes_present": _optional_int(item.get("size")) is not None,
            }
        )
    for index, item in enumerate(_list(metadata.get("content_references"))):
        if not isinstance(item, Mapping) or item.get("type") != "file":
            continue
        refs.append(
            {
                "source_kind": "file_reference",
                "source_ref": _optional_str(item.get("id")),
                "raw_path": f"/mapping/{node_id}/message/metadata/content_references/{index}",
                "filename_present": _optional_str(item.get("name")) is not None,
                "mime_present": (_optional_str(item.get("mime_type")) or _optional_str(item.get("mime"))) is not None,
                "bytes_present": _optional_int(item.get("size")) is not None,
                "metadata_keys": sorted(str(key) for key in item.keys() if key not in {"type", "id", "name", "size", "mime", "mime_type"}),
            }
        )
    content = message.get("content")
    if isinstance(content, Mapping):
        for index, asset in enumerate(_list(content.get("assets"))):
            if not isinstance(asset, Mapping):
                continue
            refs.append(
                {
                    "source_kind": "generated_asset",
                    "source_ref": _optional_str(asset.get("asset_pointer")),
                    "raw_path": f"/mapping/{node_id}/message/content/assets/{index}",
                    "filename_present": (_optional_str(asset.get("filename")) or _optional_str(asset.get("name"))) is not None,
                    "mime_present": (_optional_str(asset.get("content_type")) or _optional_str(asset.get("mime"))) is not None,
                    "bytes_present": (_optional_int(asset.get("size_bytes")) or _optional_int(asset.get("size"))) is not None,
                }
            )
    aggregate = metadata.get("aggregate_result")
    if isinstance(aggregate, Mapping):
        run_id = _optional_str(aggregate.get("run_id"))
        refs.append(
            {
                "source_kind": "code_execution_output",
                "source_ref": run_id,
                "raw_path": f"/mapping/{node_id}/message/metadata/aggregate_result",
                "filename_present": run_id is not None,
                "mime_present": True,
                "bytes_present": False,
            }
        )
    return refs


def _scheme_or_prefix(value: str | None) -> str:
    if value is None:
        return "missing"
    total = len(value)
    if "://" in value:
        scheme, rest = value.split("://", 1)
        rest_shape = _scheme_or_prefix(rest).split(" (len=", 1)[0]
        return f"{scheme}://{rest_shape} (len={total})"
    for literal in ("file-", "file_", "run-", "run_", "sandbox:"):
        if value.startswith(literal):
            return f"{literal}… (len={total})"
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value):
        return f"uuid-like (len={total})"
    match = re.match(r"^([A-Za-z]+[-_])", value)
    if match:
        return f"{match.group(1)}… (len={total})"
    classes = []
    if any(ch.isalpha() for ch in value):
        classes.append("alpha")
    if any(ch.isdigit() for ch in value):
        classes.append("digit")
    if any(not ch.isalnum() for ch in value):
        classes.append("punct")
    return f"{'+'.join(classes) or 'empty'} (len={total})"


def _source_route_hint(source_ref: str | None) -> dict[str, str | None]:
    if not source_ref:
        return {"probe_kind": None, "probe_ref": None}
    if source_ref.startswith("file-service://"):
        return {"probe_kind": "file_id", "probe_ref": source_ref.removeprefix("file-service://")}
    if source_ref.startswith("file-") or source_ref.startswith("file_"):
        return {"probe_kind": "file_id", "probe_ref": source_ref}
    if "://" in source_ref:
        scheme = source_ref.split("://", 1)[0]
        return {"probe_kind": f"scheme:{scheme}", "probe_ref": source_ref}
    return {"probe_kind": "raw_ref", "probe_ref": source_ref}


def enumerate_refs(raw_path: Path, *, scope: str) -> tuple[list[dict[str, Any]], int]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    mapping = _mapping(raw.get("mapping"))
    node_ids = _iter_current_branch_node_ids(raw) if scope == "current-branch" else list(mapping)
    refs: list[dict[str, Any]] = []
    for node_id in node_ids:
        node = mapping.get(node_id)
        message = _mapping(node.get("message")) if isinstance(node, Mapping) else {}
        if not message:
            continue
        refs.extend(_attachments_for_message(node_id, message))
    return refs, len(node_ids)


def summarize(refs: list[dict[str, Any]], *, scope: str, node_count: int) -> dict[str, Any]:
    by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in KINDS}
    for ref in refs:
        by_kind.setdefault(str(ref.get("source_kind")), []).append(ref)
    out: dict[str, Any] = {"scope": scope, "node_count": node_count, "source_kinds": {}}
    for kind in KINDS:
        items = by_kind.get(kind, [])
        examples: list[dict[str, Any]] = []
        seen_shapes: set[tuple[Any, ...]] = set()
        for item in items:
            shape = (
                _scheme_or_prefix(item.get("source_ref") if isinstance(item.get("source_ref"), str) else None),
                bool(item.get("bytes_present")),
                bool(item.get("mime_present")),
                bool(item.get("filename_present")),
            )
            if shape in seen_shapes:
                continue
            seen_shapes.add(shape)
            example = {
                "ref_format": shape[0],
                "bytes_present": shape[1],
                "mime_present": shape[2],
                "filename_present": shape[3],
            }
            if kind == "file_reference":
                keys = item.get("metadata_keys")
                if isinstance(keys, list):
                    example["extra_metadata_keys"] = keys
            examples.append(example)
            if len(examples) >= 3:
                break
        distinct_nonempty_refs = len({item.get("source_ref") for item in items if isinstance(item.get("source_ref"), str) and item.get("source_ref")})
        out["source_kinds"][kind] = {
            "count": len(items),
            "distinct_nonempty_refs": distinct_nonempty_refs,
            "bytes_present_count": sum(1 for item in items if item.get("bytes_present")),
            "mime_present_count": sum(1 for item in items if item.get("mime_present")),
            "filename_present_count": sum(1 for item in items if item.get("filename_present")),
            "examples": examples,
        }
    return out


def representative_refs(refs: list[dict[str, Any]]) -> dict[str, dict[str, str | None]]:
    reps: dict[str, dict[str, str | None]] = {}
    for kind in KINDS:
        for item in refs:
            if item.get("source_kind") != kind:
                continue
            source_ref = item.get("source_ref") if isinstance(item.get("source_ref"), str) else None
            hint = _source_route_hint(source_ref)
            if source_ref:
                reps[kind] = {"source_ref": source_ref, **hint}
                break
    return reps


def main() -> int:
    parser = argparse.ArgumentParser(description="Sanitize/enumerate cached raw-mapping attachment refs without network I/O.")
    parser.add_argument("raw_mapping", type=Path)
    parser.add_argument("--scope", choices=("current-branch", "all-mapping"), default="current-branch")
    parser.add_argument("--scratch-refs", type=Path, help="Optional /tmp JSON for full representative refs; not safe to commit.")
    args = parser.parse_args()

    refs, node_count = enumerate_refs(args.raw_mapping, scope=args.scope)
    summary = summarize(refs, scope=args.scope, node_count=node_count)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.scratch_refs is not None:
        if not str(args.scratch_refs).startswith("/tmp/"):
            raise SystemExit("--scratch-refs must be under /tmp")
        args.scratch_refs.parent.mkdir(parents=True, exist_ok=True)
        args.scratch_refs.write_text(json.dumps(representative_refs(refs), indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
