# POAMND — Amend Purchase Order

## At a glance

- **Activity:** `POAMND`
- **Main screen:** `POAMNDMAIN`
- **Screen count:** 3
- **Total slots across all screens:** 150
- **Splices:** 38 UI · 16 state · 70 data · **124 total**
- **SP chains:** 71
- **Consumes entity:** `PurchaseOrder` (id slot: `po_number`)

## Canonical spine

| # | Phase | Task | Description | SPs |
|---|---|---|---|---|
| 1 | fetch | `POAMDMAINFTH` | Fetch Amend Main Page | 0 |
| 2 | init | `POAMDMAININI` | Initialize Amend Main Page | 0 |
| 3 | fill | `*(implicit)*` | User fills the form (implicit; bot's responsibility) | 0 |
| 4 | commit | `POAMDMAINSBT` | Amend PO | 5 |
| 5 | commit | `POAMDMAINTRN1` | Default | 3 |
| 6 | commit | `POAMDMAINTRN4` | Get all Quot Line No | 1 |
| 7 | commit | `POAMDMAINTRN5` | Amend and Approve PO | 5 |
| 8 | commit | `POMAINSRRETURNTR` | Return PO | 2 |

## Commit SP chains (in execution order)

### `POAMDMAINSBT` — Amend PO

- seq 1: `poamdmm_sp_amnd_hdrchk`
- seq 1: `poamdmm_sp_amndgrd`
- seq 1: `poamdmm_sp_amnd_hdrsav`
- seq 1: `poamdmm_sp_amndhref`
- seq 2: `poamdmm_sp_amndgrd_out`

### `POAMDMAINTRN1` — Default

- seq 1: `poamdmm_sp_defgrd`
- seq 1: `poamdmm_sp_defgrd_out`
- seq 1: `poamdmm_sp_def_hdrsav`

### `POAMDMAINTRN4` — Get all Quot Line No

- seq 1: `poamdmm_sp_qtngrd`

### `POAMDMAINTRN5` — Amend and Approve PO

- seq 1: `poamdmm_sp_aprgrd`
- seq 1: `poamdmm_sp_apr_hdrsav`
- seq 1: `poamdmm_sp_aprhref`
- seq 1: `poamdmm_sp_apr_hdrchk`
- seq 2: `poamdmm_sp_aprgrd_out`

### `POMAINSRRETURNTR` — Return PO

- seq 1: `poamdmm_sp_ret_hdrsav`
- seq 1: `poamdmm_sp_ret_href`

## UI splices · 38

Sub-screens the user can open by clicking a LINK control.

- `POAMDENTLNK1` → opens **POAMNDENT** · Amend PO
- `POAMNDENTLNK2` → opens **POAMNDENT** · Amend PO
- `POAMDMAINLNK10` → opens **POAMNDMAIN** · Specify PO-SO Coverage
- `POAMDMAINLNK11` → opens **POAMNDMAIN** · Attach Notes
- `POAMDMAINLNK2` → opens **POAMNDMAIN** · Specify Schedule and Distribution
- `POAMDMAINLNK3` → opens **POAMNDMAIN** · Specify Terms and Condition
- `POAMDMAINLNK6` → opens **POAMNDMAIN** · Specify Quality Details
- `POAMDMAINLNK7` → opens **POAMNDMAIN** · Specify Budget Details
- `POAMDMAINLNK8` → opens **POAMNDMAIN** · Specify Dropship Address
- `POAMDMAINLNK9` → opens **POAMNDMAIN** · Specify PO-PR Coverage
- `POAMDMAINTAXLNK` → opens **POAMNDMAIN** · Specify Tax Details
- `POAMNDMAINBUDLNK` → opens **POAMNDMAIN** · View Budget Details
- *…and 26 more*

## Data splices · 70

Triggered when a slot value matches a specific condition in the SP code.

- `@fgbase_yes_no = YES`
- `@potype = 2`
- `@imports = 1`
- `@status = OP`
- `@workflow_app = Y`
- `@part_cov_pr_flag = YES`
- `@useroption = 1`
- `@taxstatus = A`
- `@count = 1`
- `@tran_rights_flag = Y`
- `@mbp_ms_level = DOC`
- `@status <> OP`
- *…and more*

## Screens

| Screen | Slots | Collect steps |
|---|---|---|
| `POAMNDENT` | 19 | Direct Entry, Search Criteria |
| `POAMNDMAIN` | 96 | PO Details, Amount Details, Default Entries, Data History |
| `POAMNDSCH` | 35 | PO Details, Default Entries |

---

This file is generated automatically from the parsed Ramco artifacts.
The corresponding machine-readable views are in this folder:
`01_spine.json`, `02_splices.json`, `03_screens.json`, `04_sp_chains.json`, `05_taxonomy.json`.
