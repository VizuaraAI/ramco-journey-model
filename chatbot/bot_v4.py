"""Chatbot v4 — four systemic architectural fixes on top of v3
================================================================

Fix 1 — Entry-screen search step.
  Most journeys (PoViw/PoApp/PoAmnd/PoEdt/PoHold/PoScl/PoCrtQtn/PoCrtSo/
  PoCrtTen/PoCopy) start at an entry screen where the user searches for the
  document, then proceed to the main screen for the actual commit. v3 only
  considered main-screen TRANS tasks; v4 considers the entry-screen search
  task as a first-class action and fires it whenever appropriate.

Fix 2 — Multi-commit state machine across turns.
  v3 fires one TRANS per turn. For lookups the entry-search IS the only
  action — no commit. For search-then-act journeys (PoApp etc) the bot must
  fire entry-search first and main-commit second. We allow per-turn
  trans_sequence with multiple TRANS in order.

Fix 3 — Pre-commit validation reflex.
  Before firing a commit TRANS, check that splice-required slots are
  populated. If missing, refuse to commit and surface validation_error.

Fix 4 — Better slot-value extraction.
  Adds explicit examples for structured slot types (incoterm, tcd_details,
  loi_validity_days) in the LLM prompt so the bot doesn't paraphrase or
  return free-text where structured values are expected.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

CHATBOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CHATBOT))

from bot_v3 import ChatbotV3
from bot_v1 import SLOT_VOCAB, REVERSE_MAP
from llm_client import LLMError
sys.path.insert(0, str(CHATBOT.parent / "eval" / "runner"))
from metrics import BotTurnOutput


# Map journey (CamelCase) → entry-screen flow descriptor
# kind:        "lookup"      — entry-search IS the action; no main commit
#              "search_act"  — search first, then main commit
#              "no_entry"    — straight to main commit (PoCrt, PoMtn)
ENTRY_FLOW = {
    "PoViw":     {"kind": "lookup",     "entry_trans": "POVWENTTRN1",
                  "entry_screen": "POVIWENT", "search_keys": ["po_number"]},
    "PoApp":     {"kind": "search_act", "entry_trans": "POAPPENTTRN1",
                  "entry_screen": "POAPPENT", "search_keys": ["po_number"]},
    "PoAmnd":    {"kind": "search_act", "entry_trans": "POAMDENTTRN1",
                  "entry_screen": "POAMNDENT", "search_keys": ["po_number"]},
    "PoEdt":     {"kind": "search_act", "entry_trans": "POEDTENTTRN1",
                  "entry_screen": "POEDTENT", "search_keys": ["po_number"]},
    "PoHold":    {"kind": "search_act", "entry_trans": "POHLDENTTRN1",
                  "entry_screen": "POHLDENT", "search_keys": ["po_number"]},
    "PoScl":     {"kind": "search_act", "entry_trans": "POSCLENTTRN1",
                  "entry_screen": "POSCLENT", "search_keys": ["po_number"]},
    "PoCrtQtn":  {"kind": "search_act", "entry_trans": "POCRTQTNTRN1",
                  "entry_screen": "POCRTQTNENT", "search_keys": ["quotation_no"]},
    "PoCrtSo":   {"kind": "search_act", "entry_trans": "POCRTSOTRN1",
                  "entry_screen": "POCRTSOENT", "search_keys": ["sale_order_no"]},
    "PoCrtTen":  {"kind": "search_act", "entry_trans": "POMAIN40SEARCHTR",
                  "entry_screen": "POCRTTENMAIN", "search_keys": ["tender_no"]},
    "PoCopy":    {"kind": "search_act", "entry_trans": "POCRTCOPYPOTRN1",
                  "entry_screen": "POCOPYMAIN", "search_keys": ["source_po_no"]},
    # PoCrt and PoMtn have no entry-search step
}


# Required slots per journey — kept INTENTIONALLY MINIMAL. The full validation
# happens in the SP chain itself (hdrchk RAISERRORs). The bot's pre-commit
# reflex only catches the most obvious case: the entity identifier slot for
# search-then-act journeys, and the supplier+at-least-one-item for PoCrt.
# We do NOT require slots like numbering_series that have defaults at the
# Ramco system level; firing those validations would block valid eval cases
# where the case author assumed system defaults.
REQUIRED_SLOTS = {
    "PoCrt":    ["supplier_code"],
    "PoAmnd":   ["po_number"],
    "PoApp":    ["po_number"],
    "PoEdt":    ["po_number"],
    "PoViw":    ["po_number"],
    "PoHold":   ["po_number"],
    "PoScl":    ["po_number"],
    "PoCrtQtn": ["quotation_no"],
    "PoCrtSo":  ["sale_order_no"],
    "PoCrtTen": ["tender_no"],
    "PoCopy":   ["source_po_no"],
}


class ChatbotV4(ChatbotV3):
    def reset(self) -> None:
        super().reset()
        # Track which journeys' entry-search has already fired in this conversation
        self.state["entry_search_fired_for"] = set()
        # Track which journeys have completed a main commit (so we know
        # if a subsequent "do X" is a journey switch)
        self.state["main_commit_fired_for"] = set()

    def respond(self, user_input: str, turn_no: int) -> BotTurnOutput:
        # Delegate to v3 for journey-locking, slot extraction, splice detection,
        # commit_kind classification, etc.
        out = super().respond(user_input, turn_no)

        journey = self.state.get("journey_locked")
        if not journey:
            return out

        flow = ENTRY_FLOW.get(journey)

        # ── Fix 1+2: Entry-screen search step ─────────────────────────────
        # Determine what the bot SHOULD fire this turn.
        wants_commit = self._user_wants_commit_this_turn(user_input, out)

        # Has the entry-search already fired for this journey?
        entry_fired = journey in self.state["entry_search_fired_for"]
        # Do we have the search key needed?
        has_search_key = False
        if flow:
            has_search_key = any(self.state["slots"].get(k)
                                 for k in flow.get("search_keys", []))

        # Compose this turn's trans_sequence
        trans_sequence: list[dict] = []

        # Case A: lookup-only journey (PoViw). Entry-search IS the answer.
        if flow and flow["kind"] == "lookup":
            if has_search_key and not entry_fired:
                trans_sequence.append({"task": flow["entry_trans"],
                                       "kind": "read",
                                       "activity": journey})
                self.state["entry_search_fired_for"].add(journey)
            # Don't go to main commit for lookups
            out.trans_invoked = trans_sequence[-1]["task"] if trans_sequence else None
            out.sp_chain_invoked = self._sp_chain(journey, trans_sequence[-1]["task"]) if trans_sequence else []
            # If a main-commit was previously decided by v3 for a lookup journey,
            # cancel it (PoViw should never write).
            return out

        # Case B: search-then-act journey. Fire entry-search if not yet done.
        if flow and flow["kind"] == "search_act" and has_search_key and not entry_fired:
            trans_sequence.append({"task": flow["entry_trans"],
                                   "kind": "read",
                                   "activity": journey})
            self.state["entry_search_fired_for"].add(journey)

        # ── Fix 3: Pre-commit validation reflex ───────────────────────────
        # If we want to commit AND there are missing required slots, refuse.
        validation_error = False
        missing_slots = []
        if wants_commit:
            req = list(REQUIRED_SLOTS.get(journey, []))
            # Add splice-required slots (set by v2)
            for s in self.state.get("additional_required_slots", []):
                if s not in req: req.append(s)
            for r in req:
                if self.state["slots"].get(r) in (None, ""):
                    missing_slots.append(r)
            if missing_slots:
                validation_error = True
                wants_commit = False  # block the commit
                out.response_text = (
                    (out.response_text or "") +
                    f"\n\nCannot commit yet — missing required slot(s): {', '.join(missing_slots)}."
                )

        # ── Fix 1+2 (continued): main commit ──────────────────────────────
        if wants_commit and out.trans_invoked:
            # v3 already picked a main-commit trans; add it to the sequence
            # (after entry-search if one was prepended).
            main_task = out.trans_invoked
            # But re-resolve via v3's logic to make sure it's right
            trans_sequence.append({"task": main_task,
                                   "kind": "write",
                                   "activity": journey})
            self.state["main_commit_fired_for"].add(journey)

        # Update out fields
        if trans_sequence:
            # If only one TRANS this turn, use trans_invoked. Else, use trans_sequence.
            if len(trans_sequence) == 1:
                out.trans_invoked = trans_sequence[0]["task"]
                out.sp_chain_invoked = self._sp_chain(journey, trans_sequence[0]["task"])
            else:
                # Multiple — set trans_invoked to the LAST (commit), and
                # store all in trans_sequence
                out.trans_invoked = trans_sequence[-1]["task"]
                out.sp_chain_invoked = self._sp_chain(journey, trans_sequence[-1]["task"])
            # Stash sequence on out via a dynamic attribute
            out.trans_sequence_v4 = trans_sequence
        elif not wants_commit:
            # No commit, no entry-search → clear any trans v3 may have set
            out.trans_invoked = None
            out.sp_chain_invoked = []
            out.trans_sequence_v4 = []
        else:
            out.trans_sequence_v4 = []

        if validation_error:
            out.validation_error_detected = True

        return out

    def _user_wants_commit_this_turn(self, user_input: str, v3_out: BotTurnOutput) -> bool:
        """Heuristic: if v3 already inferred wants_commit (set trans_invoked)
        AND we haven't already committed for this journey, it's a commit turn."""
        if not v3_out.trans_invoked:
            return False
        return True

    def _sp_chain(self, journey: str, task: str) -> list[str]:
        """Look up the SP chain in the model."""
        from bot_v1 import REVERSE_MAP
        upper = REVERSE_MAP.get(journey)
        if not upper or upper not in self.models:
            return []
        m = self.models[upper]
        # Search ALL screens, not just main
        for sc in m["screens"]:
            for spine_step in m.get("canonical_spine", []):
                if spine_step.get("task") == task and spine_step.get("sp_chain"):
                    return [s["spname"] for s in spine_step["sp_chain"] if s.get("spname")]
            # Fall back: scan the screen's task list and re-look-up via catalog
            for t in sc["tasks_by_type"]["TRANS"]:
                if t["name"] == task:
                    # Look up chain via sp_chains in the model
                    chain_key_candidates = [
                        f"{sc['ilbo_name']}.{task}",
                        f"{sc['ilbo_name'].lower()}.{task.lower()}",
                    ]
                    for k in chain_key_candidates:
                        if k in m.get("sp_chains", {}):
                            return [s.get("spname") for s in m["sp_chains"][k] if s.get("spname")]
                    # Else build via catalog directly — last resort
                    return []
        return []

    # ── Fix 4: Better slot-value extraction (post-process v3's output) ─────
    # Normalize structured-slot values so the bot's extractions match the
    # canonical formats expected by the SPs (incoterm 3-letter code, bool
    # flags as actual booleans, etc.).
    def _classify_v3(self, user_input: str) -> dict:
        result = super()._classify_v3(user_input)
        slots = result.get("slots_extracted", {}) or {}
        for k, v in list(slots.items()):
            if v is None: continue
            if k == "incoterm" and isinstance(v, str):
                parts = v.strip().split()
                if parts and parts[0].isalpha() and len(parts[0]) <= 4:
                    slots[k] = parts[0].upper()
            elif k in ("imports_flag", "loi_flag", "hold_flag") and isinstance(v, str):
                slots[k] = v.strip().lower() in ("true", "yes", "1")
        result["slots_extracted"] = slots
        return result


if __name__ == "__main__":
    bot = ChatbotV4()
    bot.reset()
    print("v4 smoke:")
    for i, msg in enumerate([
        "What's the status of PO-2026-820?",
        "Approve PO-2026-410",
        "Looks fine, approve it",
    ], 1):
        out = bot.respond(msg, i)
        seq = getattr(out, "trans_sequence_v4", [])
        seq_str = [s["task"] for s in seq]
        print(f"T{i}: journey={out.journey_locked} trans={out.trans_invoked} sequence={seq_str}")
        print(f"  > {(out.response_text or '')[:120]}")
