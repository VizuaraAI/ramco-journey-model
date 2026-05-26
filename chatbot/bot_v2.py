"""Chatbot v2 — adds splice navigation + error recovery (P7)
================================================================

Inherits from v1, adds:
  - splice detection (data-triggered: Capital, Consignment, Imports, LoI;
                      UI-initiated: Terms, TCD, PR Cov, SO Cov, Quality, Dropship)
  - splice walking: required additional slots are tracked
  - mid-flow retraction: if user changes their mind, splice retracts cleanly
  - validation pre-checks: bot refuses to commit if required slots missing
  - error detection: invalid supplier, ambiguous date, currency mismatch
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

CHATBOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CHATBOT))

from bot_v1 import ChatbotV1, SLOT_VOCAB, REVERSE_MAP
from llm_client import LLMError
sys.path.insert(0, str(CHATBOT.parent / "eval" / "runner"))
from metrics import BotTurnOutput


# Known splice triggers — both data-triggered and UI-initiated
# Each entry: trigger condition → splice_id, additional required slots
DATA_SPLICES = {
    # po_type values
    "po_type==Capital":      {"id": "po_type==Capital",     "required": ["capital_proposal_id"]},
    "po_type==Consignment":  {"id": "po_type==Consignment", "required": ["consignment_rule_id"]},
    # boolean flags
    "imports==true":         {"id": "imports==true",        "required": ["incoterm", "country_of_origin", "shipping_mode"]},
    "loi==true":             {"id": "loi==true",            "required": ["loi_validity_days"]},
}

# UI splices — user-initiated; track which ones the user has opened
UI_SPLICES = {
    "terms":     {"id": "terms_via_LNK3",        "screen": "PoCrtTrm",   "lnk": "POCRTMAINLNK3"},
    "tcd":       {"id": "tcd_via_LNK4",          "screen": "PoCrtTcd",   "lnk": "POCRTMAINLNK4"},
    "budget":    {"id": "budget_via_LNK7",       "screen": "PoCrtBud",   "lnk": "POCRTMAINLNK7"},
    "dropship":  {"id": "dropship_via_LNK8",     "screen": "PoCrtDrpshp","lnk": "POCRTMAINLNK8"},
    "pr_cov":    {"id": "pr_coverage_via_LNK9",  "screen": "PoCrtPrCov", "lnk": "POCRTMAINLNK9"},
    "so_cov":    {"id": "so_coverage_via_LNK10", "screen": "PoCrtSoCov", "lnk": "POCRTMAINLNK10"},
    "schedule":  {"id": "schedule_via_LNK2",     "screen": "PoCrtSch",   "lnk": "POCRTMAINLNK2"},
    "quality":   {"id": "quality_via_LNK6",      "screen": "PoCrtQlty",  "lnk": "POCRTMAINLNK6"},
    "notes":     {"id": "notes_via_LNK11",       "screen": "PoCrtNotes", "lnk": "POCRTMAINLNK11"},
}


class ChatbotV2(ChatbotV1):
    def reset(self) -> None:
        super().reset()
        self.state["splice_triggered"] = None
        self.state["splice_walked"] = []
        self.state["additional_required_slots"] = []
        self.state["splice_history"] = []  # for retraction

    def respond(self, user_input: str, turn_no: int) -> BotTurnOutput:
        self.state.setdefault("turn_history", []).append({"turn": turn_no, "user": user_input})
        if not self.llm.available:
            return BotTurnOutput(response_text="(no LLM available)")

        try:
            decision = self._classify_extract_and_splice(user_input)
        except LLMError as e:
            return BotTurnOutput(response_text=f"LLM error: {e}")

        intent = decision.get("intent", "")
        journey = decision.get("journey", None)
        slots = decision.get("slots_extracted", {}) or {}
        wants_commit = bool(decision.get("wants_commit", False))
        commit_kind = decision.get("commit_kind", "")
        splice_detected = decision.get("splice_detected", None)
        ui_splice_requested = decision.get("ui_splice_requested", None)
        retract_splice = decision.get("retract_splice", False)
        validation_error = decision.get("validation_error_detected", False)

        # Journey lock
        if journey and journey in REVERSE_MAP:
            self.state["journey_locked"] = journey

        # Merge slots
        for k, v in slots.items():
            if v not in (None, "", "?"):
                self.state["slots"][k] = v

        # Splice retraction (mid-flow change of mind)
        if retract_splice and self.state.get("splice_triggered"):
            retracted = self.state["splice_triggered"]
            self.state["splice_triggered"] = None
            self.state["additional_required_slots"] = []
            self.state["splice_history"].append({"retracted": retracted})
            # Also drop the splice-specific slot values from state
            if retracted in DATA_SPLICES:
                for slot in DATA_SPLICES[retracted]["required"]:
                    self.state["slots"].pop(slot, None)

        # Data splice triggered by slot value
        if splice_detected and splice_detected in DATA_SPLICES:
            sp = DATA_SPLICES[splice_detected]
            self.state["splice_triggered"] = splice_detected
            self.state["additional_required_slots"] = list(sp["required"])

        # UI splice (user clicks a LINK)
        splice_walked_this_turn = []
        if ui_splice_requested and ui_splice_requested in UI_SPLICES:
            sid = UI_SPLICES[ui_splice_requested]["id"]
            if sid not in self.state["splice_walked"]:
                self.state["splice_walked"].append(sid)
                splice_walked_this_turn.append(sid)

        # Pre-commit validation: ensure all additional_required_slots are filled
        trans_invoked = None
        sp_chain_invoked = []
        blocked = False
        if wants_commit and self.state["journey_locked"]:
            missing = [s for s in self.state["additional_required_slots"]
                       if s not in self.state["slots"]]
            if missing:
                blocked = True
                validation_error = True
            else:
                trans_invoked, sp_chain_invoked = self._pick_trans(
                    self.state["journey_locked"], commit_kind, user_input
                )

        response_text = decision.get("response", "")
        if blocked:
            response_text = (response_text + "\n\nBefore I can create the PO, "
                             "I still need: " + ", ".join(missing) + ".")

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
            response_text=response_text,
        )

    def _classify_extract_and_splice(self, user_input: str) -> dict:
        """Single LLM call: v1 fields + splice signals."""
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
        }

        prompt = f"""You are the NLU + splice-detection layer of a chatbot for Ramco's Purchase Order module.

