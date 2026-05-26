"""P3 · validator — coverage + gaps + determinism lint
=========================================================

Reads:  out/model/activities/*.json  +  out/parsed/*.json
Writes: out/validator/report.json + report.html

Three checks:
  v01 — coverage: % slots labelled, % TRANS captured, % splices with trigger
  v02 — gaps: which slots have no SP parameter mapping? which screens missing?
  v03 — consistency: do .htm meta Tasks match PO_info.xml task list?
  lint — scan parsers/, composer/, validator/ source for forbidden LLM imports
"""
from __future__ import annotations
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "out" / "model" / "activities"
PARSED_DIR = ROOT / "out" / "parsed"
OUT_DIR = ROOT / "out" / "validator"
JSON_OUT = OUT_DIR / "report.json"
HTML_OUT = OUT_DIR / "report.html"

USER_FACING = {
    "POCRT", "POCRTQTN", "POCRTSO", "POCRTTEN", "POCOPY",
    "POAMND", "POAPP", "POEDT", "POVIW", "POMTN",
    "POHOLD", "POSCL", "POACCCUSGMOD", "POHLP",
}

# Forbidden imports for L1/L2/L3 (no LLM at the deterministic layers)
FORBIDDEN_IMPORTS_L1_L2_L3 = {
    "google.generativeai", "genai", "openai", "anthropic",
    "llm_client",  # our own
}
DETERMINISTIC_DIRS = ["parsers", "composer", "validator"]


def v01_coverage(models: dict) -> dict:
    """% slots labelled, % TRANS captured, % splices with trigger."""
    out = {}
    for name, m in models.items():
        if not m.get("is_user_facing"): continue
        total_slots = sum(s["slot_count"] for s in m["screens"])
        labelled = sum(
            1 for s in m["screens"] for sl in s["slots"] if sl.get("display_label")
        )
        slot_label_pct = 100 * labelled / max(1, total_slots)

        total_trans = sum(len(s["tasks_by_type"]["TRANS"]) for s in m["screens"])

        total_splices = m["splice_summary"]["total"]
        splices_with_trigger = (
            sum(1 for sp in m["splices"]["ui_splices"] if sp.get("trigger")) +
            sum(1 for sp in m["splices"]["state_splices"] if sp.get("trigger")) +
            sum(1 for sp in m["splices"]["data_splices"] if sp.get("trigger"))
        )
        splice_trigger_pct = 100 * splices_with_trigger / max(1, total_splices)

        # SP coverage: how many TRANS commits have an attached SP chain
        commit_sp_attached = sum(
            1 for spine_step in m["canonical_spine"]
            if spine_step.get("phase") == "commit" and spine_step.get("sp_chain")
        )
        commit_total = sum(
            1 for s in m["canonical_spine"] if s.get("phase") == "commit"
        )
        sp_attach_pct = 100 * commit_sp_attached / max(1, commit_total)

        out[name] = {
            "slot_count": total_slots,
            "slot_label_pct": round(slot_label_pct, 1),
            "trans_count": total_trans,
            "splice_total": total_splices,
            "splice_trigger_pct": round(splice_trigger_pct, 1),
            "commit_sp_attach_pct": round(sp_attach_pct, 1),
        }
    return out


def v02_gaps(models: dict, parsed: dict) -> dict:
    """Catalog gaps for fixing later."""
    no_label_slots = []
    spine_without_commit = []
    splice_no_consequence = []

    for name, m in models.items():
        if not m.get("is_user_facing"): continue
        for s in m["screens"]:
            for sl in s["slots"]:
                if not sl.get("display_label"):
                    no_label_slots.append({
                        "activity": name, "screen": s["ilbo_name"],
                        "field_name": sl.get("field_name"),
                        "field_id": sl.get("field_id"),
                        "input_type": sl.get("input_type"),
                    })
        commits = [x for x in m["canonical_spine"] if x.get("phase") == "commit"]
        if not commits:
            spine_without_commit.append(name)

    return {
        "no_label_slots_count": len(no_label_slots),
        "no_label_slots_sample": no_label_slots[:20],
        "spine_without_commit": spine_without_commit,
    }


def v03_consistency(models: dict, parsed: dict) -> dict:
    """Compare meta-Tasks tag in .htm vs tasks declared in PO_info.xml."""
    discrepancies = []
    for name, m in models.items():
        if not m.get("is_user_facing"): continue
        for s in m["screens"]:
            d = s.get("discrepancies", {})
            if d.get("tasks_only_in_form") or d.get("tasks_only_in_manifest"):
                discrepancies.append({
                    "activity": name,
                    "screen": s["ilbo_name"],
                    "tasks_only_in_form": d["tasks_only_in_form"],
                    "tasks_only_in_manifest": d["tasks_only_in_manifest"],
                })
    return {
        "screens_with_discrepancy": len(discrepancies),
        "discrepancies_sample": discrepancies[:10],
    }


