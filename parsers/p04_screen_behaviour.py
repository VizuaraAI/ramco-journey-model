"""p04 · screen behaviour parser
==================================

Reads:  artifacts/ramco/PO/ScreenObjects/PO/*_user.js  (and bare .js if needed)
Writes: out/parsed/screen_behaviour.json

Extracts:
  - The header globals: componentName, activityName, ilboName, activityDesc, ilboDesc
  - The postTaskResultProcess switch: task name → success message (human prose)

This is a cross-check source for task descriptions. If PO_info.xml and the .htm
meta Tasks tag disagree on a task description, this gives us a third opinion.

Layer L1 — deterministic regex parsing of JS files. No JS interpreter needed.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = ROOT / "artifacts" / "ramco" / "PO" / "ScreenObjects" / "PO"
OUT_DIR = ROOT / "out" / "parsed"
OUT = OUT_DIR / "screen_behaviour.json"


# Each Ramco _user.js opens with global var assignments like:
#   componentName = "po";
#   activityName  = "pocrt";
#   ilboName      = "pocrtmain";
GLOBAL_VARS = ["componentName", "componentDesc", "activityName", "activityDesc",
               "ilboName", "ilboDesc", "TrailILBODesc"]

GLOBAL_RE = {v: re.compile(rf'\b{v}\s*=\s*"([^"]*)"') for v in GLOBAL_VARS}

# postTaskResultProcess has a switch like:
#   case "POCRTMAINFTH"
#       sTaskStatusMsg = "Fetch Create Main Page Successfully Completed";
#       break;
# (with or without colon after case, Ramco sometimes omits it)
CASE_RE = re.compile(
    r'case\s+"([^"]+)"\s*:?\s*\n?\s*sTaskStatusMsg\s*=\s*"([^"]+)"',
    re.IGNORECASE
)


def parse_behaviour_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")

    # 1. Globals
    globals_extracted = {}
    for v, rx in GLOBAL_RE.items():
        m = rx.search(text)
        if m:
            globals_extracted[v] = m.group(1)

    # 2. postTaskResultProcess switch cases
    cases = []
    for m in CASE_RE.finditer(text):
        cases.append({
            "task_name": m.group(1),
            "success_message": m.group(2),
        })

    return {
        "path": str(path.relative_to(ROOT)),
        "filename": path.name,
        "globals": globals_extracted,
        "task_messages": cases,
        "task_message_count": len(cases),
    }


def parse_all() -> dict:
    # Only the _user.js files (the per-screen behaviour). Skip ILRT/PLF utility files.
    candidates = sorted(ARTIFACT_DIR.glob("*_user.js"))
    # Some screens have both Pocrt_pocrtmain.js (base) and Pocrt_Pocrtmain_user.js (override).
    # We want the _user one if it exists. If only the base exists, also include.
    user_files = set(candidates)
    base_candidates = sorted(ARTIFACT_DIR.glob("*.js"))
    for p in base_candidates:
        if p.name.endswith("_user.js"):
            continue
        # Check for matching _user.js — if absent, include the base
        user_equivalent = p.with_name(p.stem + "_user.js")
        if user_equivalent not in user_files and "ILRT" not in p.name and "PLF" not in p.name:
            user_files.add(p)

    results: list[dict] = []
    for p in sorted(user_files):
        results.append(parse_behaviour_file(p))

    # Index by ilboName (lowercase)
    by_ilbo: dict[str, dict] = {}
    for r in results:
        ilbo = (r["globals"].get("ilboName") or "").lower()
        if ilbo and ilbo not in by_ilbo:
            by_ilbo[ilbo] = r

    # Flat task message index: task_name → success_message (across all files)
    task_message_index: dict[str, str] = {}
    for r in results:
        for c in r["task_messages"]:
            # First wins (avoid override conflicts)
            task_message_index.setdefault(c["task_name"], c["success_message"])

    return {
        "source_dir": str(ARTIFACT_DIR.relative_to(ROOT)),
        "file_count": len(user_files),
        "files": results,
        "by_ilbo": by_ilbo,
        "task_message_index": task_message_index,
        "task_message_index_count": len(task_message_index),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    r = parse_all()
    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"p04: parsed {r['file_count']} _user.js files, "
          f"{r['task_message_index_count']:,} task→message mappings → "
          f"{OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
