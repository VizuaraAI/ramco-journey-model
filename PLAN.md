# `ramco-journey-model` · the plan

> One project, one document. Bookmark this — every phase, every folder, every measurement bar lives here.

---

## Where everything lives

| What | Absolute path |
|---|---|
| **Project root** | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/` |
| **Source artifacts (symlink)** | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/artifacts/ramco` → `/Users/rajat/Downloads/Ramco Artifacts/` |
| **★ Eval cases (golden dataset, 50 multi-turn conversations) ★** | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/eval/cases/` |
| Eval schema | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/eval/schema/conversation.schema.json` |
| Eval runner code | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/eval/runner/` |
| Eval reports (HTML) | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/eval/reports/` |
| Latest report | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/eval/reports/latest.html` |
| Determinism contract | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/DETERMINISM.md` |
| Related — earlier wiki project | `/Users/rajat/Desktop/Ramco Rise Claude/po-journey-wiki/` |
| Related — teaching page | `/Users/rajat/Desktop/Ramco Rise Claude/po-journey-wiki/teaching/derive-journey-from-artifacts.html` |

---

## LLM configuration

Where the determinism contract permits LLM use (P4 labeller and P6–P8 chatbot runtime), we use **Gemini 2.5 Pro**.

| Setting | Value |
|---|---|
| Model | `gemini-2.5-pro` |
| API key | `<scrubbed — store in .env locally and as a Space secret on HF>` |
| Key file (canonical) | `/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/.env` |
| Loaded by | every module that talks to the LLM (P4 labeller, P6/P7/P8 chatbot) |

> **Security note.** This API key is stored in `PLAN.md` for visibility but the canonical store is `.env`. `.env` is `.gitignore`d so it won't be pushed to GitHub. **If we ever publish this repo publicly, scrub the key from `PLAN.md` first and rotate the key in Google AI Studio.**

Recall the layers where LLM is forbidden vs allowed (`DETERMINISM.md`):

| Layer | LLM use? |
|---|---|
| L0 — artifact mirror | ❌ |
| L1 — parsers (P1) | ❌ |
| L2 — composer (P2) | ❌ |
| L3 — validator (P3) | ❌ |
| L4 — labeller (P4) | ✅ bounded — single label rewrite, strict I/O contract, cites source |
| L5 — chatbot runtime (P6–P8) | ✅ NL understanding & generation only, never structure |

---

## The vision

A natural-language chatbot for Ramco's Purchase Order module that walks users through their 14 user-facing PO journeys (Create Direct, Create from Quotation, Amend, Approve, View, Hold, Short-Close, etc.). Users describe what they want in English; the bot identifies the right journey, collects the right slots, walks any splices that fire, and commits via the real stored-procedure call chain.

### Two principles, non-negotiable

1. **Determinism gradient.** Structure (parsers, composer, validator) is 100% deterministic — no LLM, no fuzzy matching. The LLM is only allowed at the labelling layer (bounded) and the chatbot runtime (NL only, never structure). See `DETERMINISM.md` for the full contract.
2. **Eval-first.** 50 multi-turn ground-truth conversations exist *before* any chatbot code. Every phase is measured against them. Nothing ships on vibes.

### The 14 user-facing PO journeys

| # | Activity | Description |
|---|---|---|
| 1 | `PoCrt` | Create Direct Purchase Order |
| 2 | `PoCrtQtn` | Create PO From Quotation |
| 3 | `PoCrtSo` | Create PO From Sale Order |
| 4 | `PoCrtTen` | Create PO From Tender |
| 5 | `PoCopy` | Copy and Create PO |
| 6 | `PoAmnd` | Amend PO |
| 7 | `PoApp` | Approve PO |
| 8 | `PoEdt` | Edit PO |
| 9 | `PoViw` | View PO |
| 10 | `PoMtn` | Maintain PO |
| 11 | `PoHold` | Change Status (Hold/Unhold) |
| 12 | `PoScl` | Short Close PO |
| 13 | `PoAcCcUsgMod` | AC/CC Usage Modification |
| 14 | `PoHlp` | Help On PO (field lookup) |

---

## The golden eval dataset

50 multi-turn conversations, 164 turns total, hand-curated. Located at:

```
/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/eval/cases/
├── discovery/              5 cases  — capability questions ("what can I do?")
├── single_happy/          12 cases  — one happy path per major journey
├── single_splice/         10 cases  — Capital, Consignment, Dropship, Imports, LoI,
│                                       Terms, TCD, PR-Coverage, SO-Coverage, Quality
├── error_recovery/         8 cases  — invalid input, missing slot, currency mismatch,
│                                       duplicate, mid-flow change, ambiguity, validation
│                                       reject, date ambiguity
├── cross_journey/          6 cases  — Create→Approve, Create→Amend, View→Amend,
│                                       Create→Hold, Approve→Return, View→ShortClose
├── lookup/                 5 cases  — status by number, pending approvals, by supplier,
│                                       workflow trace, lines by item
└── cross_module/           4 cases  — PR→PO, PO→GR status, PO→Quotation source,
                                        PO blocked by GR
```

