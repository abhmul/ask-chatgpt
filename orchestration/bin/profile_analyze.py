#!/usr/bin/env python3
"""Mission profiling analysis helpers for MISSION-010 PROF-2.

Stdlib-only, read-only over the committed profiling dataset plus report mtimes.
It intentionally does not inspect control-plane/src.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Iterable

DATASET = Path("orchestration/reports/PROFILING/dataset.jsonl")
MISSIONS = [f"M-{i:03d}" for i in range(1, 10)]
AGENT_KINDS = {"pi-worker", "claude-manager"}
OPERATIONAL_KINDS = {"commit", "pi-worker", "claude-manager"}
LONG_GAP_S = 6 * 3600

# Hand-extracted mission-contract estimates; derivation lines are in orchestration/tasks/MISSION-00*.md.
MISSION_ESTIMATE_H = {
    "M-001": (3.0, 6.0, "orchestration/tasks/MISSION-001.md:41"),
    "M-002": (4.0, 7.0, "orchestration/tasks/MISSION-002.md:57"),
    "M-003": (3.0, 6.0, "orchestration/tasks/MISSION-003.md:55"),
    "M-004": (4.0, 7.0, "orchestration/tasks/MISSION-004.md:71"),
    "M-005": (5.0, 8.0, "orchestration/tasks/MISSION-005.md:72"),
    "M-006": (3.0, 5.0, "orchestration/tasks/MISSION-006.md:51"),
    "M-007": (0.0, 1.5, "orchestration/tasks/MISSION-007-docs.md:3"),
    "M-008": (4.0, 6.0, "orchestration/tasks/MISSION-008.md:61"),
    "M-009": (3.0, 5.0, "orchestration/tasks/MISSION-009.md:51"),
}

M009_SLICES = {
    "claude-orch-20260611-103920-2024892-10110": ("manager", "bootstrap M-009", "spawned design; operator-blocked quickstart mission"),
    "pi-worker-20260611-104453-2029350-7734": ("worker", "T-design", "DONE; design.md"),
    "claude-orch-20260611-113342-2063928-26565": ("manager", "ingest design / dispatch T-impl-1", "DONE"),
    "pi-worker-20260611-113905-2070298-31651": ("worker", "T-impl-1 D1+D3", "DONE; config bootstrap + messages"),
    "claude-orch-20260611-115236-2081143-17860": ("manager", "ingest impl-1 / dispatch T-impl-2a", "DONE"),
    "pi-worker-20260611-120304-2095690-9405": ("worker", "T-impl-2a D2 tunnel mechanics", "DONE"),
    "claude-orch-20260611-121556-2110821-8761": ("manager", "ingest impl-2a / dispatch T-impl-2b", "DONE"),
    "pi-worker-20260611-122543-2119875-10934": ("worker", "T-impl-2b D2 wizard wiring", "DONE"),
    "claude-orch-20260611-123948-2136340-15994": ("manager", "ingest impl-2b / queue D4", "DONE; T-impl-3 subsequently reported blocked"),
    "claude-orch-20260611-125900-2161733-3566": ("manager", "replan after T-impl-3 BLOCKED", "DONE; authored T-impl-4"),
    "pi-worker-20260611-131551-2178301-31653": ("worker", "T-impl-4 owned-tunnel reuse", "DONE"),
    "claude-orch-20260611-132629-2190814-15017": ("manager", "ingest impl-4 / dispatch T-impl-3-rev", "DONE; manager chain then died"),
    "pi-worker-20260611-133013-2194593-11629": ("worker", "T-impl-3-rev D4 interactive", "BLOCKED; reuse skipped acks/browser"),
    "pi-worker-20260611-162538-2392941-24033": ("worker", "T-impl-5 source fix", "BLOCKED; fix shipped, suite still red"),
    "pi-worker-20260611-163720-2405398-31561": ("worker", "T-impl-6 env/stale-test repair", "DONE; full suite green twice"),
    "pi-worker-20260611-164710-2420713-6704": ("worker", "T-impl-3-final D4/F1/F2/docs", "DONE; quickstart acceptance"),
    "pi-worker-20260611-171038-2442006-23216": ("worker", "T-verify AUTH attempt", "HALTED by live-backlog rot; produced auth commit"),
    "pi-worker-20260611-172029-2453292-24425": ("worker", "T-impl-7 frozen backlog snapshot", "DONE"),
    "pi-worker-20260611-172342-2456495-16641": ("worker", "T-verify AUTH rerun", "DONE"),
    "pi-worker-20260611-172956-2464442-16598": ("worker", "T-verify A operator-fidelity", "FAIL"),
    "pi-worker-20260611-174142-2473411-27817": ("worker", "T-verify B security", "PASS"),
    "pi-worker-20260611-175004-2479649-20939": ("worker", "T-verify C reproduction", "PASS"),
    "pi-worker-20260611-175416-2482884-14908": ("worker", "T-verify SYNTH", "FAIL; handoff status FAILED"),
    "pi-worker-20260611-180531-2493887-16094": ("worker", "T-impl-8 corrective D3", "OPEN in dataset; no status/log"),
}

# Rework entries are deliberate, auditable judgments from M-009 state/reports/commit labels.
M009_REWORK = [
    ("report-only", "T-impl-3 BLOCKED", "frozen-file discipline/spec-harness mismatch", "orchestration/reports/M-009/impl-3.md", None),
    ("claude-orch-20260611-125900-2161733-3566", "manager replan", "spec gap", ".claude-orchestrators/claude-orch-20260611-125900-2161733-3566", None),
    ("pi-worker-20260611-131551-2178301-31653", "T-impl-4", "spec gap", ".pi-workers/pi-worker-20260611-131551-2178301-31653", None),
    ("claude-orch-20260611-132629-2190814-15017", "manager dispatch T-impl-3-rev", "spec gap", ".claude-orchestrators/claude-orch-20260611-132629-2190814-15017", None),
    ("pi-worker-20260611-133013-2194593-11629", "T-impl-3-rev BLOCKED", "frozen-file discipline/spec gap", ".pi-workers/pi-worker-20260611-133013-2194593-11629", None),
    ("pi-worker-20260611-162538-2392941-24033", "T-impl-5", "spec gap", ".pi-workers/pi-worker-20260611-162538-2392941-24033", None),
    ("pi-worker-20260611-163720-2405398-31561", "T-impl-6", "environment drift", ".pi-workers/pi-worker-20260611-163720-2405398-31561", None),
    ("pi-worker-20260611-172029-2453292-24425", "T-impl-7", "cross-team dependency rot", ".pi-workers/pi-worker-20260611-172029-2453292-24425", None),
    ("pi-worker-20260611-180531-2493887-16094", "T-impl-8", "spec gap/late verification defect", ".pi-workers/pi-worker-20260611-180531-2493887-16094", None),
]


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_dt(d: datetime | None) -> str:
    return "" if d is None else d.isoformat(timespec="seconds")


def fmt_min(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    return f"{seconds / 60:.1f}"


def fmt_h(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    return f"{seconds / 3600:.2f}"


def load_rows() -> list[dict]:
    with DATASET.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def run_id(row: dict) -> str:
    return row.get("extra", {}).get("run_id") or Path(row["source_path"]).name


def intervals_for(rows: Iterable[dict], *, agent_only: bool = True) -> list[tuple[datetime, datetime, dict]]:
    out = []
    for r in rows:
        if agent_only and r["kind"] not in AGENT_KINDS:
            continue
        s = parse_time(r.get("t_start"))
        e = parse_time(r.get("t_end"))
        if not s or not e or r.get("duration_s") is None:
            continue
        out.append((s, e, r))
    return sorted(out, key=lambda x: (x[0], x[1]))


def merge_intervals(intervals: Iterable[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for s, e in sorted(intervals):
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        elif e > merged[-1][1]:
            merged[-1][1] = e
    return [(s, e) for s, e in merged]


def duration_sum(intervals: Iterable[tuple[datetime, datetime]]) -> float:
    return sum((e - s).total_seconds() for s, e in intervals)


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def wall_rows(rows: list[dict]) -> list[list[object]]:
    table = []
    for m in MISSIONS:
        ev = []
        for r in rows:
            if r["mission"] != m or r["kind"] not in OPERATIONAL_KINDS:
                continue
            s = parse_time(r.get("t_start"))
            e = parse_time(r.get("t_end")) or s
            if s and e:
                ev.append((s, e, r))
        if not ev:
            continue
        first = min(s for s, _, _ in ev)
        last = max(e for _, e, _ in ev)
        wall_s = (last - first).total_seconds()
        agent_ints = [(s, e) for s, e, r in ev if r["kind"] in AGENT_KINDS and r.get("duration_s") is not None]
        merged = merge_intervals(agent_ints)
        active_s = duration_sum(merged)
        # No-agent gaps inside the operational wall; long gaps are separately charged as operator/outage paced.
        points = [(first, first)] + merged + [(last, last)]
        long_gap_s = 0.0
        max_gap_s = 0.0
        for (_, prev_e), (next_s, _) in zip(points, points[1:]):
            gap = (next_s - prev_e).total_seconds()
            max_gap_s = max(max_gap_s, gap)
            if gap > LONG_GAP_S:
                long_gap_s += gap
        adjusted_wall_s = wall_s - long_gap_s
        idle_s = wall_s - active_s
        table.append([
            m,
            fmt_dt(first),
            fmt_dt(last),
            fmt_h(wall_s),
            fmt_h(active_s),
            fmt_h(idle_s),
            fmt_h(long_gap_s),
            fmt_h(adjusted_wall_s),
            f"{(active_s / adjusted_wall_s * 100):.0f}%" if adjusted_wall_s > 0 else "—",
            fmt_h(max_gap_s),
        ])
    return table


def classify_phase(row: dict) -> str:
    text = (row.get("label", "") + " " + row.get("extra", {}).get("task", "")).lower()
    kind = row["kind"]
    if "verify" in text or "verification" in text or "authrun" in text or "authoritative fresh-env" in text:
        return "verification"
    if "t-acc" in text or "acceptance worker" in text or "acceptance test" in text:
        return "acceptance-test"
    if "design" in text:
        return "design"
    if "synth" in text or "handoff" in text or kind == "claude-manager":
        return "synthesis-handoff/dispatch"
    if "impl" in text or "implementation" in text or "fix" in text or "docs" in text or "runbook" in text or "scaffold" in text:
        return "impl"
    return "unclassified"


def phase_rows(rows: list[dict]) -> tuple[list[list[object]], dict[str, float]]:
    phases = ["design", "impl", "acceptance-test", "verification", "synthesis-handoff/dispatch", "unclassified"]
    by_mission: dict[str, collections.Counter] = {m: collections.Counter() for m in MISSIONS}
    totals = collections.Counter()
    for r in rows:
        if r["mission"] not in by_mission or r["kind"] not in AGENT_KINDS or r.get("duration_s") is None:
            continue
        phase = classify_phase(r)
        by_mission[r["mission"]][phase] += float(r["duration_s"])
        totals[phase] += float(r["duration_s"])
    table = []
    for m in MISSIONS:
        total = sum(by_mission[m].values())
        table.append([m] + [fmt_min(by_mission[m][p]) for p in phases] + [fmt_min(total)])
    return table, {p: totals[p] for p in phases}


def percentile_nearest(values: list[float], p: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    idx = max(0, min(len(vals) - 1, math.ceil(p * len(vals)) - 1))
    return vals[idx]


def distribution_rows(rows: list[dict]) -> list[list[object]]:
    table = []
    for kind in ["pi-worker", "claude-manager"]:
        leg_rows = [r for r in rows if r["kind"] == kind and r["mission"] in MISSIONS]
        vals = [float(r["duration_s"]) for r in leg_rows if r.get("duration_s") is not None]
        exits = collections.Counter(str(r.get("exit")) if r.get("exit") is not None else "missing" for r in leg_rows)
        table.append([
            kind,
            len(leg_rows),
            len(vals),
            fmt_min(min(vals) if vals else None),
            fmt_min(statistics.median(vals) if vals else None),
            fmt_min(percentile_nearest(vals, 0.90)),
            fmt_min(max(vals) if vals else None),
            ", ".join(f"{k}:{v}" for k, v in sorted(exits.items())),
        ])
    return table


def line_no(source_path: str) -> int | None:
    m = re.search(r":(\d+)$", source_path)
    return int(m.group(1)) if m else None


def estimate_pair_rows(rows: list[dict]) -> tuple[list[list[object]], list[list[object]]]:
    reps = [r for r in rows if r["kind"] == "report-estimate"]
    by_file: dict[str, list[dict]] = collections.defaultdict(list)
    for r in reps:
        path = re.sub(r":\d+$", "", r["source_path"])
        by_file[path].append(r)
    pairs = []
    for path, rs in by_file.items():
        rs.sort(key=lambda r: line_no(r["source_path"]) or -1)
        actuals = [r for r in rs if r.get("extra", {}).get("observation_type") in {"test-run", "actual", "duration-mention"}]
        for est in [r for r in rs if r.get("extra", {}).get("observation_type") == "estimate"]:
            est_line = line_no(est["source_path"])
            if est_line is None:
                continue
            line_text = est.get("extra", {}).get("line", "")
            if "est" not in line_text.lower():
                continue
            nxt = None
            for cand in actuals:
                cand_line = line_no(cand["source_path"])
                if cand_line is not None and cand_line > est_line:
                    nxt = cand
                    break
            if nxt and est.get("duration_s") and nxt.get("duration_s"):
                ratio = float(nxt["duration_s"]) / float(est["duration_s"])
                pairs.append((abs(math.log(max(ratio, 1e-9))), ratio, est, nxt, path))
    ratios = [p[1] for p in pairs]
    summary = [[
        len(pairs),
        f"{statistics.median(ratios):.2f}x" if ratios else "—",
        f"{percentile_nearest(ratios, 0.90):.2f}x" if ratios else "—",
        sum(1 for r in ratios if r > 2 or r < 0.5),
    ]]
    divergences = []
    for _, ratio, est, actual, path in sorted(pairs, key=lambda p: p[0], reverse=True)[:12]:
        if ratio > 2 or ratio < 0.5:
            divergences.append([
                est["mission"],
                path,
                line_no(est["source_path"]),
                fmt_min(float(est["duration_s"])),
                line_no(actual["source_path"]),
                fmt_min(float(actual["duration_s"])),
                f"{ratio:.2f}x",
            ])
    return summary, divergences


def mission_estimate_rows(rows: list[dict]) -> list[list[object]]:
    walls = {r[0]: r for r in wall_rows(rows)}
    out = []
    for m in MISSIONS:
        lo, hi, src = MISSION_ESTIMATE_H[m]
        w = walls.get(m)
        if not w:
            continue
        raw_h = float(w[3])
        adjusted_h = float(w[7])
        mid = (lo + hi) / 2 if lo else hi / 2
        raw_ratio = raw_h / mid if mid else 0
        adj_ratio = adjusted_h / mid if mid else 0
        out.append([m, f"{lo:g}–{hi:g}h" if lo else f"<{hi:g}h", src, f"{raw_h:.2f}h", f"{adjusted_h:.2f}h", f"{raw_ratio:.2f}x", f"{adj_ratio:.2f}x", "YES" if adj_ratio > 2 else "no"])
    return out


def m009_timeline_rows(rows: list[dict]) -> list[list[object]]:
    out = []
    for r in rows:
        if r["mission"] != "M-009" or r["kind"] not in AGENT_KINDS:
            continue
        rid = run_id(r)
        agent, slice_name, outcome = M009_SLICES.get(rid, (r["kind"], "unknown", r.get("label", "")[:80]))
        out.append([parse_time(r.get("t_start")), [fmt_dt(parse_time(r.get("t_start"))), fmt_min(r.get("duration_s")), agent, rid, slice_name, outcome]])
    # The original T-impl-3 appears as a report artifact but has no pi/claude run row in the dataset.
    p = Path("orchestration/reports/M-009/impl-3.md")
    if p.exists():
        st = datetime.fromtimestamp(p.stat().st_mtime).astimezone()
        out.append([st, [fmt_dt(st), "unknown", "report-only", "impl-3.md", "T-impl-3 D4", "BLOCKED; no matching agent row in dataset"]])
    # Important commit-only milestones.
    for r in rows:
        if r["mission"] == "M-009" and r["kind"] == "commit" and r.get("extra", {}).get("hash") in {"d7c6085", "82d12b8"}:
            out.append([parse_time(r["t_start"]), [fmt_dt(parse_time(r["t_start"])), "0.0", "commit", r["extra"]["hash"], "dispatch/panel decision", r["label"]]])
    out.sort(key=lambda x: (x[0] is None, x[0]))
    return [r for _, r in out]


def m009_chain_rows(rows: list[dict]) -> list[list[object]]:
    def get_interval(rid: str) -> tuple[datetime, datetime] | None:
        for r in rows:
            if r["mission"] == "M-009" and run_id(r) == rid:
                s = parse_time(r.get("t_start")); e = parse_time(r.get("t_end"))
                if s and e:
                    return s, e
        return None

    chains = [
        ("early claude-manager chain", [
            "pi-worker-20260611-104453-2029350-7734",
            "pi-worker-20260611-113905-2070298-31651",
            "pi-worker-20260611-120304-2095690-9405",
            "pi-worker-20260611-122543-2119875-10934",
            "pi-worker-20260611-131551-2178301-31653",
            "pi-worker-20260611-133013-2194593-11629",
        ]),
        ("lead/Sonnet serial impl repair", [
            "pi-worker-20260611-162538-2392941-24033",
            "pi-worker-20260611-163720-2405398-31561",
            "pi-worker-20260611-164710-2420713-6704",
        ]),
        ("verification plus auth-fix chain", [
            "pi-worker-20260611-171038-2442006-23216",
            "pi-worker-20260611-172029-2453292-24425",
            "pi-worker-20260611-172342-2456495-16641",
            "pi-worker-20260611-172956-2464442-16598",
            "pi-worker-20260611-174142-2473411-27817",
            "pi-worker-20260611-175004-2479649-20939",
            "pi-worker-20260611-175416-2482884-14908",
        ]),
        ("post-panel corrective chain", ["pi-worker-20260611-180531-2493887-16094"]),
    ]
    out = []
    for name, ids in chains:
        ints = [get_interval(i) for i in ids]
        known = [i for i in ints if i]
        if not known:
            out.append([name, "—", "—", "—", "open/no complete rows"])
            continue
        span_s = (max(e for _, e in known) - min(s for s, _ in known)).total_seconds()
        worker_s = duration_sum(known)
        out.append([name, fmt_dt(min(s for s, _ in known)), fmt_min(span_s), fmt_min(worker_s), f"{worker_s/span_s*100:.0f}%" if span_s > 0 else "—"])
    return out


def rework_rows(rows: list[dict]) -> tuple[list[list[object]], list[list[object]]]:
    by_source = {r["source_path"]: r for r in rows if r["mission"] == "M-009"}
    by_rid = {run_id(r): r for r in rows if r["mission"] == "M-009"}
    table = []
    cause_minutes = collections.Counter()
    intervals = []
    rework_agent_count = 0
    for rid, label, cause, source, _ in M009_REWORK:
        r = by_rid.get(rid)
        if r is None and source in by_source:
            r = by_source[source]
        start = end = None
        dur = None
        if rid == "report-only":
            p = Path(source)
            if p.exists():
                start = end = datetime.fromtimestamp(p.stat().st_mtime).astimezone()
        elif r:
            start = parse_time(r.get("t_start")); end = parse_time(r.get("t_end")); dur = r.get("duration_s")
            rework_agent_count += 1
            if start and end and dur is not None:
                intervals.append((start, end))
                cause_minutes[cause] += float(dur) / 60.0
        table.append([label, cause, fmt_dt(start), fmt_min(dur), source])
    m009_agents = [r for r in rows if r["mission"] == "M-009" and r["kind"] in AGENT_KINDS]
    m009_known = [r for r in m009_agents if r.get("duration_s") is not None]
    total_leg_min = sum(float(r["duration_s"]) for r in m009_known) / 60.0
    merged_active_min = duration_sum([(s, e) for s, e, _ in intervals_for([r for r in rows if r["mission"] == "M-009"])]) / 60.0
    rework_known_leg_min = sum(cause_minutes.values())
    rework_union_min = duration_sum(merge_intervals(intervals)) / 60.0
    wall = wall_rows(rows)[8]  # M-009 row, missions are ordered M-001..M-009
    wall_min = float(wall[3]) * 60.0
    summary = [
        ["M-009 agent legs in dataset", len(m009_agents), "includes one open no-status T-impl-8"],
        ["rework entries in table", len(M009_REWORK), "includes report-only T-impl-3 and open T-impl-8"],
        ["rework agent legs / M-009 agent legs", f"{rework_agent_count}/{len(m009_agents)}", f"{rework_agent_count/len(m009_agents)*100:.1f}%"],
        ["known rework leg-duration", f"{rework_known_leg_min:.1f} min", f"{rework_known_leg_min/total_leg_min*100:.1f}% of known M-009 leg-duration"],
        ["merged active rework coverage", f"{rework_union_min:.1f} min", f"{rework_union_min/merged_active_min*100:.1f}% of M-009 merged active agent time"],
        ["merged active rework coverage / raw wall", f"{rework_union_min:.1f} min", f"{rework_union_min/wall_min*100:.1f}% of M-009 raw wall"],
    ]
    for cause, minutes in cause_minutes.most_common():
        summary.append([f"cause: {cause}", f"{minutes:.1f} min", f"{minutes/rework_known_leg_min*100:.1f}% of known rework leg-duration"])
    return summary, table


def print_wall(rows: list[dict]) -> None:
    print(md_table(["mission", "first", "last", "wall_h", "active_agent_h", "idle_gap_h", "long_gap_>6h_h", "wall_minus_long_h", "active/share_adj", "max_no_agent_gap_h"], wall_rows(rows)))


def print_phase(rows: list[dict]) -> None:
    table, totals = phase_rows(rows)
    print(md_table(["mission", "design_m", "impl_m", "acceptance_m", "verification_m", "synth_dispatch_m", "unclassified_m", "total_leg_m"], table))
    total = sum(totals.values())
    verify = totals["verification"]
    rigor = verify + totals["acceptance-test"]
    print(f"\nverification_share={verify/total*100:.1f}% ({verify/3600:.1f} h / {total/3600:.1f} h agent-leg time)")
    print(f"verification_plus_acceptance_share={rigor/total*100:.1f}% ({rigor/3600:.1f} h / {total/3600:.1f} h agent-leg time)")


def print_dist(rows: list[dict]) -> None:
    print(md_table(["kind", "legs", "with_duration", "min_m", "median_m", "p90_m", "max_m", "exit_counts"], distribution_rows(rows)))


def print_estimates(rows: list[dict]) -> None:
    print("Mission-level contract estimates vs wall:\n")
    print(md_table(["mission", "contract_estimate", "source", "raw_wall", "wall_minus_long", "raw/mid", "adjusted/mid", ">2x_adjusted"], mission_estimate_rows(rows)))
    summary, divergences = estimate_pair_rows(rows)
    print("\nReport-file nearest-following estimate/test-runtime pairs (approximate):\n")
    print(md_table(["pairs", "median_actual/estimate", "p90_actual/estimate", ">2x_or_<0.5x"], summary))
    if divergences:
        print("\nLargest flagged divergences:\n")
        print(md_table(["mission", "file", "est_line", "estimate_m", "actual_line", "actual_m", "actual/estimate"], divergences))


def print_m009(rows: list[dict]) -> None:
    print("M-009 runner-chain utilization:\n")
    print(md_table(["chain", "start", "chain_span_m", "worker_runtime_m", "utilization"], m009_chain_rows(rows)))
    print("\nM-009 deep-dive timeline:\n")
    print(md_table(["start", "duration_m", "agent", "id/source", "slice", "outcome"], m009_timeline_rows(rows)))


def print_rework(rows: list[dict]) -> None:
    summary, table = rework_rows(rows)
    print("M-009 rework summary:\n")
    print(md_table(["metric", "value", "note"], summary))
    print("\nM-009 rework classified entries:\n")
    print(md_table(["entry", "primary_cause", "start", "duration_m", "source"], table))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("section", choices=["wall", "phase", "dist", "estimates", "m009", "rework", "all"])
    args = p.parse_args()
    rows = load_rows()
    if args.section in {"wall", "all"}:
        print_wall(rows)
    if args.section in {"phase", "all"}:
        print("\n" if args.section == "all" else "", end="")
        print_phase(rows)
    if args.section in {"rework", "all"}:
        print("\n" if args.section == "all" else "", end="")
        print_rework(rows)
    if args.section in {"estimates", "all"}:
        print("\n" if args.section == "all" else "", end="")
        print_estimates(rows)
    if args.section in {"dist", "all"}:
        print("\n" if args.section == "all" else "", end="")
        print_dist(rows)
    if args.section in {"m009", "all"}:
        print("\n" if args.section == "all" else "", end="")
        print_m009(rows)


if __name__ == "__main__":
    main()
