"""c09_subscreen_slot_map — derive the canonical slot set per sub-screen.

For each sub-screen that has a commit chain (see subscreen_commits.json), list
the slots (btsynonyms) that uniquely belong to that sub-screen. The bot uses
this to decide:

  "Did the user provide ANY slot that this sub-screen owns? If yes, the
   sub-screen's TRANS chain should fire."

A slot "belongs to" a sub-screen X if:
  - It appears in X.slots with a non-empty btsynonym, AND
  - It does NOT appear on the activity's main screen (so we don't accidentally
    pull main-screen slots into sub-screen dispatch).

Output: out/audit/subscreen_slot_map.json
        { activity: { screen: { owned_btsynonyms, display_labels } } }
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUB_COMMITS = json.loads((ROOT / "out/audit/subscreen_commits.json").read_text())


def _slots_for_screen(activity_camel: str, screen_camel: str) -> list[dict]:
    """Return all slot dicts for a screen, looked up by ilbo_name."""
    upper = activity_camel.upper()
    jf = ROOT / f"out/model/activities/{upper}.json"
    if not jf.exists():
        return []
    data = json.loads(jf.read_text())
    target = screen_camel.upper()
    for screen in data.get("screens", []):
        if (screen.get("ilbo_name") or "").upper() == target:
            return screen.get("slots", []) or []
    return []


def _main_screen_name(activity_camel: str) -> str:
    return f"{activity_camel}Main"


def build_map() -> dict:
    out: dict[str, dict] = {}
    for activity_camel, per_screen in SUB_COMMITS.items():
        main_slots = _slots_for_screen(activity_camel, _main_screen_name(activity_camel))
        main_bts = {(s.get("btsynonym") or "").lower()
                    for s in main_slots if s.get("btsynonym")}
        main_bts.discard("")

        per_screen_out: dict[str, dict] = {}
        for screen, info in per_screen.items():
            sub_slots = _slots_for_screen(activity_camel, screen)
            owned: list[str] = []
            labels: list[str] = []
            for s in sub_slots:
                bt = (s.get("btsynonym") or "").lower()
                if not bt:
                    continue
                if bt in main_bts:
                    continue  # shared with main screen (e.g. supplier_code) — not unique
                # Skip pure displayonly with no editable role
                if s.get("input_type") == "displayonly":
                    continue
                if bt not in owned:
                    owned.append(bt)
                    labels.append(s.get("display_label") or bt)
            per_screen_out[screen] = {
                "owned_btsynonyms": owned,
                "display_labels":   labels,
                # Also list the table-set the sub-screen writes to (for trace)
                "writes_tables":    info.get("all_tables", []),
            }
        if per_screen_out:
            out[activity_camel] = per_screen_out
    return out


def main() -> None:
    mp = build_map()
    out_path = ROOT / "out/audit/subscreen_slot_map.json"
    out_path.write_text(json.dumps(mp, indent=2))

    print("SUB-SCREEN SLOT MAP")
    print("=" * 70)
    for act in sorted(mp):
        print(f"\n{act}")
        for screen, info in mp[act].items():
            owned = info["owned_btsynonyms"]
            print(f"  {screen:<14}  owns {len(owned):>2} slots: {owned[:8]}{'...' if len(owned) > 8 else ''}")
    print(f"\nWrote: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
