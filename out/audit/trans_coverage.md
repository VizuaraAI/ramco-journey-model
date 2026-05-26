# TRANS Coverage Audit — v8 baseline

For every TRANS task in the service catalog, this audit answers:
- **Do we fire it today?** (yes/no)
- **What tables would its SP chain write to?**
- **If we don't fire it — are those tables reachable by anything we DO fire?**

---

## PoAmnd

- Fireable TRANS tasks today: **2**
- Orphan TRANS tasks (never fired): **2**
- Tables reachable today: **13**
- Tables ORPHANED today: **2**

### Orphan TRANS tasks

| screen | task | SPs | tables written | orphan? |
|---|---|---:|---|---|
| PoAmndsch | `PoamdSchTrn2` | 5 | po_pomas_pur_order_hdr, po_poprq_poprcovg_detail, po_poshd_schedule_dtl, po_poso_posocovg_detail, po_powh_allocation_dtl | — |
| PoAmndsch | `PoamdSchTrn3` | 5 | po_pomas_pur_order_hdr, po_poshd_schedule_dtl, po_powh_allocation_dtl | — |

### Tables fully orphaned (no fireable task reaches them)

- `po_poprq_poprcovg_detail`
- `po_poso_posocovg_detail`

---

## PoApp

- Fireable TRANS tasks today: **1**
- Orphan TRANS tasks (never fired): **0**
- Tables reachable today: **14**
- Tables ORPHANED today: **0**

---

## PoCopy

- Fireable TRANS tasks today: **0**
- Orphan TRANS tasks (never fired): **1**
- Tables reachable today: **0**
- Tables ORPHANED today: **3**

### Orphan TRANS tasks

| screen | task | SPs | tables written | orphan? |
|---|---|---:|---|---|
| PoCrtCopyPo | `PoCrtCopyPoTrn2` | 4 | not_notes_attachdoc, not_notes_dtl, not_notes_hdr | not_notes_attachdoc, not_notes_hdr |

### Tables fully orphaned (no fireable task reaches them)

- `not_notes_attachdoc`
- `not_notes_dtl`
- `not_notes_hdr`

---

## PoCrt

- Fireable TRANS tasks today: **2**
- Orphan TRANS tasks (never fired): **16**
- Tables reachable today: **7**
- Tables ORPHANED today: **13**

### Orphan TRANS tasks

| screen | task | SPs | tables written | orphan? |
|---|---|---:|---|---|
| PoCrtNotes | `PoCrtNotesTrn3` | 1 | po_podn_docnotes, po_poln_itemnotes | po_podn_docnotes, po_poln_itemnotes |
| PoCrtNotes | `PoCrtNotesTrn1` | 1 | po_stdnotes_table | po_stdnotes_table |
| PoCrtSch | `PoCrtSchTran4` | 5 | po_pomas_pur_order_hdr, po_poprq_poprcovg_detail, po_poshd_schedule_dtl, po_poso_posocovg_detail, po_powh_allocation_dtl | — |
| PoCrtSch | `PoCrtSchTrn3` | 5 | po_pomas_pur_order_hdr, po_poprq_poprcovg_detail, po_poshd_schedule_dtl, po_poso_posocovg_detail, po_powh_allocation_dtl | — |
| PoCrtTcdOth | `PoCrtTcdOthTran3` | 4 | po_podoc_otherdoctcd_dtl, po_potcd_otherlinetcd_dtl | — |
| PoCrtPrCov | `PoCrtPrCovTran2` | 5 | po_poitm_item_detail, po_poprq_poprcovg_detail, prjdet_mr_po_det | prjdet_mr_po_det |
| PoCrtSoCov | `PoCrtSoCovTran2` | 5 | po_poitm_item_detail, po_poso_posocovg_detail | — |
| PoCrtQlty | `PoCrtQltyTran3` | 5 | po_pomas_pur_order_hdr, po_poqly_quality_detail | — |
| PoCrtTcdOth | `PoCrtTcdOthTrn1` | 5 | po_podoc_otherdoctcd_dtl, po_pomas_pur_order_hdr, po_potcd_otherlinetcd_dtl | — |
| PoCrtPrCov | `PoCrtPrCovTrn1` | 5 | prjdet_mr_po_det | prjdet_mr_po_det |
| PoCrtTcd | `PoCrtTcdTran3` | 5 | po_dtcd_docitem_tcd, po_potcd_doclevel_detail, po_potcd_itemtcd_dtl, po_tcd_order | po_tcd_order |
| PoCrtSoCov | `PoCrtSoCovTran1` | 5 | po_poitm_item_detail, po_poso_posocovg_detail | — |
| PoCrtQlty | `PoCrtQltyTrn1` | 5 | po_pomas_pur_order_hdr, po_poqly_quality_detail | — |
| PoCrtTcd | `PocrtTcdTrn1` | 5 | po_dtcd_docitem_tcd, po_potcd_doclevel_detail, po_potcd_itemtcd_dtl, po_tcd_order | po_tcd_order |
| PoCrtTrm | `PoCrtTrmTrn3` | 5 | po_paytm_doclevel_detail, po_paytm_linelevel_detail, po_pomas_pur_order_hdr | — |
| PoCrtTrm | `PoCrtTrmTran` | 5 | po_paytm_doclevel_detail, po_paytm_linelevel_detail | — |

