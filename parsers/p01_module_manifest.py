"""p01 · module manifest parser
================================

Reads:  artifacts/ramco/PO/ScreenObjects/PO/PO_info.xml
Writes: out/parsed/module_manifest.json

Extracts every Activity → ILBO → Page → Task with task type and human description.

Layer L1 — pure deterministic XML walk. No LLM, no fuzzy matching.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "artifacts" / "ramco" / "PO" / "ScreenObjects" / "PO" / "PO_info.xml"
OUT_DIR = ROOT / "out" / "parsed"
OUT = OUT_DIR / "module_manifest.json"


# Known task types in Ramco's PO module. Anything outside this set is an unknown
# and surfaces as a parse_error so we can extend deterministically.
KNOWN_TASK_TYPES = {
    "FETCH", "INIT", "TRANS", "UI", "HELP", "LINK", "DISPOSAL", "REPORT"
}


def parse_manifest() -> dict:
    if not ARTIFACT.exists():
        raise FileNotFoundError(f"PO_info.xml not found at {ARTIFACT}")

    # PO_info.xml is not a well-formed single-rooted XML (it begins with
    # <CUSTOMER> ... and may not close cleanly). Use a tolerant regex walk
    # over the activity blocks rather than ET on the whole file.
    text = ARTIFACT.read_text(encoding="utf-8", errors="replace")

    activities: list[dict] = []
    parse_errors: list[dict] = []

    # Pull each <ACTIVITY ...> ... </ACTIVITY> block
    activity_blocks = re.findall(
        r'<ACTIVITY\s+Name="([^"]+)"\s+Desc="([^"]+)">(.*?)</ACTIVITY>',
        text, re.DOTALL
    )

    for act_name, act_desc, act_body in activity_blocks:
        ilbos: list[dict] = []
        ilbo_blocks = re.findall(
            r'<ILBO\s+Name="([^"]+)"\s+Desc="([^"]+)">(.*?)</ILBO>',
            act_body, re.DOTALL
        )
        for ilbo_name, ilbo_desc, ilbo_body in ilbo_blocks:
            pages: list[dict] = []
            page_blocks = re.findall(
                r'<PAGE\s+Name="([^"]+)"\s+Desc="([^"]+)">(.*?)</PAGE>',
                ilbo_body, re.DOTALL
            )
            for page_name, page_desc, page_body in page_blocks:
                tasks: list[dict] = []
                # Tasks are self-closing: <TASK Name="..." Desc="..." Type="..."
                #                                Pattern="..." PrimaryControlBT="..."/>
                task_matches = re.finditer(
                    r'<TASK\s+([^/]+?)/>', page_body
                )
                for tm in task_matches:
                    attrs_str = tm.group(1)
                    attrs = dict(re.findall(r'(\w+)="([^"]*)"', attrs_str))
                    task = {
                        "name": attrs.get("Name", ""),
                        "description": attrs.get("Desc", ""),
                        "type": attrs.get("Type", ""),
                        "pattern": attrs.get("Pattern", ""),
                        "primary_control_bt": attrs.get("PrimaryControlBT", ""),
                    }
                    if not task["name"]:
                        parse_errors.append({
                            "kind": "task_without_name",
                            "activity": act_name, "ilbo": ilbo_name,
                            "page": page_name, "raw": attrs_str[:200]
                        })
                        continue
                    if task["type"] and task["type"] not in KNOWN_TASK_TYPES:
                        parse_errors.append({
                            "kind": "unknown_task_type",
                            "activity": act_name, "ilbo": ilbo_name,
                            "task": task["name"], "type": task["type"]
                        })
                    tasks.append(task)
                pages.append({
                    "name": page_name,
                    "description": page_desc,
                    "tasks": tasks,
                    "task_count": len(tasks),
                })
            ilbos.append({
                "name": ilbo_name,
                "description": ilbo_desc,
                "pages": pages,
            })
        activities.append({
            "name": act_name,
            "description": act_desc,
            "ilbos": ilbos,
            "ilbo_count": len(ilbos),
            "task_count": sum(len(p["tasks"]) for i in ilbos for p in i["pages"]),
        })

    # Module-level meta from the file header
    module_meta = {}
    m = re.search(r'<COMPONENT\s+Name="([^"]+)"\s+Desc="([^"]+)"', text)
    if m:
        module_meta = {"component_name": m.group(1), "component_desc": m.group(2)}

    # Index: activity_name → activity (for fast composer lookup)
    activity_index = {a["name"]: a for a in activities}

    # Index: every task with its full address (activity, ilbo, page, task)
    task_index: list[dict] = []
    for a in activities:
        for i in a["ilbos"]:
            for p in i["pages"]:
                for t in p["tasks"]:
                    task_index.append({
                        "activity": a["name"],
                        "ilbo": i["name"],
                        "page": p["name"],
                        "task_name": t["name"],
                        "task_type": t["type"],
                        "task_desc": t["description"],
                        "primary_control_bt": t["primary_control_bt"],
                    })

    return {
        "source": str(ARTIFACT.relative_to(ROOT)),
        "module": module_meta,
        "activity_count": len(activities),
        "task_count": len(task_index),
        "parse_errors": parse_errors,
        "activities": activities,
        "activity_index": activity_index,
        "task_index": task_index,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = parse_manifest()
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"p01: parsed {result['activity_count']} activities, "
          f"{result['task_count']} tasks → {OUT.relative_to(ROOT)}")
    if result["parse_errors"]:
        print(f"  ⚠ {len(result['parse_errors'])} parse warnings (see output)")


if __name__ == "__main__":
    main()
