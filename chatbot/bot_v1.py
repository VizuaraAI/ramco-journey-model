"""Chatbot v1 — naive runtime
================================

The first runnable bot. Implements:
  - intent classification: discovery vs. specific journey vs. lookup
  - journey identification: pick from the 14 user-facing journeys
  - slot extraction from natural language
  - commit invocation: fire the right TRANS task

DOES NOT YET HANDLE (P7/P8):
  - splice detection / walking
  - error recovery / retry
  - cross-journey context carry
  - cross-module reads

LLM is allowed here (Gemini 2.5 Pro), but constrained to:
  - pick from a known journey vocabulary (14 journeys)
  - extract slots against a known slot vocabulary
  - never invent task names, slot names, or SP names
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from typing import Any

CHATBOT = Path(__file__).resolve().parent
PROJECT = CHATBOT.parent
sys.path.insert(0, str(CHATBOT))
sys.path.insert(0, str(PROJECT / "eval" / "runner"))

from llm_client import LLMClient, LLMError
from metrics import BotTurnOutput


MODEL_DIR = PROJECT / "out" / "model" / "activities"

# Map activity_name (manifest UPPERCASE) to friendly name used in eval cases (CamelCase)
ACTIVITY_NAME_MAP = {
    "POCRT": "PoCrt", "POCRTQTN": "PoCrtQtn", "POCRTSO": "PoCrtSo",
    "POCRTTEN": "PoCrtTen", "POCOPY": "PoCopy", "POAMND": "PoAmnd",
    "POAPP": "PoApp", "POEDT": "PoEdt", "POVIW": "PoViw",
    "POMTN": "PoMtn", "POHOLD": "PoHold", "POSCL": "PoScl",
    "POACCCUSGMOD": "PoAcCcUsgMod", "POHLP": "PoHlp",
}
# Reverse lookup
REVERSE_MAP = {v: k for k, v in ACTIVITY_NAME_MAP.items()}

# Canonical slot vocabulary (the things a bot might extract from NL)
SLOT_VOCAB = [
    "po_type", "supplier_code", "currency", "exchange_rate",
    "numbering_series", "po_no_manual", "po_date", "buyer",
    "folder", "imports_flag", "hold_flag", "loi_flag", "ship_from_id",
    "remarks", "item_code", "quantity", "uom", "cost", "per",
    "need_date", "schedule_type", "receipt_at", "warehouse_code",
    "ac_usage", "cc_usage", "proposal_id", "customer_code", "dropship_id",
    "budget_id", "payment_terms", "tcd_details", "quality_attributes",
    "pr_coverage", "so_coverage", "notes_text", "approval_choice",
    "approval_date", "po_number", "pr_number", "sale_order_no",
    "tender_no", "quotation_no", "source_po_no", "line_no",
    "hold_reason", "return_reason", "short_close_qty", "short_close_reason",
    "consignment_rule_id", "capital_proposal_id", "incoterm",
    "country_of_origin", "shipping_mode", "ordered_qty", "received_qty",
    "date_from", "date_to", "status_filter",
]


def load_models() -> dict:
    models = {}
    for p in sorted(MODEL_DIR.glob("*.json")):
        models[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return models


class ChatbotV1:
    def __init__(self):
        self.models = load_models()
        self.llm = LLMClient()
        self.state: dict[str, Any] = {}

    def reset(self) -> None:
        self.state = {
            "journey_locked": None,
            "slots": {},
            "turn_history": [],
        }

    def respond(self, user_input: str, turn_no: int) -> BotTurnOutput:
        """Process one user turn, return a structured BotTurnOutput."""
        self.state.setdefault("turn_history", []).append({"turn": turn_no, "user": user_input})

        if not self.llm.available:
            # Without an LLM we can only do trivial heuristics
            return self._fallback(user_input)

        try:
            decision = self._classify_and_extract(user_input)
        except LLMError as e:
            return BotTurnOutput(response_text=f"LLM error: {e}")

        # Apply the decision to state
        intent = decision.get("intent", "")
        journey = decision.get("journey", None)
        slots = decision.get("slots_extracted", {}) or {}
        wants_commit = bool(decision.get("wants_commit", False))
        commit_kind = decision.get("commit_kind", "")  # "submit" or "submit_and_approve" or "search" etc.

        # Lock journey if confidently identified
        if journey and journey in REVERSE_MAP:
            if self.state["journey_locked"] != journey:
                self.state["journey_locked"] = journey

        # Merge slots
        for k, v in slots.items():
            if v not in (None, "", "?"):
                self.state["slots"][k] = v

        # Determine which TRANS to invoke if user wants to commit
        trans_invoked = None
        sp_chain_invoked = []
        if wants_commit and self.state["journey_locked"]:
            trans_invoked, sp_chain_invoked = self._pick_trans(
                self.state["journey_locked"], commit_kind, user_input
            )

        response_text = decision.get("response", "")

        return BotTurnOutput(
            intent=intent,
            journey_locked=self.state["journey_locked"],
            journey_candidates=decision.get("journey_candidates", []),
            slots_extracted=slots,
            trans_invoked=trans_invoked,
            sp_chain_invoked=sp_chain_invoked,
            response_text=response_text,
        )

    def _fallback(self, user_input: str) -> BotTurnOutput:
        return BotTurnOutput(response_text="(no LLM available)")

    def _pick_trans(self, journey: str, commit_kind: str,
                    user_input: str) -> tuple[str | None, list[str]]:
        """Look up the right TRANS task by SCORING THE TASK DESCRIPTION.

        Task DESCRIPTIONS are stable across activities (e.g. "Amend PO",
        "Create and Approve PO"). Task NAMES are not — TRN4 means
        "Create and Approve" in PoCrt but "Get all Quote Line No" in PoApp
        and "Get all Quot Line No" in PoAmnd. Description scoring fixes
        cross-activity portability.
        """
        upper_act = REVERSE_MAP.get(journey)
        if not upper_act or upper_act not in self.models:
            return None, []
        m = self.models[upper_act]

        main_screen_name = m.get("main_screen")
        main_screen = next((s for s in m["screens"] if s["ilbo_name"] == main_screen_name), None)
        if not main_screen:
            for sc in m["screens"]:
                if sc["tasks_by_type"]["TRANS"]:
                    main_screen = sc
                    break
        if not main_screen:
            return None, []

        trans_tasks = main_screen["tasks_by_type"]["TRANS"]
        if not trans_tasks:
            return None, []

        # Description-based scoring. The description is the stable signal.
        # Keywords that indicate combined (create-and-approve-in-one) actions.
        COMBINED_PHRASES = (
            "and approve", "and authorise", "and authorize",
        )
        # Keywords for plain commit (save/create/submit, not combined).
        PLAIN_COMMIT_PHRASES = {
            # exact-match descriptions
            "create po", "amend po", "approve po", "edit po", "save",
            "change status", "shortclose po", "delete po", "return po",
        }
        # Search/lookup descriptions
        SEARCH_PHRASES = ("search",)
        # Generic fallback descriptions we should AVOID picking
        GENERIC_DESCS = {"default", ""}

        def score(task):
            desc = (task.get("description") or "").strip().lower()
            s = 0

            is_combined = any(p in desc for p in COMBINED_PHRASES)
            is_plain    = (desc in PLAIN_COMMIT_PHRASES)
            is_search   = any(p in desc for p in SEARCH_PHRASES)

            if commit_kind == "submit_and_approve":
                if is_combined: s += 200
                if is_plain:    s -= 100
                if is_search:   s -= 50
            elif commit_kind == "submit":
                if is_plain:    s += 200
                if is_combined: s -= 100   # CRITICAL
                if is_search:   s -= 50
            elif commit_kind == "search":
                if is_search:   s += 200

            # Heavily penalise generic / fallback tasks
            if desc in GENERIC_DESCS:
                s -= 200

            # If nothing scored, prefer non-generic over generic
            if s == 0 and desc not in GENERIC_DESCS:
                s += 10

            return s

        best = max(trans_tasks, key=score)
        trans_name = best["name"]

        # Look up SP chain in model
        sp_chain = []
        for spine in m.get("canonical_spine", []):
            if spine.get("phase") == "commit" and spine.get("task") == trans_name:
                sp_chain = [step.get("spname") for step in (spine.get("sp_chain") or [])
                            if step.get("spname")]
                break

        return trans_name, sp_chain

    def _classify_and_extract(self, user_input: str) -> dict:
        """Single LLM call: classify intent, pick journey, extract slots,
        decide whether the user is asking to commit, and draft a reply."""
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

        current_state = {
            "journey_locked": self.state.get("journey_locked"),
            "slots_already_collected": list(self.state.get("slots", {}).keys()),
            "slot_values_so_far": self.state.get("slots", {}),
        }

        prompt = f"""You are the natural-language understanding layer of a chatbot for Ramco's Purchase Order module.

