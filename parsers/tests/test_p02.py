"""Golden tests for p02 screen state parser."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "parsers"))
from p02_screen_state import parse_all


def test_p02() -> None:
    r = parse_all()

    # ── 1. We parsed _State.xml files ────────────────────────────────────
    assert r["file_count"] > 0
    assert r["parsed_count"] == r["file_count"], \
        f"parsed {r['parsed_count']}/{r['file_count']} (parse errors present)"

    # ── 2. PoCrtMain state file present ──────────────────────────────────
    pocrtmain = r["by_ui"].get("pocrtmain")
    assert pocrtmain is not None, f"pocrtmain missing from by_ui. Keys: {list(r['by_ui'].keys())}"

    info = pocrtmain["info"]
    assert info["activity"].lower() == "pocrt"
    assert info["component"].lower() == "po"

    # ── 3. PoCrtMain must declare EXACTLY 3 services (FETCH, CREATE, APPROVE) ──
    services = pocrtmain["services"]
    assert len(services) == 3, f"PoCrtMain services = {len(services)}, expected 3"

    svc_tasknames = sorted(s["taskname"].lower() for s in services)
    expected = sorted(["pocrtmainfth", "pocrtmainsbt", "pocrtmaintrn4"])
    assert svc_tasknames == expected, f"PoCrtMain service tasknames = {svc_tasknames}, expected {expected}"

    # ── 4. Each service has exactly 4 states ─────────────────────────────
    for svc in services:
        assert svc["state_count"] == 4, \
            f"service {svc['taskname']} has {svc['state_count']} states, expected 4"
        state_ids = sorted(s["id"] for s in svc["states"])
        assert state_ids == sorted(["project_details_off", "project_details_on",
                                    "state_off", "state_on"]), \
            f"service {svc['taskname']} state ids = {state_ids}"

    # ── 5. PoCrtTrm (Terms sub-screen) state file also present ───────────
    pocrttrm = r["by_ui"].get("pocrttrm")
    assert pocrttrm is not None, "pocrttrm state file should also be present"

    print(f"✓ p02: {r['parsed_count']} state files parsed — all assertions pass")
    print(f"   PoCrtMain: 3 services × 4 states each = canonical spine + splice triggers")


if __name__ == "__main__":
    test_p02()
