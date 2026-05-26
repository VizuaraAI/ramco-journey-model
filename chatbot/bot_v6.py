"""Chatbot v6 — same bot architecture as v5.

The v6 cycle's structural fixes live in the evaluator, not the bot:
  - Pick BEST-MATCHING action when bot fires the same TRANS multiple times
    (was picking first; now picks the one with the most-complete slot state)
  - Templated slot values accept "missing" when the slot is a system-default
    (anything ending in _date / _no / _number / _id is system-fillable)

The bot itself doesn't change. This separate version exists so the eval
report carries a v6 row showing the structural-evaluator improvements alone.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot_v5 import ChatbotV5


class ChatbotV6(ChatbotV5):
    pass
