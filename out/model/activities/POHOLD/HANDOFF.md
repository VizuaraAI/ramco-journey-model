# POHOLD — Change Status - Purchase Order

## At a glance

- **Activity:** `POHOLD`
- **Main screen:** `POHOLDMAIN`
- **Screen count:** 2
- **Total slots across all screens:** 94
- **Splices:** 23 UI · 0 state · 9 data · **32 total**
- **SP chains:** 31
- **Consumes entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|
| 1 | fetch | `POHLDMAINFTH` | Fetch Change Status Main Page | 0 |
| 2 | init | `POHLDMAININI` | Initialize Change Status Main Page | 0 |
| 3 | fill | `*(implicit)*` | User fills the form (implicit; bot's responsibility) | 0 |
| 4 | commit | `POHLDMAINSBT` | Change Status | 1 |

## Commit SP chains (in execution order)

### `POHLDMAINSBT` — Change Status

- seq 1: `pohldmn_sp_chng_docsav`

## UI splices · 23

Sub-screens the user can open by clicking a LINK control.

- `POHLDENTLNK1` → opens **POHOLDENT** · Change Status
- `POHLDENTLNK2` → opens **POHOLDENT** · Change Status
- `POHLDMAINBUYLNK` → opens **POHOLDMAIN** · View Buyer Details
- `POHLDMAINDISPLNK` → opens **POHOLDMAIN** · View Disposition Review
- `POHLDMAINEADLNK` → opens **POHOLDMAIN** · View Earliest Available Date Details
- `POHLDMAINFSTKLNK` → opens **POHOLDMAIN** · View Free Stock Details
- `POHLDMAINITMLNK` → opens **POHOLDMAIN** · View Item Details
- `POHLDMAINLNK10` → opens **POHOLDMAIN** · View PO-SO Coverage
- `POHLDMAINLNK11` → opens **POHOLDMAIN** · View Notes
- `POHLDMAINLNK12` → opens **POHOLDMAIN** · PoHldMainlnk12
- `POHLDMAINLNK2` → opens **POHOLDMAIN** · View Schedule and Distribution
- `POHLDMAINLNK3` → opens **POHOLDMAIN** · View Terms and Condition
- *…and 11 more*

## Data splices · 9

Triggered when a slot value matches a specific condition in the SP code.

- `@status_mlt = OPEN`
- `@status_mlt = AU`
- `@status_mlt = HOLD`
- `@status_mlt = HD`
- `@paymentstatus = HD`
- `@paymentstatus = RL`
- `@orderstatushdr = RL`
- `@paymentstatus = HOLD`
- `@paymentstatus = RELEASE`

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POHOLDENT` | 20 | Direct Entry, Search Criteria |
| `POHOLDMAIN` | 74 | PO Details, Amount  Details, Data History |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
