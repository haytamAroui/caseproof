"""M1/M2 negative boundaries: incomplete inventory and crop cannot become proof.

The legacy discovery is explicitly NOT the canonical verifier. The canonical
signed report is tested separately; these tests prevent the secondary route
from making stronger claims than its inputs allow.
"""
from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from apps.api.litigation_headless_verification import discover

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx(text: str) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{WORD_NS}"><w:body><w:p><w:r><w:t>'
            f'{text}</w:t></w:r></w:p></w:body></w:document>',
        )
    return out.getvalue()


def test_empty_candidate_inventory_is_unknown_not_proven_missing() -> None:
    result = discover(docx("Zie Stuk 99"), [])
    finding = result["findings"][0]
    assert finding["identity"] == "not_assessed"
    assert finding["identity_reason"] == "INVENTORY_SCOPE_UNCONFIRMED"
    assert finding["source_id"] is None
    assert finding["page_mapping"] == "page_unmapped"
    assert not result["inventory_completeness_confirmed"]
    assert not result["strong_identity_assessment_available"]


def test_candidate_inventory_match_is_not_signed_resolution() -> None:
    entries = [{"label": "Stuk", "number": "12", "source_id": "src-1",
                "version_id": "v1", "source_sha256": "a" * 64}]
    finding = discover(docx("Stuk 12"), entries)["findings"][0]
    assert finding["candidate_source_match"] is True
    assert finding["identity"] == "not_assessed"
    assert finding["identity_reason"] == "INVENTORY_UNCONFIRMED"
    assert finding["support"] == finding["fidelity"] == "not_assessed"


def test_duplicate_candidate_labels_are_ambiguous_not_absent() -> None:
    entries = [{"label": "Pièce", "number": "4", "source_id": f"source-{n}",
                "version_id": "v1"} for n in range(2)]
    finding = discover(docx("Pièce 4"), entries)["findings"][0]
    assert finding["identity"] == "ambiguous"
    assert finding["ambiguous_manifest"] is True
    assert finding["identity_reason"] == "DUPLICATE_CANDIDATE_LABEL"
    assert finding["source_id"] is None


def test_crop_does_not_certify_pdf_page_or_text_fidelity() -> None:
    crop = {"page_number": 3, "left": 0, "top": 0, "width": 100, "height": 100}
    entries = [{"label": "Stuk", "number": "1", "source_id": "s",
                "version_id": "v", "ocr_crop": crop}]
    finding = discover(docx("Stuk 1"), entries)["findings"][0]
    assert finding["pdf_page"] is None
    assert finding["candidate_crop_pdf_page"] == 3
    assert finding["page_mapping"] == "page_unmapped"
    assert finding["fidelity"] == "not_assessed"
    assert finding["support"] == "not_assessed"
    assert finding["ocr_crop"] == crop


def test_malformed_crop_never_generates_verified_page() -> None:
    entries = [{"label": "Stuk", "number": "1", "source_id": "s",
                "version_id": "v", "ocr_crop": "corrupt"}]
    finding = discover(docx("Stuk 1"), entries)["findings"][0]
    assert finding["pdf_page"] is None
    assert finding["candidate_crop_pdf_page"] is None
    assert finding["page_mapping"] == "page_unmapped"


def test_legacy_discovery_never_claims_canonical_verification() -> None:
    result = discover(docx("Stuk 1 en Pièce 2"), [])
    assert result["canonical_verification"] is False
    assert result["legacy_discovery"] is True
    assert result["recognition_coverage_complete"] is False
    assert all(f["identity"] == "not_assessed" for f in result["findings"])
