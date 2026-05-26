"""c06 · split per-activity handoff views
==============================================

The monolithic out/model/activities/POCRT.json is what the BOT consumes — it
needs all of it in one fast-loading file. But for a human (or the Chia team)
trying to read or review a journey, it's overwhelming: 1 MB / 36k lines with
6 important canonical-spine entries buried inside thousands of slot, splice,
and sp_chain entries.

This pass produces, per activity, a clean folder of focused files:

  out/model/activities/POCRT/
    ├── 01_spine.json          ← canonical journey (small, ~80 lines)
    ├── 02_splices.json        ← splices grouped by kind
    ├── 03_screens.json        ← per-screen slots + collect_steps + counts
    ├── 04_sp_chains.json      ← task → SP-chain mapping
    ├── 05_taxonomy.json       ← entity_produced / entity_consumed
    └── HANDOFF.md             ← human-readable one-pager

The bot still reads the monolithic POCRT.json. These split views are for
handoff, review, and documentation — same data, repackaged.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "out" / "model" / "activities"
TAXONOMY = json.loads((ROOT / "out" / "model" / "entity_taxonomy.json").read_text(encoding="utf-8"))


def make_handoff_md(act: str, model: dict) -> str:
    """Produce a human-readable markdown summary."""
    spine = model.get("canonical_spine", [])
    splices = model.get("splices", {})
    screens = model.get("screens", [])
    sp_chains = model.get("sp_chains", {})

    n_ui = len(splices.get("ui_splices", []))
    n_state = len(splices.get("state_splices", []))
    n_data = len(splices.get("data_splices", []))
    n_screens = len(screens)
    total_slots = sum(s.get("slot_count", 0) for s in screens)

    tax = TAXONOMY.get(act, {})
    produced = tax.get("entity_produced")
    consumed = tax.get("entity_consumed")

    lines = []
    lines.append(f"# {act} — {model.get('description', '')}")
    lines.append("")
    lines.append("## At a glance")
    lines.append("")
    lines.append(f"- **Activity:** `{act}`")
    lines.append(f"- **Main screen:** `{model.get('main_screen', '')}`")
    lines.append(f"- **Screen count:** {n_screens}")
    lines.append(f"- **Total slots across all screens:** {total_slots}")
    lines.append(f"- **Splices:** {n_ui} UI · {n_state} state · {n_data} data · **{n_ui + n_state + n_data} total**")
    lines.append(f"- **SP chains:** {len(sp_chains)}")
    if produced:
        lines.append(f"- **Produces entity:** `{produced['kind']}` (id slot: `{produced['id_slot']}`)")
    if consumed:
        lines.append(f"- **Consumes entity:** `{consumed['kind']}` (id slot: `{consumed['id_slot']}`)")
    lines.append("")
    lines.append("## Canonical spine")
    lines.append("")
    lines.append("| # | Phase | Task | Description | SPs |")
    lines.append("|---|---|---|---|---|")
    for i, step in enumerate(spine, 1):
        phase = step.get("phase", "?")
        task = step.get("task") or "*(implicit)*"
        desc = step.get("description", "")
        sps = step.get("sp_chain", []) or []
        lines.append(f"| {i} | {phase} | `{task}` | {desc} | {len(sps)} |")
    lines.append("")

    # Commits with their SP chains expanded
    commits = [s for s in spine if s.get("phase") == "commit"]
    if commits:
        lines.append("## Commit SP chains (in execution order)")
        for c in commits:
            lines.append("")
            lines.append(f"### `{c['task']}` — {c.get('description', '')}")
            lines.append("")
            sps = c.get("sp_chain", []) or []
            for sp in sps:
                lines.append(f"- seq {sp.get('sequenceno', '?')}: `{sp.get('spname', '?')}`")

    # Splices by kind
    if n_ui:
        lines.append("")
        lines.append(f"## UI splices · {n_ui}")
        lines.append("")
        lines.append("Sub-screens the user can open by clicking a LINK control.")
        lines.append("")
        ui_subset = splices["ui_splices"][:12]
        for s in ui_subset:
            lines.append(f"- `{s.get('splice_id')}` → opens **{s.get('hook_screen')}** · {s.get('description', '')}")
        if n_ui > 12:
            lines.append(f"- *…and {n_ui - 12} more*")

    if n_data:
        lines.append("")
        lines.append(f"## Data splices · {n_data}")
        lines.append("")
        lines.append("Triggered when a slot value matches a specific condition in the SP code.")
        lines.append("")
        seen = set()
        for s in splices["data_splices"]:
            trig = s.get("trigger", "")
            if trig in seen: continue
            seen.add(trig)
            if len(seen) > 12:
                lines.append(f"- *…and more*")
                break
            lines.append(f"- `{trig}`")

    # Screens summary
    if n_screens:
        lines.append("")
        lines.append("## Screens")
        lines.append("")
        lines.append("| Screen | Slots | Collect steps |")
        lines.append("|---|---|---|")
        for sc in screens:
            cs = sc.get("collect_steps", []) or []
            step_captions = ", ".join(s.get("caption", "?") for s in cs) or "—"
            lines.append(f"| `{sc.get('ilbo_name')}` | {sc.get('slot_count', 0)} | {step_captions} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("This file is generated automatically from the parsed Ramco artifacts.")
    lines.append("The corresponding machine-readable views are in this folder:")
    lines.append("`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.")
    return "\n".join(lines) + "\n"


def split_activity(act: str, model: dict, out_dir: Path) -> dict:
    """Produce the per-activity split files and HANDOFF.md."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 01 — canonical spine (small, ~80 lines for PoCrt)
    spine_view = {
        "activity":      model.get("activity"),
        "description":   model.get("description"),
        "main_screen":   model.get("main_screen"),
        "canonical_spine": model.get("canonical_spine", []),
    }
    (out_dir / "01_spine.json").write_text(json.dumps(spine_view, indent=2), encoding="utf-8")

    # 02 — splices, grouped by kind
    splices_view = {
        "activity":      model.get("activity"),
        "splice_summary": model.get("splice_summary", {}),
        "splices":        model.get("splices", {}),
    }
    (out_dir / "02_splices.json").write_text(json.dumps(splices_view, indent=2), encoding="utf-8")

    # 03 — screens (form layout)
    screens_view = {
        "activity":     model.get("activity"),
        "screen_count": model.get("screen_count"),
        "screens":      model.get("screens", []),
    }
    (out_dir / "03_screens.json").write_text(json.dumps(screens_view, indent=2), encoding="utf-8")

    # 04 — SP chains
    chains_view = {
        "activity":   model.get("activity"),
        "sp_chains":  model.get("sp_chains", {}),
        "summary":    model.get("sp_chains_summary", {}),
    }
    (out_dir / "04_sp_chains.json").write_text(json.dumps(chains_view, indent=2), encoding="utf-8")

    # 05 — taxonomy
    tax = TAXONOMY.get(act, {})
    (out_dir / "05_taxonomy.json").write_text(json.dumps(tax, indent=2), encoding="utf-8")

    # HANDOFF.md
    (out_dir / "HANDOFF.md").write_text(make_handoff_md(act, model), encoding="utf-8")

    # File sizes for reporting
    sizes = {}
    for name in ["01_spine.json", "02_splices.json", "03_screens.json",
                 "04_sp_chains.json", "05_taxonomy.json", "HANDOFF.md"]:
        path = out_dir / name
        sizes[name] = path.stat().st_size
    return sizes


def main():
    activities = sorted(MODEL_DIR.glob("*.json"))
    activities = [p for p in activities if not p.is_dir()]

    print(f"c06 · splitting {len(activities)} activities into handoff views...")
    print()

    for act_file in activities:
        act = act_file.stem
        model = json.loads(act_file.read_text(encoding="utf-8"))
        if not model.get("is_user_facing"):
            continue
        out_dir = MODEL_DIR / act
        sizes = split_activity(act, model, out_dir)
        total = sum(sizes.values())
        mono_size = act_file.stat().st_size
        print(f"  {act:14s}  monolithic={mono_size//1024:>5d} KB  →  split:")
        for n, sz in sizes.items():
            print(f"      {n:24s} {sz//1024 if sz>=1024 else 0:>3d} KB  ({sz:>7,d} bytes)")
        print()

    print("Done. The bot still reads the monolithic POCRT.json (deterministic source).")
    print("These split views are for handoff, review, documentation.")


if __name__ == "__main__":
    main()
