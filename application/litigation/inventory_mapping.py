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
from application.litigation.exhibit_passages import (
    MAX_EXCERPT,
    _claim,
    _sentences,
    status_mismatch,
)
from application.litigation.factual_values import typed_values
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
_QUOTE_RE = re.compile(r"(?:«\s*([^«»\n]{12,400}?)\s*»|\"([^\"\n]{12,400}?)\")")
_OPENING_RESERVATION_RE = re.compile(
    r"\b(?:sous\s+r[ée]serve(?:\s+de)?|onder\s+voorbehoud(?:\s+van)?|behoudens|"
    r"sauf\s+(?:accord|stipulation|convention)|hormis\s+les\s+cas|"
    r"[àa]\s+l['’]exception\s+de|subject\s+to)\b",
    re.IGNORECASE,
)


def _detect_reservation_cue_flag(
    text: str,
    start: int,
    end: int,
    preview: Any,
) -> dict[str, Any] | None:
    """Detect an opening reservation clause omitted immediately before a matched quote.

    Strictly an appraisal cue (! Appréciation requise): never changes exhibit
    mapping status and never asserts general semantic verification.
    """
    if not _readable_preview(preview):
        return None
    sentence, _values = _claim(text, start, end)
    spans = getattr(preview, "spans", ()) or ()
    source_text = preview.text
    source_folded = source_text.casefold()
    for match in _QUOTE_RE.finditer(sentence):
        quote = (match.group(1) or match.group(2) or "").strip()
        if len(quote) < 12 or _OPENING_RESERVATION_RE.search(quote) is not None:
            continue
        idx = source_folded.find(quote.casefold())
        if idx <= 0:
            continue
        prefix_lo = max(0, idx - 120)
        # Keep the check within the immediately preceding clause/sentence.
        prefix_raw = source_text[prefix_lo:idx]
        last_break = max(prefix_raw.rfind("\n"), prefix_raw.rfind(". "))
        if last_break >= 0:
            prefix_raw = prefix_raw[last_break + 1 :]
        prefix = " ".join(prefix_raw.split()).strip()
        cue = _OPENING_RESERVATION_RE.search(prefix)
        if cue is not None:
            excerpt_hi = min(len(source_text), idx + len(quote) + 60)
            excerpt = " ".join(source_text[max(0, idx - len(prefix_raw)) : excerpt_hi].split())[
                :MAX_EXCERPT
            ]
            return {
                "reservation_cue": cue.group(0),
                "draft_quote": quote[:MAX_EXCERPT],
                "omitted_source_prefix": prefix[:MAX_EXCERPT],
                "source_excerpt": excerpt,
                "pdf_page": _page_at(spans, idx),
            }
    return None


def _readable_preview(preview: Any) -> bool:
    row = getattr(preview, "row", None)
    return bool(
        row is not None
        and getattr(row, "status", None) == "ready"
        and not getattr(row, "warnings", None)
        and getattr(row, "representation_id", None)
        and isinstance(getattr(preview, "text", None), str)
        and preview.text.strip()
    )


def _page_at(spans: Sequence[Sequence[Any]], pos: int) -> int | None:
    for lo, hi, _kind, page0 in spans:
        if lo <= pos < hi and page0 is not None:
            return int(page0) + 1
    return None


def _detect_status_cue_flag(
    text: str,
    start: int,
    end: int,
    preview: Any,
) -> dict[str, Any] | None:
    """Targeted FR/NL lexical flag ('signé' vs 'envoyé pour signature').

    Strictly an appraisal cue on readable source text sharing a normalized typed
    value (date/amount). Never changes status to PASS/FAIL and never claims
    general semantic verification.
    """
    if not _readable_preview(preview):
        return None
    sentence, values = _claim(text, start, end)
    keys = sorted({v["key"] for v in values if v["key"]})
    if not keys:
        return None
    spans = getattr(preview, "spans", ()) or ()
    for key in keys:
        for lo, hi in _sentences(preview.text):
            chunk = preview.text[lo:hi]
            if key not in {k for *_x, k in typed_values(chunk)}:
                continue
            excerpt = " ".join(chunk.split())[:MAX_EXCERPT]
            mismatch = status_mismatch(sentence, excerpt)
            if mismatch is not None:
                return {
                    "claim_cue": mismatch["claim_cue"],
                    "passage_cue": mismatch["passage_cue"],
                    "claim_excerpt": sentence[:MAX_EXCERPT],
                    "source_excerpt": excerpt,
                    "matched_value_key": key,
                    "pdf_page": _page_at(spans, lo),
                }
    return None


def map_exhibit_references(
    text: str,
    *,
    brief_version_id: str,
    intake: Mapping[str, Any],
    previews: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """`intake` is an IntakeView dump: entries, sources, confirmation_id, brief_id, inventory_complete."""
    entries: Sequence[Mapping[str, Any]] = intake.get("entries") or []
    sources = {s["version_id"]: s for s in intake.get("sources") or []}
    previews_by_version = {
        getattr(getattr(p, "row", None), "version_id", None): p
        for p in (previews or ())
        if getattr(getattr(p, "row", None), "version_id", None)
    }
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
        version_id = (entry or {}).get("source_version_id")
        cue_flag = (
            _detect_status_cue_flag(
                text, ref["start"], ref["end"], previews_by_version.get(version_id)
            )
            if (
                entry is not None
                and source is not None
                and source.get("readback") != "integrity_mismatch"
                and version_id in previews_by_version
            )
            else None
        )
        reservation_flag = (
            _detect_reservation_cue_flag(
                text, ref["start"], ref["end"], previews_by_version.get(version_id)
            )
            if (
                entry is not None
                and source is not None
                and source.get("readback") != "integrity_mismatch"
                and version_id in previews_by_version
            )
            else None
        )
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
            "status_cue_flag": cue_flag,
            "reservation_cue_flag": reservation_flag,
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
