"""Golden tests for p04 screen behaviour parser."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "parsers"))
from p04_screen_behaviour import parse_all


def test_p04() -> None:
    r = parse_all()

    assert r["file_count"] > 0, "no _user.js files found"

    # PoCrtMain behaviour file present
    pocrtmain = r["by_ilbo"].get("pocrtmain")
    assert pocrtmain is not None, f"pocrtmain not in by_ilbo. Keys: {list(r['by_ilbo'].keys())}"

    g = pocrtmain["globals"]
    assert g.get("componentName") == "po"
    assert g.get("activityName") == "pocrt"
    assert g.get("ilboName") == "pocrtmain"
    assert g.get("activityDesc") == "Create Direct Purchase Order"

    # Task messages — must have at least a handful
    assert pocrtmain["task_message_count"] >= 10, \
        f"PoCrtMain task message count = {pocrtmain['task_message_count']}"

    # Index lookups
    idx = r["task_message_index"]
    assert "POCRTMAINFTH" in idx
    assert "fetch" in idx["POCRTMAINFTH"].lower()
    assert "POCRTMAINBUDDETAILLNK" in idx
    assert "budget" in idx["POCRTMAINBUDDETAILLNK"].lower()

    print(f"✓ p04: {r['file_count']} _user.js files, "
          f"{r['task_message_index_count']:,} task messages indexed — all assertions pass")


if __name__ == "__main__":
    test_p04()
