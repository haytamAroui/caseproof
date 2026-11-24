"""Exhibit mentions resolve only against a confirmed inventory. Pure logic: no I/O, no auth, no storage."""
from __future__ import annotations

from application.litigation.inventory_mapping import (
    M_ABSENT,
    M_ABSENT_OPEN,
    M_AMBIGUOUS,
    M_INTEGRITY,
    M_LABEL,
    M_LOCATED,
    M_NOT_CONFIRMED,
    M_NOTATION,
    M_OTHER_DRAFT,
    M_UNBOUND,
    map_exhibit_references,
)

V1, V2 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
SRC = {"version_id": V1, "filename": "p1.pdf", "sha256": "a" * 64, "readback": "verified", "page_count": 4}


def intake(entries, *, confirmed=True, complete=True, brief="b1", sources=(SRC,)):
    return {"entries": entries, "sources": list(sources), "confirmation_id": "c1" if confirmed else None,
            "brief_id": brief, "inventory_complete": complete}


E1 = {"label": "piece", "number": "1", "source_version_id": V1,
      "pages": [{"space": "printed", "label": "iv", "pdf_page": 2, "rationale": "x"}]}


def run(text, data):
    return map_exhibit_references(text, brief_version_id="b1", intake=data)


def reasons(out):
    return [(r["raw_text"], r["status"], r["reason"]) for r in out["references"]]


def test_located_keeps_identity_and_page_spaces_and_stays_undetermined():
    out = run("Voir Pièce 1.", intake([E1]))
    assert reasons(out) == [("Pièce 1", "UNDETERMINED", M_LOCATED)]
    entry = out["references"][0]["entry"]
    assert (entry["source_version_id"], entry["sha256"], entry["filename"]) == (V1, "a" * 64, "p1.pdf")
    assert entry["pages"] == [{"space": "printed", "label": "iv", "pdf_page": 2}]
    assert out["coverage"]["by_status"]["PASS"] == 0 and out["coverage"]["located"] == 1


def test_nothing_maps_without_confirmation_or_for_another_draft():
    assert reasons(run("Pièce 1", intake([E1], confirmed=False)))[0][2] == M_NOT_CONFIRMED
    assert reasons(run("Pièce 1", intake([E1], brief="other")))[0][2] == M_OTHER_DRAFT
    assert all(r["entry"] is None for r in run("Pièce 1", intake([E1], confirmed=False))["references"])


def test_absent_is_unverified_only_for_confirmed_complete_inventory():
    assert reasons(run("Pièce 9", intake([E1])))[0][1:] == ("UNVERIFIED", M_ABSENT)
    assert reasons(run("Pièce 9", intake([E1], complete=False)))[0][1:] == ("UNDETERMINED", M_ABSENT_OPEN)


def test_no_number_invention():
    assert reasons(run("Pièce 01", intake([E1])))[0][2] == M_NOTATION
    assert reasons(run("Stuk 1", intake([E1])))[0][2] == M_LABEL
    dup = [E1, {**E1, "source_version_id": V2}]
    assert reasons(run("Pièce 1", intake(dup)))[0][2] == M_AMBIGUOUS
    assert reasons(run("Pièce 1", intake([{**E1, "source_version_id": None}])))[0][2] == M_UNBOUND


def test_integrity_mismatch_blocks_location_and_page_cite_is_not_resolved():
    bad = {**SRC, "readback": "integrity_mismatch"}
    assert reasons(run("Pièce 1", intake([E1], sources=(bad,))))[0][2] == M_INTEGRITY
    assert "page" in reasons(run("Pièce 1, p. 3", intake([E1])))[0][2]


def test_uncited_entries_are_listed_as_not_detected():
    out = run("Pièce 1", intake([E1, {**E1, "number": "2"}]))
    assert out["coverage"]["entries_not_detected_in_brief"] == ["piece 2"]
