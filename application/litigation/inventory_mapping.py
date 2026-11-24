"""Resolve "Pièce n°" / "Stuk nr." mentions against the CONFIRMED inventory of the matter.

A coverage aid, not evidence review. The inventory identities (label, number, bound
source version, page mappings) come from the human-confirmed intake record and are
passed through untouched: this module never invents a number, never normalizes
"03" to "3", never maps across labels and never compares exhibit content to the
brief. A located reference stays UNDETERMINED ("located, content not compared").
Anything unconfirmed, unbound, ambiguous or in a page space the brief does not name
stays UNDETERMINED with its reason.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from application.litigation.exhibit_coverage import R_PAGE, R_RANGE, find_references
from application.litigation.rule_results import RuleStatus

M_LOCATED = "piece_located_in_confirmed_inventory_content_not_compared"
M_NOT_CONFIRMED = "inventory_not_confirmed_no_mapping"
M_OTHER_DRAFT = "inventory_confirmed_for_another_draft_no_mapping"
M_ABSENT = "piece_number_absent_from_confirmed_complete_inventory"
M_ABSENT_OPEN = "piece_number_absent_inventory_not_declared_complete"
M_AMBIGUOUS = "piece_number_matches_several_inventory_entries"
M_LABEL = "piece_number_found_only_under_other_label_no_mapping"
M_UNBOUND = "inventory_entry_has_no_bound_source_file"
M_SOURCE_UNKNOWN = "inventory_entry_source_not_among_matter_sources"
M_INTEGRITY = "inventory_entry_source_failed_readback_integrity"
M_NOTATION = "piece_number_notation_not_matched_exactly_no_mapping"
MAPPING_REASONS = frozenset({
    M_LOCATED, M_NOT_CONFIRMED, M_OTHER_DRAFT, M_ABSENT, M_ABSENT_OPEN, M_AMBIGUOUS, M_LABEL,
    M_UNBOUND, M_SOURCE_UNKNOWN, M_INTEGRITY, M_NOTATION, R_PAGE, R_RANGE})

_EXACT = re.compile(r"^\d{1,4}(?:bis|ter)?$")


def map_exhibit_references(
    text: str,
    *,
    brief_version_id: str,
    intake: Mapping[str, Any],
) -> dict[str, Any]:
    """`intake` is an IntakeView dump: entries, sources, confirmation_id, brief_id, inventory_complete."""
    entries: Sequence[Mapping[str, Any]] = intake.get("entries") or []
    sources = {s["version_id"]: s for s in intake.get("sources") or []}
    confirmed = bool(intake.get("confirmation_id"))
    same_draft = intake.get("brief_id") == brief_version_id
    complete = bool(intake.get("inventory_complete")) and confirmed and same_draft
    rows: list[dict[str, Any]] = []
    cited: set[tuple[str, str]] = set()
    for n, ref in enumerate(find_references(text), start=1):
        family = "stuk" if ref["word"] == "Stuk" else "piece"
        number = ref["number"]
        entry: Mapping[str, Any] | None = None
        if not confirmed:
            status, reason = RuleStatus.UNDETERMINED, M_NOT_CONFIRMED
        elif not same_draft:
            status, reason = RuleStatus.UNDETERMINED, M_OTHER_DRAFT
        elif ref["reason"]:
            status, reason = RuleStatus.UNDETERMINED, ref["reason"]
        elif not _EXACT.match(number) or number[0] == "0":
            status, reason = RuleStatus.UNDETERMINED, M_NOTATION
        else:
            same_number = [e for e in entries if e["number"] == number]
            exact = [e for e in same_number if e["label"] == family]
            if len(exact) > 1 or (not exact and len({e["label"] for e in same_number}) > 1):
                status, reason = RuleStatus.UNDETERMINED, M_AMBIGUOUS
            elif not exact and same_number:
                status, reason = RuleStatus.UNDETERMINED, M_LABEL
            elif not exact:
                status, reason = ((RuleStatus.UNVERIFIED, M_ABSENT) if complete
                                  else (RuleStatus.UNDETERMINED, M_ABSENT_OPEN))
            else:
                entry = exact[0]
                cited.add((entry["label"], entry["number"]))
                source = sources.get(entry.get("source_version_id") or "")
                if not entry.get("source_version_id"):
                    status, reason = RuleStatus.UNDETERMINED, M_UNBOUND
                elif source is None:
                    status, reason = RuleStatus.UNDETERMINED, M_SOURCE_UNKNOWN
                elif source.get("readback") == "integrity_mismatch":
                    status, reason = RuleStatus.UNDETERMINED, M_INTEGRITY
                elif ref["page"]:
                    status, reason = RuleStatus.UNDETERMINED, R_PAGE
                else:
                    status, reason = RuleStatus.UNDETERMINED, M_LOCATED
        source = sources.get((entry or {}).get("source_version_id") or "")
        rows.append({
            "reference_id": f"exhibit-ref-{n:02d}",
            "raw_text": f"{ref['word']} {ref['number']}",
            "start": ref["start"], "end": ref["end"],
            "status": str(status), "reason": reason, "page_cited": bool(ref["page"]),
            "entry": None if entry is None else {
                "label": entry["label"], "number": entry["number"],
                "source_version_id": entry.get("source_version_id"),
                "filename": None if source is None else source["filename"],
                "sha256": None if source is None else source["sha256"],
                "readback": None if source is None else source["readback"],
                "page_count": None if source is None else source.get("page_count"),
                "pages": [{"space": p["space"], "label": p["label"], "pdf_page": p["pdf_page"]}
                          for p in entry.get("pages") or []],
            },
        })
    uncited = [f"{e['label']} {e['number']}" for e in entries if (e["label"], e["number"]) not in cited]
    return {
        "inventory_confirmed": confirmed and same_draft,
        "inventory_complete": complete,
        "confirmation_id": intake.get("confirmation_id"),
        "references": rows,
        "coverage": {
            "detected": len(rows),
            "by_status": {s: sum(1 for r in rows if r["status"] == s)
                          for s in ("PASS", "FAIL", "UNVERIFIED", "UNDETERMINED")},
            "located": sum(1 for r in rows if r["reason"] == M_LOCATED),
            "inventory_entries": len(entries),
            "entries_not_detected_in_brief": uncited,
        },
    }
