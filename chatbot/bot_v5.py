"""Chatbot v5 — generic, module-agnostic structural fixes on top of v4
========================================================================

Four fixes, all module-agnostic:

Fix 1 — Generic session memory for cross-journey context carry.
  When a journey produces an entity (Create PO → po_number), the bot
  mints a synthetic ID and records it in session memory. When a later
  journey CONSUMES the same kind of entity (Amend PO needs po_number),
  the bot auto-fills the consumed-id slot from session memory. Works
  for any module — driven by entity_taxonomy.json.

Fix 2 — Typed slot vocabulary.
  Replaces the flat SLOT_VOCAB list with a typed dict ({type, format,
  examples}) so the LLM produces correctly-shaped values for structured
  slots like loi_validity_days (int), tcd_details (list[object]),
  quality_attributes (object), incoterm (3-letter code).

Fix 3 — Conservative commit interpretation.
  When the user says "create for approval" the bot used to pick TRN4
  (combined create+approve). That's an over-commit. Default to the
  SAFER interpretation (just submit; approval is a separate step)
  unless user explicitly says "AND approve" / "in one shot".

Fix 4 — Free-text reason slot matching (in the GT evaluator, not bot).
  Slots ending in _reason, _note, _description, _comment, _remarks
  are free-text. Match by content overlap, not exact value.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

CHATBOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CHATBOT))

from bot_v4 import ChatbotV4, ENTRY_FLOW, REQUIRED_SLOTS
from bot_v1 import REVERSE_MAP
from session_memory import SessionMemory, taxonomy_for
sys.path.insert(0, str(CHATBOT.parent / "eval" / "runner"))
from metrics import BotTurnOutput


# Typed slot vocabulary — used to instruct the LLM on the expected shape
# of each slot's value. Categorised by ALL modules' canonical slots.
TYPED_SLOTS: dict[str, dict] = {
    # Identifiers (strings)
    "po_number":          {"type": "string", "format": "PO-YYYY-NNNN"},
    "pr_number":          {"type": "string", "format": "PR-YYYY-NNNN"},
    "gr_number":          {"type": "string", "format": "GR-YYYY-NNNN"},
    "supplier_code":      {"type": "string", "format": "alphanumeric"},
    "buyer":              {"type": "string"},
    "item_code":          {"type": "string"},
    "warehouse_code":     {"type": "string"},
    "ship_from_id":       {"type": "string"},
    "customer_code":      {"type": "string"},
    "dropship_id":        {"type": "string"},
    "budget_id":          {"type": "string"},
    "proposal_id":        {"type": "string"},
    "capital_proposal_id":{"type": "string"},
    "consignment_rule_id":{"type": "string"},
    "quotation_no":       {"type": "string"},
    "sale_order_no":      {"type": "string"},
    "tender_no":          {"type": "string"},
    "source_po_no":       {"type": "string"},
    "numbering_series":   {"type": "string"},
    # Enums
    "po_type":            {"type": "enum", "values": ["Standard", "Capital", "Consignment"]},
    "currency":           {"type": "string", "format": "ISO 4217 code (USD, EUR, INR, ...)"},
    "incoterm":           {"type": "enum_string",
                           "format": "3-letter code ONLY (FOB, CIF, DDP, EXW, DAP, DDU, FCA, CPT, CIP)",
                           "values": ["FOB","CIF","DDP","EXW","DAP","DDU","FCA","CPT","CIP","FAS","CFR"]},
    "country_of_origin":  {"type": "string", "format": "2-letter ISO country code (DE, US, IN, CN, ...)"},
    "shipping_mode":      {"type": "enum", "values": ["air", "sea", "road", "rail"]},
    "schedule_type":      {"type": "enum", "values": ["SI", "SR", "FX"]},
    "uom":                {"type": "string", "format": "unit of measure code"},
    # Numbers
    "quantity":           {"type": "number"},
    "cost":               {"type": "number", "format": "unit price as a number"},
    "ordered_qty":        {"type": "number"},
    "received_qty":       {"type": "number"},
    "short_close_qty":    {"type": "number"},
    "exchange_rate":      {"type": "number"},
    "line_no":            {"type": "integer"},
    "loi_validity_days":  {"type": "integer", "format": "duration in days (extract the number)"},
    # Booleans
    "imports_flag":       {"type": "boolean"},
    "loi_flag":           {"type": "boolean"},
    "hold_flag":          {"type": "boolean"},
    # Dates
    "po_date":            {"type": "date", "format": "YYYY-MM-DD"},
    "need_date":          {"type": "date", "format": "YYYY-MM-DD"},
    "approval_date":      {"type": "date", "format": "YYYY-MM-DD"},
    "date_from":          {"type": "date", "format": "YYYY-MM-DD"},
    "date_to":            {"type": "date", "format": "YYYY-MM-DD"},
    # Structured composites
    "tcd_details":        {"type": "list[object]",
                           "format": "list of {type:'charge'|'discount'|'tax', name:str, value:number, basis:'fixed'|'percent'} objects"},
    "quality_attributes": {"type": "object",
                           "format": "{sample_pct:number, aql:number, test_methods:string}"},
    "schedule":           {"type": "list[object]",
                           "format": "list of {qty:number, need_date:'YYYY-MM-DD'} objects"},
    "pr_coverage":        {"type": "string", "format": "PR number being covered"},
    "so_coverage":        {"type": "string", "format": "SO number being covered"},
    "pr_coverage_ref":    {"type": "string"},
    "so_coverage_ref":    {"type": "string"},
    # Free-text
    "payment_terms":      {"type": "string", "format": "payment terms description"},
    "remarks":            {"type": "string"},
    "notes_text":         {"type": "string"},
    "hold_reason":        {"type": "free_text", "format": "short reason phrase"},
    "return_reason":      {"type": "free_text", "format": "short reason phrase"},
    "short_close_reason": {"type": "free_text", "format": "short reason phrase"},
    "ac_usage":           {"type": "string"},
    "cc_usage":           {"type": "string"},
    "status_filter":      {"type": "string"},
    "approval_choice":    {"type": "string"},
    "folder":             {"type": "string"},
}


def _typed_vocab_for_prompt() -> str:
    """Compact rendering of TYPED_SLOTS for the LLM prompt."""
    lines = []
    for k, meta in TYPED_SLOTS.items():
        t = meta.get("type", "string")
        fmt = meta.get("format", "")
        if "values" in meta:
            vals = ", ".join(meta["values"][:8])
            line = f"  {k:24s} {t}  values=[{vals}]"
        elif fmt:
            line = f"  {k:24s} {t}  ({fmt})"
        else:
            line = f"  {k:24s} {t}"
        lines.append(line)
    return "\n".join(lines)


class ChatbotV5(ChatbotV4):
    def reset(self) -> None:
        super().reset()
        self.session = SessionMemory()

    def respond(self, user_input: str, turn_no: int) -> BotTurnOutput:
        # FIX 1 PHASE A — Auto-fill consumed-entity slots BEFORE the LLM
        # sees the input, so journey routing + slot extraction work on a
        # state that already knows about previously-produced entities.
        if self.state.get("journey_locked"):
            upper_act = REVERSE_MAP.get(self.state["journey_locked"])
            if upper_act:
                auto_filled = self.session.auto_fill_consumed_slot(
                    upper_act, self.state.get("slots", {})
                )
                for k, v in auto_filled.items():
                    self.state["slots"][k] = v

        # Delegate to v4 (which delegates to v3) for journey/slot/splice/commit
        out = super().respond(user_input, turn_no)

        # FIX 1 PHASE B — If journey switched THIS turn, retry auto-fill so
        # the NEW journey's consumed-id is populated for the next turn or for
        # downstream evaluation.
        if self.state.get("journey_locked"):
            upper_act = REVERSE_MAP.get(self.state["journey_locked"])
            if upper_act:
                auto_filled = self.session.auto_fill_consumed_slot(
                    upper_act, self.state.get("slots", {})
                )
                for k, v in auto_filled.items():
                    if k not in self.state["slots"]:
                        self.state["slots"][k] = v

        # FIX 1 PHASE C — After any commit fires this turn, record entity production
        v4_seq = getattr(out, "trans_sequence_v4", None) or []
        for action in v4_seq:
            task = action.get("task", "")
            activity_camel = action.get("activity")
            if not activity_camel: continue
            upper = REVERSE_MAP.get(activity_camel)
            if not upper: continue
            # Only record on WRITE commits, not READS (entry-search)
            if action.get("kind") != "write": continue
            entity = self.session.record_production(upper, turn_no)
            if entity:
                # Make the new entity ID visible to subsequent turns
                self.state["slots"][entity["id_slot"]] = entity["synthetic_id"]

        # Also if v4 used single trans_invoked (no sequence), check that
        if not v4_seq and out.trans_invoked:
            # heuristic: if it has a tables footprint, it's a write
            activity_camel = self.state.get("journey_locked")
            upper = REVERSE_MAP.get(activity_camel) if activity_camel else None
            if upper:
                entity = self.session.record_production(upper, turn_no)
                if entity:
                    self.state["slots"][entity["id_slot"]] = entity["synthetic_id"]

        return out

    # FIX 2 — Override the v3 prompt to use the typed slot vocabulary
    def _classify_v3(self, user_input: str) -> dict:
        # Reach into v3's logic via the LLM directly with an UPGRADED prompt.
        # We compose the same prompt v3 would build but with TYPED_SLOTS in
        # place of the flat list, plus FIX 3's conservative-commit rule.
        current_state = {
            "journey_locked": self.state.get("journey_locked"),
            "slots_already_collected": list(self.state.get("slots", {}).keys()),
            "splice_triggered_so_far": self.state.get("splice_triggered"),
            "additional_required_slots": self.state.get("additional_required_slots", []),
            "splices_already_walked": self.state.get("splice_walked", []),
        }
        journey_descriptions = {
            "PoCrt":        "Create a Direct Purchase Order (from scratch).",
            "PoCrtQtn":     "Create PO From Quotation.",
            "PoCrtSo":      "Create PO From Sale Order (dropship).",
            "PoCrtTen":     "Create PO From Tender.",
            "PoCopy":       "Copy and Create PO from an existing PO.",
            "PoAmnd":       "Amend an existing PO.",
            "PoApp":        "Approve / Authorise a PO.",
            "PoEdt":        "Edit a draft PO.",
            "PoViw":        "View / search POs.",
            "PoMtn":        "Maintain supply order configuration.",
            "PoHold":       "Change PO status (Hold/Unhold).",
            "PoScl":        "Short-close a PO line or whole PO.",
            "PoAcCcUsgMod": "AC/CC Usage Modification.",
            "PoHlp":        "Field help.",
        }
        prompt = f"""You are the NLU + splice + cross-journey layer of a Ramco PO chatbot.

