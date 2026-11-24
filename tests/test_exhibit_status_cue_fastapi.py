"""Tests for BE-02: targeted lexical status-cue flag ('signé' vs 'envoyé pour signature')
wired through application.litigation.inventory_mapping and the FastAPI exhibit-references contract.
"""
from __future__ import annotations

from dataclasses import dataclass

from application.litigation.inventory_mapping import map_exhibit_references
from application.litigation.workspace_contract import ExhibitReferencesView


@dataclass(frozen=True)
class _Row:
    version_id: str
    status: str = "ready"
    warnings: tuple[str, ...] = ()
    representation_id: str | None = "rep-1"


@dataclass(frozen=True)
class _Preview:
    row: _Row
    text: str
    spans: tuple[tuple[int, int, str, int | None], ...] = ()


def _intake(*, confirmed: bool = True, readback: str = "verified") -> dict:
    return {
        "brief_id": "brief-1",
        "confirmation_id": "conf-1" if confirmed else None,
        "inventory_complete": confirmed,
        "entries": [
            {
                "label": "piece",
                "number": "1",
                "source_version_id": "ver-1",
                "pages": [{"space": "printed", "label": "4", "pdf_page": 1}],
            },
            {
                "label": "stuk",
                "number": "2",
                "source_version_id": "ver-2",
                "pages": [{"space": "printed", "label": "1", "pdf_page": 1}],
            },
        ],
        "sources": [
            {
                "version_id": "ver-1",
                "filename": "piece_1_contrat.pdf",
                "sha256": "a" * 64,
                "readback": readback,
                "page_count": 3,
            },
            {
                "version_id": "ver-2",
                "filename": "stuk_2_overeenkomst.pdf",
                "sha256": "b" * 64,
                "readback": readback,
                "page_count": 2,
            },
        ],
    }


def test_fr_signed_vs_pending_surfaces_appraisal_flag_without_changing_status() -> None:
    brief = "Le contrat a été signé le 12 mars 2026 (Pièce 1)."
    source_text = "Objet : projet de contrat envoyé pour signature le 12 mars 2026."
    previews = [
        _Preview(
            row=_Row(version_id="ver-1"),
            text=source_text,
            spans=((0, len(source_text), "pdf_page", 0),),
        )
    ]

    mapped = map_exhibit_references(
        brief, brief_version_id="brief-1", intake=_intake(), previews=previews
    )
    view = ExhibitReferencesView.model_validate({
        "schema": "caseproof-exhibit-references-v1",
        "brief_version_id": "brief-1",
        "snapshot_hash": "c" * 64,
        "note": "Inventory mapping test.",
        **mapped,
    })

    assert len(view.references) == 1
    ref = view.references[0]
    assert ref.status == "UNDETERMINED"
    assert ref.status_cue_flag is not None
    assert ref.status_cue_flag.claim_cue == "signé"
    assert ref.status_cue_flag.passage_cue == "pour signature"
    assert ref.status_cue_flag.matched_value_key == "date:2026-03-12"
    assert ref.status_cue_flag.pdf_page == 1


def test_nl_ondertekend_vs_ter_ondertekening_surfaces_flag() -> None:
    brief = "De overeenkomst werd ondertekend op 12 maart 2026 (Stuk 2)."
    source_text = "Gelieve het ontwerp ter ondertekening terug te vinden op 12 maart 2026."
    previews = [_Preview(row=_Row(version_id="ver-2"), text=source_text)]

    mapped = map_exhibit_references(
        brief, brief_version_id="brief-1", intake=_intake(), previews=previews
    )
    ref = mapped["references"][0]
    assert ref["status"] == "UNDETERMINED"
    assert ref["status_cue_flag"] is not None
    assert ref["status_cue_flag"]["claim_cue"] == "ondertekend"
    assert ref["status_cue_flag"]["passage_cue"] == "ter ondertekening"


def test_abstains_on_negation_unreadable_preview_and_unconfirmed_inventory() -> None:
    source_text = "Contrat envoyé pour signature le 12 mars 2026."

    # 1. Negation in brief -> abstain
    neg_brief = "Le contrat n'a pas été signé le 12 mars 2026 (Pièce 1)."
    res_neg = map_exhibit_references(
        neg_brief,
        brief_version_id="brief-1",
        intake=_intake(),
        previews=[_Preview(row=_Row(version_id="ver-1"), text=source_text)],
    )
    assert res_neg["references"][0]["status_cue_flag"] is None

    # 2. Warned / OCR-unreliable preview -> abstain
    pos_brief = "Le contrat a été signé le 12 mars 2026 (Pièce 1)."
    res_warn = map_exhibit_references(
        pos_brief,
        brief_version_id="brief-1",
        intake=_intake(),
        previews=[
            _Preview(
                row=_Row(version_id="ver-1", warnings=("ocr_low_confidence",)),
                text=source_text,
            )
        ],
    )
    assert res_warn["references"][0]["status_cue_flag"] is None

    # 3. Unconfirmed inventory -> abstain
    res_unconf = map_exhibit_references(
        pos_brief,
        brief_version_id="brief-1",
        intake=_intake(confirmed=False),
        previews=[_Preview(row=_Row(version_id="ver-1"), text=source_text)],
    )
    assert res_unconf["references"][0]["status_cue_flag"] is None


def test_omitted_opening_reservation_cue_surfaces_in_exhibit_references_view() -> None:
    brief = "Le bail prévoit que « le locataire peut céder son droit au bail » (Pièce 1)."
    source_text = (
        "Article 8. Sous réserve de l'accord écrit du bailleur, "
        "le locataire peut céder son droit au bail."
    )
    previews = [
        _Preview(
            row=_Row(version_id="ver-1"),
            text=source_text,
            spans=((0, len(source_text), "pdf-page-1", 0),),
        )
    ]

    mapped = map_exhibit_references(
        brief, brief_version_id="brief-1", intake=_intake(), previews=previews
    )
    validated = ExhibitReferencesView.model_validate(
        {
            "schema": "caseproof-exhibit-references-v1",
            "brief_version_id": "brief-1",
            "snapshot_hash": "b" * 64,
            "note": "Located never means content verified.",
            **mapped,
        }
    )
    ref = validated.references[0]
    assert ref.status == "UNDETERMINED"
    assert ref.reservation_cue_flag is not None
    assert "sous réserve" in ref.reservation_cue_flag.reservation_cue.casefold()
    assert "accord écrit" in ref.reservation_cue_flag.omitted_source_prefix
    assert ref.reservation_cue_flag.pdf_page == 1

    # When the draft quote preserves the opening reservation, do NOT false-alarm.
    clean_brief = (
        "Le bail prévoit que « Sous réserve de l'accord écrit du bailleur, "
        "le locataire peut céder son droit au bail » (Pièce 1)."
    )
    clean_mapped = map_exhibit_references(
        clean_brief, brief_version_id="brief-1", intake=_intake(), previews=previews
    )
    assert clean_mapped["references"][0]["reservation_cue_flag"] is None