JOURNEY VOCABULARY (you may ONLY pick from these):
{json.dumps(journey_descriptions, indent=2)}

SLOT VOCABULARY (you may ONLY extract slots from this list):
{json.dumps(SLOT_VOCAB)}

CURRENT CONVERSATION STATE:
{json.dumps(current_state, indent=2)}

USER INPUT THIS TURN:
\"\"\"{user_input}\"\"\"

YOUR TASK: classify the user's intent, identify the journey if they've named one,
extract any slots they mentioned (with their values), and decide if they're
asking the bot to commit (fire the TRANS task).

RULES:
1. Never invent a journey not in JOURNEY VOCABULARY.
2. Never invent a slot not in SLOT VOCABULARY.
3. If the user input is a discovery question ("what can I do?", "list everything"),
   intent=discovery and journey=null. Your `response` should actually enumerate
   the journey list, not be vague.
4. If the user mentions multiple possible journeys without naming one, set
   journey=null AND journey_candidates=[list of candidates]. Your `response`
   should list the candidates and ask the user to pick.
5. wants_commit=true ONLY if the user explicitly says "create", "save",
   "approve", "do it", "submit", etc. Asking a question is not committing.
6. commit_kind: choose ONE of "submit", "submit_and_approve", "search", or "":
   - "submit"            → user wants to save/create but NOT approve yet
                          (e.g. "just create", "don't approve yet", "save")
   - "submit_and_approve"→ user explicitly wants approval too
                          (e.g. "create and approve", "approve too")
   - "search"            → lookup/view query
   - ""                  → no commit this turn
   Negation matters: "create but don't approve" => submit, NOT submit_and_approve.
