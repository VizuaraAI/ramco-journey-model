# POCRTTEN — Create Purchase Order From Tender

## At a glance

- **Activity:** `POCRTTEN`
- **Main screen:** `POCRTTENMAIN`
- **Screen count:** 1
- **Total slots across all screens:** 4
- **Splices:** 2 UI · 0 state · 0 data · **2 total**
- **SP chains:** 5
- **Produces entity:** `PurchaseOrder` (id slot: `po_number`)
- **Consumes entity:** `Tender` (id slot: `tender_no`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|


## UI splices · 2

Sub-screens the user can open by clicking a LINK control.

- `POMAIN40EDITBPLK` → opens **POCRTTENUI** · Link to Edit BPo
- `POMAIN40EDITPOLK` → opens **POCRTTENUI** · Link to Edit Po

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POCRTTENUI` | 4 | — |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
