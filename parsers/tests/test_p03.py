"""Golden tests for p03 screen form parser."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "parsers"))
from p03_screen_form import parse_all, parse_meta_tasks


def test_meta_tasks_parse() -> None:
    sample = "POCRTMAINFTH~Default Fetch:FETCH,POCRTMAINSBT~Create PO:TRANS,POCRTMAINLNK3~Specify Terms and Condition:LINK"
    tasks = parse_meta_tasks(sample)
    assert len(tasks) == 3
    assert tasks[0]["name"] == "POCRTMAINFTH"
    assert tasks[0]["type"] == "FETCH"
    assert tasks[1]["description"] == "Create PO"
    assert tasks[2]["name"] == "POCRTMAINLNK3"
    assert tasks[2]["description"] == "Specify Terms and Condition"


def test_p03() -> None:
    test_meta_tasks_parse()

    r = parse_all()

    # PoCrtMain screen .htm must be parsed
    pocrtmain = r["by_ilbo"].get("pocrtmain")
    assert pocrtmain is not None, f"pocrtmain missing. Available: {list(r['by_ilbo'].keys())[:20]}"

    # Meta identity
    assert pocrtmain["meta"]["activity_name"] == "POCRT"
    assert pocrtmain["meta"]["ilbo_name"] == "POCRTMAIN"

    # Meta Tasks tag — should have the full task set including LNK4 which
    # PO_info.xml DOES NOT contain. This is exactly the discrepancy P3
    # validator will surface.
    task_names = {t["name"] for t in pocrtmain["tasks_from_meta_tag"]}
    must_have_in_htm = {"POCRTMAINFTH", "POCRTMAINSBT", "POCRTMAINTRN4",
                        "POCRTMAINLNK3", "POCRTMAINLNK4", "POCRTMAINLNK7",
                        "POCRTMAINLNK8", "POCRTMAINSUPPUI"}
    missing = must_have_in_htm - task_names
    assert not missing, f"PoCrtMain .htm meta Tasks missing: {missing}"

    # LNK4 must be in .htm (proving the discrepancy with PO_info.xml)
    lnk4 = next((t for t in pocrtmain["tasks_from_meta_tag"]
                 if t["name"] == "POCRTMAINLNK4"), None)
    assert lnk4 is not None
    assert lnk4["type"] == "LINK"
    assert "tax" in lnk4["description"].lower() or "charge" in lnk4["description"].lower()

    # Slot count: should have meaningful slots
    assert pocrtmain["slot_count"] > 50, f"PoCrtMain slot_count = {pocrtmain['slot_count']}"

    # At least one slot should have a non-empty display label
    labelled = [s for s in pocrtmain["slots"] if s["display_label"]]
    assert len(labelled) > 0, "No slots with display labels"

    print(f"✓ p03: {r['file_count']} screens parsed, "
          f"PoCrtMain has {pocrtmain['task_count_from_meta']} tasks (meta tag) "
          f"and {pocrtmain['slot_count']} slots — all assertions pass")


if __name__ == "__main__":
    test_p03()
