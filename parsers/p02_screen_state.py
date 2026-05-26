"""p02 · screen state parser
==============================

Reads:  artifacts/ramco/PO/ScreenObjects/PO/*_State.xml
Writes: out/parsed/screen_states.json

Each _State.xml file declares the services on a screen and the named states
under which sections/controls become visible/enabled. The services are the
canonical-spine skeleton of that screen. The state IDs are splice triggers.

Layer L1 — deterministic XML walk.
"""
from __future__ import annotations
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = ROOT / "artifacts" / "ramco" / "PO" / "ScreenObjects" / "PO"
OUT_DIR = ROOT / "out" / "parsed"
OUT = OUT_DIR / "screen_states.json"


def parse_state_file(path: Path) -> dict:
    """Parse one *_State.xml file into structured form."""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        # Files are well-formed enough for ET when wrapped in safe parsing
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return {"path": str(path), "parse_error": str(e)}

    info = {
        "customer":  root.get("customer", ""),
        "project":   root.get("project", ""),
        "process":   root.get("process", ""),
        "component": root.get("component", ""),
        "activity":  root.get("activity", ""),
        "ui":        root.get("ui", ""),
    }

    services: list[dict] = []
    for svc in root.findall(".//service"):
        states: list[dict] = []
        for st in svc.findall("state"):
            sections = []
            for sec in st.findall(".//section"):
                sections.append({
                    "name": sec.get("name", ""),
                    "visible": sec.get("visible", ""),
                    "enable": sec.get("enable", ""),
                    "collapse": sec.get("collapse", ""),
                })
            controls = []
            for ctrl in st.findall(".//control"):
                views = []
                for vw in ctrl.findall("views/vw"):
                    views.append({
                        "n": vw.get("n", ""),
                        "visible": vw.get("visible", ""),
                    })
                controls.append({
                    "id": ctrl.get("id", ""),
                    "name": ctrl.get("name", ""),
                    "section": ctrl.get("sectionname", ""),
                    "visible": ctrl.get("visible", ""),
                    "enable": ctrl.get("enable", ""),
                    "views": views,
                })
            states.append({
                "id": st.get("id", ""),
                "systemstate": st.get("systemstate", ""),
                "default": st.get("default", ""),
                "focuscontrol": st.get("focuscontrol", ""),
                "sections": sections,
                "controls": controls,
            })
        services.append({
            "name": svc.get("name", ""),
            "taskname": svc.get("taskname", ""),
            "pagename": svc.get("pagename", ""),
            "states": states,
            "state_count": len(states),
        })

    return {
        "path": str(path.relative_to(ROOT)),
        "info": info,
        "services": services,
        "service_count": len(services),
    }


def parse_all() -> dict:
    files = sorted(ARTIFACT_DIR.glob("*_State.xml"))
    results: list[dict] = []
    for p in files:
        results.append(parse_state_file(p))

    # Index by ui_name (lowercase) for fast composer lookup
    by_ui: dict[str, dict] = {}
    parse_errors: list[dict] = []
    for r in results:
        if "parse_error" in r:
            parse_errors.append(r)
            continue
        ui = (r["info"].get("ui") or "").lower()
        if ui:
            by_ui[ui] = r

    return {
        "source_dir": str(ARTIFACT_DIR.relative_to(ROOT)),
        "file_count": len(files),
        "parsed_count": len(by_ui),
        "parse_errors": parse_errors,
        "screens": results,
        "by_ui": by_ui,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    r = parse_all()
    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"p02: parsed {r['parsed_count']}/{r['file_count']} _State.xml files "
          f"→ {OUT.relative_to(ROOT)}")
    if r["parse_errors"]:
        print(f"  ⚠ {len(r['parse_errors'])} files failed to parse")


if __name__ == "__main__":
    main()
