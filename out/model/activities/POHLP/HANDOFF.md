# POHLP — Help On Purchase Order

## At a glance

- **Activity:** `POHLP`
- **Main screen:** `POHLPMAIN`
- **Screen count:** 1
- **Total slots across all screens:** 13
- **Splices:** 0 UI · 0 state · 2 data · **2 total**
- **SP chains:** 5
- **Consumes entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|
| 1 | fetch | `POHLPMAINFTH` | Fetch Help on Po Main page | 0 |
| 2 | init | `POHLPMAININI` | Initialize Help on Po main Page | 0 |
| 3 | fill | `*(implicit)*` | User fills the form (implicit; bot's responsibility) | 0 |
| 4 | commit | `POHLPMAINTRN1` | Search | 2 |

## Commit SP chains (in execution order)

### `POHLPMAINTRN1` — Search

- seq 1: `popohlp_sp_srch_hdrfet`
- seq 2: `popohlp_sp_srchgrd`

## Data splices · 2

Triggered when a slot value matches a specific condition in the SP code.

- `@workflow_app = Y`
- `@error = 1`

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POHLPMAIN` | 13 | Search Criteria |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
