"""HTML report renderer for evaluator results."""
from __future__ import annotations
import html
from collections import Counter, defaultdict


def render_html(result: dict) -> str:
    cases = result["cases"]
    n = result["case_count"]
    passed = result["cases_passed"]
    pct = 100 * passed / max(1, n)
    m_total = result["metrics_total"]
    m_passed = result["metrics_passed"]
    m_pct = 100 * m_passed / max(1, m_total)

    by_cat = defaultdict(lambda: {"total": 0, "passed": 0, "m_total": 0, "m_passed": 0})
    for c in cases:
        bucket = by_cat[c["category"]]
        bucket["total"] += 1
        bucket["passed"] += 1 if c["overall_pass"] else 0
        bucket["m_total"] += c["total_metrics"]
        bucket["m_passed"] += c["passed_metrics"]

    rows_cat = "\n".join(
        f'<tr><td>{html.escape(cat)}</td><td>{b["passed"]} / {b["total"]}</td>'
        f'<td>{b["m_passed"]} / {b["m_total"]}'
        f' &nbsp;<span class="pct">{100*b["m_passed"]/max(1,b["m_total"]):.0f}%</span></td></tr>'
        for cat, b in sorted(by_cat.items())
    )

    case_blocks = []
    for c in cases:
        case_pct = 100 * c["passed_metrics"] / max(1, c["total_metrics"])
        status = "pass" if c["overall_pass"] else "fail"
        turn_blocks = []
        for t in c["turns"]:
            metric_items = []
            for m in t["metrics"]:
                mark = "✓" if m["passed"] else "✗"
                cls = "mp" if m["passed"] else "mf"
                detail = html.escape(m.get("detail") or "")
                det_html = f' &mdash; <span class="det">{detail}</span>' if detail else ""
                metric_items.append(
                    f'<li class="{cls}">{mark} {html.escape(m["name"])}{det_html}</li>'
                )
            turn_blocks.append(
                f'<div class="turn">'
                f'<div class="t-head">Turn {t["turn"]} · '
                f'<span class="t-score">{t["passed"]}/{t["passed"]+t["failed"]}</span></div>'
                f'<div class="t-user">"{html.escape(t["user"])}"</div>'
                f'<ul class="metrics">{"".join(metric_items)}</ul>'
                f'</div>'
            )
        case_blocks.append(
            f'<details class="case {status}" {"open" if not c["overall_pass"] else ""}>'
            f'<summary><span class="cid">{html.escape(c["id"])}</span> '
            f'<span class="ctitle">{html.escape(c["title"])}</span>'
            f' <span class="cscore">{c["passed_metrics"]}/{c["total_metrics"]} '
            f'({case_pct:.0f}%)</span></summary>'
            f'<div class="case-body">{"".join(turn_blocks)}</div>'
            f'</details>'
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Eval report — {html.escape(result["bot_name"])}</title>
<style>
:root {{ --cream:#f4ecdc; --ink:#2b2620; --muted:#7a6f5e; --purple:#6b5b8e;
        --green:#3d5c3d; --red:#8b4040; --rule:#d8ccb0; --code:#f8f1de; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:var(--cream); color:var(--ink); font-family:-apple-system, system-ui, sans-serif;
       font-size:14px; line-height:1.5; }}
.page {{ max-width:1100px; margin:0 auto; padding:48px 32px; }}
h1 {{ font-family:Georgia, serif; font-weight:500; font-size:36px; margin-bottom:6px; }}
.meta {{ color:var(--muted); font-family:'JetBrains Mono', monospace; font-size:11px; margin-bottom:32px; }}
.summary {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:32px; }}
.summary .card {{ background:#faf3df; border:1px solid var(--rule); border-radius:8px; padding:18px 22px; }}
.summary .label {{ font-family:'JetBrains Mono', monospace; font-size:10px; letter-spacing:0.1em;
                   text-transform:uppercase; color:var(--muted); margin-bottom:8px; }}
.summary .big {{ font-family:Georgia, serif; font-size:32px; }}
.summary .sub {{ color:var(--muted); font-size:12px; margin-top:4px; }}
table {{ width:100%; border-collapse:collapse; background:#faf3df; border:1px solid var(--rule);
        border-radius:8px; margin-bottom:32px; overflow:hidden; }}
th, td {{ text-align:left; padding:10px 14px; border-bottom:1px solid var(--rule); font-size:13px; }}
th {{ font-family:'JetBrains Mono', monospace; font-size:10px; letter-spacing:0.1em;
     text-transform:uppercase; color:var(--muted); background:#f4ecdc; }}
.pct {{ color:var(--muted); font-size:11px; font-family:'JetBrains Mono', monospace; }}
h2 {{ font-family:Georgia, serif; font-size:22px; font-weight:500; margin:24px 0 12px; }}
.case {{ background:#faf3df; border:1px solid var(--rule); border-radius:8px; margin-bottom:10px; padding:14px 18px; }}
.case.pass {{ border-left:4px solid var(--green); }}
.case.fail {{ border-left:4px solid var(--red); }}
.case summary {{ cursor:pointer; list-style:none; display:flex; gap:14px; align-items:baseline; }}
.cid {{ font-family:'JetBrains Mono', monospace; font-size:11px; color:var(--purple); }}
.ctitle {{ flex:1; font-weight:500; }}
.cscore {{ font-family:'JetBrains Mono', monospace; font-size:11px; color:var(--muted); }}
.case-body {{ margin-top:14px; }}
.turn {{ background:#fff; border:1px solid var(--rule); border-radius:6px; padding:12px 16px; margin-top:10px; }}
.t-head {{ font-family:'JetBrains Mono', monospace; font-size:11px; color:var(--purple);
          letter-spacing:0.08em; text-transform:uppercase; margin-bottom:6px; }}
.t-score {{ color:var(--muted); margin-left:6px; }}
.t-user {{ font-style:italic; color:var(--ink); margin-bottom:10px; padding-left:10px;
          border-left:2px solid var(--rule); }}
.metrics {{ list-style:none; }}
.metrics li {{ padding:3px 0; font-family:'JetBrains Mono', monospace; font-size:11px; }}
.mp {{ color:var(--green); }}
.mf {{ color:var(--red); }}
.det {{ color:var(--muted); }}
</style></head>
<body><div class="page">
<h1>Eval report</h1>
<div class="meta">bot = <b>{html.escape(result["bot_name"])}</b> · {html.escape(result["generated_at"])}</div>

<div class="summary">
  <div class="card">
    <div class="label">Cases passed</div>
    <div class="big">{passed} / {n}</div>
    <div class="sub">{pct:.1f}% — a case passes only if all its metrics pass</div>
  </div>
  <div class="card">
    <div class="label">Metrics passed</div>
    <div class="big">{m_passed} / {m_total}</div>
    <div class="sub">{m_pct:.1f}% — total per-turn assertions across all cases</div>
  </div>
</div>

<h2>By category</h2>
<table>
<thead><tr><th>Category</th><th>Cases</th><th>Metrics</th></tr></thead>
<tbody>
{rows_cat}
</tbody>
</table>

<h2>Per-case detail</h2>
{"".join(case_blocks)}

</div></body></html>"""
