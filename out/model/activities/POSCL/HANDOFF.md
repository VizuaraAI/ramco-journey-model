# POSCL — Short Close Purchase Order

## At a glance

- **Activity:** `POSCL`
- **Main screen:** `POSCLMAIN`
- **Screen count:** 2
- **Total slots across all screens:** 103
- **Splices:** 24 UI · 0 state · 7 data · **31 total**
- **SP chains:** 28
- **Consumes entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|
| 1 | fetch | `POSCLMAINFTH` | Fetch Shortclose Main Page | 0 |
| 2 | fill | `*(implicit)*` | User fills the form (implicit; bot's responsibility) | 0 |
| 3 | commit | `POSCLMAINSBT` | Shortclose PO | 4 |

## Commit SP chains (in execution order)

### `POSCLMAINSBT` — Shortclose PO

- seq 1: `posclm_sp_scl_docsav`
- seq 3: `posc_wf_sp_iscall`
- seq 12: `po_dummy_sp`
- seq 13: `po_shcl_sp_Return_State_out`

## UI splices · 24

Sub-screens the user can open by clicking a LINK control.

- `POSCLENTLNK1` → opens **POSCLENT** · Shortclose PO
- `POSCLENTLNK2` → opens **POSCLENT** · Shortclose PO
- `POMAIN14COLLABLK` → opens **POSCLMAIN** · Link to Collaborate
- `POMAIN14VWORDELK` → opens **POSCLMAIN** · Link to View Mapped LCs
- `POSCLMAINBUYLNK` → opens **POSCLMAIN** · View Buyer Details
- `POSCLMAINDISPLNK` → opens **POSCLMAIN** · View Disposition Review
- `POSCLMAINEADLNK` → opens **POSCLMAIN** · View Earliest Available Date Details
- `POSCLMAINFSTKLNK` → opens **POSCLMAIN** · View Free Stock Details
- `POSCLMAINITMLNK` → opens **POSCLMAIN** · View item details
- `POSCLMAINLNK10` → opens **POSCLMAIN** · View PO-SO Coverage
- `POSCLMAINLNK11` → opens **POSCLMAIN** · View Notes
- `POSCLMAINLNK12` → opens **POSCLMAIN** · Posclmainlnk12
- *…and 12 more*

## Data splices · 7

Triggered when a slot value matches a specific condition in the SP code.

- `@prtype <> DP`
- `@status = AM`
- `@groption = Y`
- `@modeflag <> S`
- `@potype <> 3`
- `@ctxt_service_in = poscle_ser_scl`
- `@ctxt_service_in = posclm_ser_scl`

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POSCLENT` | 21 | Direct Entry, Search Criteria |
| `POSCLMAIN` | 82 | PO Details, Amount Details, Data History |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
