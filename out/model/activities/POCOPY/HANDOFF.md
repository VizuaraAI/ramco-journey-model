# POCOPY — Copy And Create Purchase Order

## At a glance

- **Activity:** `POCOPY`
- **Main screen:** `POCOPYMAIN`
- **Screen count:** 1
- **Total slots across all screens:** 29
- **Splices:** 1 UI · 0 state · 6 data · **7 total**
- **SP chains:** 8
- **Produces entity:** `PurchaseOrder` (id slot: `po_number`)
- **Consumes entity:** `SourcePO` (id slot: `source_po_no`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|


## UI splices · 1

Sub-screens the user can open by clicking a LINK control.

- `POCRTCOPYPOLNK` → opens **POCRTCOPYPO** · Link to Edit PO Page

## Data splices · 6

Triggered when a slot value matches a specific condition in the SP code.

- `@pps_po_combo_default_flag = YES`
- `@modeflag = Z`
- `@back_dated_flag = YES`
- `@rate_mismatch = LT`
- `@sogenflag = REQ`
- `@rate_mismatch = EQ`

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POCRTCOPYPO` | 29 | Search Criteria, PO Details |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
