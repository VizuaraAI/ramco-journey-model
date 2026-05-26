# POCRTSO — Create Purchase Order From Sale Order

## At a glance

- **Activity:** `POCRTSO`
- **Main screen:** `POCRTSOMAIN`
- **Screen count:** 1
- **Total slots across all screens:** 25
- **Splices:** 9 UI · 0 state · 11 data · **20 total**
- **SP chains:** 17
- **Produces entity:** `PurchaseOrder` (id slot: `po_number`)
- **Consumes entity:** `SaleOrder` (id slot: `sale_order_no`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|


## UI splices · 9

Sub-screens the user can open by clicking a LINK control.

- `POCRTSOBUYLNK` → opens **POCRTSOENT** · View Buyer Details
- `POCRTSODISPLNK` → opens **POCRTSOENT** · View Disposition Review
- `POCRTSOEADLNK` → opens **POCRTSOENT** · View Earliest Available Date
- `POCRTSOFSTKLNK` → opens **POCRTSOENT** · View Free Stock Details
- `POCRTSOITMLNK` → opens **POCRTSOENT** · View Item Details
- `POCRTSOLNK1` → opens **POCRTSOENT** · Edit PO
- `POCRTSOSOLNK` → opens **POCRTSOENT** · View SO Details
- `POCRTSOSSROULNK` → opens **POCRTSOENT** · View Stock Status Review - OU Wise
- `POCRTSOSSRWHLNK` → opens **POCRTSOENT** · View Stock Status Review - Warehouse Wise

## Data splices · 11

Triggered when a slot value matches a specific condition in the SP code.

- `@pps_po_combo_default_flag = YES`
- `@back_dated_flag = YES`
- `@adhocitemclassml = NONE`
- `@sogenflag = REQ`
- `@supclass = IN`
- `@num_series <> ~MANUAL~`
- `@po_puom <> @souom_tmp`
- `@convflag = 1`
- `@order_quantity_mul <> FLOOR`
- `@potype = 3`
- `@hdn_processingaction = ALL`

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POCRTSOENT` | 25 | Search Criteria, PO Details |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
