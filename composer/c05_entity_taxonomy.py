"""c05 · entity taxonomy
============================

For every activity in the journey model, derive:
  - `entity_produced`:  the entity kind this activity creates (if any), with
                        the slot that will hold the assigned ID
  - `entity_consumed`:  the entity kind this activity operates on (if any),
                        with the slot the user provides

This is DELIBERATELY module-agnostic — the rules parse the activity description
(e.g. "Create Direct Purchase Order", "Amend Purchase Order") not the activity
name. Same code will work for GR/PR/PQ/SIN activities once their `*_info.xml`
is parsed.

Verb taxonomy:
  PRODUCERS:  Create, Save, Generate, Issue, Acknowledge, Receive, Make
  CONSUMERS:  Amend, Edit, Approve, Authorise, View, Hold, Unhold, Close,
              Short Close, Cancel, Reject, Return, Maintain, Modify, Change,
              Specify, Set, Update, Delete, Print, Copy, Convert

Entity-kind extraction is regex-based on the noun phrase after the verb:
  "Create Direct Purchase Order"  → entity = "PurchaseOrder"
  "Create PO From Quotation"      → produces = "PurchaseOrder", consumes = "Quotation"
  "Amend Purchase Order"          → entity = "PurchaseOrder"
  "Acknowledge Milestone Completion" → entity = "Milestone"
  "View LC Details"               → entity = "LC"

Slot-name convention: entity → snake_case_id_slot
  PurchaseOrder → po_number
  Quotation     → quotation_no
  SaleOrder     → sale_order_no
  Tender        → tender_no
  Milestone     → milestone_no
  PurchaseRequest → pr_number
  GoodsReceipt  → gr_number
  Invoice       → invoice_number
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "out" / "model" / "activities"
PARSED = ROOT / "out" / "parsed"
OUT = ROOT / "out" / "model" / "entity_taxonomy.json"


PRODUCER_VERBS = {
    "create", "save", "generate", "issue", "acknowledge", "receive", "make",
}
CONSUMER_VERBS = {
    "amend", "edit", "approve", "authorise", "authorize", "view", "hold",
    "unhold", "close", "short", "cancel", "reject", "return", "maintain",
    "modify", "change", "specify", "set", "update", "delete", "print",
    "copy", "convert", "help",
}

# Entity kind → canonical id slot. Convention: <entity>_<id_word>.
# `id_word` is "_number" for things called "Number"/"No", "_id" for IDs.
ENTITY_TO_ID_SLOT = {
    "PurchaseOrder":   "po_number",
    "PurchaseRequest": "pr_number",
    "GoodsReceipt":    "gr_number",
    "Quotation":       "quotation_no",
    "SaleOrder":       "sale_order_no",
    "Tender":          "tender_no",
    "Invoice":         "invoice_number",
    "Milestone":       "milestone_no",
    "LC":              "lc_number",
    "LetterOfCredit":  "lc_number",
    "Supplier":        "supplier_code",
    # PO sub-references (Copy from)
    "SourcePO":        "source_po_no",
}

# Recognise common entity nouns in descriptions
ENTITY_PATTERNS = [
    (r"\b(?:direct\s+)?purchase\s*order\b",         "PurchaseOrder"),
    (r"\bpo\b(?!\s*amend\b)",                       "PurchaseOrder"),
    (r"\bpurchase\s*request\b|\bpr\b",              "PurchaseRequest"),
    (r"\bgoods\s*receipt\b|\bgr\b",                 "GoodsReceipt"),
    (r"\bquotation\b",                              "Quotation"),
    (r"\bsale\s*order\b|\bso\b",                    "SaleOrder"),
    (r"\btender\b",                                 "Tender"),
    (r"\binvoice\b",                                "Invoice"),
    (r"\bmilestone\b",                              "Milestone"),
    (r"\bletter\s*of\s*credit\b|\blc\b",            "LC"),
]


def detect_entities(text: str) -> list[str]:
    text_lc = text.lower()
    found = []
    for pattern, kind in ENTITY_PATTERNS:
        if re.search(pattern, text_lc):
            if kind not in found: found.append(kind)
    return found


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z]+", s.lower())


def classify_activity(activity: dict) -> dict:
    """Return {entity_produced, entity_consumed, role}.

    Verb detection scans the WHOLE description (not just first word), so
    'Copy and Create' is recognised as both consumer (copy) and producer (create).
    """
    desc = (activity.get("description") or "").strip()
    desc_lc = desc.lower()
    tokens = set(_tokens(desc_lc))

    has_producer = bool(tokens & PRODUCER_VERBS)
    has_consumer = bool(tokens & CONSUMER_VERBS)

    entities = detect_entities(desc)
    primary = entities[0] if entities else None

    # "X From Y" → produces X, consumes Y (the source doc)
    secondary = None
    m = re.search(r"\bfrom\b", desc_lc)
    if m:
        tail = desc_lc[m.end():]
        secondary_list = detect_entities(tail)
        secondary = secondary_list[0] if secondary_list else None

    # "Copy and Create X" — copying an X consumes a SOURCE-X
    if "copy" in tokens and primary:
        secondary = "Source" + primary if primary != "PurchaseOrder" else "SourcePO"

    produced = None
    consumed = None

    if has_producer and primary:
        produced = {"kind": primary, "id_slot": ENTITY_TO_ID_SLOT.get(primary)}
    if has_consumer and primary:
        # If the activity both produces and consumes the same kind, the
        # consumption is of a different instance (typically by source doc)
        if produced and not secondary:
            secondary = None  # no explicit secondary; not a true consume of separate doc
        else:
            consumed = {"kind": primary, "id_slot": ENTITY_TO_ID_SLOT.get(primary)}
    if produced and secondary:
        consumed = {"kind": secondary, "id_slot": ENTITY_TO_ID_SLOT.get(secondary)}

    role = (
        "producer+consumer" if (produced and consumed) else
        "producer" if produced else
        "consumer" if consumed else
        "unknown"
    )
    return {"entity_produced": produced, "entity_consumed": consumed, "role": role}


def main():
    taxonomy: dict[str, dict] = {}
    for p in sorted(MODEL_DIR.glob("*.json")):
        activity = json.loads(p.read_text(encoding="utf-8"))
        if not activity.get("is_user_facing"):
            continue
        tax = classify_activity(activity)
        taxonomy[activity["activity"]] = {
            "activity": activity["activity"],
            "description": activity.get("description", ""),
            **tax,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(taxonomy, indent=2), encoding="utf-8")

    # Summary print
    by_role = {}
    for a in taxonomy.values():
        by_role.setdefault(a["role"], []).append(a["activity"])
    print(f"Entity taxonomy → {OUT.relative_to(ROOT)}")
    print(f"  {len(taxonomy)} user-facing activities classified")
    for role, acts in sorted(by_role.items()):
        print(f"  [{role}] ({len(acts)}): {', '.join(acts)}")

    print("\nProduced entities per activity:")
    for name, a in taxonomy.items():
        p = a.get("entity_produced")
        c = a.get("entity_consumed")
        ps = f"+{p['kind']}({p['id_slot']})" if p else ""
        cs = f"⇐{c['kind']}({c['id_slot']})" if c else ""
        print(f"  {name:14s}  {ps:25s}  {cs}")


if __name__ == "__main__":
    main()
