"""Diagnostic: classify every failure in the v3 eval run into one of five buckets.

Goal: answer the question "are the broad logical steps correct?" by separating
structural failures (real bugs in the bot — wrong journey, wrong TRANS, wrong
SP chain) from semantic failures (right behaviour, wrong literal text).

Five buckets per failed metric:
  1. STRUCTURAL_CRITICAL  — journey_locked, journey_switched, trans_invoked,
                            sp_chain_invoked, validation_error_detected
                            (these change what tables get populated)
  2. STRUCTURAL_SLOTS     — slots_extracted, additional_required_slots,
                            splice_triggered, splice_walked
                            (these change what data gets written)
  3. STRUCTURAL_AUX       — journey_candidates, cross_module_query
                            (these gate behaviour but don't change writes)
  4. TEXT_SEMANTIC        — bot_must (loose phrase matching)
  5. TEXT_HARD            — bot_must_not (forbidden phrases)

Also compute, per case, the TABLE FOOTPRINT: which tables would get
written if the bot's chosen TRANS fired vs the expected TRANS. If the
two footprints are equal, the bot's structural choice was equivalent
(even if the literal TRANS name differs).
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS = ROOT / "eval" / "reports"
SP_PARSED = ROOT / "out" / "parsed" / "sp_branches.json"
CATALOG_PARSED = ROOT / "out" / "parsed" / "service_catalog.json"

STRUCT_CRITICAL = {"journey_locked", "journey_switched", "trans_invoked",
                   "sp_chain_invoked", "validation_error_detected"}
STRUCT_SLOTS = {"slots_extracted", "additional_required_slots",
                "splice_triggered", "splice_walked"}
STRUCT_AUX = {"journey_candidates", "cross_module_query"}
TEXT_SEMANTIC = {"bot_must"}
TEXT_HARD = {"bot_must_not"}


def bucket(metric_name: str) -> str:
    if metric_name in STRUCT_CRITICAL: return "STRUCTURAL_CRITICAL"
    if metric_name in STRUCT_SLOTS:    return "STRUCTURAL_SLOTS"
    if metric_name in STRUCT_AUX:      return "STRUCTURAL_AUX"
    if metric_name in TEXT_SEMANTIC:   return "TEXT_SEMANTIC"
    if metric_name in TEXT_HARD:       return "TEXT_HARD"
    return "OTHER"


def latest_report(bot: str) -> dict:
    # Only timestamped reports — exclude diagnose_*.json
    candidates = sorted(
        [p for p in REPORTS.glob(f"*_{bot}.json") if p.name[0].isdigit()],
        reverse=True
    )
    if not candidates:
        raise FileNotFoundError(f"No report for {bot}")
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def load_sp_branches() -> dict:
    return json.loads(SP_PARSED.read_text(encoding="utf-8"))


def load_catalog() -> dict:
    return json.loads(CATALOG_PARSED.read_text(encoding="utf-8"))


def tables_written_by_sp_chain(sp_chain: list[str], sp_data: dict) -> set[str]:
    """Aggregate every table touched by INSERT/UPDATE/DELETE across this SP chain."""
    tables = set()
    sps = sp_data.get("sps", {})
    for sp_name in sp_chain:
        sp = sps.get(sp_name.lower())
        if not sp:
            continue
        # Walk every branch and collect ins/upd/del
        for b in sp.get("branches", []):
            cons = b.get("consequences", {})
            for t in cons.get("inserts", []):  tables.add(t.lower())
            for t in cons.get("updates", []):  tables.add(t.lower())
            for t in cons.get("deletes", []):  tables.add(t.lower())
    return tables


def sp_chain_for_trans(catalog: dict, activity_camel: str, ui_name: str,
                       task_name: str) -> list[str]:
    """Look up the SP chain for a TRANS task — case-insensitive on task name."""
    prefix = f"{activity_camel}|{ui_name}|"
    target = task_name.lower()
    for key, chain in catalog.get("chains", {}).items():
        if not key.startswith(prefix): continue
        actual_task = key[len(prefix):]
        if actual_task.lower() == target:
            return [step.get("spname") for step in chain if step.get("spname")]
    return []


# Map UPPER-case activity → CamelCase (matches catalog keys)
ACT_MAP = {
    "PoCrt": "PoCrt", "PoCrtQtn": "PoCrtQtn", "PoCrtSo": "PoCrtSo",
    "PoCrtTen": "PoCrtTen", "PoCopy": "PoCopy", "PoAmnd": "PoAmnd",
    "PoApp": "PoApp", "PoEdt": "PoEdt", "PoViw": "PoViw",
    "PoMtn": "PoMtn", "PoHold": "PoHold", "PoScl": "PoScl",
    "PoHlp": "PoHlp",
}


# Lookup tables for the conventional main-screen + task names we expect
# given a journey + commit_kind hint (extracted from the eval case expected output).
def upper_to_camel(act_upper_or_camel: str) -> str:
    """Map either upper or camel back to camel."""
    return ACT_MAP.get(act_upper_or_camel, act_upper_or_camel)


def main():
    bot = sys.argv[1] if len(sys.argv) > 1 else "v3"
    report = latest_report(bot)
    sp_data = load_sp_branches()
    catalog = load_catalog()

    cases = report["cases"]
    print(f"Diagnosing {bot}: {report['cases_passed']}/{report['case_count']} "
          f"cases passed, {report['metrics_passed']}/{report['metrics_total']} metrics passed.\n")

    # 1. Bucket every failed metric
    bucket_counts_fail: dict[str, int] = Counter()
    bucket_counts_pass: dict[str, int] = Counter()
    by_case_failure_kind: dict[str, set[str]] = defaultdict(set)

    for c in cases:
        for t in c["turns"]:
            for m in t["metrics"]:
                b = bucket(m["name"])
                if m["passed"]:
                    bucket_counts_pass[b] += 1
                else:
                    bucket_counts_fail[b] += 1
                    by_case_failure_kind[c["id"]].add(b)

    all_buckets = ["STRUCTURAL_CRITICAL", "STRUCTURAL_SLOTS", "STRUCTURAL_AUX",
                   "TEXT_SEMANTIC", "TEXT_HARD", "OTHER"]
    print("Per-metric-class pass/fail counts:")
    print(f"  {'BUCKET':22s}  {'PASS':>5s}  {'FAIL':>5s}  {'%pass':>6s}")
    for b in all_buckets:
        p = bucket_counts_pass[b]
        f = bucket_counts_fail[b]
        tot = p + f
        pct = 100 * p / max(1, tot)
        print(f"  {b:22s}  {p:5d}  {f:5d}  {pct:5.1f}%")

    # 2. Categorise cases by failure mode
    cases_pass_overall = 0
    cases_struct_only_pass = 0   # structural metrics ALL pass; only text fails
    cases_struct_critical_fail = 0  # at least one STRUCTURAL_CRITICAL failed
    cases_struct_slots_fail = 0
    for c in cases:
        kinds = by_case_failure_kind[c["id"]]
        if c["overall_pass"]:
            cases_pass_overall += 1
            continue
        if "STRUCTURAL_CRITICAL" in kinds:
            cases_struct_critical_fail += 1
            continue
        if "STRUCTURAL_SLOTS" in kinds:
            cases_struct_slots_fail += 1
            continue
        # If only TEXT_* buckets failed, structural is fine
        if not (kinds & {"STRUCTURAL_CRITICAL", "STRUCTURAL_SLOTS", "STRUCTURAL_AUX"}):
            cases_struct_only_pass += 1

    print(f"\nCase classification ({len(cases)} total):")
    print(f"  fully PASS:                        {cases_pass_overall:3d}")
    print(f"  structurally CORRECT, text fails:  {cases_struct_only_pass:3d}  ← these are 'logically right' but the bot text doesn't match")
    print(f"  STRUCTURAL_CRITICAL failure:       {cases_struct_critical_fail:3d}  ← wrong journey / wrong TRANS / wrong SP chain (real bugs)")
    print(f"  STRUCTURAL_SLOTS failure:          {cases_struct_slots_fail:3d}  ← right journey but wrong slot extraction / splice")

    # 3. Table footprint comparison for cases that have a trans_invoked expectation
    print("\n" + "=" * 78)
    print("TABLE-LEVEL CORRECTNESS — for every turn with an expected TRANS task,")
    print("compute the set of tables the expected SP chain writes vs. the bot's chain.")
    print("=" * 78)

    footprint_results = []
    for c in cases:
        for t in c["turns"]:
            expected_trans = None
            got_trans = None
            metrics_lookup = {m["name"]: m for m in t["metrics"]}
            if "trans_invoked" not in metrics_lookup:
                continue
            # Pull from the case definition — we need to re-read the case file to get expected
            # OR we can rely on the `detail` field of the metric which has "expected=X got=Y"
            detail = metrics_lookup["trans_invoked"]["detail"]
            # Format: "expected=POCRTMAINSBT got=POCRTMAINTRN4" or with None
            if "expected=" in detail and "got=" in detail:
                exp = detail.split("expected=")[1].split(" got=")[0].strip()
                got = detail.split("got=")[1].strip()
                if exp == "None" or got == "None":
                    continue

                # We need the activity context — infer from the case's covers_journeys
                # Load full case (path stored is relative to eval/ dir)
                case_path = ROOT / "eval" / c["path"]
                if not case_path.exists():
                    continue
                case_full = json.loads(case_path.read_text(encoding="utf-8"))
                journeys = case_full.get("covers_journeys", [])
                if not journeys:
                    continue
                activity_camel = upper_to_camel(journeys[0])

                # Conventionally the main screen for an activity is "PoCrt|PoCrtMain"
                # We need the screen name for this task. We can look it up by scanning
                # the catalog for which UI hosts this task within this activity.
                ui_for_exp = _find_ui_for_task(catalog, activity_camel, exp)
                ui_for_got = _find_ui_for_task(catalog, activity_camel, got)

                exp_chain = sp_chain_for_trans(catalog, activity_camel, ui_for_exp, exp) if ui_for_exp else []
                got_chain = sp_chain_for_trans(catalog, activity_camel, ui_for_got, got) if ui_for_got else []

                exp_tables = tables_written_by_sp_chain(exp_chain, sp_data)
                got_tables = tables_written_by_sp_chain(got_chain, sp_data)

                same_footprint = (exp_tables == got_tables) and len(exp_tables) > 0
                exp_only = exp_tables - got_tables
                got_only = got_tables - exp_tables
                shared = exp_tables & got_tables

                footprint_results.append({
                    "case": c["id"],
                    "turn": t["turn"],
                    "expected_trans": exp,
                    "got_trans": got,
                    "expected_chain_len": len(exp_chain),
                    "got_chain_len": len(got_chain),
                    "exp_tables": sorted(exp_tables),
                    "got_tables": sorted(got_tables),
                    "shared": sorted(shared),
                    "exp_only": sorted(exp_only),
                    "got_only": sorted(got_only),
                    "footprint_equal": same_footprint,
                    "footprint_overlap_pct": (100 * len(shared) /
                        max(1, len(exp_tables | got_tables))) if (exp_tables | got_tables) else 0,
                })

    equal = sum(1 for f in footprint_results if f["footprint_equal"])
    overlap_high = sum(1 for f in footprint_results
                       if not f["footprint_equal"] and f["footprint_overlap_pct"] >= 70)
    overlap_partial = sum(1 for f in footprint_results
                          if not f["footprint_equal"] and 30 <= f["footprint_overlap_pct"] < 70)
    disjoint = sum(1 for f in footprint_results
                   if f["footprint_overlap_pct"] < 30)

    print(f"\nFootprint comparison ({len(footprint_results)} turns with TRANS mismatch where we could resolve both):")
    print(f"  EQUAL footprints (bot picked equivalent task):  {equal}")
    print(f"  HIGH overlap (>=70%, near-equivalent):          {overlap_high}")
    print(f"  PARTIAL overlap (30-70%):                       {overlap_partial}")
    print(f"  DISJOINT (<30%, real divergence):               {disjoint}")

    if footprint_results:
        print("\nFirst 8 mismatches with the per-case verdict:")
        for f in footprint_results[:8]:
            mark = "EQ" if f["footprint_equal"] else (
                "HIGH" if f["footprint_overlap_pct"] >= 70 else
                "PART" if f["footprint_overlap_pct"] >= 30 else "DIVERG"
            )
            print(f"  [{mark:6s}] {f['case']}.t{f['turn']}  "
                  f"expected={f['expected_trans']:25s}  got={f['got_trans']:25s}  "
                  f"overlap={f['footprint_overlap_pct']:4.0f}%")
            if f["exp_only"] or f["got_only"]:
                print(f"           exp_only_tables: {f['exp_only'][:4]}")
                print(f"           got_only_tables: {f['got_only'][:4]}")

    # Save the diagnostic
    out_dir = REPORTS
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"diagnose_{bot}.json"
    out_path.write_text(json.dumps({
        "bot": bot,
        "bucket_pass": dict(bucket_counts_pass),
        "bucket_fail": dict(bucket_counts_fail),
        "case_classification": {
            "fully_pass": cases_pass_overall,
            "structurally_correct_text_fails": cases_struct_only_pass,
            "structural_critical_fail": cases_struct_critical_fail,
            "structural_slots_fail": cases_struct_slots_fail,
        },
        "footprint_results": footprint_results,
    }, indent=2), encoding="utf-8")
    print(f"\nDiagnostic JSON → {out_path.relative_to(ROOT)}")


def _find_ui_for_task(catalog: dict, activity_camel: str, task_name: str) -> str | None:
    """Walk the catalog to find which UI hosts the given task within an activity."""
    prefix = activity_camel + "|"
    for key in catalog.get("chains", {}):
        if not key.startswith(prefix):
            continue
        _, ui, task = key.split("|", 2)
        if task.lower() == task_name.lower():
            return ui
    return None


if __name__ == "__main__":
    main()
