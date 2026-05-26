"""P2 · composer — build the journey model
=============================================

Joins the 6 parser outputs into one structured journey model per activity.

Reads:
  out/parsed/module_manifest.json     (p01)
  out/parsed/screen_states.json       (p02)
  out/parsed/screen_forms.json        (p03)
  out/parsed/screen_behaviour.json    (p04)
  out/parsed/service_catalog.json     (p05)
  out/parsed/sp_branches.json         (p06)

Writes:
  out/model/activities/<ACTIVITY>.json  (one per user-facing journey)
  out/model/module_graph.json           (cross-journey edges)

Determinism: L2 — pure joins, no LLM, no fuzzy matching.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT / "out" / "parsed"
OUT_DIR = ROOT / "out" / "model" / "activities"
GRAPH_OUT = ROOT / "out" / "model" / "module_graph.json"


# The 14 user-facing PO journeys (admin journeys excluded for now)
USER_FACING = {
    "POCRT", "POCRTQTN", "POCRTSO", "POCRTTEN", "POCOPY",
    "POAMND", "POAPP", "POEDT", "POVIW", "POMTN",
    "POHOLD", "POSCL", "POACCCUSGMOD", "POHLP",
}


def load_parsers() -> dict:
    return {
        "manifest":  json.loads((PARSED / "module_manifest.json").read_text()),
        "states":    json.loads((PARSED / "screen_states.json").read_text()),
        "forms":     json.loads((PARSED / "screen_forms.json").read_text()),
        "behaviour": json.loads((PARSED / "screen_behaviour.json").read_text()),
        "catalog":   json.loads((PARSED / "service_catalog.json").read_text()),
        "sps":       json.loads((PARSED / "sp_branches.json").read_text()),
    }


def build_activity(activity_name: str, parsed: dict) -> dict:
    """Build the model for one activity."""
    act = parsed["manifest"]["activity_index"].get(activity_name)
    if act is None:
        return {"activity": activity_name, "error": "not in manifest"}

    # Map activity name → catalog activity casing (catalog uses CamelCase, manifest uses UPPERCASE)
    # e.g. POCRT → PoCrt
    cat_summaries = parsed["catalog"]["activity_summaries"]
    cat_act_key = None
    for k in cat_summaries:
        if k.upper() == activity_name:
            cat_act_key = k
            break
    cat_summary = cat_summaries.get(cat_act_key, {}) if cat_act_key else {}

    # SP chains: pull all chains under this activity
    chains = parsed["catalog"]["chains"]
    activity_chains: dict[str, dict] = {}
    if cat_act_key:
        prefix = cat_act_key + "|"
        for key, chain in chains.items():
            if key.startswith(prefix):
                _, ui, task = key.split("|", 2)
                activity_chains[f"{ui}.{task}"] = chain

    # Screens: for each ILBO, build screen entry by joining state + form + behaviour
    screens: list[dict] = []
    for ilbo in act["ilbos"]:
        ilbo_lc = ilbo["name"].lower()
        state = parsed["states"]["by_ui"].get(ilbo_lc)
        form = parsed["forms"]["by_ilbo"].get(ilbo_lc)
        behav = parsed["behaviour"]["by_ilbo"].get(ilbo_lc)

        # Canonical spine: services from state XML (in order Fetch → Submit → Approve)
        services_canonical = []
        if state:
            for svc in state["services"]:
                services_canonical.append({
                    "service_name": svc["name"],
                    "taskname": svc["taskname"],
                    "states": [s["id"] for s in svc["states"]],
                })

        # All tasks for this ILBO from manifest
        ilbo_tasks = []
        for page in ilbo["pages"]:
            for t in page["tasks"]:
                # Augment with the JS success message if available
                t2 = dict(t)
                msg = parsed["behaviour"]["task_message_index"].get(t["name"])
                if msg:
                    t2["js_success_message"] = msg
                ilbo_tasks.append(t2)

        # Categorise tasks
        trans_tasks = [t for t in ilbo_tasks if t.get("type") == "TRANS"]
        link_tasks  = [t for t in ilbo_tasks if t.get("type") == "LINK"]
        ui_tasks    = [t for t in ilbo_tasks if t.get("type") == "UI"]
        help_tasks  = [t for t in ilbo_tasks if t.get("type") == "HELP"]
        fetch_tasks = [t for t in ilbo_tasks if t.get("type") == "FETCH"]
        init_tasks  = [t for t in ilbo_tasks if t.get("type") == "INIT"]

        # Slots from the form .htm parser
        slots = form.get("slots", []) if form else []

        # Also get tasks from the form's meta tag (richer than manifest in some cases)
        form_tasks = form.get("tasks_from_meta_tag", []) if form else []
        # Detect manifest-vs-form discrepancies
        manifest_task_names = {t["name"] for t in ilbo_tasks}
        form_task_names = {t["name"] for t in form_tasks}
        only_in_form = sorted(form_task_names - manifest_task_names)
        only_in_manifest = sorted(manifest_task_names - form_task_names)

        # NEW: collect_steps — decorative section grouping from p03's section
        # records. Strictly read-only: bot reads this for UX only; never feeds
        # back into TRANS selection, SP chain, validation, or splice triggers.
        # Filter: only TITLED, non-garbage sections become user-visible steps.
        sections_from_form = (form or {}).get("sections", [])
        collect_steps = []
        step_no = 0
        for sec in sections_from_form:
            # Skip layout sections that aren't user-visible step boundaries
            if sec.get("caption_garbage"):  continue
            if not sec.get("is_titled"):    continue
            if sec.get("slot_count", 0) == 0 and not sec.get("is_grid"):
                # Empty non-grid sections (e.g. "Links") aren't fill steps
                continue
            step_no += 1
            collect_steps.append({
                "step": step_no,
                "section_id":      sec["section_id"],
                "caption":         sec["caption_clean"] or sec["section_id"],
                "label":           f"Collect {sec['caption_clean']}" if sec["caption_clean"] else "",
                "is_grid":         sec["is_grid"],
                "slot_count":      sec["slot_count"],
                "mandatory_count": sec["mandatory_count"],
                "slot_labels":     sec.get("slot_labels", []),
            })

        screens.append({
            "ilbo_name": ilbo["name"],
            "ilbo_desc": ilbo["description"],
            "canonical_services": services_canonical,
            "task_count": len(ilbo_tasks),
            "tasks_by_type": {
                "FETCH": fetch_tasks, "INIT": init_tasks,
                "TRANS": trans_tasks, "LINK": link_tasks,
                "UI": ui_tasks, "HELP": help_tasks,
            },
            "slot_count": len(slots),
            "slots": slots,
            "collect_steps": collect_steps,        # NEW: decorative UX layer
            "discrepancies": {
                "tasks_only_in_form": only_in_form,
                "tasks_only_in_manifest": only_in_manifest,
            },
        })

    # SPLICES — three sources:
    # A) UI splices: every LINK task on any screen of this activity
    ui_splices = []
    for sc in screens:
        for link in sc["tasks_by_type"]["LINK"]:
            ui_splices.append({
                "kind": "ui_link",
                "splice_id": link["name"],
                "description": link["description"],
                "hook_screen": sc["ilbo_name"],
                "trigger": f"user_clicks_{link['primary_control_bt']}",
                "optional": True,
            })

    # B) State splices: named states from each screen's state XML
    state_splices = []
    for sc in screens:
        for svc in sc["canonical_services"]:
            for state_id in svc["states"]:
                if state_id in ("default", ""):
                    continue
                state_splices.append({
                    "kind": "state_machine",
                    "splice_id": f"{sc['ilbo_name']}.{svc['taskname']}.{state_id}",
                    "hook_screen": sc["ilbo_name"],
                    "hook_service": svc["taskname"],
                    "trigger": state_id,  # e.g. "project_details_on"
                    "optional": False,
                })

    # C) Data splices: real splices from SPs that this activity invokes
    activity_sps = set()
    for chain in activity_chains.values():
        for step in chain:
            if step["spname"]:
                activity_sps.add(step["spname"])

    data_splices = []
    for splice_key, occurrences in parsed["sps"]["splice_index"].items():
        # Keep if at least one occurrence is in an SP this activity uses
        relevant = [o for o in occurrences if o["sp"] in activity_sps]
        if relevant:
            data_splices.append({
                "kind": "data_triggered",
                "splice_id": splice_key,
                "trigger": splice_key,
                "sp_occurrences": relevant[:3],
                "optional": False,
            })

    # Canonical spine = sequence of commit-grade tasks on the MAIN screen
    # The "main" screen has activity name + "MAIN" (e.g. POCRTMAIN)
    main_ilbo_name = activity_name + "MAIN"
    main_screen = next((s for s in screens if s["ilbo_name"] == main_ilbo_name), None)
    canonical_spine = []
    if main_screen:
        # Order: FETCH → INIT → fill (implicit) → TRANS commits
        for fetch in main_screen["tasks_by_type"]["FETCH"]:
            canonical_spine.append({
                "phase": "fetch", "task": fetch["name"], "description": fetch["description"]
            })
        for init in main_screen["tasks_by_type"]["INIT"]:
            canonical_spine.append({
                "phase": "init", "task": init["name"], "description": init["description"]
            })
        canonical_spine.append({
            "phase": "fill",
            "task": None,
            "description": "User fills the form (implicit; bot's responsibility)",
        })
        for trans in main_screen["tasks_by_type"]["TRANS"]:
            # SP chain lookup — try both upper-case and CamelCase key shapes.
            # Catalog key format: "<ui>.<task>" with the casing matching what
            # parsed/service_catalog.json stored.
            sp_chain = _find_chain(activity_chains, main_ilbo_name, trans["name"])
            canonical_spine.append({
                "phase": "commit",
                "task": trans["name"],
                "description": trans["description"],
                "sp_chain": sp_chain,
            })

    return {
        "activity": activity_name,
        "description": act["description"],
        "is_user_facing": activity_name in USER_FACING,
        "screen_count": len(screens),
        "main_screen": main_ilbo_name,
        "canonical_spine": canonical_spine,
        "splice_summary": {
            "ui_splices": len(ui_splices),
            "state_splices": len(state_splices),
            "data_splices": len(data_splices),
            "total": len(ui_splices) + len(state_splices) + len(data_splices),
        },
        "splices": {
            "ui_splices": ui_splices,
            "state_splices": state_splices,
            "data_splices": data_splices,
        },
        "screens": screens,
        "sp_chains": activity_chains,
        "sp_chains_summary": cat_summary,
    }


def _find_chain(activity_chains: dict, ilbo: str, task: str) -> list:
    """Find SP chain for ilbo.task — try multiple casing conventions."""
    # activity_chains keys look like "PoCrtMain.PoCrtMainSbt" (after we strip activity prefix)
    targets = [
        f"{ilbo}.{task}",                                # direct upper
        f"{ilbo.lower()}.{task.lower()}",                # lower
    ]
    for k, chain in activity_chains.items():
        if k.upper() == f"{ilbo}.{task}".upper():
            return chain
    return []


def build_module_graph(activities_built: dict[str, dict], parsed: dict) -> dict:
    """Build cross-journey edges by finding LINK tasks that point to other activities."""
    edges = []
    # We know certain LINK tasks navigate to other activities by description match
    # (e.g. "Edit PO" → POEDT, "Approve PO" → POAPP, "Amend PO" → POAMND)
    desc_to_activity = {
        "edit po": "POEDT",
        "amend po": "POAMND",
        "approve po": "POAPP",
        "shortclose po": "POSCL",
        "change status": "POHOLD",
        "view purchase order": "POVIW",
    }
    for act_name, act in activities_built.items():
        if "error" in act: continue
        for splice in act["splices"]["ui_splices"]:
            desc_lc = splice["description"].lower()
            for needle, target in desc_to_activity.items():
                if needle in desc_lc and target != act_name:
                    edges.append({
                        "from_activity": act_name,
                        "from_screen": splice["hook_screen"],
                        "via_task": splice["splice_id"],
                        "to_activity": target,
                        "label": splice["description"],
                    })

    return {
        "node_count": len(activities_built),
        "edge_count": len(edges),
        "nodes": sorted(activities_built.keys()),
        "edges": edges,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_OUT.parent.mkdir(parents=True, exist_ok=True)

    parsed = load_parsers()
    activity_names = sorted(parsed["manifest"]["activity_index"].keys())

    built: dict[str, dict] = {}
    for name in activity_names:
        model = build_activity(name, parsed)
        built[name] = model
        out_file = OUT_DIR / f"{name}.json"
        out_file.write_text(json.dumps(model, indent=2), encoding="utf-8")

    # User-facing journeys summary
    user_facing = [a for a in built.values() if a.get("is_user_facing")]

    print(f"P2: built {len(built)} activity models → {OUT_DIR.relative_to(ROOT)}/")
    print(f"   {len(user_facing)} user-facing journeys:")
    for a in user_facing:
        if "error" in a:
            print(f"     ✗ {a['activity']:14s}  ERROR: {a['error']}")
            continue
        print(f"     {a['activity']:14s}  spine={len(a['canonical_spine']):2d}  "
              f"splices: {a['splice_summary']['ui_splices']:2d} UI + "
              f"{a['splice_summary']['state_splices']:2d} state + "
              f"{a['splice_summary']['data_splices']:2d} data")

    graph = build_module_graph(built, parsed)
    GRAPH_OUT.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(f"   module graph: {graph['edge_count']} cross-journey edges → {GRAPH_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
