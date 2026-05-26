# POCRT — Create Direct Purchase Order

## At a glance

- **Activity:** `POCRT`
- **Main screen:** `POCRTMAIN`
- **Screen count:** 15
- **Total slots across all screens:** 549
- **Splices:** 126 UI · 14 state · 133 data · **273 total**
- **SP chains:** 222
- **Produces entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|
| 1 | fetch | `POCRTMAINFTH` | Fetch Create Main Page | 0 |
| 2 | init | `POCRTMAININI` | Initialize Create Main Page | 0 |
| 3 | fill | `*(implicit)*` | User fills the form (implicit; bot's responsibility) | 0 |
| 4 | commit | `POCRTMAINSBT` | Create PO | 6 |
| 5 | commit | `POCRTMAINTRN2` | Default | 3 |
| 6 | commit | `POCRTMAINTRN4` | Create and Approve PO | 6 |

## Commit SP chains (in execution order)

### `POCRTMAINSBT` — Create PO

- seq 1: `pocrmn_sp_crt_hdrsav`
- seq 1: `pocrmn_sp_crt_hdrchk`
- seq 1: `pocrmn_sp_crtgrd`
- seq 1: `pocrmn_sp_init_suptxreg`
- seq 2: `pocrmn_sp_aprhref`
- seq 3: `pocrmn_sp_crtgrd_out`

### `POCRTMAINTRN2` — Default

- seq 1: `pocrmn_sp_def_hdrsav`
- seq 1: `pocrmn_sp_defgrd`
- seq 1: `pocrmn_sp_defgrd_out`

### `POCRTMAINTRN4` — Create and Approve PO

- seq 1: `pocrmn_sp_apr_hdrchk`
- seq 1: `pocrmn_sp_apr_hdrsav`
- seq 1: `pocrmn_sp_aprgrd`
- seq 1: `pocrmn_sp_init_suptxreg`
- seq 2: `pocrmn_sp_aprhref`
- seq 3: `pocrmn_sp_aprgrd_out`

## UI splices · 126

Sub-screens the user can open by clicking a LINK control.

- `POCRTBUDBUDLNK` → opens **POCRTBUD** · View Budget Details
- `POCRTBUDITMLNK` → opens **POCRTBUD** · View Item Details
- `POCRTBUDLNK10` → opens **POCRTBUD** · Specify PO-SO Coverage
- `POCRTBUDLNK11` → opens **POCRTBUD** · Attach Notes
- `POCRTBUDLNK8` → opens **POCRTBUD** · Specify Dropship Address
- `POCRTBUDLNK9` → opens **POCRTBUD** · Specify PO-PR Coverage
- `POCRTBUDPROPSLLNK` → opens **POCRTBUD** · View Proposal Details
- `POCRTBUDSUPPLNK` → opens **POCRTBUD** · View Supplier Details
- `POMAINEECOLLABLK` → opens **POCRTBUD** · Link to Collaborate
- `POCRTDRPSHPDRPLNK` → opens **POCRTDRPSHP** · View Dropship Id Details
- `POCRTDRPSHPITMLNK` → opens **POCRTDRPSHP** · View Item Details
- `POCRTDRPSHPLNK10` → opens **POCRTDRPSHP** · Specify PO-SO Coverage
- *…and 114 more*

## Data splices · 133

Triggered when a slot value matches a specific condition in the SP code.

- `@fgbase_yes_no = YES`
- `@potype = 2`
- `@imports = 1`
- `@pps_po_combo_default_flag = YES`
- `@useroption = 1`
- `@taxstatus = A`
- `@count = 1`
- `@budchk = Y`
- `@back_dated_flag = YES`
- `@modeflag = D`
- `@adhocitem = NONE`
- `@catchweightitem = 1`
- *…and more*

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POCRTBUD` | 31 | PO Details, Default Entries |
| `POCRTDRPSHP` | 29 | PO Details, Default Entries |
| `POCRTLATE` | 14 | Document Details, Delivery Penalty |
| `POCRTMAIN` | 86 | PO Details, Amount Details, Default Entries, Line Details, Data History |
| `POCRTMS` | 22 | — |
| `POCRTNOTES` | 36 | PO Details, Notes Details |
| `POCRTPRCOV` | 42 | PO Details, Item Details |
| `POCRTQLTY` | 42 | PO Details, Item Details |
| `POCRTSCH` | 37 | PO Details, Default Entries |
| `POCRTSOCOV` | 41 | PO Details, Item Details |
| `POCRTTCD` | 44 | PO Details |
| `POCRTTCDOTH` | 36 | PO Details |
| `POCRTTRM` | 43 | PO Details, Payment And Insurance Details, Shipping And Delivery Details, LC Details |
| `POCRTVAT` | 37 | — |
| `POSTANDNTSHLP` | 9 | Search Criteria |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
