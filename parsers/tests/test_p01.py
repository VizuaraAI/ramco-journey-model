"""Golden tests for p01 module manifest parser.

Tests pin specific facts that MUST be in the parsed output. If these break,
something changed in the source XML or the parser regressed.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "parsers"))
from p01_module_manifest import parse_manifest


def test_p01() -> None:
    r = parse_manifest()

    # ── 1. Module identity ────────────────────────────────────────────────
    assert r["module"]["component_name"] == "PO", f"component_name = {r['module'].get('component_name')}"

    # ── 2. Activities ─────────────────────────────────────────────────────
    activity_names = {a["name"] for a in r["activities"]}
    expected = {"POCRT", "POAMND", "POAPP", "POEDT", "POVIW", "POCOPY",
                "POCRTQTN", "POCRTSO", "POCRTTEN", "POMTN", "POHOLD",
                "POSCL", "POHLP"}
    missing = expected - activity_names
    assert not missing, f"Missing activities: {missing}"

    # ── 3. PoCrt-specific facts ───────────────────────────────────────────
    pocrt = r["activity_index"]["POCRT"]
    assert pocrt["description"] == "Create Direct Purchase Order"
    pocrt_ilbo_names = {i["name"] for i in pocrt["ilbos"]}
    assert "POCRTMAIN" in pocrt_ilbo_names, f"POCRTMAIN missing from PoCrt ILBOs: {pocrt_ilbo_names}"

    # ── 4. PoCrtMain canonical tasks must be present with correct types ──
    pocrtmain = next(i for i in pocrt["ilbos"] if i["name"] == "POCRTMAIN")
    page = pocrtmain["pages"][0]
    tasks_by_name = {t["name"]: t for t in page["tasks"]}

    # NOTE: PO_info.xml does NOT contain every task that appears in the
    # screen .htm meta Tasks tag (e.g. POCRTMAINLNK4 for TCD is in the .htm
    # but absent from PO_info.xml). P3 validator should flag this discrepancy.
    # Here we assert only what PO_info.xml does declare on POCRTMAIN.
    expected_tasks = {
        "POCRTMAINFTH":     "FETCH",
        "POCRTMAININI":     "INIT",
        "POCRTMAINSBT":     "TRANS",
        "POCRTMAINTRN4":    "TRANS",
        "POCRTMAINLNK2":    "LINK",   # Schedule
        "POCRTMAINLNK3":    "LINK",   # Terms
        "POCRTMAINLNK6":    "LINK",   # Quality
        "POCRTMAINLNK7":    "LINK",   # Budget
        "POCRTMAINLNK8":    "LINK",   # Dropship
        "POCRTMAINLNK9":    "LINK",   # PR Coverage
        "POCRTMAINLNK10":   "LINK",   # SO Coverage
        "POCRTMAINSUPPUI":  "UI",
    }
    for tname, ttype in expected_tasks.items():
        assert tname in tasks_by_name, f"PoCrtMain missing task: {tname}"
        assert tasks_by_name[tname]["type"] == ttype, \
            f"{tname} type = {tasks_by_name[tname]['type']}, expected {ttype}"

    # ── 5. Description sanity ────────────────────────────────────────────
    assert tasks_by_name["POCRTMAINSBT"]["description"] == "Create PO"
    assert tasks_by_name["POCRTMAINLNK3"]["description"] == "Specify Terms and Condition"
    assert tasks_by_name["POCRTMAINLNK8"]["description"] == "Specify Dropship Address"

    # ── 6. No unknown task types (or, if any, surfaced as parse_errors) ──
    unknowns = [e for e in r["parse_errors"] if e["kind"] == "unknown_task_type"]
    # Allow zero or a small number; this just shouldn't be massive
    assert len(unknowns) <= 5, f"Too many unknown task types: {unknowns[:10]}"

    print(f"✓ p01: {r['activity_count']} activities, {r['task_count']} tasks, "
          f"{len(r['parse_errors'])} warnings — all assertions pass")


if __name__ == "__main__":
    test_p01()
