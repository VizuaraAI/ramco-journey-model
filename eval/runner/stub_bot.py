"""A stub chatbot that returns nothing useful — for baseline measurement.

Every real chatbot implementation must conform to the same `respond(user_input,
state) -> BotTurnOutput` interface. This baseline lets us verify the harness
runs end-to-end and produces a 0% report.
"""
from __future__ import annotations
from typing import Any
from metrics import BotTurnOutput


class StubBot:
    """Returns a do-nothing response for every turn."""

    def __init__(self):
        self.state: dict[str, Any] = {}

    def reset(self) -> None:
        self.state = {}

    def respond(self, user_input: str, turn_no: int) -> BotTurnOutput:
        return BotTurnOutput(
            intent=None,
            journey_locked=None,
            journey_candidates=[],
            slots_extracted={},
            splice_triggered=None,
            splice_walked=[],
            trans_invoked=None,
            sp_chain_invoked=[],
            response_text="I do not know.",
        )
