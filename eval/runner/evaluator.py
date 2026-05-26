"""End-to-end evaluator: load cases, run them against a bot, score, report.

Cases are independent → parallelizable across cases via ThreadPoolExecutor.
Turns within a case are sequential (state-dependent).
"""
from __future__ import annotations
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loader import load_cases, validate_cases
from metrics import BotTurnOutput, MetricResult, score_turn
from stub_bot import StubBot


# Default concurrency — overridable via env. Gemini has generous QPS limits;
# 8 workers is conservative.
DEFAULT_WORKERS = int(os.environ.get("EVAL_WORKERS", "8"))


@dataclass
class TurnEval:
    turn: int
    user: str
    metrics: list[dict]
    passed: int
    failed: int


@dataclass
class CaseEval:
    id: str
    title: str
    category: str
    path: str
    turns: list[TurnEval]
    total_metrics: int
    passed_metrics: int
    failed_metrics: int
    overall_pass: bool


def run_case(case: dict, bot_factory) -> CaseEval:
    """Each thread gets its own bot instance via the factory (state isolation)."""
    bot = bot_factory()
    bot.reset()
    turn_evals: list[TurnEval] = []
    total = 0
    passed_total = 0
    failed_total = 0

    for turn in case["conversation"]:
        try:
            bot_out = bot.respond(turn["user"], turn["turn"])
        except Exception as e:
            bot_out = BotTurnOutput(response_text=f"<<bot error: {type(e).__name__}: {e}>>")
        metrics = score_turn(turn["expected"], bot_out)
        passed = sum(1 for m in metrics if m.passed)
        failed = sum(1 for m in metrics if not m.passed)
        total += len(metrics)
        passed_total += passed
        failed_total += failed
        turn_evals.append(TurnEval(
            turn=turn["turn"],
            user=turn["user"],
            metrics=[{"name": m.name, "passed": m.passed, "detail": m.detail} for m in metrics],
            passed=passed,
            failed=failed,
        ))

    return CaseEval(
        id=case["id"],
        title=case["title"],
        category=case["category"],
        path=case.get("_path", ""),
        turns=turn_evals,
        total_metrics=total,
        passed_metrics=passed_total,
        failed_metrics=failed_total,
        overall_pass=(failed_total == 0 and total > 0),
    )


def _bot_factory(bot_name: str):
    if bot_name == "stub":
        return lambda: StubBot()
    if bot_name == "v1":
        sys.path.insert(0, str(ROOT.parent / "chatbot"))
        from bot_v1 import ChatbotV1
        return lambda: ChatbotV1()
    if bot_name == "v2":
        sys.path.insert(0, str(ROOT.parent / "chatbot"))
        from bot_v2 import ChatbotV2
        return lambda: ChatbotV2()
    if bot_name == "v3":
        sys.path.insert(0, str(ROOT.parent / "chatbot"))
        from bot_v3 import ChatbotV3
        return lambda: ChatbotV3()
    raise RuntimeError(f"Unknown bot {bot_name}")


def run_all(bot_name: str = "stub", workers: int = DEFAULT_WORKERS) -> dict:
    cases = load_cases()
    errs = validate_cases(cases)
    if errs:
        raise RuntimeError(f"Cases failed structural validation: {errs[:3]}")

    factory = _bot_factory(bot_name)

    t0 = time.time()
    case_evals: list[CaseEval] = []
    if workers > 1:
        print(f"Running {len(cases)} cases against {bot_name} with {workers} workers…")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(run_case, c, factory): c for c in cases}
            for i, fut in enumerate(as_completed(futures), 1):
                ce = fut.result()
                case_evals.append(ce)
                print(f"  [{i:>2}/{len(cases)}] {ce.id:24s} "
                      f"{'PASS' if ce.overall_pass else 'fail'} "
                      f"{ce.passed_metrics}/{ce.total_metrics}",
                      flush=True)
    else:
        for c in cases:
            case_evals.append(run_case(c, factory))
    elapsed = time.time() - t0
    print(f"\n  Elapsed: {elapsed:.1f}s")

    # Sort by id for stable report
    case_evals.sort(key=lambda c: c.id)

    return {
        "bot_name": bot_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "case_count": len(case_evals),
        "cases_passed": sum(1 for c in case_evals if c.overall_pass),
        "metrics_total": sum(c.total_metrics for c in case_evals),
        "metrics_passed": sum(c.passed_metrics for c in case_evals),
        "metrics_failed": sum(c.failed_metrics for c in case_evals),
        "elapsed_seconds": round(elapsed, 1),
        "workers": workers,
        "cases": [asdict(c) for c in case_evals],
    }


if __name__ == "__main__":
    bot_name = sys.argv[1] if len(sys.argv) > 1 else "stub"
    result = run_all(bot_name)
    print(f"Bot: {result['bot_name']}")
    print(f"Cases: {result['cases_passed']} / {result['case_count']} passed")
    print(f"Metrics: {result['metrics_passed']} / {result['metrics_total']} passed "
          f"({100*result['metrics_passed']/max(1,result['metrics_total']):.1f}%)")

    # Write JSON + HTML reports
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = reports_dir / f"{stamp}_{bot_name}.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nJSON report: {json_path}")

    # Defer HTML to a separate module
    from report import render_html
    html_path = reports_dir / f"{stamp}_{bot_name}.html"
    html_path.write_text(render_html(result), encoding="utf-8")
    print(f"HTML report: {html_path}")
    latest = reports_dir / "latest.html"
    latest.write_text(render_html(result), encoding="utf-8")
    print(f"Latest pointer: {latest}")