JOURNEYS (pick only from these):
{json.dumps(journey_descriptions, indent=2)}

TYPED SLOTS (extract values that match the declared type/format):
{_typed_vocab_for_prompt()}

SPLICES (UI-initiated, set ui_splice_requested):
  terms tcd budget dropship pr_cov so_cov schedule quality notes

SPLICES (data-triggered by po_type / boolean flags):
  "po_type==Capital"  "po_type==Consignment"  "imports==true"  "loi==true"

CURRENT STATE:
{json.dumps(current_state, indent=2)}

USER INPUT THIS TURN:
\"\"\"{user_input}\"\"\"

EXTRACTION GUIDANCE (CRITICAL):
  - Always return values in the DECLARED type. If a slot is `integer`, give a
    number (not "60 days"). If `enum_string` with values, use ONE of the values
    only (e.g. incoterm "FOB" not "FOB Hamburg"). If `list[object]`, return an
    actual JSON list, not a sentence.
  - For `loi_validity_days`: if user says "valid 60 days", extract 60.
  - For `incoterm`: just the 3-letter code.
  - For `tcd_details`: parse "$200 freight charge" → {{"type":"charge","name":"freight","value":200,"basis":"fixed"}}.
  - For `quality_attributes`: parse "sample 5%, AQL 0.65, X test" →
    {{"sample_pct":5, "aql":0.65, "test_methods":"X test"}}.
  - For `schedule`: parse "50 next week, 30 next month" →
    [{{"qty":50,"need_date":"<next week>"}}, {{"qty":30,"need_date":"<next month>"}}].
  - Reason / note slots are free text — copy the user's words concisely.

