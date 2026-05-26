"""p06 · SP branches parser  ←  the splice discovery engine
==============================================================

Reads:  artifacts/ramco/PO/SPS/*.sql
Writes: out/parsed/sp_branches.json

This is the most important parser in P1. It extracts structured branch
information from every stored procedure:

  1. SP signature: parameters (slots) with their data types
  2. Every IF / CASE branch with parsed condition: (LHS, op, RHS)
  3. The branch's consequence: which EXEC fires, which RAISERROR triggers,
     which INSERT/UPDATE/DELETE happens

These IF branches ARE the data-triggered splices. When the LHS is a parameter
name (a slot the user fills), the branch becomes a slot-gated splice.

Layer L1 — deterministic regex + simple block walker. No LLM.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = ROOT / "artifacts" / "ramco" / "PO" / "SPS"
OUT_DIR = ROOT / "out" / "parsed"
OUT = OUT_DIR / "sp_branches.json"


# Parameter declaration at the top of an SP:
#   @additionalcharge              udd_amount,
#   @loi                           udd_modeflag,
PARAM_RE = re.compile(
    r'^\s*(@\w+)\s+([\w_]+)\s*(?:,|$|\n|/\*|--)',
    re.MULTILINE
)

# DECLARE @x udd_type — local variables inside the SP body
DECLARE_RE = re.compile(
    r'^\s*DECLARE\s+(@\w+)\s+([\w_]+)',
    re.MULTILINE | re.IGNORECASE
)

# Ramco null/empty sentinels used in parameter passing — branches comparing
# against these are coalescing null defaults, not real splice triggers.
SENTINELS = {"~#~", "-915", "01/01/1900", "0"}

# Procedure name
PROC_RE = re.compile(
    r'(?:create|alter)\s+procedure\s+(\w+)',
    re.IGNORECASE
)

# IF conditions — we want to capture the condition LHS / op / RHS.
# IF @var = value | IF @var IS NULL | IF @var IS NOT NULL
# IF @var <> value | IF @var > value | IF EXISTS (...) ...
# We try several patterns.
IF_BINARY_RE = re.compile(
    r'\bIF\s+(@\w+(?:_tmp)?|\w+\.\w+)\s*'
    r'(=|<>|!=|>=|<=|>|<|LIKE|IN)\s*'
    r"('[^']*'|-?\d+(?:\.\d+)?|@\w+|\w+)",
    re.IGNORECASE
)

IF_IS_NULL_RE = re.compile(
    r'\bIF\s+(@\w+(?:_tmp)?)\s+(IS\s+NOT\s+NULL|IS\s+NULL)',
    re.IGNORECASE
)

IF_EXISTS_RE = re.compile(
    r'\bIF\s+(NOT\s+)?EXISTS\s*\(',
    re.IGNORECASE
)

# CASE WHEN ... THEN
CASE_WHEN_RE = re.compile(
    r'WHEN\s+(@\w+(?:_tmp)?|\w+\.\w+)\s*(=|<>|!=)\s*'
    r"('[^']*'|-?\d+(?:\.\d+)?|@\w+|\w+)\s+THEN",
    re.IGNORECASE
)

# Consequences inside a branch (find what an IF body does)
EXEC_RE = re.compile(r'\bEXEC\s+(\w+)', re.IGNORECASE)
RAISERROR_RE = re.compile(
    r'\b(?:RAISERROR|raiserror|fin_german_raiserror_sp)\s*\(?\s*[\'"]?\w*[\'"]?(?:,\s*[^,]+,\s*(\d+))?',
    re.IGNORECASE
)
INSERT_RE = re.compile(r'\bINSERT\s+(?:INTO\s+)?(\w+)', re.IGNORECASE)
UPDATE_RE = re.compile(r'\bUPDATE\s+(\w+)', re.IGNORECASE)
DELETE_RE = re.compile(r'\bDELETE\s+FROM\s+(\w+)', re.IGNORECASE)


def _line_of(text: str, idx: int) -> int:
    return text.count('\n', 0, idx) + 1


def _extract_branch_body(text: str, if_end: int, max_lines: int = 60) -> str:
    """Extract the rough body that follows an IF — until next IF/END/blank-block."""
    # Take next max_lines lines after the IF condition
    body_end = if_end
    line_count = 0
    while body_end < len(text) and line_count < max_lines:
        nl = text.find('\n', body_end + 1)
        if nl == -1:
            body_end = len(text)
            break
        body_end = nl
        line_count += 1
        # Heuristic stop: a line that starts with another top-level IF or END
        line_start = text.rfind('\n', 0, body_end) + 1
        line = text[line_start:body_end].lstrip()
        # Don't stop on every IF — only on dedented IFs (column 0 or 1).
        # Cheap heuristic: stop on END or top-level IF after we have some content.
        if line_count > 3 and (line.upper().startswith("END") or line.upper().startswith("IF ")):
            # peek if it's an inner or outer IF — we don't truly know; conservative break
            if line.upper().startswith("END"):
                break
    return text[if_end:body_end]


def parse_sp_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")

    # Procedure name
    proc_match = PROC_RE.search(text)
    proc_name = proc_match.group(1) if proc_match else path.stem

    # Parameters — only scan the prologue (before BEGIN or first SELECT/IF)
    # Heuristic: cut at first 'AS\n' or 'BEGIN' (case-insensitive)
    body_start = len(text)
    for marker in [r'\bAS\s*\n', r'\bBEGIN\b']:
        m = re.search(marker, text, re.IGNORECASE)
        if m and m.start() < body_start:
            body_start = m.start()

    params_text = text[:body_start]
    params = []
    for m in PARAM_RE.finditer(params_text):
        params.append({
            "name": m.group(1).lower(),
            "udd_type": m.group(2),
        })

    # Param name set for quick lookup
    param_names = {p["name"] for p in params}

    # Local DECLARE'd variables — many _tmp shadows live here
    locals_decl = []
    for m in DECLARE_RE.finditer(text):
        locals_decl.append({
            "name": m.group(1).lower(),
            "udd_type": m.group(2),
        })
    local_names = {d["name"] for d in locals_decl}
    # A canonical-slot name set is param ∪ (local without _tmp suffix)
    slot_like_names = set(param_names)
    for ln in local_names:
        slot_like_names.add(ln)
        if ln.endswith("_tmp"):
            slot_like_names.add(ln[:-len("_tmp")])

    # Walk every IF / CASE branch
    branches: list[dict] = []

    # Binary IF
    for m in IF_BINARY_RE.finditer(text):
        line = _line_of(text, m.start())
        lhs_raw = m.group(1).lower()
        op = m.group(2).upper()
        rhs = m.group(3).strip("'")
        # Map @x_tmp back to @x (Ramco _tmp shadow convention)
        lhs_canon = lhs_raw.replace("_tmp", "") if lhs_raw.endswith("_tmp") else lhs_raw
        is_param = lhs_canon in param_names
        is_slot_like = lhs_canon in slot_like_names or lhs_canon in param_names
        body = _extract_branch_body(text, m.end())
        cons = _branch_consequences(body)
        is_sentinel = rhs in SENTINELS
        # A real splice trigger: slot-like LHS, non-sentinel RHS, and the
        # branch body actually does something (exec, raise, ins/upd/del).
        has_consequence = any(cons[k] for k in ["execs","raiserrors","inserts","updates","deletes"])
        is_real_splice = is_slot_like and not is_sentinel and has_consequence
        branches.append({
            "line": line,
            "kind": "if_binary",
            "lhs": lhs_canon,
            "lhs_raw": lhs_raw,
            "op": op,
            "rhs": rhs,
            "lhs_is_parameter": is_param,
            "lhs_is_slot_like": is_slot_like,
            "is_sentinel_coalesce": is_sentinel,
            "is_real_splice": is_real_splice,
            "consequences": cons,
        })

    # IS NULL / IS NOT NULL
    for m in IF_IS_NULL_RE.finditer(text):
        line = _line_of(text, m.start())
        lhs_raw = m.group(1).lower()
        op = " ".join(m.group(2).upper().split())
        lhs_canon = lhs_raw.replace("_tmp", "") if lhs_raw.endswith("_tmp") else lhs_raw
        is_param = lhs_canon in param_names
        is_slot_like = lhs_canon in slot_like_names or lhs_canon in param_names
        body = _extract_branch_body(text, m.end())
        branches.append({
            "line": line,
            "kind": "if_isnull",
            "lhs": lhs_canon,
            "lhs_raw": lhs_raw,
            "op": op,
            "rhs": None,
            "lhs_is_parameter": is_param,
            "consequences": _branch_consequences(body),
        })

    # IF EXISTS — content-based branch (we record presence but not a slot)
    for m in IF_EXISTS_RE.finditer(text):
        line = _line_of(text, m.start())
        body = _extract_branch_body(text, m.end())
        branches.append({
            "line": line,
            "kind": "if_exists",
            "lhs": None,
            "op": "EXISTS",
            "rhs": None,
            "lhs_is_parameter": False,
            "consequences": _branch_consequences(body),
        })

    # CASE WHEN
    for m in CASE_WHEN_RE.finditer(text):
        line = _line_of(text, m.start())
        lhs_raw = m.group(1).lower()
        op = m.group(2).upper()
        rhs = m.group(3).strip("'")
        lhs_canon = lhs_raw.replace("_tmp", "") if lhs_raw.endswith("_tmp") else lhs_raw
        is_param = lhs_canon in param_names
        is_slot_like = lhs_canon in slot_like_names or lhs_canon in param_names
        branches.append({
            "line": line,
            "kind": "case_when",
            "lhs": lhs_canon,
            "lhs_raw": lhs_raw,
            "op": op,
            "rhs": rhs,
            "lhs_is_parameter": is_param,
            "consequences": {},  # CASE bodies are harder to scope; skip for now
        })

    # Splice grading
    slot_gated = [b for b in branches if b.get("lhs_is_slot_like")]
    real_splices = [b for b in branches if b.get("is_real_splice")]

    return {
        "path": str(path.relative_to(ROOT)),
        "sp_name": proc_name.lower(),
        "param_count": len(params),
        "params": params,
        "local_count": len(locals_decl),
        "locals": locals_decl,
        "total_branches": len(branches),
        "slot_gated_branches": len(slot_gated),
        "real_splice_branches": len(real_splices),
        "branches": branches,
    }


def _branch_consequences(body: str) -> dict:
    """Parse the body of an IF for what it actually does."""
    return {
        "execs": list(set(m.group(1).lower() for m in EXEC_RE.finditer(body)))[:5],
        "raiserrors": list(set(m.group(1) for m in RAISERROR_RE.finditer(body) if m.group(1)))[:5],
        "inserts": list(set(m.group(1).lower() for m in INSERT_RE.finditer(body)))[:5],
        "updates": list(set(m.group(1).lower() for m in UPDATE_RE.finditer(body)))[:5],
        "deletes": list(set(m.group(1).lower() for m in DELETE_RE.finditer(body)))[:5],
    }


def parse_all() -> dict:
    files = sorted(ARTIFACT_DIR.glob("*.sql"))
    sps: dict[str, dict] = {}
    total_branches = 0
    total_slot_gated = 0
    parse_errors: list[dict] = []

    for p in files:
        try:
            r = parse_sp_file(p)
            sps[r["sp_name"]] = r
            total_branches += r["total_branches"]
            total_slot_gated += r["slot_gated_branches"]
        except Exception as e:
            parse_errors.append({"path": str(p.relative_to(ROOT)), "error": str(e)})

    # Splice catalog: aggregate ONLY real splices (slot-like + non-sentinel + has consequence)
    # Each entry: (lhs slot, op, rhs value) → list of (sp, line, consequences)
    splice_index: dict[str, list[dict]] = defaultdict(list)
    total_real_splices = 0
    for sp_name, sp in sps.items():
        for b in sp["branches"]:
            if not b.get("is_real_splice"): continue
            total_real_splices += 1
            key = f"{b['lhs']} {b['op']} {b.get('rhs','')}"
            splice_index[key].append({
                "sp": sp_name,
                "line": b["line"],
                "kind": b["kind"],
                "consequences": b["consequences"],
            })

    return {
        "source_dir": str(ARTIFACT_DIR.relative_to(ROOT)),
        "sp_count": len(sps),
        "total_branches": total_branches,
        "total_slot_gated_branches": total_slot_gated,
        "total_real_splices": total_real_splices,
        "splice_keys": len(splice_index),
        "parse_errors": parse_errors,
        "sps": sps,
        "splice_index": dict(splice_index),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    r = parse_all()
    # Trim full output for size — keep summary + indexed splices but cap per-SP branch detail
    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"p06: parsed {r['sp_count']:,} SPs, {r['total_branches']:,} branches "
          f"({r['total_slot_gated_branches']:,} slot-gated, {r['total_real_splices']:,} REAL splices), "
          f"{r['splice_keys']:,} distinct splice conditions → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
