from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ask_chatgpt.capture import _resolved_attachment_file_id
from ask_chatgpt.errors import HumanActionNeededError
from ask_chatgpt.session import Session

TARGET_URL = "https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31"
DATA_DIR = Path("cache")


def _attachment_path_size(root: Path, local_path: str | None) -> int:
    if not local_path:
        return 0
    candidate = (root / local_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return 0
    try:
        return candidate.stat().st_size
    except OSError:
        return 0


def _summarize(session: Session) -> dict[str, Any]:
    transcript = session.store.load_transcript(TARGET_URL)
    conversation_id = transcript.conversation.conversation_id
    if conversation_id is None:
        raise RuntimeError("target conversation missing local id")
    paths = session.store.ensure_conversation(transcript.conversation)
    by_kind: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "distinct_source_refs": set(),
        "distinct_backend_tokens": set(),
        "states": Counter(),
        "total_bytes": 0,
        "mime_types": Counter(),
        "local_paths": set(),
    })
    for turn in transcript.turns:
        for attachment in turn.attachments:
            kind = attachment.source_kind
            bucket = by_kind[kind]
            if attachment.source_ref:
                bucket["distinct_source_refs"].add(attachment.source_ref)
            resolved = _resolved_attachment_file_id(attachment)
            if resolved is not None:
                bucket["distinct_backend_tokens"].add(resolved)
            bucket["states"][attachment.download_state] += 1
            bucket["mime_types"][attachment.mime or "<missing>"] += 1
            if attachment.download_state == "downloaded" and attachment.local_path:
                if attachment.local_path not in bucket["local_paths"]:
                    bucket["local_paths"].add(attachment.local_path)
                    bucket["total_bytes"] += _attachment_path_size(paths.root, attachment.local_path)
    safe_by_kind = {}
    for kind in sorted(by_kind):
        bucket = by_kind[kind]
        safe_by_kind[kind] = {
            "distinct_source_refs": len(bucket["distinct_source_refs"]),
            "distinct_backend_tokens": len(bucket["distinct_backend_tokens"]),
            "states": dict(sorted(bucket["states"].items())),
            "total_bytes": bucket["total_bytes"],
            "mime_types": dict(sorted(bucket["mime_types"].items())),
        }
    disk_files = [item for item in paths.attachments_dir.iterdir() if item.is_file()]
    return {
        "attachment_dir_exists": paths.attachments_dir.exists(),
        "attachment_files_on_disk": len(disk_files),
        "attachment_bytes_on_disk": sum(item.stat().st_size for item in disk_files),
        "turns": len(transcript.turns),
        "by_source_kind": safe_by_kind,
    }


def main() -> int:
    session = Session(data_dir=DATA_DIR, channel="cdp")
    try:
        session.scrape(TARGET_URL, with_attachments=True)
        summary = _summarize(session)
    except HumanActionNeededError:
        print("HUMAN-ACTION-NEEDED")
        return 21
    except Exception as exc:  # noqa: BLE001 - counts-only harness must not dump content-bearing tracebacks.
        print(f"ERROR {type(exc).__name__}")
        return 1
    finally:
        try:
            session.detach(close_managed_tabs=True)
        except Exception:
            pass
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
