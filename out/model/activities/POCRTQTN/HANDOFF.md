# POCRTQTN — Create Purchase Order From Quotation

## At a glance

- **Activity:** `POCRTQTN`
- **Main screen:** `POCRTQTNMAIN`
- **Screen count:** 1
- **Total slots across all screens:** 31
- **Splices:** 10 UI · 0 state · 7 data · **17 total**
- **SP chains:** 20
- **Produces entity:** `PurchaseOrder` (id slot: `po_number`)
- **Consumes entity:** `Quotation` (id slot: `quotation_no`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|


## UI splices · 10

Sub-screens the user can open by clicking a LINK control.

- `POCRTQTNBUYLNK` → opens **POCRTQTNENT** · View Buyer Details
- `POCRTQTNDISPLNK` → opens **POCRTQTNENT** · View Disposition Review
- `POCRTQTNEADLNK` → opens **POCRTQTNENT** · View Earliest Available Date
- `POCRTQTNFSTKLNK` → opens **POCRTQTNENT** · View Free Stock Details
- `POCRTQTNITEMLNK` → opens **POCRTQTNENT** · View Item Details
- `POCRTQTNLNK1` → opens **POCRTQTNENT** · Edit PO
- `POCRTQTNQTNLNK` → opens **POCRTQTNENT** · View Quotation Details
- `POCRTQTNSSROULNK` → opens **POCRTQTNENT** · View Stock Status Review - OU Wise
- `POCRTQTNSSRWHLNK` → opens **POCRTQTNENT** · View Stock Status Review - Warehouse Wise
- `POCRTQTNSUPPLNK` → opens **POCRTQTNENT** · View Supplier Details

## Data splices · 7

Triggered when a slot value matches a specific condition in the SP code.

- `@pps_po_combo_default_flag = YES`
- `@back_dated_flag = YES`
- `@rate_mismatch = LT`
- `@sogenflag = REQ`
- `@rate_mismatch = EQ`
- `@flag = YES`
- `@fprowno <= 1`

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POCRTQTNENT` | 31 | Search Criteria, PO Details |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
