"""Chatbot v3 — adds cross-journey context carry + cross-module reads (P8)
============================================================================

Inherits from v2, adds:
  - cross-journey context carry: po_number persists across PoCrt→PoApp→PoAmnd
  - journey switching detection: "now approve it" → switch to PoApp, carry PO no
  - cross-module reads: "show me the GR for PO123" → query GR module
  - filtered list queries: "POs pending my approval", "POs older than 90 days"
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

CHATBOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CHATBOT))

from bot_v2 import ChatbotV2, SLOT_VOCAB, REVERSE_MAP
from llm_client import LLMError
sys.path.insert(0, str(CHATBOT.parent / "eval" / "runner"))
from metrics import BotTurnOutput


class ChatbotV3(ChatbotV2):
    def reset(self) -> None:
        super().reset()
        # Context that persists across journey switches
        self.state["cross_journey_context"] = {}
        self.state["last_committed_po"] = None
        self.state["filter_params"] = {}

    def respond(self, user_input: str, turn_no: int) -> BotTurnOutput:
        self.state.setdefault("turn_history", []).append({"turn": turn_no, "user": user_input})
        if not self.llm.available:
            return BotTurnOutput(response_text="(no LLM available)")

        try:
            decision = self._classify_v3(user_input)
        except LLMError as e:
            return BotTurnOutput(response_text=f"LLM error: {e}")

        intent = decision.get("intent", "")
        journey = decision.get("journey")
        slots = decision.get("slots_extracted", {}) or {}
        wants_commit = bool(decision.get("wants_commit", False))
        commit_kind = decision.get("commit_kind", "")
        splice_detected = decision.get("splice_detected")
        ui_splice_requested = decision.get("ui_splice_requested")
        retract_splice = decision.get("retract_splice", False)
        validation_error = decision.get("validation_error_detected", False)
        cross_module_query = decision.get("cross_module_query")
        is_journey_switch = decision.get("journey_switch", False)

        # Journey switching with context carry
        prior_journey = self.state.get("journey_locked")
        if journey and journey in REVERSE_MAP:
            if prior_journey and prior_journey != journey:
                # SWITCH — carry context forward
                self._carry_context(prior_journey, journey)
            self.state["journey_locked"] = journey

        # Merge slots; also write into cross_journey_context for portable slots
        for k, v in slots.items():
            if v not in (None, "", "?"):
                self.state["slots"][k] = v
                if k in {"po_number", "pr_number", "sale_order_no", "tender_no",
                         "quotation_no", "supplier_code"}:
                    self.state["cross_journey_context"][k] = v

        # If bot has a committed PO from a prior journey and the new turn references "it"
        # implicitly, hydrate po_number from cross_journey_context
        if (self.state.get("last_committed_po")
            and "po_number" not in self.state["slots"]
            and any(w in user_input.lower()
                    for w in ["it", "that", "this", "just created", "the one"])):
            self.state["slots"]["po_number"] = self.state["last_committed_po"]

        # Splice retraction
        if retract_splice and self.state.get("splice_triggered"):
            from bot_v2 import DATA_SPLICES
            ret = self.state["splice_triggered"]
            self.state["splice_triggered"] = None
            self.state["additional_required_slots"] = []
            if ret in DATA_SPLICES:
                for slot in DATA_SPLICES[ret]["required"]:
                    self.state["slots"].pop(slot, None)

        # Data splice activation
        if splice_detected:
            from bot_v2 import DATA_SPLICES
            if splice_detected in DATA_SPLICES:
                self.state["splice_triggered"] = splice_detected
                self.state["additional_required_slots"] = list(DATA_SPLICES[splice_detected]["required"])

        # UI splice tracking
        if ui_splice_requested:
            from bot_v2 import UI_SPLICES
            if ui_splice_requested in UI_SPLICES:
                sid = UI_SPLICES[ui_splice_requested]["id"]
                if sid not in self.state["splice_walked"]:
                    self.state["splice_walked"].append(sid)

        # Commit + validation
        trans_invoked = None
        sp_chain_invoked = []
        if wants_commit and self.state["journey_locked"]:
            missing = [s for s in self.state["additional_required_slots"]
                       if s not in self.state["slots"]]
            if missing:
                validation_error = True
            else:
                trans_invoked, sp_chain_invoked = self._pick_trans(
                    self.state["journey_locked"], commit_kind, user_input
                )
                # Record committed PO for cross-journey reference next turn
                if trans_invoked and any(t in trans_invoked.upper()
                                         for t in ["SBT", "TRN4", "TRN5"]):
                    # Synthesise / remember a PO number for context-carry
                    self.state["last_committed_po"] = self.state["slots"].get(
                        "po_number", f"PO-{self.state.get('journey_locked','x')}-NEW"
                    )

        return BotTurnOutput(
            intent=intent,
            journey_locked=self.state["journey_locked"],
            journey_candidates=decision.get("journey_candidates", []),
            slots_extracted=slots,
            splice_triggered=self.state.get("splice_triggered"),
            splice_walked=self.state.get("splice_walked", []),
            additional_required_slots=self.state.get("additional_required_slots", []),
            trans_invoked=trans_invoked,
            sp_chain_invoked=sp_chain_invoked,
            validation_error_detected=validation_error,
            context_carried=dict(self.state.get("cross_journey_context", {})),
            cross_module_query=cross_module_query,
            response_text=decision.get("response", ""),
        )

    def _carry_context(self, from_journey: str, to_journey: str) -> None:
        """When switching journeys, carry portable identifiers forward."""
        carry_keys = ["po_number", "pr_number", "sale_order_no", "supplier_code",
                      "line_no", "quotation_no"]
        for k in carry_keys:
            if k in self.state["slots"]:
                self.state["cross_journey_context"][k] = self.state["slots"][k]
        # Also carry the last_committed_po if no explicit po_number
        if "po_number" not in self.state["slots"] and self.state.get("last_committed_po"):
            self.state["slots"]["po_number"] = self.state["last_committed_po"]
            self.state["cross_journey_context"]["po_number"] = self.state["last_committed_po"]

    def _classify_v3(self, user_input: str) -> dict:
        journey_descriptions = {
            "PoCrt":        "Create a Direct Purchase Order (from scratch).",
            "PoCrtQtn":     "Create PO From Quotation.",
            "PoCrtSo":      "Create PO From Sale Order (dropship pattern).",
            "PoCrtTen":     "Create PO From Tender.",
            "PoCopy":       "Copy and Create PO from an existing PO.",
            "PoAmnd":       "Amend an existing PO.",
            "PoApp":        "Approve / Authorise a PO.",
            "PoEdt":        "Edit a draft PO.",
            "PoViw":        "View / search POs.",
            "PoMtn":        "Maintain supply order configuration.",
            "PoHold":       "Change PO status (Hold/Unhold).",
            "PoScl":        "Short-close a PO line or whole PO.",
            "PoAcCcUsgMod": "AC/CC Usage Modification on existing PO.",
            "PoHlp":        "Field-level help on PO.",
        }
        current = {
            "journey_locked": self.state.get("journey_locked"),
            "slots_already_collected": self.state.get("slots", {}),
            "splice_triggered_so_far": self.state.get("splice_triggered"),
            "additional_required_slots": self.state.get("additional_required_slots", []),
            "splices_already_walked": self.state.get("splice_walked", []),
            "cross_journey_context": self.state.get("cross_journey_context", {}),
            "last_committed_po": self.state.get("last_committed_po"),
        }

        prompt = f"""You are the NLU layer of a Ramco PO chatbot with cross-journey and cross-module awareness.

