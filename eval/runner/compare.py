"""Generate a side-by-side comparison of multiple eval runs."""
from __future__ import annotations
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def find_latest(bot: str) -> dict | None:
    """Find the most recent JSON report for a given bot name."""
    candidates = sorted(REPORTS.glob(f"*_{bot}.json"), reverse=True)
    if not candidates:
        return None
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def main():
    bots = ["stub", "v1", "v2", "v3"]
    runs = {b: find_latest(b) for b in bots}
    runs = {b: r for b, r in runs.items() if r}
    print(f"Comparing runs: {list(runs.keys())}")

    # Per-case, per-bot pass status
    all_case_ids = set()
    for r in runs.values():
        for c in r["cases"]:
            all_case_ids.add(c["id"])

    # Per-category aggregation
    by_cat: dict[str, dict[str, dict]] = defaultdict(lambda: {b: {"pass":0,"fail":0,"mp":0,"mt":0} for b in runs})
    case_lookup: dict[str, dict[str, dict]] = defaultdict(dict)
    for bot, r in runs.items():
        for c in r["cases"]:
            cat = c["category"]
            if c["overall_pass"]:
                by_cat[cat][bot]["pass"] += 1
            else:
                by_cat[cat][bot]["fail"] += 1
            by_cat[cat][bot]["mp"] += c["passed_metrics"]
            by_cat[cat][bot]["mt"] += c["total_metrics"]
            case_lookup[c["id"]][bot] = c

    # Render HTML
    bot_cols = "".join(f"<th>{html.escape(b)}</th>" for b in runs)

    # Top summary
    summary_html = ""
    for bot, r in runs.items():
        pct = 100 * r['metrics_passed'] / max(1, r['metrics_total'])
        summary_html += (
            f"<div class='stat-card'>"
            f"<div class='label'>{html.escape(bot)}</div>"
            f"<div class='big'>{r['metrics_passed']}/{r['metrics_total']}</div>"
            f"<div class='sub'>{pct:.1f}% metrics · {r['cases_passed']}/{r['case_count']} cases · "
            f"{r.get('elapsed_seconds','?')}s</div></div>"
        )

    # Per-category table
    cat_rows = ""
    for cat in sorted(by_cat):
        cells = []
        for bot in runs:
            b = by_cat[cat][bot]
            pct = 100 * b["mp"] / max(1, b["mt"])
            cells.append(
                f"<td>{b['pass']}/{b['pass']+b['fail']}<span class='pct'> · {b['mp']}/{b['mt']} ({pct:.0f}%)</span></td>"
            )
        cat_rows += f"<tr><td><b>{html.escape(cat)}</b></td>{''.join(cells)}</tr>"

    # Per-case table — show ID, title, and per-bot pass/fail + metric scores
    case_rows = ""
    for cid in sorted(all_case_ids):
        any_case = next(iter(case_lookup[cid].values()))
        title = any_case["title"][:60]
        cat = any_case["category"]
        cells = []
        for bot in runs:
            c = case_lookup[cid].get(bot)
            if c is None:
                cells.append("<td>-</td>")
                continue
            mark_cls = "ok" if c["overall_pass"] else "bad"
            pct = 100 * c["passed_metrics"] / max(1, c["total_metrics"])
            cells.append(
                f"<td class='{mark_cls}'>{c['passed_metrics']}/{c['total_metrics']} "
                f"<span class='pct'>({pct:.0f}%)</span></td>"
            )
        case_rows += f"<tr><td><span class='mono'>{html.escape(cid)}</span></td><td>{html.escape(title)}</td>{''.join(cells)}</tr>"

    out = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Eval comparison · stub/v1/v2/v3</title>
<style>
:root {{ --cream:#f4ecdc; --ink:#2b2620; --muted:#7a6f5e; --purple:#6b5b8e;
         --green:#3d5c3d; --red:#8b4040; --rule:#d8ccb0; --code:#f8f1de; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:var(--cream); color:var(--ink); font-family:-apple-system, sans-serif; font-size:14px; }}
.page {{ max-width:1280px; margin:0 auto; padding:48px 32px; }}
h1 {{ font-family:Georgia,serif; font-weight:500; font-size:36px; margin-bottom:6px; }}
.meta {{ color:var(--muted); font-family:'JetBrains Mono',monospace; font-size:11px; margin-bottom:32px; }}
.summary {{ display:grid; grid-template-columns:repeat({len(runs)},1fr); gap:16px; margin-bottom:32px; }}
.stat-card {{ background:#faf3df; border:1px solid var(--rule); border-radius:8px; padding:18px 22px; }}
.label {{ font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:var(--purple); margin-bottom:8px; font-weight:600; }}
.big {{ font-family:Georgia,serif; font-size:30px; font-weight:500; }}
.sub {{ color:var(--muted); font-size:11px; margin-top:6px; font-family:'JetBrains Mono',monospace; }}
h2 {{ font-family:Georgia,serif; font-weight:500; font-size:22px; margin:32px 0 12px; }}
table {{ width:100%; border-collapse:collapse; background:#faf3df; border:1px solid var(--rule); border-radius:8px; overflow:hidden; }}
th,td {{ text-align:left; padding:10px 14px; border-bottom:1px solid var(--rule); font-size:13px; }}
th {{ font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:var(--muted); background:#f4ecdc; }}
.pct {{ color:var(--muted); font-size:10px; font-family:'JetBrains Mono',monospace; }}
.mono {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--purple); }}
td.ok {{ color:var(--green); }}
td.bad {{ color:var(--red); }}
</style></head><body>
<div class="page">
<h1>Eval comparison: bot versions</h1>
<div class="meta">stub (baseline) · v1 (NLU + commit) · v2 (+splices +recovery) · v3 (+cross-journey +cross-module)</div>
<div class="summary">{summary_html}</div>

<h2>By category</h2>
<table>
<tr><th>Category</th>{bot_cols}</tr>
{cat_rows}
</table>

<h2>Per-case metric scores</h2>
<table>
<tr><th>Case ID</th><th>Title</th>{bot_cols}</tr>
{case_rows}
</table>
</div></body></html>"""

    out_path = REPORTS / "comparison.html"
    out_path.write_text(out, encoding="utf-8")
    print(f"\nComparison report → {out_path}")

    # Console summary
    print("\nHeadline numbers:")
    for bot, r in runs.items():
        pct = 100 * r['metrics_passed'] / max(1, r['metrics_total'])
        print(f"  {bot:5s}  cases={r['cases_passed']:2d}/{r['case_count']:2d}  "
              f"metrics={r['metrics_passed']:3d}/{r['metrics_total']:3d} ({pct:5.1f}%)  "
              f"elapsed={r.get('elapsed_seconds','?')}s")

    print("\nBy category (metrics %):")
    for cat in sorted(by_cat):
        line = f"  {cat:30s}"
        for bot in runs:
            b = by_cat[cat][bot]
            pct = 100 * b["mp"] / max(1, b["mt"])
            line += f"  {bot}={pct:4.0f}%"
        print(line)


if __name__ == "__main__":
    main()
