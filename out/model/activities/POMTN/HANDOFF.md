# POMTN — Maintain Purchase Order

## At a glance

- **Activity:** `POMTN`
- **Main screen:** `POMTNMAIN`
- **Screen count:** 1
- **Total slots across all screens:** 117
- **Splices:** 8 UI · 20 state · 4 data · **32 total**
- **SP chains:** 56
- **Consumes entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|


## UI splices · 8

Sub-screens the user can open by clicking a LINK control.

- `POMAIN29ORDERLLK` → opens **POMTN** · Link to Order LCMap Lnk
- `POMAIN29SPECI_LK` → opens **POMTN** · Link to Specify Tax Details
- `POMAIN29ATTACHLK` → opens **POMTN** · Link to Attach Notes
- `POMAIN29COLLABLK` → opens **POMTN** · Link to Collaborate
- `POMAIN29OPERATLK` → opens **POMTN** · Link to Operational Checklist
- `POMAIN29SPECIFLK` → opens **POMTN** · Link to Specify Tax Charges Discount
- `POMAIN29SPECIYLK` → opens **POMTN** · Link to Specify PO PR Coverage
- `POMAIN29TAX_CALK` → opens **POMTN** · Link to Tax Calculation Summary

## Data splices · 4

Triggered when a slot value matches a specific condition in the SP code.

- `@pps_po_combo_default_flag = YES`
- `@useroption = 1`
- `@taxstatus = A`
- `@count = 1`

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POMTN` | 117 | Order Terms, Supplier Creation Details |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
