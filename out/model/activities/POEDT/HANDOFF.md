# POEDT — Edit Purchase Order

## At a glance

- **Activity:** `POEDT`
- **Main screen:** `POEDTMAIN`
- **Screen count:** 2
- **Total slots across all screens:** 107
- **Splices:** 28 UI · 16 state · 70 data · **114 total**
- **SP chains:** 62
- **Consumes entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|
| 1 | fetch | `POEDTMAINFTH` | Fetch Edit Main Page | 0 |
| 2 | init | `POEDTMAININI` | Initialize Edit Main Page | 0 |
| 3 | fill | `*(implicit)*` | User fills the form (implicit; bot's responsibility) | 0 |
| 4 | commit | `POEDTMAINSBT` | Edit PO | 5 |
| 5 | commit | `POEDTMAINTRN2` | Default | 3 |
| 6 | commit | `POEDTMAINTRN5` | Get All Quot Line No. | 1 |
| 7 | commit | `POEDTMAINTRN6` | Delete PO | 2 |
| 8 | commit | `POEDTMAINTRN7` | Edit and Approve PO | 5 |

## Commit SP chains (in execution order)

### `POEDTMAINSBT` — Edit PO

- seq 1: `poemn_sp_edthref`
- seq 1: `poemn_sp_edt_hdrchk`
- seq 1: `poemn_sp_edt_hdrsav`
- seq 1: `poemn_sp_aprgrd`
- seq 2: `poemn_sp_aprgrd_out`

### `POEDTMAINTRN2` — Default

- seq 1: `poemn_sp_defgrd`
- seq 1: `poemn_sp_defgrd_out`
- seq 1: `poemn_sp_def_hdrsav`

### `POEDTMAINTRN5` — Get All Quot Line No.

- seq 1: `poemn_sp_qtngrd`

### `POEDTMAINTRN6` — Delete PO

- seq 1: `poemn_sp_del_docsav`
- seq 1: `poemn_sp_Del_HRef`

### `POEDTMAINTRN7` — Edit and Approve PO

- seq 1: `poemn_sp_aprgrd`
- seq 1: `poemn_sp_aprhref`
- seq 1: `poemn_sp_apr_hdrsav`
- seq 1: `poemn_sp_apr_hdrchk`
- seq 2: `poemn_sp_aprgrd_out`

## UI splices · 28

Sub-screens the user can open by clicking a LINK control.

- `POEDTENTLNK1` → opens **POEDTENT** · Edit PO
- `POEDTENTLNK2` → opens **POEDTENT** · Edit PO
- `POEDTMAINBUDDETAILLNK` → opens **POEDTMAIN** · View Budget Details
- `POEDTMAINBULNK` → opens **POEDTMAIN** · View Buyer Detail
- `POEDTMAINDISPNLNK` → opens **POEDTMAIN** · View Disposition Review
- `POEDTMAINEARAVLBLDTLNK` → opens **POEDTMAIN** · View Earliest Available Date
- `POEDTMAINFREESTKLNK` → opens **POEDTMAIN** · View Free Stock Details
- `POEDTMAINITMLNK` → opens **POEDTMAIN** · View Item Detail
- `POEDTMAINLNK10` → opens **POEDTMAIN** · Specify PO-SO Coverage
- `POEDTMAINLNK11` → opens **POEDTMAIN** · Attach Notes
- `POEDTMAINLNK2` → opens **POEDTMAIN** · Specify Schedule and Distribution
- `POEDTMAINLNK3` → opens **POEDTMAIN** · Specify Terms and Condition
- *…and 16 more*

## Data splices · 70

Triggered when a slot value matches a specific condition in the SP code.

- `@fgbase_yes_no = YES`
- `@imports = 1`
- `@workflow_app = Y`
- `@part_cov_pr_flag = YES`
- `@pps_po_combo_default_flag = YES`
- `@useroption = 1`
- `@taxstatus = A`
- `@count = 1`
- `@tran_rights_flag = Y`
- `@budchk = Y`
- `@back_dated_flag = YES`
- `@sched_typeml = STAG`
- *…and more*

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POEDTENT` | 18 | Direct Entry, Search Criteria |
| `POEDTMAIN` | 89 | PO Details, Amount Details, Default Entries, Print Document, Data History |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
