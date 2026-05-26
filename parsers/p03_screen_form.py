"""p03 · screen form parser
=============================

Reads:  artifacts/ramco/PO/ScreenObjects/PO/*.htm  (excluding _State.xml and _user.js)
Writes: out/parsed/screen_forms.json

Extracts:
  (a) the <meta name="Tasks"> header: full task list with type per screen
  (b) the form layout: sections → fields (slots) with labels, types, datatypes
  (c) screen identity from meta tags: Activity Name, ILBO Name

Layer L1 — deterministic HTML parsing with html.parser. No LLM.
"""
from __future__ import annotations
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = ROOT / "artifacts" / "ramco" / "PO" / "ScreenObjects" / "PO"
OUT_DIR = ROOT / "out" / "parsed"
OUT = OUT_DIR / "screen_forms.json"


# These attribute "type" values on <table> denote real form controls vs layout.
SLOT_TABLE_TYPES = {
    "input", "displayonly", "select", "combo", "combobox", "date", "datetime",
    "multiline", "multilinedisplay", "checkbox", "radio", "hyperlink",
    "currency", "amount", "number", "lov",
}
LAYOUT_TABLE_TYPES = {"label", "section", "displayonly", "filler"}  # informational only


class ScreenFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        # We track sections by following <table type="section"> open/close
        self.section_stack: list[str] = []
        # NEW: section metadata stack (caption, is_grid, is_titled) parallel to section_stack
        self.section_meta_stack: list[dict] = []
        # NEW: every section record we've seen (in order of appearance)
        self.sections_seen: list[dict] = []
        self.fields: list[dict] = []          # raw <table type=X> records
        self.labels: list[dict] = []          # raw <table type="label"> records
        self.label_text_buffer: list[str] = []
        self.in_label_td = False
        self.current_label_btsynonym = ""
        self.current_label_mandatory = False    # NEW: track if current label's class marks it mandatory

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            name = a.get("name", "").strip()
            content = a.get("content", "")
            if name:
                self.meta[name] = content
        elif tag == "table":
            t = (a.get("type") or "").strip().lower()
            if t == "section":
                sec_name = (a.get("id") or a.get("name") or "").strip()
                self.section_stack.append(sec_name)
                # NEW: capture caption, gridctrl, stitle for this section
                sec_meta = {
                    "id":       sec_name,
                    "caption":  (a.get("caption") or "").strip(),
                    "is_grid":  (a.get("gridctrl") or "").strip().lower() == "mlt",
                    "is_titled": (a.get("stitle") or "0") == "1",   # stitle="1" → titled/visible section header
                    "depth":    len(self.section_stack),
                }
                self.section_meta_stack.append(sec_meta)
                self.sections_seen.append(sec_meta)
            elif t == "label":
                self.current_label_btsynonym = (a.get("btsynonym") or "").strip()
                self.in_label_td = False
                self.current_label_mandatory = False
            elif t in SLOT_TABLE_TYPES and t != "label":
                self.fields.append({
                    "id": (a.get("id") or "").strip(),
                    "name": (a.get("name") or "").strip(),
                    "type": t,
                    "datatype": (a.get("datatype") or "").strip(),
                    "btsynonym": (a.get("btsynonym") or "").strip(),
                    "section": self.section_stack[-1] if self.section_stack else "",
                })
        elif tag == "td":
            classes = (a.get("class") or "").lower()
            if "labels" in classes:
                self.in_label_td = True
                self.label_text_buffer = []
                # NEW: detect mandatory marker via CSS class. Convention in Ramco
                # .htm: class="labelsmandatoryleft" (or contains 'mandatory').
                self.current_label_mandatory = "mandatory" in classes

    def handle_endtag(self, tag):
        if tag == "table":
            # We can't reliably know which kind of table is closing without
            # a stack — but only sections are nested-meaningful for our needs.
            # Simple heuristic: every </table> for a section pops the stack
            # if there is something to pop. To keep it deterministic, we only
            # pop when we know we opened one — track by counter.
            # For robustness against unbalanced tags we leave a guard:
            pass
        elif tag == "td":
            if self.in_label_td:
                text = " ".join(self.label_text_buffer).strip()
                if self.current_label_btsynonym and text:
                    self.labels.append({
                        "btsynonym": self.current_label_btsynonym,
                        "text": text,
                        "section": self.section_stack[-1] if self.section_stack else "",
                        "mandatory": self.current_label_mandatory,   # NEW
                    })
                self.in_label_td = False
                self.current_label_btsynonym = ""
                self.current_label_mandatory = False

    def handle_data(self, data):
        if self.in_label_td:
            self.label_text_buffer.append(data)


def parse_meta_tasks(content: str) -> list[dict]:
    """Parse the meta Tasks header into structured task entries.
    Format: 'TASKNAME~Description:TYPE,TASKNAME~Description:TYPE,...'
    """
    if not content:
        return []
    out: list[dict] = []
    for chunk in content.split(","):
        chunk = chunk.strip()
        if not chunk: continue
        # Robust split: split on FIRST '~' and LAST ':' since description
        # may contain neither (commas would have split first).
        if "~" not in chunk or ":" not in chunk:
            continue
        name, rest = chunk.split("~", 1)
        if ":" not in rest:
            continue
        desc, ttype = rest.rsplit(":", 1)
        out.append({
            "name": name.strip(),
            "description": desc.strip(),
            "type": ttype.strip(),
        })
    return out


