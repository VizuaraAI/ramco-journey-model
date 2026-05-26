"""Golden tests for p06 SP branches parser — the splice discovery engine."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "parsers"))
from p06_sp_branches import parse_sp_file, parse_all


def test_pocrmn_sp_crt_hdrchk() -> None:
    """Deep test on the canonical Create-Header-Check SP.

    From our prior investigation we know this SP has:
      - parameter @potypeenum (PO type)
      - parameter @imports (imports flag)
      - parameter @loi (LoI flag)
      - parameter @schedtype with branch IF @schedtype_tmp = 'SI'
      - branch IF @qcchk = 1
      - branch IF EXISTS (...po_poitm_item_detail...)
    """
    sp_path = ROOT / "artifacts" / "ramco" / "PO" / "SPS" / "pocrmn_sp_crt_hdrchk.sql"
    assert sp_path.exists(), f"missing SP file: {sp_path}"

    r = parse_sp_file(sp_path)
    assert r["sp_name"] == "pocrmn_sp_crt_hdrchk"

    # ── Parameters ───────────────────────────────────────────────────────
    param_names = {p["name"] for p in r["params"]}
    must_have_params = {"@potypeenum", "@imports", "@loi", "@supplier_code",
                        "@currencycode"}
    missing = must_have_params - param_names
    assert not missing, f"SP missing parameters: {missing}"

    # ── Branches ─────────────────────────────────────────────────────────
    assert r["total_branches"] > 20, f"total_branches = {r['total_branches']}, expected >20"

    # ── Slot-like branches: includes params AND _tmp locals ──────────────
    slot_like = [b for b in r["branches"] if b.get("lhs_is_slot_like")]
    assert len(slot_like) > 5, f"slot_like branches = {len(slot_like)}, expected >5"

    # ── REAL splices: slot-like + non-sentinel + has consequence ──────────
    real_splices = [b for b in r["branches"] if b.get("is_real_splice")]
    assert len(real_splices) >= 1, f"real_splices = {len(real_splices)}, expected >=1"

    # The @schedtype = 'SI' branch — line 672 in our prior inspection —
    # MUST be detected as a real splice (it has INSERT consequences)
    schedtype_branches = [b for b in real_splices
                          if b["lhs"] == "@schedtype" and b["rhs"] == "SI"]
    assert schedtype_branches, \
        f"branch IF @schedtype = 'SI' must be a real splice. " \
        f"All real splices: {[(b['lhs'], b['op'], b['rhs']) for b in real_splices[:10]]}"

    # ── Sentinel coalescing branches are correctly excluded from real splices ─
    sentinel = [b for b in r["branches"] if b.get("is_sentinel_coalesce")]
    assert len(sentinel) > 20, f"sentinel coalesces detected = {len(sentinel)}, expected >20"
    sentinel_real = [b for b in sentinel if b.get("is_real_splice")]
    assert not sentinel_real, "sentinel coalesces must never be marked as real splices"

    # ── EXISTS branches ─────────────────────────────────────────────────
    exists_branches = [b for b in r["branches"] if b["kind"] == "if_exists"]
    assert len(exists_branches) >= 1, "should find IF EXISTS branches"

    print(f"✓ p06.SP-deep: pocrmn_sp_crt_hdrchk has "
          f"{r['param_count']} params, {r['local_count']} locals, "
          f"{r['total_branches']} branches, "
          f"{r['real_splice_branches']} REAL splices (sentinel coalesces filtered out)")


def test_p06_bulk() -> None:
    """Run the full parse and check aggregate numbers."""
    r = parse_all()
    assert r["sp_count"] > 500, f"sp_count = {r['sp_count']}, expected >500"
    assert r["total_branches"] > 1000, f"total_branches = {r['total_branches']}, expected >1000"
    assert r["total_real_splices"] > 50, \
        f"real_splices = {r['total_real_splices']}, expected >50"
    assert r["splice_keys"] > 20, f"splice_keys = {r['splice_keys']}, expected >20"

    print(f"✓ p06.bulk: {r['sp_count']:,} SPs, {r['total_branches']:,} branches, "
          f"{r['total_real_splices']:,} REAL splices, {r['splice_keys']:,} distinct splice keys")


if __name__ == "__main__":
    test_pocrmn_sp_crt_hdrchk()
    test_p06_bulk()
