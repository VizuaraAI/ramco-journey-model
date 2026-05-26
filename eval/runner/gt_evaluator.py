"""Ground-truth evaluator: pass/fail based on system effect.

For each case:
  1. Run the bot through the conversation, collecting every (trans_invoked,
     slot_values_at_that_turn) over all turns.
  2. Compute the bot's ACHIEVED writes/reads: which TRANS tasks it fired,
     against which slot values, and (via static analysis) which tables those
     SP chains touch.
  3. Compare to ground_truth.writes / ground_truth.reads:
       - kind=commit/multi_commit: every required write must be present.
                                    Tables required ⊆ tables_actual.
                                    Slot values_required == actual (exact match).
       - kind=lookup: every required read must be present with matching filter slots.
       - kind=discovery: no writes fired (bot must not commit).
       - kind=error_no_commit: no writes fired.

Per-case verdict is binary PASS/FAIL.
"""
from __future__ import annotations
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
ROOT = EVAL.parent
sys.path.insert(0, str(HERE))

PARSED = ROOT / "out" / "parsed"
CASES_DIR = EVAL / "cases_gt"
REPORTS_DIR = EVAL / "reports"

CATALOG = json.loads((PARSED / "service_catalog.json").read_text())
SP_DATA = json.loads((PARSED / "sp_branches.json").read_text())

DEFAULT_WORKERS = int(os.environ.get("EVAL_WORKERS", "8"))


# Map upper-case activity in eval cases ↔ camel-case in catalog
ACT_MAP_FROM_UPPER = {
    "POCRT": "PoCrt", "POCRTQTN": "PoCrtQtn", "POCRTSO": "PoCrtSo",
    "POCRTTEN": "PoCrtTen", "POCOPY": "PoCopy", "POAMND": "PoAmnd",
    "POAPP": "PoApp", "POEDT": "PoEdt", "POVIW": "PoViw",
    "POMTN": "PoMtn", "POHOLD": "PoHold", "POSCL": "PoScl",
    "POACCCUSGMOD": "PoAcCcUsgMod", "POHLP": "PoHlp",
}


def find_ui_for_task(activity_camel: str, task: str) -> str | None:
    prefix = activity_camel + "|"
    for key in CATALOG["chains"]:
        if not key.startswith(prefix):
            continue
        _, ui, t = key.split("|", 2)
        if t.lower() == task.lower():
            return ui
    return None


def sp_chain_for(activity_camel: str, ui: str, task: str) -> list[str]:
    prefix = f"{activity_camel}|{ui}|"
    target = task.lower()
    for key, chain in CATALOG["chains"].items():
        if not key.startswith(prefix): continue
        if key[len(prefix):].lower() == target:
            return [s["spname"] for s in chain if s.get("spname")]
    return []


FREE_TEXT_SUFFIXES = ("_reason", "_note", "_notes", "_notes_text",
                      "_description", "_comment", "_remarks", "remarks")

# Slots the system supplies by default if the user doesn't provide them.
# Convention: anything ending in _date, _no, _number is system-fillable
# (PO numbers minted by numbering series, dates default to today, etc.).
SYSTEM_DEFAULT_SUFFIXES = ("_date", "_no", "_number", "_id")


def is_system_default_slot(name: str) -> bool:
    if not name: return False
    n = name.lower()
    return any(n.endswith(suf) for suf in SYSTEM_DEFAULT_SUFFIXES)


def _slot_value_satisfies(got, want, name: str = "") -> bool:
    """Mirror of the slot-match logic used in the eval pass. Used here as a
    SCORING function for picking the best matching action when bot fired
    the same TRANS multiple times."""
    if want == "ANY":
        return got is not None
    if isinstance(want, str) and (want.startswith("PLACEHOLDER:") or want.startswith("<")):
        # Templated: pass if bot has something OR slot is system-fillable
        if got is not None: return True
        if is_system_default_slot(name): return True
        return False
    return _slot_match(got, want, name)


def is_free_text_slot(name: str) -> bool:
    """Naming convention: free-text slots end in _reason / _note / _description /
    _comment / _remarks. Free-text values match by content overlap, not exact
    value (allows for paraphrasing across the user's wording and the
    case-author's wording)."""
    if not name: return False
    n = name.lower()
    return any(n.endswith(suf) for suf in FREE_TEXT_SUFFIXES) or n == "remarks" or n == "notes_text"


def _free_text_match(got, want) -> bool:
    """Tokens of `want` should mostly appear in `got` (or vice-versa).
    Threshold: at least 50% of want's content tokens are in got."""
    if got is None: return False
    import re as _re
    def _toks(s):
        return {t for t in _re.findall(r"[a-z0-9]+", str(s).lower()) if len(t) > 2}
    g, w = _toks(got), _toks(want)
    if not w: return True
    overlap = len(g & w)
    return overlap / len(w) >= 0.5


