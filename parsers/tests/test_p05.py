"""Golden tests for p05 service catalog parser."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "parsers"))
from p05_service_catalog import parse_service_catalog


def test_p05() -> None:
    r = parse_service_catalog()

    # ── 1. Bulk shape ─────────────────────────────────────────────────────
    assert r["rows_kept"] > 4000, f"rows_kept={r['rows_kept']}, expected >4000"

    # ── 2. PoCrt activity must be present with PoCrtMain screen ──────────
    pocrt = r["activity_summaries"]["PoCrt"]
    assert "PoCrtMain" in pocrt["screens"]
    assert pocrt["task_count"] >= 200, f"PoCrt task_count={pocrt['task_count']}, expected >=200"
    assert pocrt["sp_count"] >= 300, f"PoCrt sp_count={pocrt['sp_count']}, expected >=300"

    # ── 3. PoCrtMainSbt chain must be present with 6 SPs ─────────────────
    key = "PoCrt|PoCrtMain|PoCrtMainSbt"
    chain = r["chains"][key]
    assert len(chain) == 6, f"PoCrtMainSbt chain length = {len(chain)}, expected 6"

    sps_in_chain = [step["spname"] for step in chain]
    expected_sps = {
        "pocrmn_sp_crt_hdrsav", "pocrmn_sp_crt_hdrchk", "pocrmn_sp_crtgrd",
        "pocrmn_sp_init_suptxreg", "pocrmn_sp_aprhref", "pocrmn_sp_crtgrd_out"
    }
    missing = expected_sps - set(sps_in_chain)
    assert not missing, f"Missing SPs in PoCrtMainSbt chain: {missing}"

    # ── 4. Order: seq 1 items first, then seq 2, then seq 3 ──────────────
    # Last item must have the highest sequenceno (3 or None)
    seqs = [s["sequenceno"] for s in chain]
    assert seqs == sorted(seqs, key=lambda s: (s is None, s or 0)), \
        f"chain not sorted by sequenceno: {seqs}"
    assert seqs[-1] == 3 and seqs[0] == 1, f"seq endpoints not 1...3: {seqs}"

    # ── 5. PoCrtMainTrn4 (Create+Approve) chain present and uses apr_ SPs ──
    trn4 = r["chains"]["PoCrt|PoCrtMain|PoCrtMainTrn4"]
    apr_sps = [s["spname"] for s in trn4 if "apr" in s["spname"].lower()]
    assert len(apr_sps) >= 3, f"PoCrtMainTrn4 should have >=3 apr_ SPs, got: {apr_sps}"

    # ── 6. PoAmnd, PoApp, PoViw activities present ────────────────────────
    for act in ["PoAmnd", "PoApp", "PoViw", "PoEdt", "PoHold", "PoScl"]:
        assert act in r["activity_summaries"], f"activity missing: {act}"

    print(f"✓ p05: {r['rows_kept']:,} rows, {len(r['chains']):,} chains — all assertions pass")


if __name__ == "__main__":
    test_p05()
