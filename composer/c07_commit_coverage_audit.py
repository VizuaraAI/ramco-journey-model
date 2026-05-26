"""c07_commit_coverage_audit — TRANS coverage audit for the chatbot.

For each (activity, screen, TRANS task) triple in the service catalog this audit
answers three questions:

    1. Does our chatbot ever fire this TRANS task?
    2. Which tables would this TRANS write to (via its SP chain)?
    3. If we never fire it, are any of those tables ORPHANED (i.e. not
       reachable by any TRANS we DO fire)?

Output: out/audit/trans_coverage.json + a human-readable Markdown report.

This is the audit that should have been run before v2, v3 ... v8 shipped.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "out/parsed/service_catalog.json").read_text())
SP_DATA = json.loads((ROOT / "out/parsed/sp_branches.json").read_text())["sps"]


def _tables_written_by_sp(sp_name: str) -> set[str]:
    sp = SP_DATA.get(sp_name.lower(), {})
    out: set[str] = set()
    for branch in sp.get("branches", []):
        for kind in ("inserts", "updates", "deletes"):
            for tbl in branch["consequences"].get(kind, []):
                out.add(tbl.lower())
    # Filter staging / temp / parser-junk
    out = {t for t in out
           if "tmp" not in t and "temp" not in t and len(t) > 3
           and t not in ("dtl", "data", "into")}
    return out


def _tables_for_chain(chain_key: str) -> set[str]:
    out: set[str] = set()
    for step in CATALOG.get("chains", {}).get(chain_key, []):
        out |= _tables_written_by_sp(step.get("spname", ""))
    return out


# ── The set of TRANS tasks our v8 bot actually fires ──
# v8 inherits from v7 → v6 → ... → v1. The picker in v1/v2 selects ONLY from
# the MAIN screen's TRANS tasks for the locked journey. Sub-screen TRANS are
# never fired today.
def _v8_fireable_keys() -> set[str]:
    """Conservative inventory of catalog chains that v8 can fire today.
    For PoCrt the main screen is PoCrtMain; for PoAmnd it's PoAmndMain; etc.
    """
    fireable: set[str] = set()
    # Iterate activities; the convention is <activity>Main is the main screen.
    for chain_key in CATALOG.get("chains", {}):
        parts = chain_key.split("|")
        if len(parts) != 3:
            continue
        activity, screen, task = parts
        if screen.lower() == (activity + "main").lower():
            # main-screen tasks. v8's picker selects from the TRANS subset.
            if re.search(r"(Trn\d|Tran\d?|Sbt|Save|Sub|Apr|Approve)", task, re.I):
                fireable.add(chain_key)
    return fireable


def audit() -> dict:
    """Build the coverage report."""
    fireable = _v8_fireable_keys()
    fireable_tables: set[str] = set()
    for k in fireable:
        fireable_tables |= _tables_for_chain(k)

    activity_reports: dict[str, dict] = {}

    for chain_key, steps in CATALOG.get("chains", {}).items():
        parts = chain_key.split("|")
        if len(parts) != 3:
            continue
        activity, screen, task = parts

        # Only TRANS-ish tasks; skip LINK / FETCH / INIT / UI helpers
        if not re.search(r"(Trn\d|Tran\d?|Sbt|Sub|Apr|Approve|Save)$", task, re.I):
            continue

        sps = [step.get("spname", "") for step in steps]
        tables = _tables_for_chain(chain_key)
        if not tables:
            continue  # tasks with no DB effect — skip
        fired_today = chain_key in fireable
        orphan_tables = sorted(tables - fireable_tables) if not fired_today else []

        act = activity_reports.setdefault(activity, {
            "fireable_tasks": [],
            "orphan_tasks": [],
            "tables_reachable_today": set(),
            "tables_orphaned_today": set(),
        })
        entry = {
            "screen": screen,
            "task": task,
            "chain_key": chain_key,
            "sp_count": len(sps),
            "sps": sps,
            "tables": sorted(tables),
            "orphan_tables_for_this_task": orphan_tables,
        }
        if fired_today:
            act["fireable_tasks"].append(entry)
            act["tables_reachable_today"] |= tables
        else:
            act["orphan_tasks"].append(entry)
            # Truly orphaned = no fireable task in same activity touches them
            local_fireable_tables: set[str] = set()
            for k in fireable:
                if k.startswith(activity + "|"):
                    local_fireable_tables |= _tables_for_chain(k)
            local_orphans = tables - local_fireable_tables
            act["tables_orphaned_today"] |= local_orphans

    # Convert sets → sorted lists for JSON
    for act, rep in activity_reports.items():
        rep["tables_reachable_today"] = sorted(rep["tables_reachable_today"])
        rep["tables_orphaned_today"] = sorted(rep["tables_orphaned_today"])

    return activity_reports


def render_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# TRANS Coverage Audit — v8 baseline\n")
    lines.append("For every TRANS task in the service catalog, this audit answers:")
    lines.append("- **Do we fire it today?** (yes/no)")
    lines.append("- **What tables would its SP chain write to?**")
    lines.append("- **If we don't fire it — are those tables reachable by anything we DO fire?**\n")
    lines.append("---\n")

    for activity in sorted(report.keys()):
        rep = report[activity]
        fired = rep["fireable_tasks"]
        orphan = rep["orphan_tasks"]
        lines.append(f"## {activity}\n")
        lines.append(f"- Fireable TRANS tasks today: **{len(fired)}**")
        lines.append(f"- Orphan TRANS tasks (never fired): **{len(orphan)}**")
        lines.append(f"- Tables reachable today: **{len(rep['tables_reachable_today'])}**")
        lines.append(f"- Tables ORPHANED today: **{len(rep['tables_orphaned_today'])}**\n")

        if orphan:
            lines.append("### Orphan TRANS tasks\n")
            lines.append("| screen | task | SPs | tables written | orphan? |")
            lines.append("|---|---|---:|---|---|")
            for o in orphan:
                tabs = ", ".join(o["tables"])
                orph = ", ".join(o["orphan_tables_for_this_task"]) or "—"
                lines.append(f"| {o['screen']} | `{o['task']}` | {o['sp_count']} | {tabs} | {orph} |")
            lines.append("")

        if rep["tables_orphaned_today"]:
            lines.append("### Tables fully orphaned (no fireable task reaches them)\n")
            for t in rep["tables_orphaned_today"]:
                lines.append(f"- `{t}`")
            lines.append("")

        lines.append("---\n")
    return "\n".join(lines)


def main() -> None:
    report = audit()
    (ROOT / "out/audit").mkdir(parents=True, exist_ok=True)
    json_path = ROOT / "out/audit/trans_coverage.json"
    md_path = ROOT / "out/audit/trans_coverage.md"

    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(render_markdown(report))

    # Console summary
    print("TRANS COVERAGE AUDIT (v8 baseline)")
    print("=" * 70)
    total_orphan_tasks = 0
    total_orphan_tables: set[str] = set()
    for act in sorted(report.keys()):
        rep = report[act]
        n_orphan = len(rep["orphan_tasks"])
        n_orphan_tables = len(rep["tables_orphaned_today"])
        total_orphan_tasks += n_orphan
        total_orphan_tables |= set(rep["tables_orphaned_today"])
        if n_orphan or n_orphan_tables:
            print(f"  {act:<8}  orphan_tasks={n_orphan:<3}  orphan_tables={n_orphan_tables}")
    print("-" * 70)
    print(f"TOTAL orphan TRANS tasks across all activities: {total_orphan_tasks}")
    print(f"TOTAL orphan tables across all activities:      {len(total_orphan_tables)}")
    print(f"\nWrote: {json_path.relative_to(ROOT)}")
    print(f"Wrote: {md_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