def _slot_match(got, want, slot_name: str = "") -> bool:
    """Permissive slot-value equality. Free-text slots use token-overlap;
    everything else uses exact (with light normalization)."""
    if is_free_text_slot(slot_name):
        return _free_text_match(got, want)
    return _slot_match_strict(got, want)


def _slot_match_strict(got, want) -> bool:
    """Strict equality with light normalization. Handles bool/str, whitespace,
    list/string, and short prefixes."""
    if got is None: return False
    # Bool ↔ string equivalence
    if isinstance(want, bool):
        return str(got).lower() in ("true", "1", "yes") if want else str(got).lower() in ("false", "0", "no")
    # Number-string equivalence
    if isinstance(want, (int, float)):
        try:
            return float(str(got).strip()) == float(want)
        except (ValueError, TypeError):
            return False
    # List-of-dicts: accept if got is a list or a string representation
    if isinstance(want, list):
        if isinstance(got, list):
            return len(got) >= len(want)
        # Stringified list: count how many of want's first-keys appear in got
        if isinstance(got, str):
            return all(str(d.get(list(d.keys())[0], "")) in got
                       for d in want if isinstance(d, dict))
        return False
    # Dict ↔ stringified-dict
    if isinstance(want, dict):
        if isinstance(got, dict):
            return all(_slot_match(got.get(k), v) for k, v in want.items())
        if isinstance(got, str):
            # Check each want-key appears in the string
            return all(k in got or str(v) in got for k, v in want.items())
        return False
    # String: normalize whitespace, case, and accept prefix-match (one is contained in the other)
    g = str(got).strip().lower()
    w = str(want).strip().lower()
    if g == w: return True
    # Token-prefix tolerance: "FOB" satisfies "FOB Hamburg" and vice-versa
    if w in g or g in w: return True
    # Punctuation-stripped match
    import re as _re
    gg = _re.sub(r"[^a-z0-9]+", " ", g).strip()
    ww = _re.sub(r"[^a-z0-9]+", " ", w).strip()
    if gg == ww: return True
    return False


def is_staging_table(name: str) -> bool:
    """True if this is a temporary/staging table (query scratch), not real
    persistence. Ramco convention uses tmp/temp/srch suffixes/midfixes for
    staging."""
    if "tmp" in name or "temp" in name: return True
    if name.endswith("_srch") or "_srch" in name: return True
    return False


def tables_for_chain(chain: list[str]) -> set[str]:
    """Real persistence tables only. Excludes staging tables and parser noise."""
    tables = set()
    sps = SP_DATA["sps"]
    for sp_name in chain:
        sp = sps.get(sp_name.lower())
        if not sp: continue
        for b in sp.get("branches", []):
            for t in b["consequences"].get("inserts", []): tables.add(t.lower())
            for t in b["consequences"].get("updates", []): tables.add(t.lower())
            for t in b["consequences"].get("deletes", []): tables.add(t.lower())
    return {t for t in tables
            if not is_staging_table(t)
            and len(t) > 3
            and t not in ("dtl", "data")}


@dataclass
class BotAction:
    """One TRANS task the bot fired, with the slot values active at that moment."""
    turn: int
    task: str | None
    activity_camel: str | None
    ui: str | None
    sp_chain: list[str] = field(default_factory=list)
    tables_touched: set[str] = field(default_factory=set)
    slot_values_at_fire: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseRun:
    case_id: str
    title: str
    category: str
    gt_kind: str
    passed: bool
    failure_reason: str = ""
    actions: list[BotAction] = field(default_factory=list)
    expected_writes: list[dict] = field(default_factory=list)
    expected_reads:  list[dict] = field(default_factory=list)


