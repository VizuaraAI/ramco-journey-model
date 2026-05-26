# POAPP — Approve Purchase Order

## At a glance

- **Activity:** `POAPP`
- **Main screen:** `POAPPMAIN`
- **Screen count:** 3
- **Total slots across all screens:** 134
- **Splices:** 28 UI · 16 state · 56 data · **100 total**
- **SP chains:** 59
- **Consumes entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|
| 1 | fetch | `POAPPMAINFTH` | Fetch Approve Main Page | 0 |
| 2 | init | `POAPPMAININI` | Initialize Approve Main Page | 0 |
| 3 | fill | `*(implicit)*` | User fills the form (implicit; bot's responsibility) | 0 |
| 4 | commit | `POAPPMAINSBT` | Approve PO | 5 |
| 5 | commit | `POAPPMAINTRN1` | Default | 2 |
| 6 | commit | `POAPPMAINTRN4` | Get All Quote Line No. | 1 |
| 7 | commit | `POAPPMAINTRN5` | Return PO | 2 |

## Commit SP chains (in execution order)

### `POAPPMAINSBT` — Approve PO

- seq 1: `poaprmn_sp_aprgrd`
- seq 1: `poaprmn_sp_apr_hdrchk`
- seq 1: `poaprmn_sp_aprhref`
- seq 1: `poaprmn_sp_apr_hdrsav`
- seq 2: `poaprmn_sp_aprgrd_out`

### `POAPPMAINTRN1` — Default

- seq 1: `poaprmn_sp_def_grd`
- seq 2: `poaprmn_sp_defgrd`

### `POAPPMAINTRN4` — Get All Quote Line No.

- seq 1: `poaprmn_sp_qtngrd`

### `POAPPMAINTRN5` — Return PO

- seq 1: `poaprmn_Mt_Del_HRef`
- seq 1: `poaprmn_sp_ret_docsav`

## UI splices · 28

Sub-screens the user can open by clicking a LINK control.

- `POAPPENTLNK1` → opens **POAPPENT** · Approve PO
- `POAPPENTMAINLNK2` → opens **POAPPENT** · Approve PO
- `POAPPMAINBUDDETAILLNK` → opens **POAPPMAIN** · View Budget Details
- `POAPPMAINDISPNLNK` → opens **POAPPMAIN** · View Disposition Review
- `POAPPMAINEARAVLBLDTLNK` → opens **POAPPMAIN** · View Earliest Available Date
- `POAPPMAINFREESTKLNK` → opens **POAPPMAIN** · View Free Stock Details
- `POAPPMAINLNK10` → opens **POAPPMAIN** · Specify PO-SO Coverage
- `POAPPMAINLNK11` → opens **POAPPMAIN** · Attach Notes
- `POAPPMAINLNK12` → opens **POAPPMAIN** · View Item Details
- `POAPPMAINLNK13` → opens **POAPPMAIN** · View Supplier Details
- `POAPPMAINLNK14` → opens **POAPPMAIN** · View Buyer Details
- `POAPPMAINLNK15` → opens **POAPPMAIN** · View Warehouse Details
- *…and 16 more*

## Data splices · 56

Triggered when a slot value matches a specific condition in the SP code.

- `@fgbase_yes_no = YES`
- `@imports = 1`
- `@status = OP`
- `@workflow_app = Y`
- `@loi = 1`
- `@part_cov_pr_flag = YES`
- `@pps_po_combo_default_flag = YES`
- `@useroption = 1`
- `@taxstatus = A`
- `@count = 1`
- `@tran_rights_flag = Y`
- `@mbp_ms_level = DOC`
- *…and more*

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POAPPENT` | 33 | Direct Entry, Search Criteria |
| `POAPPMAIN` | 95 | PO Details, Amount Details, Default Entries, Data History |
| `POAPPREP` | 6 | — |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
