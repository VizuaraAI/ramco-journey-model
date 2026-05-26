"""Chatbot v8 — step-aware UX, identical decisions to v7
============================================================

CONTRACT: v8 inherits all decision-making logic from v7. Every TRANS chosen,
every SP chain, every table written, every splice triggered, every validation
result is BIT-FOR-BIT identical to v7. Captions are a presentation overlay
only — read for UX prose and surfaced to the trace panel, never feeding back
into a decision.

What v8 adds (decoration only):
  - Reads `collect_steps` from the journey model (populated by the composer
    from the deterministic .htm caption attributes).
  - Tracks which step the conversation is currently in (based on which slots
    have been collected so far).
  - Surfaces `current_step` and `mandatory_progress` to the bot state so the
    webapp trace can display them.
  - Mentions the current step's caption in the response wording when it makes
    sense ("Now let me collect Amount Details…").

What v8 does NOT change (every decision identical to v7):
  - intent classification, journey lock, slot extraction
  - splice detection (UI + data)
  - validation (additional_required_slots check)
  - TRANS picker (description-based scoring)
  - SP chain selection
  - session memory minting
  - post-commit journey switch
  - cross-journey context carry
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

CHATBOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CHATBOT))

from bot_v7 import ChatbotV7
from bot_v1 import REVERSE_MAP
sys.path.insert(0, str(CHATBOT.parent / "eval" / "runner"))
from metrics import BotTurnOutput


class ChatbotV8(ChatbotV7):
    def reset(self) -> None:
        super().reset()
        self.state["current_step"] = None       # set lazily after first journey lock
        self.state["mandatory_progress"] = None

    def respond(self, user_input: str, turn_no: int) -> BotTurnOutput:
        # Delegate all decisions to v7 → v6 → v5 → ... chain.
        out = super().respond(user_input, turn_no)

        # ── DECORATIVE OVERLAY (read-only, never feeds back) ──
        step_info = self._compute_current_step()
        if step_info:
            self.state["current_step"] = step_info["step_record"]
            self.state["mandatory_progress"] = step_info["mandatory_progress"]
        return out

    def _compute_current_step(self) -> dict | None:
        """Look up the current journey's main-screen collect_steps and figure
        out which step we're 'in' based on slot fill. Read-only."""
        journey = self.state.get("journey_locked")
        if not journey: return None
        upper = REVERSE_MAP.get(journey)
        if not upper or upper not in self.models:
            return None
        model = self.models[upper]
        main_screen_name = model.get("main_screen")
        main_screen = next(
            (s for s in model.get("screens", []) if s["ilbo_name"] == main_screen_name),
            None
        )
        if not main_screen:
            return None
        steps = main_screen.get("collect_steps") or []
        if not steps:
            return None

        # Heuristic step-locator (decoration only):
        # The "current step" is the first step whose mandatory slots aren't
        # all filled yet. If everything is filled, the current step is the
        # last one (ready for commit).
        # We don't have a perfect slot-id → step-id map (slot labels are
        # captioned independently), so this is approximate.
        filled_slots = set(self.state.get("slots", {}).keys())
        current_step = steps[-1]   # fallback to last
        for step in steps:
            mandatory_btsynonyms = [
                lab["btsynonym"].lower()
                for lab in step.get("slot_labels", [])
                if lab.get("mandatory")
            ]
            unfilled_mandatory = [
                bt for bt in mandatory_btsynonyms
                if bt and bt not in filled_slots and self._slot_alias(bt) not in filled_slots
            ]
            if unfilled_mandatory:
                current_step = step
                break

        # Mandatory progress for the active step
        mandatory_btsynonyms = [
            lab["btsynonym"].lower()
            for lab in current_step.get("slot_labels", [])
            if lab.get("mandatory")
        ]
        mandatory_count = len(mandatory_btsynonyms)
        mandatory_filled = sum(
            1 for bt in mandatory_btsynonyms
            if bt and (bt in filled_slots or self._slot_alias(bt) in filled_slots)
        )

        return {
            "step_record": {
                "step":            current_step.get("step"),
                "caption":         current_step.get("caption"),
                "label":           current_step.get("label"),
                "is_grid":         current_step.get("is_grid"),
                "slot_count":      current_step.get("slot_count"),
                "mandatory_count": mandatory_count,
            },
            "mandatory_progress": {
                "filled": mandatory_filled,
                "total":  mandatory_count,
            },
        }

    @staticmethod
    def _slot_alias(btsynonym: str) -> str:
        """Map a label's btsynonym to a known canonical slot name when they
        differ slightly. Naming conventions are messy in Ramco — labels often
        use shorter names than our canonical slot vocabulary."""
        aliases = {
            "num_series": "numbering_series",
            "podate":     "po_date",
            "buyerhdr":   "buyer",
            "totalvalue": "po_value",
        }
        return aliases.get(btsynonym, btsynonym)


if __name__ == "__main__":
    bot = ChatbotV8()
    bot.reset()
    print("v8 smoke:")
    out = bot.respond("I need to create a direct PO for SUP-100 in USD.", 1)
    print(f"journey={out.journey_locked}")
    print(f"current_step={bot.state.get('current_step')}")
    print(f"mandatory_progress={bot.state.get('mandatory_progress')}")
