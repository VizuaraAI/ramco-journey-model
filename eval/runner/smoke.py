"""Run the evaluator on a small subset of cases — fast sanity check before full sweep."""
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluator import _bot_factory, run_case, DEFAULT_WORKERS
from loader import load_cases
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

SMOKE_IDS = {
    "EVAL-DISC-001",       # discovery question (no commit)
    "EVAL-HAPPY-001",      # simple Create Direct PO
    "EVAL-HAPPY-009",      # View PO
    "EVAL-SPLICE-001",     # Capital PO — splice (likely fails on v1)
    "EVAL-LOOKUP-001",     # status by number
}


def main():
    bot_name = sys.argv[1] if len(sys.argv) > 1 else "v1"
    factory = _bot_factory(bot_name)
    cases = [c for c in load_cases() if c["id"] in SMOKE_IDS]
    print(f"Smoke-testing {bot_name} against {len(cases)} cases:")
    for c in cases:
        print(f"  · {c['id']}")
    print()

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(run_case, c, factory): c for c in cases}
        for fut in as_completed(futures):
            ce = fut.result()
            mark = "PASS" if ce.overall_pass else "FAIL"
            print(f"  [{mark}] {ce.id} — {ce.passed_metrics}/{ce.total_metrics} metrics")
            if not ce.overall_pass:
                for t in ce.turns:
                    fails = [m for m in t.metrics if not m["passed"]]
                    if fails:
                        print(f"    turn {t.turn}: {len(fails)} failing")
                        for m in fails[:3]:
                            print(f"      ✗ {m['name']}: {m['detail'][:80]}")
    print(f"\nSmoke elapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