7. response: 2-3 sentence natural-language reply. If you need a slot, ask for
   it specifically by its business name. If discovery, enumerate options. If
   committing, confirm the action and mention the task name if relevant.
8. Be liberal extracting multiple slots from one sentence — sentences like
   "ITM-200, 10 units at 50 USD, need date 30 days from now" contain
   item_code, quantity, cost, AND need_date.

OUTPUT STRICT JSON:
{{
  "intent": "string",
  "journey": "PoCrt" | "PoCrtQtn" | ... | null,
  "journey_candidates": ["PoCrt", "PoCrtQtn", ...],
  "slots_extracted": {{ "supplier_code": "SUP-100", ... }},
  "wants_commit": false,
  "commit_kind": "submit" | "submit_and_approve" | "search" | "",
  "response": "Short natural-language reply to the user."
}}"""
        return self.llm.call_json(prompt, temperature=0.0, max_output_tokens=2000)


if __name__ == "__main__":
    # Quick smoke test
    bot = ChatbotV1()
    bot.reset()
    out = bot.respond("I need to create a direct purchase order for supplier SUP-100", 1)
    print("Smoke test:")
    print(f"  journey_locked: {out.journey_locked}")
    print(f"  slots: {out.slots_extracted}")
    print(f"  response: {out.response_text}")