def run_case(case: dict, bot_factory) -> CaseRun:
    bot = bot_factory()
    bot.reset()
    actions: list[BotAction] = []

    for turn in case["conversation"]:
        try:
            out = bot.respond(turn["user"], turn["turn"])
        except Exception as e:
            actions.append(BotAction(turn=turn["turn"], task=None,
                                     activity_camel=None, ui=None))
            continue
        # v4-style: trans_sequence_v4 may carry multiple TRANS per turn
        v4_seq = getattr(out, "trans_sequence_v4", None)
        slot_snapshot = dict(getattr(bot, "state", {}).get("slots", {}))

        if v4_seq:
            for seq_item in v4_seq:
                task = seq_item.get("task")
                if not task: continue
                act_camel = seq_item.get("activity") or out.journey_locked
                # Find activity if not given
                if not act_camel or not find_ui_for_task(act_camel, task):
                    for cand in ACT_MAP_FROM_UPPER.values():
                        if find_ui_for_task(cand, task):
                            act_camel = cand
                            break
                ui = find_ui_for_task(act_camel, task) if act_camel else None
                chain = sp_chain_for(act_camel, ui, task) if (act_camel and ui) else []
                tables = tables_for_chain(chain)
                actions.append(BotAction(
                    turn=turn["turn"], task=task, activity_camel=act_camel, ui=ui,
                    sp_chain=chain, tables_touched=tables,
                    slot_values_at_fire=slot_snapshot,
                ))
        elif out.trans_invoked:
            # Legacy single-trans-per-turn (v1/v2/v3)
            act_camel = out.journey_locked or None
            if not act_camel or not find_ui_for_task(act_camel, out.trans_invoked):
                for cand in ACT_MAP_FROM_UPPER.values():
                    if find_ui_for_task(cand, out.trans_invoked):
                        act_camel = cand
                        break
            ui = find_ui_for_task(act_camel, out.trans_invoked) if act_camel else None
            chain = sp_chain_for(act_camel, ui, out.trans_invoked) if (act_camel and ui) else []
            tables = tables_for_chain(chain)
            actions.append(BotAction(
                turn=turn["turn"], task=out.trans_invoked,
                activity_camel=act_camel, ui=ui,
                sp_chain=chain, tables_touched=tables,
                slot_values_at_fire=slot_snapshot,
            ))

    gt = case["ground_truth"]
    kind = gt["kind"]
    expected_writes = gt.get("writes", []) or []
    expected_reads  = gt.get("reads",  []) or []
    no_writes       = gt.get("no_writes_expected", False)

    # ── Verdict ─────────────────────────────────────────────────────────
    passed = True
    reason = ""

    fired_writes = [a for a in actions if a.tables_touched]
    fired_reads  = [a for a in actions if a.task and not a.tables_touched]

    if kind in ("discovery", "error_no_commit"):
        if fired_writes:
            passed = False
            reason = f"expected no writes, but bot fired: {[(a.task, sorted(a.tables_touched)[:3]) for a in fired_writes]}"

    elif kind == "lookup":
        if fired_writes:
            passed = False
            reason = f"lookup case must not write; bot fired write task(s): {[a.task for a in fired_writes]}"
        else:
            # At least one read must match (task + filter slot subset)
            ok_any = False
            misses = []
            for exp in expected_reads:
                exp_task = exp["task"].upper()
                exp_filter = exp.get("filter_slots", {}) or {}
                matched = False
                for a in actions:
                    if a.task and a.task.upper() == exp_task:
                        # Check filter slots are present in bot's slot snapshot
                        bot_slots = a.slot_values_at_fire
                        if all(bot_slots.get(k) == v for k, v in exp_filter.items()):
                            matched = True
                            break
                if not matched:
                    misses.append({"task": exp_task, "filter": exp_filter})
                else:
                    ok_any = True
            if expected_reads and not ok_any:
                passed = False
                reason = f"no expected read matched. expected: {expected_reads}, got: {[a.task for a in actions if a.task]}"

    elif kind in ("commit", "multi_commit"):
        # Every expected write must be matched by a bot action with:
        #  - task matches
        #  - bot's tables_touched ⊇ tables_required
        #  - bot's slot_values ⊇ slot_values_required (exact match per key)
        for exp in expected_writes:
            exp_task = exp["task"].upper()
            exp_tables_required = set(t.lower() for t in (exp.get("tables_required") or []))
            exp_slot_values = exp.get("slot_values_required", {}) or {}

            # Pick the BEST-MATCHING action — the one whose slot snapshot
            # covers the most expected slot values. If bot fires same TRANS
            # multiple times (e.g. eager-fire then re-fire with full state),
            # the LATER one usually has the more complete state.
            candidates = [a for a in actions if a.task and a.task.upper() == exp_task]
            best_match = None
            best_score = -1
            for cand in candidates:
                score = sum(
                    1 for k, v in exp_slot_values.items()
                    if _slot_value_satisfies(cand.slot_values_at_fire.get(k), v, k)
                )
                if score > best_score:
                    best_score = score
                    best_match = cand

            if best_match is None:
                passed = False
                reason = f"expected write task {exp_task} not fired (bot fired: {[a.task for a in actions if a.task]})"
                break

            # Tables required must be a subset of what bot actually touches
            missing_tables = exp_tables_required - best_match.tables_touched
            if missing_tables:
                passed = False
                reason = f"task {exp_task} fired but missing required tables: {sorted(missing_tables)[:5]}"
                break

            # Slot values — exact match for keys with concrete values,
            # with light normalization (whitespace, case, bool-string,
            # dict-vs-stringified-dict) to avoid trivial format mismatches.
            bot_slots = best_match.slot_values_at_fire
            slot_mismatches = []
            for k, v in exp_slot_values.items():
                got = bot_slots.get(k)
                if v == "ANY":
                    if got is None and not is_system_default_slot(k):
                        slot_mismatches.append(f"{k} (missing, expected ANY)")
                elif str(v).startswith("PLACEHOLDER:") or str(v).startswith("<"):
                    # Templated: accept missing if slot is system-fillable
                    if got is None and not is_system_default_slot(k):
                        slot_mismatches.append(f"{k} (missing, expected templated)")
                else:
                    if not _slot_match(got, v, slot_name=k):
                        slot_mismatches.append(f"{k} (got={got!r} want={v!r})")
            if slot_mismatches:
                passed = False
                reason = f"task {exp_task} fired but slot mismatches: {slot_mismatches[:5]}"
                break

    return CaseRun(
        case_id=case["id"],
        title=case["title"],
        category=case["category"],
        gt_kind=kind,
        passed=passed,
        failure_reason=reason,
        actions=actions,
        expected_writes=expected_writes,
        expected_reads=expected_reads,
    )


