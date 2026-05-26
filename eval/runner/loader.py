"""Load and validate all eval cases against the JSON Schema."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "cases"
SCHEMA_PATH = ROOT / "schema" / "conversation.schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def iter_case_files() -> Iterator[Path]:
    for p in sorted(CASES_DIR.rglob("EVAL-*.json")):
        yield p


def load_cases() -> list[dict]:
    cases = []
    for p in iter_case_files():
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
            c["_path"] = str(p.relative_to(ROOT))
            cases.append(c)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in {p}: {e}") from e
    return cases


def validate_cases(cases: list[dict], schema: dict | None = None) -> list[str]:
    """Light structural validation without external jsonschema dep.

    Returns a list of error strings; empty list = all valid.
    """
    errors: list[str] = []
    required_top = {"id", "title", "covers_journeys", "category", "difficulty",
                    "user_persona", "conversation", "evaluation_metrics"}
    valid_cats = {"discovery", "single-journey-happy-path", "single-journey-with-splice",
                  "error-recovery", "cross-journey", "lookup", "cross-module"}
    seen_ids: set[str] = set()
    for c in cases:
        path = c.get("_path", "?")
        missing = required_top - set(c.keys())
        if missing:
            errors.append(f"{path}: missing required keys {sorted(missing)}")
            continue
        if c["id"] in seen_ids:
            errors.append(f"{path}: duplicate id {c['id']}")
        seen_ids.add(c["id"])
        if c["category"] not in valid_cats:
            errors.append(f"{path}: invalid category {c['category']}")
        if not isinstance(c["conversation"], list) or not c["conversation"]:
            errors.append(f"{path}: conversation must be non-empty list")
            continue
        for i, turn in enumerate(c["conversation"]):
            if "turn" not in turn or "user" not in turn or "expected" not in turn:
                errors.append(f"{path}: turn {i} missing turn/user/expected")
    return errors


if __name__ == "__main__":
    cases = load_cases()
    errors = validate_cases(cases)
    print(f"Loaded {len(cases)} cases from {CASES_DIR}")
    if errors:
        print(f"\n{len(errors)} validation error(s):")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    print("All cases pass structural validation.\n")
    # Summary breakdown
    from collections import Counter
    cats = Counter(c["category"] for c in cases)
    print("By category:")
    for cat, n in sorted(cats.items()):
        print(f"  {cat:35s}  {n}")
    diffs = Counter(c["difficulty"] for c in cases)
    print("\nBy difficulty:")
    for d, n in sorted(diffs.items()):
        print(f"  {d:8s}  {n}")
    journeys = Counter()
    for c in cases:
        for j in c["covers_journeys"]:
            journeys[j] += 1
    print(f"\nJourney coverage ({len(journeys)} distinct):")
    for j, n in sorted(journeys.items(), key=lambda kv: -kv[1]):
        print(f"  {j:14s}  {n}")
    total_turns = sum(len(c["conversation"]) for c in cases)
    print(f"\nTotal conversation turns: {total_turns}")
    print(f"Avg turns per case: {total_turns / len(cases):.1f}")