### Tables fully orphaned (no fireable task reaches them)

- `po_dtcd_docitem_tcd`
- `po_podn_docnotes`
- `po_podoc_otherdoctcd_dtl`
- `po_poln_itemnotes`
- `po_poprq_poprcovg_detail`
- `po_poqly_quality_detail`
- `po_poso_posocovg_detail`
- `po_potcd_doclevel_detail`
- `po_potcd_itemtcd_dtl`
- `po_potcd_otherlinetcd_dtl`
- `po_stdnotes_table`
- `po_tcd_order`
- `prjdet_mr_po_det`

---

## PoCrtQtn

- Fireable TRANS tasks today: **0**
- Orphan TRANS tasks (never fired): **1**
- Tables reachable today: **0**
- Tables ORPHANED today: **7**

### Orphan TRANS tasks

| screen | task | SPs | tables written | orphan? |
|---|---|---:|---|---|
| PoCrtQtnEnt | `PoCrtQtnSub` | 4 | not_notes_attachdoc, not_notes_dtl, not_notes_hdr, po_paytm_linelevel_detail, po_podoc_otherdoctcd_dtl, po_pomas_pur_order_hdr, po_potcd_doclevel_detail | not_notes_attachdoc, not_notes_hdr |

### Tables fully orphaned (no fireable task reaches them)

- `not_notes_attachdoc`
- `not_notes_dtl`
- `not_notes_hdr`
- `po_paytm_linelevel_detail`
- `po_podoc_otherdoctcd_dtl`
- `po_pomas_pur_order_hdr`
- `po_potcd_doclevel_detail`

---

## PoCrtSo

- Fireable TRANS tasks today: **0**
- Orphan TRANS tasks (never fired): **1**
- Tables reachable today: **0**
- Tables ORPHANED today: **11**

### Orphan TRANS tasks

| screen | task | SPs | tables written | orphan? |
|---|---|---:|---|---|
| PoCrtSoEnt | `PoCrtSoSub` | 5 | not_notes_attachdoc, not_notes_dtl, not_notes_hdr, po_podoc_otherdoctcd_dtl, po_poitm_item_detail, po_poqly_quality_detail, po_poshd_schedule_dtl, po_poso_posocovg_detail, po_potcd_doclevel_detail, po_potcd_itemtcd_dtl, po_powh_allocation_dtl | not_notes_attachdoc, not_notes_hdr |

### Tables fully orphaned (no fireable task reaches them)

- `not_notes_attachdoc`
- `not_notes_dtl`
- `not_notes_hdr`
- `po_podoc_otherdoctcd_dtl`
- `po_poitm_item_detail`
- `po_poqly_quality_detail`
- `po_poshd_schedule_dtl`
- `po_poso_posocovg_detail`
- `po_potcd_doclevel_detail`
- `po_potcd_itemtcd_dtl`
- `po_powh_allocation_dtl`

---

## PoEdt

- Fireable TRANS tasks today: **3**
- Orphan TRANS tasks (never fired): **1**
- Tables reachable today: **14**
- Tables ORPHANED today: **0**

### Orphan TRANS tasks

| screen | task | SPs | tables written | orphan? |
|---|---|---:|---|---|
| PoEdtEnt | `PoEdtEntTrn2` | 4 | po_poso_posocovg_detail | — |

---

## PoHold

- Fireable TRANS tasks today: **1**
- Orphan TRANS tasks (never fired): **1**
- Tables reachable today: **3**
- Tables ORPHANED today: **0**

### Orphan TRANS tasks

| screen | task | SPs | tables written | orphan? |
|---|---|---:|---|---|
| PoHoldEnt | `PoHldEntTrn2` | 4 | po_paytm_doclevel_detail, po_pomas_pur_order_hdr, po_posta_status_detail | — |

---

## PoScl

- Fireable TRANS tasks today: **1**
- Orphan TRANS tasks (never fired): **0**
- Tables reachable today: **1**
- Tables ORPHANED today: **0**

---
