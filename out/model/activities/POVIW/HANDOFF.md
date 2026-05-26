# POVIW — View Purchase Order

## At a glance

- **Activity:** `POVIW`
- **Main screen:** `POVIWMAIN`
- **Screen count:** 13
- **Total slots across all screens:** 500
- **Splices:** 128 UI · 10 state · 8 data · **146 total**
- **SP chains:** 105
- **Consumes entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|
| 1 | fetch | `POVWMAINFTH` | Fetch View Main Page | 0 |
| 2 | init | `POVWMAININI` | Initialize View Main Page | 0 |
| 3 | fill | `*(implicit)*` | User fills the form (implicit; bot's responsibility) | 0 |


## UI splices · 128

Sub-screens the user can open by clicking a LINK control.

- `POMAIN16BUDGETLK` → opens **POVIWBUD** · Link to Budget Id
- `POMAIN16COLLABLK` → opens **POVIWBUD** · Link to Collaborate
- `POMAIN16PRPSLILK` → opens **POVIWBUD** · Link to Proposal Id
- `POVWBUDBUDLNK` → opens **POVIWBUD** · View Budget Id Details
- `POVWBUDITMLNK` → opens **POVIWBUD** · View item details
- `POVWBUDLNK10` → opens **POVIWBUD** · View PO-SO Coverage
- `POVWBUDLNK11` → opens **POVIWBUD** · View Notes
- `POVWBUDLNK8` → opens **POVIWBUD** · View Dropship Address
- `POVWBUDLNK9` → opens **POVIWBUD** · View PO-PR Coverage
- `POVWBUDPROPSLLNK` → opens **POVIWBUD** · View Proposal Id Details
- `POVWBUDSUPPLNK` → opens **POVIWBUD** · View Supplier details
- `POMAIN17COLLABLK` → opens **POVIWDRPSHP** · Link to Collaborate
- *…and 116 more*

## Data splices · 8

Triggered when a slot value matches a specific condition in the SP code.

- `@useroption = 1`
- `@taxstatus = A`
- `@count = 1`
- `@tran_rights_flag = Y`
- `@adhocitemclass = ALL`
- `@wbsparam = N`
- `@wbsparam = Y`
- `@loi = N`

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POVIWBUD` | 22 | PO Details |
| `POVIWDRPSHP` | 22 | PO Details |
| `POVIWENT` | 21 | Direct Entry, Search Criteria |
| `POVIWMAIN` | 101 | PO Details, Amount Details, Data History |
| `POVIWNOTES` | 33 | PO Details, Notes Details |
| `POVIWPRCOV` | 38 | PO Details, Item Details |
| `POVIWQLTY` | 38 | PO Details, Item Details |
| `POVIWSCH` | 26 | PO Details |
| `POVIWSOCOV` | 36 | PO Details, Item Details |
| `POVIWTCD` | 36 | PO Details |
| `POVIWTCDOTH` | 30 | PO Details |
| `POVIWTRM` | 70 | Payment And Insurance Details, Shipping And Delivery Details, LC Details |
| `POVIWVAT` | 27 | — |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