Each case is a JSON document with:
- the multi-turn conversation (user text per turn)
- per-turn expected state assertions (journey locked, slots extracted, splices triggered, trans invoked, SP chain expected, bot-must-say / bot-must-not-say)
- terminal-state expectations (final journey, commit task, PO status, splices walked, next possible journeys)
- evaluation metrics (named pass/fail rules)

Run the evaluator:

```bash
cd "/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model"
python3 eval/runner/evaluator.py stub   # baseline against the do-nothing stub bot
```

Open `eval/reports/latest.html` to see the per-case, per-turn, per-metric breakdown.

---

## The phases

Eight phases, P0 through P8. P0 is done. P1–P5 build the deterministic journey model. P6–P8 build the chatbot on top, with the eval harness measuring progress at every step.

### P0 — Eval foundation · **DONE**

**What.** Ground-truth dataset, evaluator harness, baseline.

**Files.** Everything under `eval/`.

**Eval bar.** Harness runs end-to-end and produces a per-case, per-turn HTML report. Baseline with the stub bot reports `0 / 50` cases passed (a few "do-nothing" metrics trivially pass — the real number to watch is cases-passing).

**Status.** ✅ 50 cases written, 164 turns, all pass structural validation. Baseline run = 0/50, HTML report renders.

---

### P1 — Six parsers (the determinism core)

**What.** One parser per artifact type. Each parser reads source files and produces structured JSON conforming to its schema. **No LLM. No fuzzy matching.** If something can't be parsed, fail loudly.

**Files (to be created under `parsers/`):**

| Parser | Reads | Produces |
|---|---|---|
| `p01_module_manifest.py` | `PO_info.xml` | every Activity → ILBO → Page → Task, with type (FETCH/INIT/TRANS/UI/HELP/LINK/DISPOSAL) and description |
| `p02_screen_state.py` | `*_State.xml` (e.g. `PoCrt_PoCrtMain_State.xml`) | services per screen, named states, control-visibility per state |
| `p03_screen_form.py` | `*.htm` (e.g. `Pocrt_pocrtmain.htm`) | sections and slots (with labels, types, datatypes) + the meta Tasks header parsed into structured task list |
| `p04_screen_behaviour.py` | `*_user.js` (e.g. `Pocrt_pocrtmain_user.js`) | task descriptions from the `postTaskResultProcess` switch (cross-check for P1/P3) |
| `p05_service_catalog.py` | `Service_details_PO.csv` | task → ordered SP chain (group by `(ui_name, task_name)`, order by `sequenceno`) |
| `p06_sp_branches.py` | `*.sql` (1,219 SPs) | structured `(slot, op, value, consequence)` tuples from every `IF`/`CASE` branch. **This is the splice-discovery engine.** |

**Eval bar.** Per-parser unit tests pass. Golden tests: pin specific facts in `tests/` (e.g. "p01 must find activity POCRT with task POCRTMAINSBT type=TRANS"; "p06 must find `@potypeenum` as a parameter and `@potypeenum = 'Capital'` as a branch condition in `pocrmn_sp_crt_hdrchk.sql`").

**Order.** Build `p06_sp_branches.py` first — it's the riskiest piece. If splice extraction from one SP works, the rest of the parsers are mechanical XML/HTML/CSV walkers.

**LLM usage.** None. If we're tempted, the parser needs better rules instead.

---

### P2 — Composer

**What.** Pure joins over P1 outputs. Builds the journey model — one JSON file per activity, plus a module-level graph.

**Files:**

```
composer/
├── c01_join_screen.py             # one screen = state + form + behaviour
├── c02_join_activity.py           # one activity = manifest + screens + sp chains
├── c03_splice_catalog.py          # combine UI splices (.htm LINK) + state splices
│                                   #   (*_State.xml) + data splices (SP IF branches)
└── c04_cross_journey_graph.py     # LINK tasks pointing to other activities
```

**Output:**

```
out/model/
├── activities/
│   ├── PoCrt.json          # canonical spine + slots + splices + sp chains
│   ├── PoAmnd.json
│   ├── PoApp.json
│   └── ...                 # one per user-facing journey
└── module_graph.json       # cross-journey edges (PoCrt → PoApp, PoCrt → PoAmnd, etc.)
```