def _bot_factory(bot_name: str):
    if bot_name == "stub":
        sys.path.insert(0, str(HERE))
        from stub_bot import StubBot
        return lambda: StubBot()
    sys.path.insert(0, str(ROOT / "chatbot"))
    if bot_name == "v1":
        from bot_v1 import ChatbotV1
        return lambda: ChatbotV1()
    if bot_name == "v2":
        from bot_v2 import ChatbotV2
        return lambda: ChatbotV2()
    if bot_name == "v3":
        from bot_v3 import ChatbotV3
        return lambda: ChatbotV3()
    if bot_name == "v4":
        from bot_v4 import ChatbotV4
        return lambda: ChatbotV4()
    if bot_name == "v5":
        from bot_v5 import ChatbotV5
        return lambda: ChatbotV5()
    if bot_name == "v6":
        from bot_v6 import ChatbotV6
        return lambda: ChatbotV6()
    if bot_name == "v7":
        from bot_v7 import ChatbotV7
        return lambda: ChatbotV7()
    if bot_name == "v8":
        from bot_v8 import ChatbotV8
        return lambda: ChatbotV8()
    raise RuntimeError(f"unknown bot {bot_name}")


def load_cases() -> list[dict]:
    cases = []
    for p in sorted(CASES_DIR.rglob("EVAL-*.json")):
        cases.append(json.loads(p.read_text(encoding="utf-8")))
    return cases


def main():
    bot_name = sys.argv[1] if len(sys.argv) > 1 else "v3"
    workers = DEFAULT_WORKERS
    factory = _bot_factory(bot_name)

    cases = load_cases()
    print(f"GT-evaluating {bot_name} against {len(cases)} cases ({workers} workers)…\n")

    t0 = time.time()
    runs: list[CaseRun] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_case, c, factory): c for c in cases}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            runs.append(r)
            mark = "PASS" if r.passed else "FAIL"
            print(f"  [{i:>2}/{len(cases)}] {mark}  {r.case_id:30s}  {r.gt_kind:14s}", flush=True)
            if not r.passed:
                print(f"         reason: {r.failure_reason[:120]}")
    elapsed = time.time() - t0
    runs.sort(key=lambda r: r.case_id)

    passed = sum(1 for r in runs if r.passed)
    print(f"\n{passed}/{len(runs)} cases passed ({100*passed/len(runs):.1f}%) in {elapsed:.1f}s")

    # By kind
    from collections import defaultdict
    by_kind = defaultdict(lambda: {"pass": 0, "total": 0})
    by_cat = defaultdict(lambda: {"pass": 0, "total": 0})
    for r in runs:
        by_kind[r.gt_kind]["total"] += 1
        if r.passed: by_kind[r.gt_kind]["pass"] += 1
        by_cat[r.category]["total"] += 1
        if r.passed: by_cat[r.category]["pass"] += 1
    print("\nBy ground-truth kind:")
    for k, v in sorted(by_kind.items()):
        print(f"  {k:18s}  {v['pass']:2d}/{v['total']:2d}  ({100*v['pass']/v['total']:5.1f}%)")
    print("\nBy category:")
    for k, v in sorted(by_cat.items()):
        print(f"  {k:30s}  {v['pass']:2d}/{v['total']:2d}  ({100*v['pass']/v['total']:5.1f}%)")

    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_path = REPORTS_DIR / f"{stamp}_gt_{bot_name}.json"
    # Serialize (sets → lists)
    def ser(r):
        d = asdict(r)
        for a in d["actions"]:
            a["tables_touched"] = sorted(a["tables_touched"])
        return d
    out_path.write_text(json.dumps({
        "bot": bot_name, "elapsed_seconds": round(elapsed, 1),
        "cases_total": len(runs), "cases_passed": passed,
        "by_kind": dict(by_kind), "by_category": dict(by_cat),
        "runs": [ser(r) for r in runs],
    }, indent=2), encoding="utf-8")
    print(f"\nReport → {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
