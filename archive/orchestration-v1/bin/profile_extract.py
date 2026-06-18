#!/usr/bin/env python3
"""Extract a durable orchestration profiling dataset.

Stdlib-only. The script intentionally reads only the profiling ground-truth
sources named in orchestration/tasks/MISSION-010-profiling.md:
  * git log subjects/dates
  * .pi-workers run metadata/status files
  * .claude-orchestrators run metadata/status files
  * markdown reports for cheap estimate/duration harvesting
  * orchestration handoff/state JSON snapshots

It writes one JSONL row per extracted event and prints a compact summary to
stdout. Re-running overwrites the requested output path deterministically.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "orchestration" / "reports" / "PROFILING" / "dataset.jsonl"

MISSION_RE = re.compile(r"(?i)\b(?:MISSION|M)[-_ ]?0*(\d{1,3})(?:\.\d+)?(?:-docs)?\b")
TASK_RE = re.compile(r"\bTASK-\d{3}\b")
ISO_LIKE_RE = re.compile(
    r"\b20\d{2}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?\b"
)

DURATION_RE = re.compile(
    r"(?i)(?P<approx>~|≈|about|approx(?:imately)?|est\.?|estimated)?\s*"
    r"(?P<n1>\d+(?:\.\d+)?)"
    r"(?:\s*(?:-|–|—|to)\s*(?P<n2>\d+(?:\.\d+)?))?\s*"
    r"(?P<unit>hours?|hrs?|hr|h|minutes?|mins?|min|m|seconds?|secs?|sec|s)\b"
)
DURATION_SIGNAL_RE = re.compile(
    r"(?i)\b(estimate|estimated|est\.?|actual|duration|elapsed|runtime|wall[- ]?clock|took|passed in|failed in|seconds?|minutes?|hours?)\b"
)
TOKEN_USAGE_RE = re.compile(
    r"(?i)(?:\b(?:input|output|total|prompt|completion|cached|reasoning)\s+tokens?\s*[:=]?\s*\d[\d,]*"
    r"|\b\d[\d,]*\s+(?:input|output|total|prompt|completion|cached|reasoning)?\s*tokens?\b"
    r"|\busage\b[^\n]{0,80}\btokens?\b[^\n]{0,40}\d)"
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return str(path)


def short(text: str | None, n: int = 180) -> str:
    if not text:
        return ""
    one = " ".join(str(text).split())
    return one if len(one) <= n else one[: n - 1] + "…"


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    s = str(text).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    # Preserve explicit source offsets from git/metadata; mtime datetimes are already localized.
    return dt.isoformat(timespec="seconds")


def mtime_dt(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone()
    except FileNotFoundError:
        return None


def duration_seconds(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds(), 3)


def norm_mission_number(n: str) -> str | None:
    try:
        i = int(n)
    except ValueError:
        return None
    if 1 <= i <= 10:
        return f"M-{i:03d}"
    return None


def mission_candidates(text: str | None) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for m in MISSION_RE.finditer(text):
        nm = norm_mission_number(m.group(1))
        if nm and nm not in found:
            found.append(nm)
    return found


def infer_mission(*texts: str | None) -> tuple[str, list[str]]:
    candidates: list[str] = []
    task_seen = False
    for text in texts:
        if not text:
            continue
        for cand in mission_candidates(text):
            if cand not in candidates:
                candidates.append(cand)
        if TASK_RE.search(text):
            task_seen = True
    if candidates:
        return candidates[0], candidates
    if task_seen:
        return "math-tasks", []
    return "unknown", []


def parse_metadata(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return data
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def start_from_run_id(name: str) -> datetime | None:
    m = re.search(r"(?:pi-worker|claude-orch)-(\d{8})-(\d{6})", name)
    if not m:
        return None
    try:
        naive = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    # The run id timestamp is local wall-clock; attach the current local zone.
    return naive.replace(tzinfo=datetime.now().astimezone().tzinfo)


def read_status(path: Path) -> int | str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except FileNotFoundError:
        return None
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return text


def tail_text(path: Path, max_bytes: int = 200_000) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes), os.SEEK_SET)
            return f.read().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def token_lines_from_log(path: Path) -> list[str]:
    lines: list[str] = []
    for line in tail_text(path).splitlines():
        if TOKEN_USAGE_RE.search(line) and "budget" not in line.lower():
            lines.append(short(line, 240))
        if len(lines) >= 20:
            break
    return lines


def make_row(
    *,
    kind: str,
    mission: str,
    label: str,
    t_start: datetime | None,
    t_end: datetime | None,
    duration_s: float | int | None,
    exit_value: int | str | None,
    source_path: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "mission": mission,
        "label": label,
        "t_start": iso(t_start),
        "t_end": iso(t_end),
        "duration_s": duration_s,
        "exit": exit_value,
        "source_path": source_path,
        "extra": extra or {},
    }


def collect_commits() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    proc = subprocess.run(
        ["git", "log", "--format=%h|%cI|%s"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    for line in proc.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        h, date_text, subject = parts
        dt = parse_iso(date_text)
        mission, candidates = infer_mission(subject)
        rows.append(
            make_row(
                kind="commit",
                mission=mission,
                label=subject,
                t_start=dt,
                t_end=dt,
                duration_s=0,
                exit_value=None,
                source_path=f"git:{h}",
                extra={"hash": h, "subject": subject, "mission_candidates": candidates},
            )
        )
    return rows


def collect_run_dirs(base: Path, kind: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not base.exists():
        return rows
    for run_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        metadata_path = run_dir / "metadata.txt"
        status_path = run_dir / "status"
        output_path = run_dir / "output.log"
        md = parse_metadata(metadata_path)
        task = md.get("task", "")
        mission, candidates = infer_mission(task, run_dir.name)
        start = parse_iso(md.get("started_at"))
        start_source = "metadata.started_at" if start else None
        if start is None:
            start = start_from_run_id(run_dir.name)
            start_source = "run_id_local" if start else None
        end = mtime_dt(status_path) if status_path.exists() else None
        exit_value = read_status(status_path)
        output_mtime = mtime_dt(output_path) if output_path.exists() else None
        extra: dict[str, Any] = {
            "run_id": run_dir.name,
            "task": task,
            "cwd": md.get("cwd"),
            "tmux_session": md.get("tmux_session"),
            "metadata_keys": sorted(md.keys()),
            "mission_candidates": candidates,
            "start_source": start_source,
            "end_source": "mtime" if end else None,
            "status_path": rel(status_path) if status_path.exists() else None,
            "output_log_mtime": iso(output_mtime),
        }
        for key in ("tools", "model", "effort", "permission_mode", "allowed_tools", "append_system_prompt_file"):
            if key in md:
                extra[key] = md[key]
        tokens = token_lines_from_log(output_path)
        if tokens:
            extra["token_usage_lines"] = tokens
        rows.append(
            make_row(
                kind=kind,
                mission=mission,
                label=f"{run_dir.name}: {short(task, 140)}",
                t_start=start,
                t_end=end,
                duration_s=duration_seconds(start, end),
                exit_value=exit_value,
                source_path=rel(run_dir),
                extra=extra,
            )
        )
    return rows


def unit_seconds(unit: str) -> float:
    u = unit.lower()
    if u.startswith("h"):
        return 3600.0
    if u.startswith("m") and u not in {"ms"}:
        return 60.0
    return 1.0


def classify_duration_line(line: str) -> str:
    low = line.lower()
    if "estimate" in low or re.search(r"\best\.?\b", low):
        return "estimate"
    if "actual" in low:
        return "actual"
    if "passed in" in low or "failed in" in low or "pytest" in low or "test" in low:
        return "test-run"
    if "took" in low or "elapsed" in low or "runtime" in low or "duration" in low or "wall" in low:
        return "actual"
    return "duration-mention"


def collect_report_estimates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reports = ROOT / "orchestration" / "reports"
    if not reports.exists():
        return rows
    for path in sorted(reports.rglob("*.md")):
        if "PROFILING" in path.parts:
            continue
        rel_path = rel(path)
        mission, candidates = infer_mission(rel_path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if not DURATION_SIGNAL_RE.search(line):
                continue
            for m in DURATION_RE.finditer(line):
                n1 = float(m.group("n1"))
                n2 = float(m.group("n2")) if m.group("n2") else None
                mult = unit_seconds(m.group("unit"))
                low_s = n1 * mult
                high_s = (n2 * mult) if n2 is not None else low_s
                mid_s = (low_s + high_s) / 2.0
                kind = classify_duration_line(line)
                rows.append(
                    make_row(
                        kind="report-estimate",
                        mission=mission,
                        label=f"{path.name}:{line_no}:{kind}",
                        t_start=None,
                        t_end=None,
                        duration_s=round(mid_s, 3),
                        exit_value=None,
                        source_path=f"{rel_path}:{line_no}",
                        extra={
                            "observation_type": kind,
                            "line": short(line, 300),
                            "match_text": m.group(0),
                            "duration_min_s": round(low_s, 3),
                            "duration_max_s": round(high_s, 3),
                            "duration_interpretation": "midpoint_for_range" if n2 is not None else "exact_or_stated_single_value",
                            "mission_candidates": candidates,
                        },
                    )
                )
    return rows


def collect_json_strings(obj: Any, out: list[str], max_items: int = 50) -> None:
    if len(out) >= max_items:
        return
    if isinstance(obj, dict):
        for v in obj.values():
            collect_json_strings(v, out, max_items)
            if len(out) >= max_items:
                return
    elif isinstance(obj, list):
        for v in obj:
            collect_json_strings(v, out, max_items)
            if len(out) >= max_items:
                return
    elif isinstance(obj, str):
        for m in ISO_LIKE_RE.finditer(obj):
            s = m.group(0)
            if s not in out:
                out.append(s)
            if len(out) >= max_items:
                return


def collect_mission_boundaries() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    json_paths: list[Path] = []
    for sub in (ROOT / "orchestration" / "handoffs", ROOT / "orchestration" / "state"):
        if sub.exists():
            json_paths.extend(sorted(sub.glob("*.json")))
    for path in sorted(json_paths):
        rel_path = rel(path)
        mtime = mtime_dt(path)
        data: Any = None
        parse_error = None
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:  # keep a row for malformed source snapshots
            parse_error = f"{type(exc).__name__}: {exc}"
        text_for_mission = rel_path
        if isinstance(data, dict):
            text_for_mission += " " + str(data.get("mission", ""))
        mission, candidates = infer_mission(text_for_mission)
        timestamps: list[str] = []
        if data is not None:
            collect_json_strings(data, timestamps)
        status = data.get("status") if isinstance(data, dict) else None
        title = data.get("title") if isinstance(data, dict) else None
        label_bits = [path.name]
        if status:
            label_bits.append(f"status={status}")
        if title:
            label_bits.append(short(str(title), 80))
        extra: dict[str, Any] = {
            "json_status": status,
            "json_title": title,
            "mission_field": data.get("mission") if isinstance(data, dict) else None,
            "mission_candidates": candidates,
            "embedded_timestamp_strings_first50": timestamps,
            "start_source": "mtime",
            "end_source": "mtime",
            "parse_error": parse_error,
        }
        if isinstance(data, dict):
            for key in ("started", "started_at", "completed", "updated", "utc", "phase", "overall_verdict", "final_verdict"):
                if key in data:
                    extra[f"json_{key}"] = short(str(data[key]), 500)
        rows.append(
            make_row(
                kind="mission-boundary",
                mission=mission,
                label=" | ".join(label_bits),
                t_start=mtime,
                t_end=mtime,
                duration_s=0,
                exit_value=None,
                source_path=rel_path,
                extra=extra,
            )
        )
    return rows


def sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        row.get("t_start") or "9999-99-99T99:99:99",
        row.get("kind") or "",
        row.get("source_path") or "",
        row.get("label") or "",
    )


def print_summary(rows: list[dict[str, Any]], out_path: Path) -> None:
    by_kind = Counter(row["kind"] for row in rows)
    by_mission = Counter(row["mission"] for row in rows)
    by_kind_mission = Counter((row["kind"], row["mission"]) for row in rows)
    unknown_count = by_mission.get("unknown", 0)
    print(f"dataset={rel(out_path)}")
    print(f"rows_total={len(rows)}")
    print("by_kind:")
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind}: {count}")
    print("by_mission:")
    for mission, count in sorted(by_mission.items()):
        print(f"  {mission}: {count}")
    print("by_kind_mission:")
    for (kind, mission), count in sorted(by_kind_mission.items()):
        print(f"  {kind}|{mission}: {count}")
    print(f"unattributed_count={unknown_count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="JSONL output path")
    args = parser.parse_args()
    out_path = args.out if args.out.is_absolute() else ROOT / args.out

    rows: list[dict[str, Any]] = []
    rows.extend(collect_commits())
    rows.extend(collect_run_dirs(ROOT / ".pi-workers", "pi-worker"))
    rows.extend(collect_run_dirs(ROOT / ".claude-orchestrators", "claude-manager"))
    rows.extend(collect_report_estimates())
    rows.extend(collect_mission_boundaries())
    rows.sort(key=sort_key)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp_path.replace(out_path)
    print_summary(rows, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