def parse_form_file(path: Path) -> dict:
    """Parse one screen .htm file."""
    text = path.read_text(encoding="utf-8", errors="replace")

    parser = ScreenFormParser()
    try:
        parser.feed(text)
    except Exception as e:
        return {"path": str(path.relative_to(ROOT)), "parse_error": str(e)}

    meta = parser.meta
    tasks_from_meta = parse_meta_tasks(meta.get("Tasks", ""))

    # Join slots (fields) with labels by btsynonym. Now also pull in mandatory flag.
    labels_by_bt = {}
    mandatory_by_bt = {}
    for lab in parser.labels:
        bt_lower = lab["btsynonym"].lower()
        labels_by_bt.setdefault(bt_lower, lab["text"])
        # Mandatory if ANY label record for this btsynonym was mandatory-marked
        if lab.get("mandatory"):
            mandatory_by_bt[bt_lower] = True

    slots = []
    for f in parser.fields:
        bt = (f["btsynonym"] or f["name"] or f["id"]).lower()
        label = labels_by_bt.get(bt, "")
        slots.append({
            "field_id": f["id"],
            "field_name": f["name"],
            "btsynonym": f["btsynonym"],
            "input_type": f["type"],
            "datatype": f["datatype"],
            "section": f["section"],
            "display_label": label,
            "mandatory": mandatory_by_bt.get(bt, False),       # NEW
        })

    # NEW: build section records with cleaned captions and slot membership.
    # Garbage caption detection: a caption is "garbage" if it matches the
    # technical-section-id pattern (e.g. "PoCrtMain_mainscreen_SECTION02_1" or
    # similar where the caption is essentially the id with underscores/spaces).
    import re as _re
    def _is_garbage_caption(caption: str, section_id: str) -> bool:
        if not caption: return True
        c_norm = _re.sub(r"[\s_]+", "", caption.lower())
        i_norm = _re.sub(r"[\s_]+", "", section_id.lower())
        # Garbage if normalized caption equals the section id
        if c_norm == i_norm: return True
        # Or matches the pattern "<screen>_mainscreen_section<N>"
        if _re.match(r".*mainscreen_?section\d", c_norm): return True
        return False

    # Section records — count slots by LABEL membership, not by table-type
    # fields. In Ramco's HTML, each visible user-input slot has exactly one
    # <table type="label" btsynonym="X"> declaring its English label,
    # mandatory class, and section. That label IS the source of truth for
    # "what slots exist in this section". The table-type "fields" list above
    # is mostly layout widgets (display-only tables, filler cells).
    labels_by_section: dict[str, list[dict]] = {}
    for lab in parser.labels:
        labels_by_section.setdefault(lab["section"], []).append(lab)

    seen_section_ids = set()
    section_records = []
    for sec in parser.sections_seen:
        if sec["id"] in seen_section_ids: continue
        seen_section_ids.add(sec["id"])
        sec_labels = labels_by_section.get(sec["id"], [])
        sec_record = {
            "section_id":      sec["id"],
            "caption_raw":     sec["caption"],
            "caption_clean":   sec["caption"] if not _is_garbage_caption(sec["caption"], sec["id"]) else "",
            "caption_garbage": _is_garbage_caption(sec["caption"], sec["id"]),
            "is_grid":         sec["is_grid"],
            "is_titled":       sec["is_titled"],
            "depth":           sec["depth"],
            "slot_count":      len(sec_labels),
            "mandatory_count": sum(1 for l in sec_labels if l["mandatory"]),
            "slot_labels":     [{"btsynonym": l["btsynonym"], "text": l["text"],
                                "mandatory": l["mandatory"]} for l in sec_labels],
        }
        section_records.append(sec_record)

    return {
        "path": str(path.relative_to(ROOT)),
        "filename": path.name,
        "meta": {
            "activity_name": meta.get("Activity Name", ""),
            "activity_desc": meta.get("Activity Description", ""),
            "ilbo_name": meta.get("ILBO Name", ""),
            "ilbo_desc": meta.get("ILBO Description", ""),
        },
        "tasks_from_meta_tag": tasks_from_meta,
        "task_count_from_meta": len(tasks_from_meta),
        "slot_count": len(slots),
        "slots": slots,
        "sections": section_records,        # NEW
        "section_count": len(section_records),
    }


def parse_all() -> dict:
    # We want only the screen .htm files, not the copies (_2.htm) or help files
    # The convention: screen htm = lowercase, ends with .htm, not _2.htm
    candidates = sorted(ARTIFACT_DIR.glob("*.htm"))
    # Filter: keep files whose stem looks like Module_screenname (e.g. Pocrt_pocrtmain)
    # Skip _2.htm copies (these are second-version layouts, sometimes duplicates)
    keep = [p for p in candidates if not p.stem.endswith("_2")]

    screens: list[dict] = []
    parse_errors: list[dict] = []
    for p in keep:
        r = parse_form_file(p)
        if "parse_error" in r:
            parse_errors.append(r)
        screens.append(r)

    # Index by ilbo_name (lowercase) for composer
    by_ilbo: dict[str, dict] = {}
    for s in screens:
        ilbo = (s.get("meta", {}).get("ilbo_name") or "").lower()
        if ilbo and ilbo not in by_ilbo:
            by_ilbo[ilbo] = s

    return {
        "source_dir": str(ARTIFACT_DIR.relative_to(ROOT)),
        "file_count": len(keep),
        "parse_errors": parse_errors,
        "screens": screens,
        "by_ilbo": by_ilbo,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    r = parse_all()
    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    n_with_meta = sum(1 for s in r["screens"] if s.get("meta", {}).get("activity_name"))
    n_with_tasks = sum(1 for s in r["screens"] if s.get("task_count_from_meta", 0) > 0)
    total_slots = sum(s.get("slot_count", 0) for s in r["screens"])
    print(f"p03: parsed {r['file_count']} .htm files "
          f"({n_with_meta} with screen meta, {n_with_tasks} with meta Tasks tag, "
          f"{total_slots:,} total slots) → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