COMMIT GUIDANCE (CRITICAL):
  - wants_commit=true ONLY if user explicitly says create/save/approve/submit/do it.
  - commit_kind is "submit_and_approve" ONLY if user explicitly mentions BOTH the
    create/save AND the approve in the SAME utterance. Phrases like "create for
    approval", "send for approval", "submit it for approval" mean "submit so that
    SOMEONE ELSE can approve later" — that's commit_kind="submit", not
    "submit_and_approve". Default to "submit" when in doubt.

JOURNEY-SWITCH GUIDANCE:
  - If user references a freshly-created entity ("it", "that PO", "the one I just
    made") and asks for a new action, set journey to the new action's journey.
    The bot's session memory will carry the entity ID forward.

OUTPUT STRICT JSON:
{{
  "intent": "string",
  "journey": "PoCrt"|"PoApp"|...|null,
  "journey_candidates": ["..."],
  "slots_extracted": {{ "supplier_code": "SUP-100", ... }},
  "splice_detected": "po_type==Capital"|...|null,
  "ui_splice_requested": "terms"|...|null,
  "retract_splice": false,
  "validation_error_detected": false,
  "wants_commit": false,
  "commit_kind": "submit"|"submit_and_approve"|"search"|"",
  "response": "2-3 sentence reply."
}}"""
        result = self.llm.call_json(prompt, temperature=0.0, max_output_tokens=4000)

        # Normalize structured slot values (incoterm short, bool flags, etc.)
        slots = result.get("slots_extracted", {}) or {}
        for k, v in list(slots.items()):
            if v is None: continue
            meta = TYPED_SLOTS.get(k, {})
            t = meta.get("type", "")
            if t == "enum_string" and isinstance(v, str):
                # Take just the first uppercase token
                parts = v.strip().split()
                if parts:
                    candidate = parts[0].upper()
                    values = meta.get("values", [])
                    if not values or candidate in values:
                        slots[k] = candidate
            elif t == "boolean" and isinstance(v, str):
                slots[k] = v.strip().lower() in ("true", "yes", "1")
            elif t in ("number", "integer") and isinstance(v, str):
                try:
                    slots[k] = int(v) if t == "integer" else float(v)
                except ValueError:
                    pass
        result["slots_extracted"] = slots
        return result


if __name__ == "__main__":
    bot = ChatbotV5()
    bot.reset()
    print("v5 smoke (multi-commit context carry):")
    msgs = [
        "Quick PO for SUP-100, USD, today, BUY-1, ITM-50 10 at 30. Just save it.",
        "Now approve the one I just created.",
    ]
    for i, m in enumerate(msgs, 1):
        out = bot.respond(m, i)
        seq = getattr(out, "trans_sequence_v4", [])
        seq_names = [s["task"] for s in seq] if seq else ([out.trans_invoked] if out.trans_invoked else [])
        print(f"T{i}: journey={out.journey_locked} fired={seq_names} po_number_in_state={bot.state['slots'].get('po_number')}")
