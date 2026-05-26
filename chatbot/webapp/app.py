"""Flask app wrapping ChatbotV6 with full trace + file-reference instrumentation."""
from __future__ import annotations
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
sys.path.insert(0, str(PROJECT / "chatbot"))
sys.path.insert(0, str(PROJECT / "eval" / "runner"))

from flask import Flask, request, jsonify, send_from_directory
from bot_v8 import ChatbotV8
from bot_v1 import REVERSE_MAP

# Pre-load reference data for the trace panel
CATALOG = json.loads((PROJECT / "out" / "parsed" / "service_catalog.json").read_text())
SP_DATA = json.loads((PROJECT / "out" / "parsed" / "sp_branches.json").read_text())
ENTITY_TAX = json.loads((PROJECT / "out" / "model" / "entity_taxonomy.json").read_text())


app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")

SESSIONS: dict[str, dict] = {}   # session_id → {"bot": ..., "turn": int, "history": [...]}


@app.route("/")
def index():
    return send_from_directory(str(HERE), "index.html")


@app.route("/reset", methods=["POST"])
def reset():
    sid = request.json.get("session_id") or str(uuid.uuid4())
    SESSIONS[sid] = {"bot": ChatbotV8(), "turn": 0, "history": []}
    SESSIONS[sid]["bot"].reset()
    return jsonify({"session_id": sid})


def _sp_chain_meta(activity_camel: str, ui: str, task: str) -> dict:
    """Look up the SP chain in catalog and the tables each SP touches."""
    target = task.lower()
    prefix = f"{activity_camel}|{ui}|" if (activity_camel and ui) else None
    chain = []
    if prefix:
        for key, ch in CATALOG.get("chains", {}).items():
            if key.startswith(prefix) and key[len(prefix):].lower() == target:
                chain = ch
                break
    rich = []
    for step in chain:
        sp_name = step.get("spname") or ""
        sp = SP_DATA.get("sps", {}).get(sp_name.lower(), {})
        tables = set()
        for b in sp.get("branches", []):
            for t in b["consequences"].get("inserts", []): tables.add(t.lower())
            for t in b["consequences"].get("updates", []): tables.add(t.lower())
            for t in b["consequences"].get("deletes", []): tables.add(t.lower())
        # filter staging
        tables = sorted(t for t in tables
                        if "tmp" not in t and "temp" not in t and len(t) > 3
                        and t not in ("dtl", "data"))
        rich.append({
            "seq": step.get("sequenceno"),
            "sp_name": sp_name,
            "branches": len(sp.get("branches", [])),
            "tables": tables[:8],
        })
    return {"chain": rich}


def _find_ui_for_task(activity_camel: str, task: str) -> str | None:
    if not activity_camel: return None
    prefix = activity_camel + "|"
    for key in CATALOG.get("chains", {}):
        if not key.startswith(prefix): continue
        _, ui, t = key.split("|", 2)
        if t.lower() == task.lower():
            return ui
    return None


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    sid = data.get("session_id")
    msg = (data.get("message") or "").strip()
    if not sid or sid not in SESSIONS:
        return jsonify({"error": "no session — call /reset first"}), 400
    if not msg:
        return jsonify({"error": "empty message"}), 400

    sess = SESSIONS[sid]
    sess["turn"] += 1
    turn_no = sess["turn"]

    bot = sess["bot"]
    started = datetime.now()
    try:
        out = bot.respond(msg, turn_no)
        bot_response = out.response_text or "(no response text)"
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500
    elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)

    # Collect trace from out + bot.state
    state_slots = dict(bot.state.get("slots", {}))
    journey = out.journey_locked
    upper_act = REVERSE_MAP.get(journey) if journey else None

    # v4-style multi-trans-per-turn
    v4_seq = getattr(out, "trans_sequence_v4", None) or []
    if not v4_seq and out.trans_invoked:
        v4_seq = [{"task": out.trans_invoked, "kind": "write",
                   "activity": journey}]

    trans_details = []
    for t in v4_seq:
        task = t.get("task")
        act_c = t.get("activity") or journey
        ui = _find_ui_for_task(act_c, task) if (act_c and task) else None
        meta = _sp_chain_meta(act_c, ui, task) if (act_c and ui and task) else {"chain": []}
        trans_details.append({
            "task": task,
            "kind": t.get("kind", "?"),
            "activity": act_c,
            "ui": ui,
            "sp_chain": meta["chain"],
        })

    # Session memory entities
    session_entities = []
    if hasattr(bot, "session"):
        session_entities = [
            {"kind": e["kind"], "id_slot": e["id_slot"],
             "synthetic_id": e["synthetic_id"],
             "produced_by": e["produced_by"],
             "turn": e["turn"]}
            for e in bot.session.entities
        ]

    # Entity taxonomy for current journey
    taxonomy_for_journey = ENTITY_TAX.get(upper_act, {}) if upper_act else {}

    # Post-commit context (v7+) — what the bot knows about already-fired commits
    post_commit = getattr(bot, "state", {}).get("post_commit_context")

    # v8 decorative overlay: current step + mandatory progress
    current_step       = getattr(bot, "state", {}).get("current_step")
    mandatory_progress = getattr(bot, "state", {}).get("mandatory_progress")

    # Files this turn would have referenced
    files_referenced = []
    if upper_act:
        files_referenced.append({
            "path": f"out/model/activities/{upper_act}.json",
            "why": f"Loaded the journey model for {journey} — canonical spine, screens, splices",
        })
    files_referenced.append({
        "path": "out/model/entity_taxonomy.json",
        "why": "Looked up entity production/consumption taxonomy for cross-journey context carry",
    })
    if v4_seq:
        files_referenced.append({
            "path": "out/parsed/service_catalog.json",
            "why": "Resolved TRANS task → SP call chain",
        })
        files_referenced.append({
            "path": "out/parsed/sp_branches.json",
            "why": "Determined which tables each SP in the chain writes to",
        })

    turn_record = {
        "turn": turn_no,
        "user": msg,
        "bot": bot_response,
        "elapsed_ms": elapsed_ms,
        "trace": {
            "intent": out.intent,
            "journey_locked": journey,
            "journey_candidates": out.journey_candidates,
            "slots_extracted_this_turn": out.slots_extracted or {},
            "all_slots_in_state": state_slots,
            "splice_triggered": out.splice_triggered,
            "splices_walked": out.splice_walked,
            "additional_required_slots": out.additional_required_slots,
            "validation_error_detected": out.validation_error_detected,
            "trans_details": trans_details,
            "session_entities": session_entities,
            "entity_taxonomy_for_journey": taxonomy_for_journey,
            "post_commit_context": post_commit,
            "current_step": current_step,
            "mandatory_progress": mandatory_progress,
        },
        "files_referenced": files_referenced,
    }
    sess["history"].append(turn_record)
    return jsonify(turn_record)


@app.route("/history", methods=["POST"])
def history():
    sid = (request.json or {}).get("session_id")
    if not sid or sid not in SESSIONS:
        return jsonify({"history": []})
    return jsonify({"history": SESSIONS[sid]["history"]})


if __name__ == "__main__":
    print("\n" + "=" * 64)
    print("Ramco PO chatbot · interactive test environment")
    print("=" * 64)
    print(f"Open http://127.0.0.1:5050 in your browser.")
    print(f"Bot:  v8   |   Sessions stored in memory; restart server = reset all")
    print("=" * 64 + "\n")
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