**Eval bar.** Round-trip:
- every TRANS task in `PO_info.xml` for an activity appears in that activity's model
- every slot in the activity's main `.htm` appears with a label
- every splice with a state-XML name has a trigger condition (from P6's SP scan)

**LLM usage.** None.

---

### P3 — Validator

**What.** Coverage + gap diagnostics on the P2 model. Read-only.

**Files:**

```
validator/
├── v01_coverage.py            # % slots labelled, % TRANS captured, % splices with trigger
├── v02_gaps.py                # which slots have no SP parameter mapping?
│                              # which splices have a state ID but no SP trigger condition?
├── v03_consistency.py         # do .htm meta Tasks match PO_info.xml task list?
└── lint_determinism.py        # scans parsers/, composer/, validator/ for any LLM imports
                               # — fails CI if violated
```

**Eval bar.** `v01` reports ≥95% slots labelled, 100% TRANS captured, ≥90% splices with a clean trigger. `lint_determinism.py` reports zero violations.

**LLM usage.** None.

---

### P4 — Labeller (bounded LLM, optional but recommended)

**What.** Rewrite terse artifact labels into more natural bot-facing prose. Strict input/output contract: input is one raw label, output is one rewritten label with a citation back. **Cannot invent structure. Cannot cross-cite. Cannot change semantics.**

**Files:**

```
labeller/
├── l01_label_terse.py             # rewriter — uses Gemini 2.5 Pro with strict prompt
├── label_io.schema.json           # strict contract for input/output
└── prompt_v1.md                   # versioned prompt (every change bumps version)
```

**Example.**
- Input: `{ "raw_label": "POMAIN29SAVE1TR · Save", "context": "PoMtn screen, after editing payment terms" }`
- Output: `{ "rewritten_label": "Save the changes to the supply order configuration", "cites": ["raw_label"], "model": "gemini-2.5-pro", "prompt_version": "v1" }`

**Eval bar.** Every rewrite has a citation. Human spot-check on 20 random rewrites: 100% preserve meaning, 0% invent.

**LLM usage.** Allowed here, bounded. This is the *only* layer where LLM touches the model.

---

### P5 — Viewer (static HTML, no LLM)

**What.** A browsable HTML page to inspect the model. For each activity: canonical spine, splices nested under their hook step, slots per screen, SP chains per task, cross-journey edges. Like the wiki we built earlier but driven from the deterministic model, not from documents.

**Files:**

```
viewer/
├── build.py            # reads out/model/, writes out/viewer/
└── viewer.template.html
out/viewer/
├── index.html
├── data.json           # the model
└── viewer.js
```

**Eval bar.** Open `out/viewer/index.html`. Click `PoCrt`. See: 5 canonical steps with TRANS task names, 12 LINK splices grouped under the right step, 30+ slots with labels and types, the SP call chain for each commit task. **No invented content.**

**LLM usage.** None. The viewer renders model JSON.

---

### P6 — Chatbot v1 (naive)

**What.** First runnable chatbot. Implements:
- intent classification (LLM-assisted, against a fixed intent vocabulary)
- journey identification (matches user input to one of the 14 journeys)
- slot extraction from natural language (LLM-assisted, slots constrained to model vocabulary)
- commit action (invokes the right TRANS task via the parsed SP chain)

Does **not yet** handle splices or error recovery. Designed to pass discovery + simple happy-path cases.

**Files:**

```
chatbot/
├── intent_classifier.py
├── slot_filler.py
├── journey_router.py
├── state_machine.py
├── runtime.py
├── llm_prompts/
│   ├── intent_v1.md
│   ├── slot_extract_v1.md
│   └── disambiguate_v1.md
└── app.py                          # CLI + simple web UI
```

**Eval bar.** Re-run `python3 eval/runner/evaluator.py v1`. Target: **discovery (5) + simple single-journey-happy-path (10) pass = ~15 / 50**.

**LLM usage.** LLM for intent, slot extraction, response generation. LLM never invents structure — it picks from model vocabulary.

---

### P7 — Chatbot v2 (splices + error recovery)

**What.** Adds:
- splice detection from user input (data-triggered — "Capital PO", "Consignment", "dropship to customer")
- splice walking (open the right sub-screen, collect additional slots, return)
- validation pre-checks before commit (catch `qcchk=1` mandatory-slot violations client-side)
- mid-flow corrections (user changes mind — retract splice cleanly)
- ambiguity detection (ask before acting)
- slot re-prompt on invalid input

**Files added/modified:**

```
chatbot/
├── splice_navigator.py            # new — walks UI/data/state splices
├── validator.py                   # new — pre-commit checks against SP IF conditions
├── recovery.py                    # new — retract splices, re-prompt slots
└── (existing files updated)
```

**Eval bar.** Re-run evaluator. Target: **+ all 10 splice + all 8 error_recovery + 2 more happy-paths = ~35 / 50**.

**LLM usage.** Same as v1 plus prompted "is this a splice trigger?" classification with bounded vocabulary.

---

### P8 — Chatbot v3 (cross-journey + cross-module)

**What.** Adds:
- cross-journey context carry (PO number from Create → carried into Approve)
- journey switching detection ("now amend it" → switch to PoAmnd)
- cross-module reads (fetch from PR / GR / PQ when the user references them)
- cross-module writes via callback (e.g., PR status updated when PO covers it)

**Files added/modified:**

```
chatbot/
├── context_carry.py               # new — multi-journey state
├── journey_switcher.py            # new — detects switch, validates legality
├── cross_module_adapter.py        # new — reads/writes other module models
└── (existing files updated)
```

**Eval bar.** Re-run evaluator. Target: **all 6 cross_journey + 5 lookup + 4 cross_module + remaining cases = ~48-50 / 50**.

**LLM usage.** Same as v2.

---

## Summary table

| Phase | Deliverable | Eval target | LLM allowed? |
|---|---|---|---|
| **P0** ✅ done | Eval foundation: 50 cases, harness, baseline | 0/50 (baseline) | No |
| **P1** | Six parsers, structured JSON outputs | per-parser unit tests | **No** |
| **P2** | Composer: one JSON per activity, module graph | round-trip validations | **No** |
| **P3** | Validator: coverage + gap report + determinism lint | ≥95% slots labelled, 100% TRANS | **No** |
| **P4** | Labeller (bounded LLM): nicer prose for terse labels | every rewrite cites source | **Yes** (only here in model layer) |
| **P5** | Viewer: static HTML to browse model | renders cleanly, no invented content | No |
| **P6** | Chatbot v1: intent + slot fill + commit (no splices) | ~15 / 50 cases | Yes (runtime only) |
| **P7** | Chatbot v2: + splices + error recovery | ~35 / 50 cases | Yes |
| **P8** | Chatbot v3: + cross-journey + cross-module | ~48-50 / 50 cases | Yes |

---

## Running the eval (any time)

```bash
cd "/Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model"

# Validate all 50 cases parse against the schema
python3 eval/runner/loader.py

# Run the evaluator against a specific bot
python3 eval/runner/evaluator.py stub       # baseline (do-nothing)
python3 eval/runner/evaluator.py v1         # after P6
python3 eval/runner/evaluator.py v2         # after P7
python3 eval/runner/evaluator.py v3         # after P8

# Open the latest HTML report
open -a "Google Chrome" eval/reports/latest.html
```

Each run produces:
- a JSON report at `eval/reports/<timestamp>_<bot>.json`
- an HTML report at `eval/reports/<timestamp>_<bot>.html`
- the symlink-ish file `eval/reports/latest.html` (just the latest HTML)

---

## Current status — v6 checkpoint reached (34/50 = 68%)

| Component | State |
|---|---|
| Project skeleton | ✅ |
| `README.md` + `DETERMINISM.md` + `WALKTHROUGH.md` | ✅ |
| Eval schema (v0 per-turn metrics) | ✅ legacy |
| **Ground-truth eval schema (`eval/schema/ground_truth.schema.json`)** | ✅ current |
| **50 conversation cases** | ✅ all written, validated, migrated to ground-truth schema |
| Evaluator harness (loader / metrics / stub_bot / evaluator / report) | ✅ legacy |
| **GT evaluator (`gt_evaluator.py`) — system-effect grading** | ✅ current |
| Baseline report (stub bot) | ✅ 0/50 |
| **P1 — six parsers** | ✅ all with golden tests |
| **P2 — composer + entity taxonomy** | ✅ produces per-activity JSON + taxonomy |
| **P3 — validator** | ✅ 0 determinism violations |
| P4 — labeller | ⬜ deferred (not blocking the chatbot) |
| **P5 — viewer** | ✅ static HTML browser |
| **P6 — chatbot v1 (intent + commit)** | ✅ 18/50 |
| **P7 — chatbot v2 (splices + recovery)** | ✅ 22/50 |
| **P8 — chatbot v3 (cross-journey + cross-module)** | ✅ 24/50 |
| **bot v4 (entry-screen + description scoring)** | ✅ 26/50 |
| **bot v5 (entity taxonomy + session memory + typed slots + free-text matcher)** | ✅ 32/50 |
| **bot v6 (best-match action picker + system-default leniency)** | ✅ **34/50** |

See `WALKTHROUGH.md` for the full architectural narrative, the six structural fixes that moved the numbers, and the playbook for extending to GR / PR / PQ / SIN modules.
| P8 — chatbot v3 | ⬜ |
