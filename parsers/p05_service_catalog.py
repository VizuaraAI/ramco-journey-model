"""p05 · service catalog parser
================================

Reads:  artifacts/ramco/PO/ModelInfo/Service_details_PO.csv
Writes: out/parsed/service_catalog.json

Extracts the task → SP call chain for every (activity, ui, task) tuple.
`sequenceno` orders the SPs within one task invocation.

Layer L1 — deterministic CSV walk. No LLM.

CSV columns (17):
  0:parent_service_name 1:parent_method_name 2:component_name 3:process_name
  4:activity_name       5:activitydesc       6:createddate    7:ui_name
  8:description         9:task_name          10:taskdesc      11:service_name
  12:method_name        13:spname            14:lvl           15:ps_sequenceno
  16:sequenceno
"""
from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "artifacts" / "ramco" / "PO" / "ModelInfo" / "Service_details_PO.csv"
OUT_DIR = ROOT / "out" / "parsed"
OUT = OUT_DIR / "service_catalog.json"


COL_ACTIVITY = 4
COL_ACTIVITY_DESC = 5
COL_UI = 7
COL_DESCRIPTION = 8
COL_TASK = 9
COL_TASK_DESC = 10
COL_SERVICE = 11
COL_METHOD = 12
COL_SP = 13
COL_LVL = 14
COL_SEQUENCENO = 16


def parse_service_catalog() -> dict:
    if not ARTIFACT.exists():
        raise FileNotFoundError(f"Service_details_PO.csv not found at {ARTIFACT}")

    rows: list[dict] = []
    parse_errors: list[dict] = []
    n_total = 0
    n_skipped_short = 0
    n_skipped_null_activity = 0

    with open(ARTIFACT, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        for line_no, r in enumerate(rdr, start=2):
            n_total += 1
            if len(r) < 17:
                n_skipped_short += 1
                continue
            activity = r[COL_ACTIVITY].strip()
            if not activity or activity.upper() == "NULL":
                n_skipped_null_activity += 1
                continue
            seq_raw = r[COL_SEQUENCENO].strip()
            try:
                seq = int(seq_raw) if seq_raw.isdigit() else None
            except Exception:
                seq = None
                parse_errors.append({"line": line_no, "kind": "bad_sequenceno", "value": seq_raw})

            rows.append({
                "activity": activity,
                "activity_desc": r[COL_ACTIVITY_DESC].strip(),
                "ui": r[COL_UI].strip(),
                "task_name": r[COL_TASK].strip(),
                "task_desc": r[COL_TASK_DESC].strip(),
                "service_name": r[COL_SERVICE].strip(),
                "method_name": r[COL_METHOD].strip(),
                "spname": r[COL_SP].replace(".sql", "").strip(),
                "lvl": r[COL_LVL].strip(),
                "sequenceno": seq,
                "description": r[COL_DESCRIPTION].strip(),
            })

    # Group by (activity, ui, task) → ordered SP chain
    chains: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = f"{row['activity']}|{row['ui']}|{row['task_name']}"
        chains[key].append({
            "sequenceno": row["sequenceno"],
            "spname": row["spname"],
            "method_name": row["method_name"],
            "service_name": row["service_name"],
            "lvl": row["lvl"],
        })

    # Sort each chain by sequenceno (None last)
    for key, ch in chains.items():
        ch.sort(key=lambda x: (x["sequenceno"] is None, x["sequenceno"] or 0))

    # Per-activity slices
    by_activity: dict[str, list[str]] = defaultdict(list)
    for key in chains:
        activity = key.split("|", 1)[0]
        by_activity[activity].append(key)

    # Unique sets per activity for quick reference
    activity_summaries: dict[str, dict] = {}
    for activity, keys in by_activity.items():
        screens, tasks, sps, methods = set(), set(), set(), set()
        for key in keys:
            _, ui, task = key.split("|", 2)
            screens.add(ui)
            tasks.add(task)
            for step in chains[key]:
                if step["spname"]: sps.add(step["spname"])
                if step["method_name"]: methods.add(step["method_name"])
        activity_summaries[activity] = {
            "screens": sorted(screens),
            "tasks": sorted(tasks),
            "sp_count": len(sps),
            "method_count": len(methods),
            "task_count": len(tasks),
        }

    return {
        "source": str(ARTIFACT.relative_to(ROOT)),
        "total_rows_seen": n_total,
        "rows_kept": len(rows),
        "rows_skipped_short": n_skipped_short,
        "rows_skipped_null_activity": n_skipped_null_activity,
        "parse_errors": parse_errors,
        "chains": chains,
        "activity_summaries": activity_summaries,
        "rows": rows,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    r = parse_service_catalog()
    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"p05: parsed {r['rows_kept']:,} catalog rows from {r['total_rows_seen']:,} total "
          f"({len(r['chains']):,} (activity, ui, task) chains) → {OUT.relative_to(ROOT)}")
    if r["parse_errors"]:
        print(f"  ⚠ {len(r['parse_errors'])} parse warnings")


if __name__ == "__main__":
    main()
