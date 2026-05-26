# ramco-journey-model

A deterministic, eval-first journey model for Ramco's Purchase Order module, with a chatbot built on top.

## Why this exists

Ramco's PO module exposes 14 user-facing journeys (Create Direct PO, Amend, Approve, View, Hold, Short-Close, etc.). A real user wants to talk to it in natural language — "create a PO for SUP001 for 10 widgets". To do that, we need a structured model of every journey: its canonical step spine, slots, splices, SP call chains, and cross-journey edges.

Earlier work tried to extract this model from training documents using LLM clustering. The result was noisy because documents are derivative. **This project extracts the same model directly from the screen artifacts**, where the structure is encoded deterministically.

## Determinism gradient

| Layer | What it does | LLM allowed? |
|-------|--------------|--------------|
| L0 — artifact mirror | symlink to source files, no transformation | No |
| L1 — parsers | one parser per artifact type, structured JSON output | **No** |
| L2 — composer | joins parser outputs into journey model | **No** |
| L3 — validator | coverage + gap diagnostics | **No** |
| L4 — labeller | paraphrase terse artifact labels into bot prose | bounded; strict I/O contract; cites source; never invents |
| L5 — runtime | chatbot conversation | hybrid; LLM for NL understanding & generation, never for structure |

If we're tempted to use an LLM in L1–L3, that's a signal the parser needs better rules — not a smarter model.

## Eval-first discipline

Before any code is written, the `eval/` directory holds 50 hand-curated multi-turn conversation cases that cover the 14 user-facing PO journeys plus cross-module questions. Every phase ships when its eval cases pass; nothing ships on vibes.

```
eval/cases/                # 50 ground-truth multi-turn conversations
  discovery/               # 5 cases — capability questions
  single_happy/            # 12 cases — one happy path per major journey
  single_splice/           # 10 cases — splice-triggered variants
  error_recovery/          # 8 cases — invalid input, retries, validation rejects
  cross_journey/           # 6 cases — multi-journey flows (Create → Amend etc.)
  lookup/                  # 5 cases — status / search queries
  cross_module/            # 4 cases — PO ↔ PR / GR / Quotation
```

Each case is a JSON document with the conversation, per-turn expected state (journey identified, slots extracted, splices triggered, terminal commit invoked), and the metrics it tests.

## Phases (eval-driven)

| Phase | Deliverable | Eval bar |
|-------|-------------|----------|
| P0 | Eval foundation: 50 cases, schema, runner, baseline 0% report | Harness runs and produces a report |
| P1 | Six parsers (manifest, state, form, behaviour, catalog, SP) | Per-parser unit tests pass |
| P2 | Composer: one JSON per activity | Round-trip — every TRANS in PO_info.xml appears in model |
| P3 | Validator: coverage report | ≥95% slots labelled, 100% TRANS captured |
| P4 | Labeller (bounded LLM) | Each rewrite cites source; never invents structure |
| P5 | Viewer (static HTML, no LLM) | Click activity → see spine + splices + slots |
| P6 | Chatbot v1 — naive bot | Discovery + simple happy-path eval cases pass |
| P7 | Chatbot v2 — splice navigation + error recovery | Splice + error eval cases pass |
| P8 | Chatbot v3 — cross-journey + cross-module | All 50 eval cases pass at agreed thresholds |

## Layout

```
ramco-journey-model/
├── README.md                    # this file
├── DETERMINISM.md               # the L0-L5 contract in detail
├── artifacts/                   # symlinks to source files
├── schemas/                     # JSON Schema for every model object
├── parsers/                     # L1
├── composer/                    # L2
├── validator/                   # L3
├── labeller/                    # L4 (bounded LLM)
├── viewer/                      # L5 static HTML
├── chatbot/                     # L5 runtime
│   ├── intent_classifier.py
│   ├── slot_filler.py
│   ├── splice_navigator.py
│   ├── state_machine.py
│   ├── llm_prompts/             # all prompts versioned in git
│   └── app.py
├── eval/                        # ground truth + evaluator
│   ├── schema/                  # case schema
│   ├── cases/                   # 50 conversations
│   ├── runner/                  # evaluator + metrics + report
│   ├── reports/                 # historical eval runs
│   └── fixtures/                # canned bot responses for harness self-test
├── observability/               # per-conversation trace logs
└── out/                         # generated model JSON (per-phase outputs)
```
