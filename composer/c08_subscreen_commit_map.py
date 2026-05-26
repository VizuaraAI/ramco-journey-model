"""c08_subscreen_commit_map — auto-derive the sub-screen commit dispatch table.

For each activity, for each sub-screen, classify its TRANS tasks into
{save, approve} buckets so the bot can pick the right one based on the user's
commit intent.

Classification heuristics (in order):
  1. Description keyword match (`Approve` / `Authorise` → approve; `Specify` /
     `Save` → save).
  2. SP family naming convention (`*_sp_apr_*` → approve; `*_sp_spfy_*` /
     `*_sp_save_*` → save).
  3. Suffix heuristic on the task name (`Trn3`/`Trn4` historically mean
     approve in this codebase; `Tran`/`Tran2`/`Trn1` mean save).

Output:
  out/audit/subscreen_commits.json  — { activity: { screen: { save, approve,
                                       save_chain_tables, approve_chain_tables,
                                       all_tables } } }

Sub-screens included are exactly the ones that own at least one orphan TRANS
(i.e. ones the bot needs to learn to fire).
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "out/parsed/service_catalog.json").read_text())
SP_DATA = json.loads((ROOT / "out/parsed/sp_branches.json").read_text())["sps"]
TRANS_AUDIT = json.loads((ROOT / "out/audit/trans_coverage.json").read_text())

# Per-activity description map: { task_name_upper: description }
def _load_descriptions() -> dict[str, str]:
    out: dict[str, str] = {}
    activities_dir = ROOT / "out/model/activities"
    for jf in activities_dir.glob("*.json"):
        try:
            data = json.loads(jf.read_text())
        except Exception:
            continue
        for screen in data.get("screens", []):
            for kind in ("TRANS", "FETCH", "INIT", "LINK"):
                for task in screen.get("tasks_by_type", {}).get(kind, []) or []:
                    name = (task.get("name") or "").upper()
                    desc = task.get("description") or ""
                    if name:
                        out[name] = desc
    return out


DESCRIPTIONS = _load_descriptions()


def _tables_for_sp(sp_name: str) -> set[str]:
    sp = SP_DATA.get(sp_name.lower(), {})
    out: set[str] = set()
    for branch in sp.get("branches", []):
        for kind in ("inserts", "updates", "deletes"):
            for t in branch["consequences"].get(kind, []):
                out.add(t.lower())
    return {t for t in out
            if "tmp" not in t and "temp" not in t and len(t) > 3
            and t not in ("dtl", "data", "into")}


def _tables_for_chain(chain_key: str) -> list[str]:
    tabs: set[str] = set()
    for step in CATALOG.get("chains", {}).get(chain_key, []):
        tabs |= _tables_for_sp(step.get("spname", ""))
    return sorted(tabs)


def _classify_task(activity: str, screen: str, task: str) -> str:
    """Return 'save' or 'approve'."""
    chain = CATALOG.get("chains", {}).get(f"{activity}|{screen}|{task}", [])
    sps = [s.get("spname", "").lower() for s in chain]
    desc = DESCRIPTIONS.get(task.upper(), "").lower()

    # Rule 1: explicit description keywords
    if re.search(r"approve|authoris|authorize", desc):
        return "approve"
    if re.search(r"specify|save|create|submit", desc):
        return "save"

    # Rule 2: SP family naming
    if any("_apr_" in sp or sp.endswith("_apr") or sp.startswith("po") and "apr" in sp.split("_") for sp in sps):
        if any("_apr_" in sp for sp in sps):
            return "approve"
    if any("_spfy_" in sp or "_save_" in sp for sp in sps):
        return "save"

    # Rule 3: suffix heuristic — Trn3/Trn4 historically = approve
    m = re.search(r"Trn(\d+)$", task)
    if m and int(m.group(1)) >= 3:
        return "approve"
    return "save"


def build_map() -> dict:
    out: dict[str, dict] = {}
    for activity, rep in TRANS_AUDIT.items():
        main_screen_lower = (activity + "main").lower()
        per_screen: dict[str, dict] = {}

        all_orphan_tasks = rep.get("orphan_tasks", [])
        # Group orphan tasks by screen, excluding the main screen
        by_screen: dict[str, list[dict]] = {}
        for o in all_orphan_tasks:
            if o["screen"].lower() == main_screen_lower:
                continue  # main-screen orphans handled by main commit picker
            by_screen.setdefault(o["screen"], []).append(o)

        for screen, tasks in by_screen.items():
            buckets: dict[str, dict] = {}
            for t in tasks:
                kind = _classify_task(activity, screen, t["task"])
                tables = _tables_for_chain(t["chain_key"])
                if kind not in buckets:
                    buckets[kind] = {
                        "task": t["task"],
                        "chain_key": t["chain_key"],
                        "tables": tables,
                        "description": DESCRIPTIONS.get(t["task"].upper(), ""),
                    }
                else:
                    # Multiple tasks in same bucket — keep the first one with more tables
                    if len(tables) > len(buckets[kind]["tables"]):
                        buckets[kind] = {
                            "task": t["task"],
                            "chain_key": t["chain_key"],
                            "tables": tables,
                            "description": DESCRIPTIONS.get(t["task"].upper(), ""),
                        }

            all_tables = sorted({tb for b in buckets.values() for tb in b["tables"]})
            per_screen[screen] = {
                "save":    buckets.get("save"),
                "approve": buckets.get("approve"),
                "all_tables": all_tables,
            }

        if per_screen:
            out[activity] = per_screen
    return out


def main() -> None:
    mp = build_map()
    out_path = ROOT / "out/audit/subscreen_commits.json"
    out_path.write_text(json.dumps(mp, indent=2))

    print("SUB-SCREEN COMMIT MAP")
    print("=" * 70)
    for act in sorted(mp):
        print(f"\n{act}")
        for screen, info in mp[act].items():
            save = info.get("save")
            apr  = info.get("approve")
            print(f"  {screen}")
            if save:
                print(f"    save     → {save['task']:<22} writes {len(save['tables'])} tables: {save['tables']}")
            if apr:
                print(f"    approve  → {apr['task']:<22} writes {len(apr['tables'])} tables: {apr['tables']}")
    print(f"\nWrote: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
