# Determinism contract

This document is binding. Anything that violates it is a bug.

## Layer L0 — artifact mirror

**Allowed:** symlinks or read-only refs to source artifacts.
**Forbidden:** any transformation, copy, or derived file at L0.

L0 is a stable reference plane. The artifacts under `artifacts/ramco/` are not edited or processed in place; downstream code reads from them.

## Layer L1 — parsers

One parser per artifact type. Each parser produces structured JSON that conforms to a schema in `schemas/`.

**Allowed:** standard library parsing (xml.etree, html.parser, csv, re), structured AST walkers, validated output.

**Forbidden:**
- LLM calls of any kind
- Fuzzy matching for structure decisions (no Levenshtein, no semantic similarity)
- Heuristics that "usually work"
- Skipping data that doesn't parse — instead, fail loudly and surface the case

If a parser cannot extract a piece of structured data, it must:
1. Log the failure with file path and location
2. Emit a structured `parse_error` record in the output
3. Not silently default or guess

## Layer L2 — composer

Joins L1 outputs into the journey model. Pure functions over structured data.

**Allowed:** dictionary lookups, set operations, joins on canonical ids.
**Forbidden:** LLM, fuzzy matching, any inference beyond explicit joins.

If a composition step has ambiguity (e.g., two LINK tasks both could map to the same sub-screen), it must:
1. Emit both candidates with a `disambiguation_needed` flag
2. Not pick one

## Layer L3 — validator

Reports coverage and gaps. Read-only over L2 outputs.

**Allowed:** counting, set diff, threshold checks.
**Forbidden:** modifying the model, calling LLMs.

## Layer L4 — labeller

Bounded LLM use. Only allowed function: rewrite a terse artifact-derived label into a more natural human-facing label.

**Strict contract:**
- Input: `{ "artifact_source": "...", "raw_label": "POMAIN29SAVE1TR · Save", "context": "..." }`
- Output: `{ "rewritten_label": "Save the changes", "cites": ["raw_label"], "model": "...", "prompt_version": "..." }`

**Forbidden in L4:**
- Inventing structure (no new tasks, slots, splices)
- Changing semantics (the rewrite must preserve meaning)
- Cross-citing different artifacts (the rewrite uses only `raw_label`)
- Any structural decision

Every L4 output is auditable: source label, prompt version, model version, output. If audit fails, the rewrite is discarded.

## Layer L5 — chatbot runtime

LLM is allowed for natural language understanding and generation. But the LLM never modifies the journey model, never invents tasks/slots/splices, and never bypasses validation.

**Allowed:**
- LLM for intent classification (with confidence scores)
- LLM for slot extraction from user utterances (against the known slot vocabulary)
- LLM for response generation (constrained to known journey state)

**Forbidden:**
- LLM choosing what slots exist (must be from the model)
- LLM inventing splice triggers
- LLM committing actions (commits go through the parsed SP chain only)

Every chatbot decision is logged with: input, candidate options from the model, LLM confidence, chosen option, output. Every conversation produces a trace in `observability/traces/`.

## What happens if this is violated

Code that calls an LLM at L1–L3, or that does fuzzy matching for structure, fails the determinism lint check (planned: `validator/lint_determinism.py`). The lint check runs as part of every test cycle. Violations block merge.
