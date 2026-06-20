#!/usr/bin/env python3
"""Attended M5 CDP capture measurement driver.

Importing this module and running ``--help`` performs no browser/CDP/network I/O.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

from ask_chatgpt.capture import catalogue_completion_status_vocab, validate_backend_shape
from ask_chatgpt.channels.base import FetchResult
from ask_chatgpt.models import Transcript, TurnRecord
from ask_chatgpt.session import Session


def _rss_mib() -> float:
    # Linux ru_maxrss is KiB.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _memory_snapshot() -> dict[str, float]:
    current, peak = tracemalloc.get_traced_memory()
    return {
        "rss_max_mib": round(_rss_mib(), 3),
        "tracemalloc_current_mib": round(current / (1024 * 1024), 3),
        "tracemalloc_peak_mib": round(peak / (1024 * 1024), 3),
    }


def _assistant_markdown(turns: tuple[TurnRecord, ...]) -> str:
    return "\n\n".join(turn.content_markdown for turn in turns if turn.role == "assistant")


def _fidelity(markdown: str) -> dict[str, bool]:
    return {
        "contains_widehat": "\\widehat" in markdown,
        "contains_ne_or_neq": "\\ne" in markdown or "\\neq" in markdown,
        "contains_frac": "\\frac" in markdown,
        "no_literal_not_equal_replacement": "≠" not in markdown,
        "no_flattened_frac_observed": "\\frac" in markdown,
    }


def _write_markdown(path: Path, transcript: Transcript) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_assistant_markdown(transcript.turns), encoding="utf-8")


def _capture_with_measurements(session: Session, conversation: str) -> tuple[Transcript, dict[str, Any]]:
    measurements: dict[str, Any] = {}
    channel = session._channel()  # The driver instruments the Session-owned channel, then calls Session.scrape.
    original_wait_for_request = channel.wait_for_request
    original_fetch_in_page = channel.fetch_in_page

    def measured_wait_for_request(*args: Any, **kwargs: Any) -> Any:
        result = original_wait_for_request(*args, **kwargs)
        measurements["after_attach_open_header_acquire"] = _memory_snapshot()
        return result

    def measured_fetch_in_page(*args: Any, **kwargs: Any) -> FetchResult:
        started = time.monotonic()
        before = _memory_snapshot()
        result = original_fetch_in_page(*args, **kwargs)
        elapsed = time.monotonic() - started
        bytes_written = result.body_path.stat().st_size if result.body_path is not None and result.body_path.exists() else len(result.body_bytes or b"")
        measurements["fetch_only"] = {**_memory_snapshot(), "rss_before_mib": before["rss_max_mib"], "status": result.status, "bytes_written": bytes_written, "elapsed_s": elapsed}
        return result

    channel.wait_for_request = measured_wait_for_request  # type: ignore[method-assign]
    channel.fetch_in_page = measured_fetch_in_page  # type: ignore[method-assign]
    try:
        transcript = session.scrape(conversation)
    finally:
        channel.wait_for_request = original_wait_for_request  # type: ignore[method-assign]
        channel.fetch_in_page = original_fetch_in_page  # type: ignore[method-assign]
    measurements["end_to_end"] = _memory_snapshot()
    if transcript.raw_mapping_path is not None and transcript.conversation.conversation_id is not None:
        top = validate_backend_shape(transcript.raw_mapping_path, transcript.conversation.conversation_id)
        measurements["raw_top_level_keys"] = list(top.top_level_keys)
        measurements["mapping_node_count"] = top.mapping_node_count
    return transcript, measurements


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure attended M5 CDP scrape fidelity without printing content or secrets.")
    parser.add_argument("--conversation", required=True, help="Conversation URL/id/alias to scrape")
    parser.add_argument("--data-dir", required=True, type=Path, help="ask-chatgpt data directory")
    parser.add_argument("--out", type=Path, default=None, help="Optional markdown output path; content is never printed")
    parser.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222", help="Operator CDP endpoint")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tracemalloc.start()
    out_path = args.out or (Path(tempfile.gettempdir()) / f"ask-chatgpt-m5-{os.getpid()}.md")
    session = Session(cdp_endpoint=args.cdp_endpoint, data_dir=args.data_dir, channel="cdp")
    try:
        transcript, measurements = _capture_with_measurements(session, args.conversation)
        _write_markdown(out_path, transcript)
        raw_path = transcript.raw_mapping_path
        vocab = catalogue_completion_status_vocab(raw_path) if raw_path is not None else {}
        assistant_markdown = _assistant_markdown(transcript.turns)
        raw_bytes = raw_path.stat().st_size if raw_path is not None and raw_path.exists() else None
        summary = {
            "turn_count": len(transcript.turns),
            "assistant_markdown_total_length": len(assistant_markdown),
            "raw_mapping_byte_size": raw_bytes,
            "mapping_node_count": measurements.get("mapping_node_count"),
            "raw_top_level_keys": measurements.get("raw_top_level_keys", []),
            "fidelity": _fidelity(assistant_markdown),
            "completion_vocab": vocab,
            "memory": measurements,
            "markdown_out": str(out_path),
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    finally:
        session.detach()
        tracemalloc.stop()


if __name__ == "__main__":
    raise SystemExit(main())
