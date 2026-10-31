"""Real-format M1/M2 intake and reference coverage on frozen fictional M0 inputs.

Exercises real bounded Linux parser and original-byte SHA-256. This is a
DISPOSABLE, unsigned integration check, not live Auth or customer approval.
"""
from __future__ import annotations

from hashlib import sha256

import pytest

from apps.api.signed_document_parse import parse_verified_original
from infrastructure.parsers.docx_reference_discovery import discover_docx_references
from scripts.m0_real_format_fixtures import generate

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(scope="module")
def material(tmp_path_factory):
    base = tmp_path_factory.mktemp("m1-m2-synthetic-originals")
    manifest = generate(base)
    return base, {case["id"]: case for case in manifest["cases"]}


@pytest.mark.parametrize(
    ("case_id", "expected_label"),
    [
        ("NL_OFFSET_21", "stuk"),
        ("FR_CLEAN_25", "pièce"),
        ("MIX_TRANSLATION_32", "pièce"),
    ],
)
def test_actual_docx_references_are_scanned_but_recall_is_unproven(
    material, case_id, expected_label,
):
    base, _cases = material
    raw = (base / case_id / "conclusions.docx").read_bytes()
    assert raw[:2] == b"PK"
    found = discover_docx_references(raw)
    assert any(ref.label.casefold() == expected_label for ref in found.references)
    # Real python-docx files include Word settings/style story parts that the
    # conservative inventory does NOT silently count as scanned text.
    assert found.region_manifest["regions_scanned"] >= 1
    assert not found.text_coverage_complete
    assert found.unscanned_parts
    assert not found.coverage_complete  # DOCX parsing != full reference recall
    text, manifest = parse_verified_original(
        document_id="synthetic-docx-" + case_id,
        version_id="v1",
        data=raw,
        media_type=DOCX_MEDIA,
    )
    assert sha256(raw).hexdigest() == manifest["original_sha256"]
    assert case_id in text or expected_label in text.casefold()
    assert manifest["page_mapping"] == "unverified"  # never invent DOCX PDF pages
    assert manifest["parser_id"]


@pytest.mark.parametrize("case_id", ["NL_OFFSET_21", "FR_CLEAN_25", "EN_CLEAN_30"])
def test_actual_text_pdf_has_preserved_byte_and_physical_page_lineage(material, case_id):
    base, cases = material
    source = next(s for s in cases[case_id]["sources"] if not s["image_only"])
    raw = (base / source["path"]).read_bytes()
    assert raw.startswith(b"%PDF-")
    text, parsed = parse_verified_original(
        document_id="synthetic-pdf-" + case_id,
        version_id="v1",
        data=raw,
        media_type="application/pdf",
    )
    assert parsed["original_sha256"] == sha256(raw).hexdigest()
    assert len(parsed["pages"]) == source["pdf_page"]
    assert parsed["page_mapping"] == "pdf_physical_page"
    assert parsed["pages"][source["pdf_page"] - 1]["status"] in (
        "text_extracted", "needs_visual_review",
    )
    assert "CaseProof M0" in text


@pytest.mark.parametrize("case_id", ["NL_SCAN_23", "FR_CLEAN_25", "EN_SCAN_37"])
def test_image_only_source_never_claims_full_fidelity_without_ocr(material, case_id):
    base, cases = material
    source = next(s for s in cases[case_id]["sources"] if s["image_only"])
    raw = (base / source["path"]).read_bytes()
    _text, parsed = parse_verified_original(
        document_id="synthetic-scan-" + case_id,
        version_id="v1",
        data=raw,
        media_type="application/pdf",
    )
    assert parsed["original_sha256"] == sha256(raw).hexdigest()
    assert parsed["complete"] is False
    assert parsed["coverage"] == "partial"
    assert len(parsed["pages"]) == source["pdf_page"]
    assert any(p["status"] in ("needs_ocr", "needs_visual_review") for p in parsed["pages"])
    assert "ocr_candidates" not in parsed  # no OCR worker was configured
