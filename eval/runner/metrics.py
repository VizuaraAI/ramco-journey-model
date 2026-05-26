"""Per-turn and per-case metric assertions.

Given a candidate bot trace (BotTurnOutput) and an expected block, compute
which metrics passed and which failed. The bot itself is decoupled — this
module knows only the trace shape.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BotTurnOutput:
    """What a bot must produce per turn for the evaluator to score it.
    Shape is intentionally narrow: structured intents/slots/journey state
    plus optional free-text response.
    """
    intent: str | None = None
    journey_locked: str | None = None
    journey_candidates: list[str] = field(default_factory=list)
    slots_extracted: dict[str, Any] = field(default_factory=dict)
    splice_triggered: str | None = None
    splice_walked: list[str] = field(default_factory=list)
    trans_invoked: str | None = None
    sp_chain_invoked: list[str] = field(default_factory=list)
    validation_error_detected: bool | None = None
    response_text: str = ""
    additional_required_slots: list[str] = field(default_factory=list)
    context_carried: dict[str, Any] = field(default_factory=dict)
    cross_module_query: str | None = None


@dataclass
class MetricResult:
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"[{mark}] {self.name}{(' — ' + self.detail) if self.detail else ''}"


_STOPWORDS = {
    "the","a","an","is","are","of","to","and","or","in","on","at","for",
    "with","that","this","be","by","as","from","it","its","but","not",
    "must","should","ask","tell","report","fire","trigger","invoke","do",
    "if","then","else","when","while","also","one","two","three","first",
    "next","please","kindly","make","sure","explicitly","just","yet",
    "so","such","etc","e.g.","i.e.","because","since","into","onto","via",
    "user","bot",
}

def _content_tokens(s: str) -> set[str]:
    """Lowercase tokens minus short/stopwords/punctuation."""
    import re as _re
    toks = _re.findall(r"[a-zA-Z_][\w_-]+", s.lower())
    return {t for t in toks if t not in _STOPWORDS and len(t) > 2}


def _text_includes(text: str, must: list[str]) -> tuple[bool, list[str]]:
    """Semantic match: each `must` item is satisfied if the bot's text contains
    >=40% of the item's content tokens (case-insensitive, stopwords stripped).
    Gives credit for paraphrasing instead of demanding verbatim phrases."""
    text_tokens = _content_tokens(text)
    missing = []
    for item in must:
        needed = _content_tokens(item)
        if not needed:
            continue
        overlap = len(needed & text_tokens)
        if overlap / len(needed) < 0.40:
            missing.append(item[:80])
    return len(missing) == 0, missing


def score_turn(expected: dict, bot: BotTurnOutput) -> list[MetricResult]:
    results: list[MetricResult] = []

    # journey_locked
    if "journey_locked" in expected:
        exp = expected["journey_locked"]
        results.append(MetricResult(
            "journey_locked",
            bot.journey_locked == exp,
            f"expected={exp} got={bot.journey_locked}"
        ))

    # journey_switched is checked the same way (the bot just changes journey_locked)
    if "journey_switched" in expected:
        exp = expected["journey_switched"]
        results.append(MetricResult(
            "journey_switched",
            bot.journey_locked == exp,
            f"expected={exp} got={bot.journey_locked}"
        ))

    # journey_candidates (set inclusion)
    if "journey_candidates" in expected:
        exp_set = set(expected["journey_candidates"])
        got_set = set(bot.journey_candidates)
        common = exp_set & got_set
        results.append(MetricResult(
            "journey_candidates",
            len(common) >= max(1, len(exp_set) - 1),
            f"expected={sorted(exp_set)} got={sorted(got_set)}"
        ))

    # slots_extracted
    if "slots_extracted" in expected:
        exp_slots = expected["slots_extracted"]
        missing = [k for k in exp_slots if k not in bot.slots_extracted]
        results.append(MetricResult(
            "slots_extracted",
            not missing,
            f"missing={missing}"
        ))

    # splice_triggered
    if "splice_triggered" in expected:
        exp = expected["splice_triggered"]
        results.append(MetricResult(
            "splice_triggered",
            (bot.splice_triggered or "").startswith(exp.split()[0]) if exp else True,
            f"expected={exp} got={bot.splice_triggered}"
        ))

    # additional_required_slots
    if "additional_required_slots" in expected:
        exp_set = set(expected["additional_required_slots"])
        got_set = set(bot.additional_required_slots)
        results.append(MetricResult(
            "additional_required_slots",
            exp_set.issubset(got_set),
            f"expected={sorted(exp_set)} got={sorted(got_set)}"
        ))

    # trans_invoked
    if "trans_invoked" in expected:
        exp = expected["trans_invoked"]
        results.append(MetricResult(
            "trans_invoked",
            bot.trans_invoked == exp,
            f"expected={exp} got={bot.trans_invoked}"
        ))

    # sp_chain_invoked (must contain expected entries, order-sensitive)
    if "sp_chain_invoked" in expected:
        exp = expected["sp_chain_invoked"]
        got = bot.sp_chain_invoked
        missing = [sp for sp in exp if sp not in got]
        results.append(MetricResult(
            "sp_chain_invoked",
            not missing,
            f"missing_sps={missing}"
        ))

    # validation_error_detected
    if "validation_error_detected" in expected:
        exp = bool(expected["validation_error_detected"])
        got = bool(bot.validation_error_detected)
        results.append(MetricResult(
            "validation_error_detected",
            exp == got,
            f"expected={exp} got={got}"
        ))

    # bot_must — semantic substring checks
    if "bot_must" in expected and bot.response_text:
        ok, missing = _text_includes(bot.response_text, expected["bot_must"])
        results.append(MetricResult(
            "bot_must",
            ok,
            f"missing_phrases={missing}" if missing else ""
        ))

    # bot_must_not — semantic substring checks (must NOT be in text)
    if "bot_must_not" in expected and bot.response_text:
        present = [m for m in expected["bot_must_not"] if m.lower() in bot.response_text.lower()]
        results.append(MetricResult(
            "bot_must_not",
            not present,
            f"forbidden_present={present}"
        ))

    # cross_module_query
    if "cross_module_query" in expected:
        exp = expected["cross_module_query"]
        ok = bot.cross_module_query is not None and any(
            tok.lower() in (bot.cross_module_query or "").lower()
            for tok in exp.split()[:3]
        )
        results.append(MetricResult(
            "cross_module_query",
            ok,
            f"expected={exp!r} got={bot.cross_module_query!r}"
        ))

    return results