def lint_determinism() -> dict:
    """Scan source files for forbidden LLM imports at deterministic layers."""
    violations = []
    for sub in DETERMINISTIC_DIRS:
        d = ROOT / sub
        if not d.exists(): continue
        for p in d.rglob("*.py"):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                imported_names = []
                if isinstance(node, ast.Import):
                    imported_names = [n.name for n in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported_names = [node.module or ""] + [n.name for n in node.names]
                for nm in imported_names:
                    for forbidden in FORBIDDEN_IMPORTS_L1_L2_L3:
                        if forbidden in (nm or ""):
                            violations.append({
                                "file": str(p.relative_to(ROOT)),
                                "imported": nm,
                                "matched": forbidden,
                            })
    return {
        "violation_count": len(violations),
        "violations": violations,
    }


def load_models() -> dict:
    out = {}
    for p in sorted(MODEL_DIR.glob("*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def load_parsed() -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(PARSED_DIR.glob("*.json"))}


def render_html(report: dict) -> str:
    """Render the validator report as an HTML page."""
    rows = []
    for name, c in report["v01_coverage"].items():
        rows.append(
            f"<tr><td>{name}</td>"
            f"<td>{c['slot_count']}</td>"
            f"<td>{c['slot_label_pct']}%</td>"
            f"<td>{c['trans_count']}</td>"
            f"<td>{c['splice_total']}</td>"
            f"<td>{c['commit_sp_attach_pct']}%</td></tr>"
        )
    discrep_html = ""
    for d in report["v03_consistency"]["discrepancies_sample"]:
        only_form = ", ".join(d["tasks_only_in_form"][:5])
        only_manifest = ", ".join(d["tasks_only_in_manifest"][:5])
        discrep_html += (
            f"<tr><td>{d['activity']}</td><td>{d['screen']}</td>"
            f"<td>{only_form}</td><td>{only_manifest}</td></tr>"
        )
    lint = report["lint_determinism"]
    lint_state = "✓ clean" if lint["violation_count"] == 0 else f"✗ {lint['violation_count']} violations"
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Validator report</title>
<style>
body {{ background:#f4ecdc; color:#2b2620; font-family:-apple-system,sans-serif; padding:32px; }}
h1 {{ font-family:Georgia,serif; font-weight:500; }}
table {{ border-collapse:collapse; background:#faf3df; border:1px solid #d8ccb0; border-radius:6px; margin:16px 0; }}
th,td {{ text-align:left; padding:8px 14px; border-bottom:1px solid #d8ccb0; font-size:13px; }}
th {{ font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:#7a6f5e; background:#f4ecdc; }}
.card {{ background:#faf3df; border:1px solid #d8ccb0; border-radius:8px; padding:16px 22px; margin:8px 0; }}
.mono {{ font-family:'JetBrains Mono',monospace; }}
</style></head>
<body>
<h1>Validator report</h1>

<div class="card">
  <h2>Determinism lint</h2>
  <p class="mono">{lint_state}</p>
</div>

<h2>v01 — Coverage per user-facing journey</h2>
<table>
<tr><th>Activity</th><th>Slots</th><th>% Labelled</th><th>TRANS</th><th>Splices</th><th>Commit SP attach %</th></tr>
{"".join(rows)}
</table>

<h2>v02 — Gaps</h2>
<div class="card">
  <p>Slots without display labels: <b>{report['v02_gaps']['no_label_slots_count']:,}</b></p>
  <p>Activities with no commit task on spine: <b>{', '.join(report['v02_gaps']['spine_without_commit']) or 'none'}</b></p>
</div>

<h2>v03 — Manifest vs Form .htm discrepancies</h2>
<p>Screens with mismatched task lists: <b>{report['v03_consistency']['screens_with_discrepancy']}</b></p>
<table>
<tr><th>Activity</th><th>Screen</th><th>Only in .htm meta</th><th>Only in PO_info.xml</th></tr>
{discrep_html}
</table>

</body></html>"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    models = load_models()
    parsed = load_parsed()

    report = {
        "v01_coverage": v01_coverage(models),
        "v02_gaps": v02_gaps(models, parsed),
        "v03_consistency": v03_consistency(models, parsed),
        "lint_determinism": lint_determinism(),
    }

    JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    HTML_OUT.write_text(render_html(report), encoding="utf-8")

    print(f"P3: validator report → {HTML_OUT.relative_to(ROOT)}")
    print(f"   Determinism lint: {report['lint_determinism']['violation_count']} violations")
    print(f"   No-label slots: {report['v02_gaps']['no_label_slots_count']}")
    print(f"   Manifest↔form discrepancies: {report['v03_consistency']['screens_with_discrepancy']}")
    print(f"\n   Per-journey coverage:")
    for name, c in report['v01_coverage'].items():
        print(f"     {name:14s}  slots={c['slot_count']:3d} ({c['slot_label_pct']:5.1f}% labelled) "
              f"TRANS={c['trans_count']:2d}  splices={c['splice_total']:3d}  "
              f"SP-attach={c['commit_sp_attach_pct']:5.1f}%")


if __name__ == "__main__":
    main()