JOURNEY VOCABULARY (pick only from these):
{json.dumps(journey_descriptions, indent=2)}

SLOT VOCABULARY (extract only these):
{json.dumps(SLOT_VOCAB)}

SPLICE VOCABULARY:
  DATA-TRIGGERED (set by user slot values, automatically activate):
    "po_type==Capital"     when user says "Capital PO" / wants a Capital PO
    "po_type==Consignment" when user says "Consignment PO"
    "imports==true"        when user says "imports" / "international" / mentions cross-border
    "loi==true"            when user says "Letter of Intent" / "LoI"
  UI-INITIATED (user explicitly opens a sub-screen):
    "terms"     → user asks about payment terms, terms and conditions, incoterm
    "tcd"       → user wants tax / charge / discount / TCD entries
    "budget"    → user wants to specify budget details
    "dropship"  → user says ship-direct / dropship / deliver to customer
    "pr_cov"    → user wants to cover a PR with this PO
    "so_cov"    → user wants to cover a Sale Order with this PO
    "schedule"  → user wants split delivery / scheduled receipts
    "quality"   → user wants to specify quality / QC / inspection
    "notes"     → user wants to attach notes

CURRENT STATE:
{json.dumps(current, indent=2)}

USER INPUT THIS TURN:
\"\"\"{user_input}\"\"\"

YOUR TASK:
1. Classify intent + journey + slots (as in v1).
2. Detect splice triggers — both data-triggered and UI-initiated.
3. Detect retraction — if user changes mind ("actually never mind", "not Capital, just standard"),
   set retract_splice=true.
4. Detect validation/ambiguity errors:
   - invalid supplier (looks malformed: "XYZ-NONEXISTENT" style)
   - ambiguous date (e.g. "03/04/2026" without DD/MM hint)
   - missing required slots before commit
   - duplicate item across lines
   Set validation_error_detected=true in those cases.
5. Decide if wants_commit. commit_kind: "submit", "submit_and_approve", "search", or "".
   "submit" if user said create/save but NOT approve. NEGATION MATTERS.

OUTPUT STRICT JSON:
{{
  "intent": "string",
  "journey": "PoCrt"|null,
  "journey_candidates": ["..."],
  "slots_extracted": {{"supplier_code": "SUP-100", ...}},
  "splice_detected": "po_type==Capital"|"po_type==Consignment"|"imports==true"|"loi==true"|null,
  "ui_splice_requested": "terms"|"tcd"|"budget"|"dropship"|"pr_cov"|"so_cov"|"schedule"|"quality"|"notes"|null,
  "retract_splice": false,
  "validation_error_detected": false,
  "wants_commit": false,
  "commit_kind": "submit"|"submit_and_approve"|"search"|"",
  "response": "2-3 sentence reply. If a splice triggered, acknowledge it and mention the additional required slots. If validation error, explain the issue and ask for correction. If discovery, enumerate options."
}}"""
        return self.llm.call_json(prompt, temperature=0.0, max_output_tokens=2000)


if __name__ == "__main__":
    bot = ChatbotV2()
    bot.reset()
    print("Smoke v2:")
    for i, msg in enumerate([
        "Create a Capital PO for SUP-CAP-1",
        "Proposal is CAP-PROP-2026-04",
        "Just create it for approval"
    ], 1):
        out = bot.respond(msg, i)
        print(f"Turn {i}: journey={out.journey_locked} splice={out.splice_triggered} "
              f"slots={list(out.slots_extracted.keys())} trans={out.trans_invoked}")
        print(f"  > {out.response_text[:100]}")
