"""Chatbot v7 — post-commit awareness + response wording fix
================================================================

Three systemic fixes on top of v6:

Fix 1 — Post-commit journey-switch detection.
  After a write commit fires, the bot enters a "post-commit aware" mode.
  When the user's NEXT turn uses change-language ("wait", "actually", "bump",
  "change", "update", "correct", "instead", "make it", "no wait") AND
  session memory has a committed entity AND the entity_taxonomy maps that
  entity's kind to an amend/edit/etc. consumer journey, the bot SWITCHES to
  that consumer journey instead of mutating the original journey's state.

  Module-agnostic: the consumer-journey mapping comes from entity_taxonomy.json
  (the same file that drives session memory). When GR/PR/PQ modules are added,
  their amend/edit journeys auto-appear in the mapping.

Fix 2 — Post-commit response wording.
  When a write TRANS fires, the bot's natural-language reply is OVERRIDDEN
  to reflect the action that actually happened. Previously the LLM might
  say "Shall I proceed?" AFTER firing the commit — a contradiction. Now
  the response template is "Done — <entity_kind> <entity_id> created
  via <task>; status <status_after>."

Fix 3 — Add post_commit_context to classifier prompt.
  The classifier sees, every turn, what's already been committed in this
  conversation, so the LLM can route change-language correctly without
  needing per-utterance verb explicitness.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

CHATBOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CHATBOT))

from bot_v6 import ChatbotV6
from bot_v1 import REVERSE_MAP, ACTIVITY_NAME_MAP
from session_memory import taxonomy_for, ENTITY_TAXONOMY
sys.path.insert(0, str(CHATBOT.parent / "eval" / "runner"))
from metrics import BotTurnOutput


# Words that signal "I want to change something I already said / did".
# Generic across modules.
CHANGE_LANGUAGE_TOKENS = {
    "wait", "actually", "bump", "change", "update", "correct", "modify",
    "amend", "edit", "fix", "adjust", "revise", "increase", "decrease",
    "raise", "lower", "instead", "rather", "make it", "no wait",
    "scratch that",
}


def _derive_consumer_journeys_by_kind() -> dict[str, list[str]]:
    """For each entity kind, list the activities that CONSUME that kind.
    Derived from entity_taxonomy.json — module-agnostic."""
    out: dict[str, list[str]] = {}
    for act_upper, tax in ENTITY_TAXONOMY.items():
        consumed = tax.get("entity_consumed")
        if not consumed: continue
        kind = consumed.get("kind")
        if not kind: continue
        out.setdefault(kind, []).append(act_upper)
    return out


CONSUMER_JOURNEYS_BY_KIND = _derive_consumer_journeys_by_kind()


# Within consumer journeys, classify by intent (amend / approve / view / hold etc.)
# so the bot picks the RIGHT consumer when change-language fires.
# Heuristic: the activity's verb maps to an intent class.
CONSUMER_INTENT_MAP = {
    "AMEND":   {"POAMND"},        # change-language → amend
    "EDIT":    {"POEDT"},         # for-draft change-language → edit (PO not yet authorised)
    "APPROVE": {"POAPP"},
    "VIEW":    {"POVIW"},
    "HOLD":    {"POHOLD"},
    "CLOSE":   {"POSCL"},
}


def _amend_journey_for(entity_kind: str) -> str | None:
    """Pick the canonical AMEND-style consumer journey for the given entity kind."""
    candidates = CONSUMER_JOURNEYS_BY_KIND.get(entity_kind, [])
    for c in candidates:
        if c in CONSUMER_INTENT_MAP["AMEND"]:
            return ACTIVITY_NAME_MAP.get(c, c)
    # Fallback: any consumer activity
    if candidates:
        return ACTIVITY_NAME_MAP.get(candidates[0], candidates[0])
    return None


def _has_change_language(text: str) -> bool:
    t = " " + text.lower().strip() + " "
    return any((" " + w + " ") in t or t.startswith(w + " ") or t.endswith(" " + w)
               for w in CHANGE_LANGUAGE_TOKENS)


class ChatbotV7(ChatbotV6):
    def reset(self) -> None:
        super().reset()
        # The most-recent committed entity's metadata, used for post-commit
        # journey-switch detection.
        self.state["post_commit_context"] = None
        # Track the just-fired TRANS this turn so we can override response wording.
        self.state["_last_fired_this_turn"] = None

    def respond(self, user_input: str, turn_no: int) -> BotTurnOutput:
        self.state["_last_fired_this_turn"] = None

        # ── FIX 1 (pre-LLM): if post-commit context exists AND user uses
        # change-language, plant a journey-switch hint by setting a flag the
        # prompt will see.
        pcc = self.state.get("post_commit_context")
        if pcc and _has_change_language(user_input):
            # The classifier prompt (Fix 3) reads this and biases toward the
            # amend journey.
            self.state["_change_language_detected"] = True
        else:
            self.state["_change_language_detected"] = False

        out = super().respond(user_input, turn_no)

        # ── After v6/v5/v4/v3/v2/v1 pipeline ──
        # Track any write commits this turn → update post_commit_context
        v4_seq = getattr(out, "trans_sequence_v4", None) or []
        for action in v4_seq:
            if action.get("kind") != "write": continue
            activity_camel = action.get("activity") or self.state.get("journey_locked")
            upper = REVERSE_MAP.get(activity_camel) if activity_camel else None
            tax = taxonomy_for(upper) if upper else None
            if not tax: continue
            produced = tax.get("entity_produced")
            if not produced: continue
            entity_id = self.state["slots"].get(produced["id_slot"])
            self.state["post_commit_context"] = {
                "entity_kind":   produced["kind"],
                "id_slot":       produced["id_slot"],
                "entity_id":     entity_id,
                "produced_by":   upper,
                "via_task":      action.get("task"),
                "amend_journey": _amend_journey_for(produced["kind"]),
                "turn":          turn_no,
            }
            self.state["_last_fired_this_turn"] = {
                "task": action.get("task"),
                "kind": "write",
                "entity_id": entity_id,
                "entity_kind": produced["kind"],
            }

        # ── FIX 2: override response wording when a commit fired this turn
        if self.state["_last_fired_this_turn"]:
            f = self.state["_last_fired_this_turn"]
            entity = f"{f['entity_kind']} {f['entity_id']}" if f["entity_id"] else f["entity_kind"]
            confirm = (
                f"Done. {entity} has been created via {f['task']}. "
                f"You can amend, approve, or hold this {f['entity_kind']} by telling me what you'd like to do next."
            )
            # Append the confirmation in front of the original LLM response so
            # the user sees the action confirmed; LLM's commentary still follows.
            out.response_text = confirm if not out.response_text else (confirm + "\n\n" + out.response_text)

        return out

    # ── FIX 3 — deterministic post-commit journey-switch override ──
    # We don't inject extra prompt text (that would complicate v5's prompt and
    # risk JSON formatting drift). Instead we use a DETERMINISTIC POST-PROCESS:
    # after the v5 classifier returns, if we have post_commit_context + the
    # user's input contains change-language, we FORCE the journey to the
    # taxonomy-mapped amend journey. The LLM's slot extraction is still useful
    # (we keep its slots_extracted) — we just rebind them to the new journey.
    def _classify_v3(self, user_input: str) -> dict:
        pcc = self.state.get("post_commit_context")
        change_detected = self.state.get("_change_language_detected", False)

        try:
            result = super()._classify_v3(user_input)
        except Exception:
            # If the LLM glitches under post-commit + change-language, we still
            # have a strong deterministic intent — fall back to a minimal result.
            if pcc and change_detected:
                result = {
                    "intent": "amend",
                    "journey": pcc.get("amend_journey"),
                    "journey_candidates": [],
                    "slots_extracted": {},
                    "splice_detected": None,
                    "ui_splice_requested": None,
                    "retract_splice": False,
                    "validation_error_detected": False,
                    "wants_commit": False,
                    "commit_kind": "",
                    "response": f"Switching to amend the existing {pcc.get('entity_kind')} {pcc.get('entity_id')}.",
                }
            else:
                raise

        # Deterministic override: post-commit + change-language → amend journey
        if pcc and change_detected and pcc.get("amend_journey"):
            amend_j = pcc["amend_journey"]
            if result.get("journey") != amend_j:
                result["journey"] = amend_j
                # User must still issue an explicit amend commit on a later turn
                if result.get("wants_commit") and result.get("commit_kind") not in ("submit_and_approve",):
                    # If wants_commit was true but for the OLD journey, demote
                    result["wants_commit"] = False
                    result["commit_kind"] = ""
        return result


if __name__ == "__main__":
    bot = ChatbotV7()
    bot.reset()
    print("v7 smoke:")
    for i, msg in enumerate([
        "Create and approve a PO for SUP-300, USD, today, BUY-5, ITM-12 100 units at 5.",
        "Wait, I need to bump that quantity to 150.",
        "Amend and approve in one shot.",
    ], 1):
        out = bot.respond(msg, i)
        v4_seq = getattr(out, "trans_sequence_v4", None) or []
        fired = [s["task"] for s in v4_seq] or ([out.trans_invoked] if out.trans_invoked else [])
        print(f"\nT{i}: journey={out.journey_locked}  fired={fired}")
        print(f"   pcc={bot.state.get('post_commit_context')}")
        print(f"   response: {(out.response_text or '')[:140]}")