JOURNEY VOCABULARY:
{json.dumps(journey_descriptions, indent=2)}

SLOT VOCABULARY:
{json.dumps(SLOT_VOCAB)}

SPLICE VOCABULARY:
  DATA-TRIGGERED: po_type==Capital, po_type==Consignment, imports==true, loi==true
  UI-INITIATED: terms, tcd, budget, dropship, pr_cov, so_cov, schedule, quality, notes

CROSS-MODULE QUERY:
  Set cross_module_query (free-form description) when user references another module:
  - GR for po_number=X     (Goods Receipt module)
  - PR for pr_number=X     (Purchase Request module)
  - Quotation for X        (Purchase Quotation module)
  - SO for sale_order_no=X (Sale Order)

CURRENT STATE (includes cross-journey context from prior turns):
{json.dumps(current, indent=2)}

USER INPUT THIS TURN:
\"\"\"{user_input}\"\"\"

YOUR TASK:
1. All v2 tasks (intent, journey, slots, splices, validation).
2. Detect journey SWITCH: user references a PO they made earlier ("approve it",
   "amend that one", "put it on hold") — set journey_switch=true and use the
   po_number from cross_journey_context / last_committed_po if user didn't repeat it.
3. Cross-module query detection — set cross_module_query when user asks about
   GR, PR, Quotation, SO, etc. tied to a PO.
4. Filtered lookups (PoViw): "pending my approval", "older than 90 days",
   "for supplier X", "by buyer Y", "in Q1 2026" — translate dates to ISO,
   put filter into slots (date_from, date_to, status_filter, supplier_code, etc.)

OUTPUT STRICT JSON:
{{
  "intent": "string",
  "journey": "PoCrt"|null,
  "journey_candidates": ["..."],
  "journey_switch": false,
  "slots_extracted": {{...}},
  "splice_detected": null,
  "ui_splice_requested": null,
  "retract_splice": false,
  "validation_error_detected": false,
  "cross_module_query": null,
  "wants_commit": false,
  "commit_kind": "submit"|"submit_and_approve"|"search"|"",
  "response": "Natural 2-3 sentence reply. For journey switches, acknowledge the carry-over of context. For cross-module queries, name the other module explicitly. For filtered queries, summarise the filter."
}}"""
        return self.llm.call_json(prompt, temperature=0.0, max_output_tokens=2000)


if __name__ == "__main__":
    bot = ChatbotV3()
    bot.reset()
    print("Smoke v3 (cross-journey):")
    for i, msg in enumerate([
        "Create a quick PO for SUP-100, USD, today, BUY-1, ITM-50 10 at 30. Just save.",
        "Now approve the one I just created."
    ], 1):
        out = bot.respond(msg, i)
        print(f"Turn {i}: journey={out.journey_locked} trans={out.trans_invoked} "
              f"ctx={out.context_carried} slots={list(out.slots_extracted.keys())}")
        print(f"  > {out.response_text[:120]}")
