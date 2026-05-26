"""Generic session memory for cross-journey context carry.

Module-agnostic. Driven entirely by `out/model/entity_taxonomy.json` which
maps activity → entity_produced / entity_consumed. When an activity in any
module is added (GR, PR, PQ, ...), the entity taxonomy gets regenerated and
this module needs no changes.

Behaviour:
  1. When a bot fires a COMMIT TRANS for an activity whose taxonomy says
     `entity_produced.kind = X with id_slot = Y`, this module mints a
     synthetic ID (`X-NEW-<n>`) and binds it to slot Y in session memory.
  2. When a bot enters an activity whose taxonomy says
     `entity_consumed.kind = X with id_slot = Y` AND slot Y is empty AND
     session memory holds an X, the bot's slots get auto-populated from
     session memory.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
TAXONOMY_PATH = PROJECT / "out" / "model" / "entity_taxonomy.json"

try:
    ENTITY_TAXONOMY = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    ENTITY_TAXONOMY = {}


def taxonomy_for(activity_upper: str) -> dict | None:
    return ENTITY_TAXONOMY.get(activity_upper)


class SessionMemory:
    """Tracks entities produced during this conversation, keyed by kind.

    Each entity has:
      kind:         "PurchaseOrder", "PurchaseRequest", ...
      id_slot:      slot name in the bot's vocabulary ("po_number", "pr_number", ...)
      synthetic_id: a stable made-up ID for this conversation
      produced_by:  activity that produced it (e.g. "POCRT")
      turn:         turn number it was produced
    """
    def __init__(self):
        self.entities: list[dict] = []
        self._next_id: dict[str, int] = {}

    def reset(self):
        self.entities.clear()
        self._next_id.clear()

    def mint_id(self, kind: str) -> str:
        """Generate a stable synthetic ID for an entity kind."""
        self._next_id[kind] = self._next_id.get(kind, 0) + 1
        # Convention: <PREFIX>-NEW-<N>. Prefix mirrors common ERP naming.
        prefix_map = {
            "PurchaseOrder":   "PO",
            "PurchaseRequest": "PR",
            "GoodsReceipt":    "GR",
            "Quotation":       "QTN",
            "SaleOrder":       "SO",
            "Tender":          "TEN",
            "Invoice":         "INV",
            "Milestone":       "MS",
            "LC":              "LC",
        }
        prefix = prefix_map.get(kind, kind[:3].upper())
        return f"{prefix}-NEW-{self._next_id[kind]:03d}"

    def record_production(self, activity_upper: str, turn: int) -> dict | None:
        """If this activity produces an entity, mint an ID and record it.
        Returns the new entity dict (with id_slot and synthetic_id), or None."""
        tax = taxonomy_for(activity_upper)
        if not tax: return None
        produced = tax.get("entity_produced")
        if not produced or not produced.get("id_slot"): return None
        entity = {
            "kind": produced["kind"],
            "id_slot": produced["id_slot"],
            "synthetic_id": self.mint_id(produced["kind"]),
            "produced_by": activity_upper,
            "turn": turn,
        }
        self.entities.append(entity)
        return entity

    def latest_of_kind(self, kind: str) -> dict | None:
        for e in reversed(self.entities):
            if e["kind"] == kind:
                return e
        return None

    def auto_fill_consumed_slot(self, activity_upper: str,
                                current_slots: dict[str, Any]) -> dict[str, Any]:
        """For activities that CONSUME an entity, if the user hasn't provided
        the consumed-id slot value but session memory has one of the right
        kind, return slots augmented with the synthetic ID. Returns a dict
        of slots to MERGE into current_slots."""
        tax = taxonomy_for(activity_upper)
        if not tax: return {}
        consumed = tax.get("entity_consumed")
        if not consumed or not consumed.get("id_slot"): return {}
        id_slot = consumed["id_slot"]
        if current_slots.get(id_slot): return {}   # user already provided it
        ent = self.latest_of_kind(consumed["kind"])
        if not ent: return {}
        return {id_slot: ent["synthetic_id"]}
