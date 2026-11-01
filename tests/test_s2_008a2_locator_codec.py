"""S2-008a2 typed persistence boundary: no SQL, live Auth or approval path."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

from apps.api.evidence_locator_codec import (
    LOCATOR_SCHEMA_VERSION,
    ExpectedEvidenceParent,
    StoredLocatorError,
    decode_anchor_projection,
    decode_locator,
    encode_anchor_projection,
    encode_locator,
    validate_against_verified_bytes,
)
from packages.evidence_kernel.domain.anchors import (
    JSON_BASIS,
    PDF_BASIS,
    SHEET_BASIS,
    TEXT_BASIS,
    EvidenceAnchor,
    PdfLayout,
    PdfPage,
    PdfRegion,
    SheetRange,
    StructuredField,
    StructuredLayout,
    TextSpan,
    WorkbookLayout,
    WorkbookSheet,
)

ORIGINAL = b"Original supplier invoice"
UNICODE = "café 👩🏽‍💻 factuur"
SRC_HASH = hashlib.sha256(ORIGINAL).hexdigest()
TEXT_BYTES = UNICODE.encode("utf-8")
REP_HASH = hashlib.sha256(TEXT_BYTES).hexdigest()
ORG = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CASE = UUID("aaaaaaaa-1111-4111-8111-111111111111")


def parent(*, representation_id: str = "ocr-1") -> ExpectedEvidenceParent:
    return ExpectedEvidenceParent(
        org_id=ORG, case_id=CASE, document_id="invoice/doc-1",
        version_id="v1", representation_id=representation_id,
        source_sha256_hex=SRC_HASH, representation_sha256_hex=REP_HASH,
    )


def anchor(locator: TextSpan | PdfRegion | SheetRange | StructuredField,
           *, representation_id: str = "ocr-1",
           rep_hash: str = REP_HASH) -> EvidenceAnchor:
    return EvidenceAnchor(
        anchor_id="anchor:1", document_id="invoice/doc-1",
        version_id="v1", source_sha256_hex=SRC_HASH,
        representation_id=representation_id,
        representation_sha256_hex=rep_hash, locator=locator,
    )


LOCATORS = [
    TextSpan(start=0, end=4, encoding="utf-8", normalization="none"),
    PdfRegion(
        page_index=0, x0=Decimal("1.000010"), y0=Decimal("2.1"),
        x1=Decimal("25.000010"), y1=Decimal("40.0"),
        page_width=Decimal("595.00"), page_height=Decimal("842"),
        rotation=90,
    ),
    SheetRange(sheet_id="sheet-stable-id", a1_range="AA2:AC10", table_id="t-1"),
    StructuredField(schema_id="invoice-v3", path=("lines", 1, "total", 0)),
]


@pytest.mark.parametrize("locator", LOCATORS)
def test_lossless_locator_and_projection_jsonb_round_trip(locator: object) -> None:
    kind, version, payload = encode_locator(locator)  # type: ignore[arg-type]
    assert version == LOCATOR_SCHEMA_VERSION
    as_jsonb = json.loads(json.dumps(payload, ensure_ascii=False))
    assert decode_locator(kind, version, as_jsonb) == locator
    assert decode_locator(kind, version, json.dumps(payload)) == locator
    row = encode_anchor_projection(anchor(locator), parent())  # type: ignore[arg-type]
    as_db_row = json.loads(json.dumps(row))
    assert decode_anchor_projection(as_db_row, parent()) == anchor(locator)  # type: ignore[arg-type]
    assert set(as_db_row) == {
        "org_id", "case_id", "kernel_anchor_id", "kernel_document_id",
        "kernel_version_id", "kernel_representation_id",
        "source_sha256_hex", "representation_sha256_hex",
        "locator_kind", "locator_schema_version", "locator",
    }


def test_pdf_decimal_precision_never_serializes_as_float() -> None:
    kind, version, payload = encode_locator(LOCATORS[1])
    assert payload["x0"] == "1.000010"
    assert payload["x1"] == "25.000010"
    assert isinstance(payload["page_width"], str)
    assert decode_locator(kind, version, payload) == LOCATORS[1]
    for bad in (1.25, True, None, "NaN", "Infinity", "-1", "01.20", "1e10"):
        altered = {**payload, "x0": bad}
        with pytest.raises(StoredLocatorError):
            decode_locator(kind, version, altered)


@pytest.mark.parametrize(("kind", "payload"), [
    ("text_span", {"start": 0, "end": 1, "encoding": "utf-8"}),
    ("text_span", {"start": True, "end": 2, "encoding": "utf-8", "normalization": "none"}),
    ("text_span", {"start": 0, "end": 1, "encoding": "utf-8", "normalization": "none", "extra": 1}),
    ("text_span", {"start": 2, "end": 2, "encoding": "utf-8", "normalization": "none"}),
    ("sheet_range", {"sheet_id": "s", "a1_range": "A1:A2", "table_id": False}),
    ("structured_field", {"schema_id": "s", "path": ["key", True]}),
    ("structured_field", {"schema_id": "s", "path": [0, -1]}),
    ("structured_field", {"schema_id": "s", "path": ["", 1]}),
    ("structured_field", {"schema_id": "s", "path": []}),
    ("other", {}),
])
def test_invalid_locator_shapes_fail_closed(kind: str, payload: object) -> None:
    with pytest.raises(StoredLocatorError):
        decode_locator(kind, LOCATOR_SCHEMA_VERSION, payload)


def test_encoder_rejects_kernel_valid_but_nonrepresentable_locators() -> None:
    # Valid domain locations can still exceed the bounded persistence wire.
    huge = PdfRegion(
        page_index=0, x0=Decimal(0), y0=Decimal(0),
        x1=Decimal("1E+10000000"), y1=Decimal(1),
        page_width=Decimal("1E+10000000"), page_height=Decimal(10),
        rotation=0,
    )
    with pytest.raises(StoredLocatorError):
        encode_locator(huge)
    too_precise = replace(
        LOCATORS[1], x0=Decimal("1e-64"),
    )
    with pytest.raises(StoredLocatorError):
        encode_locator(too_precise)
    for invalid in (
        StructuredField("schema", ("field-" + "x" * 257,)),
        StructuredField("schema", tuple(range(129))),
        StructuredField("s" * 257, ("x",)),
        SheetRange(sheet_id="x" * 257, a1_range="A1"),
    ):
        with pytest.raises(StoredLocatorError):
            encode_locator(invalid)
    many_large_keys = StructuredField("schema", tuple("x" * 128 + str(i) for i in range(80)))
    with pytest.raises(StoredLocatorError):
        encode_locator(many_large_keys)


def test_unknown_version_duplicates_and_nonfinite_json_rejected() -> None:
    kind, version, payload = encode_locator(LOCATORS[0])
    with pytest.raises(StoredLocatorError):
        decode_locator(kind, "krn102-locator-v9", payload)
    with pytest.raises(StoredLocatorError):
        decode_locator(kind, version, '{"start":0,"start":1,"end":4,"encoding":"utf-8","normalization":"none"}')
    with pytest.raises(StoredLocatorError):
        decode_locator(kind, version, '{"start":NaN,"end":4,"encoding":"utf-8","normalization":"none"}')
    with pytest.raises(StoredLocatorError):
        decode_locator(kind, version, [])
    with pytest.raises(StoredLocatorError):
        decode_locator(kind, version, "{" + ("x" * 9000) + "}")


def test_opaque_representation_id_not_deduplicated_by_hash() -> None:
    a = encode_anchor_projection(anchor(LOCATORS[0], representation_id="ocr-1"), parent())
    b = encode_anchor_projection(
        anchor(LOCATORS[0], representation_id="ocr-2"),
        parent(representation_id="ocr-2"),
    )
    assert a["representation_sha256_hex"] == b["representation_sha256_hex"]
    assert a["kernel_representation_id"] != b["kernel_representation_id"]
    with pytest.raises(StoredLocatorError):
        decode_anchor_projection(b, parent())


@pytest.mark.parametrize(("field", "value"), [
    ("org_id", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
    ("case_id", "aaaaaaaa-2121-4121-8121-aaaaaaaaaaaa"),
    ("kernel_document_id", "invoice/other"),
    ("kernel_version_id", "v2"),
    ("kernel_representation_id", "ocr-2"),
    ("source_sha256_hex", "f" * 64),
    ("representation_sha256_hex", "f" * 64),
    ("locator_schema_version", "krn102-locator-v3"),
    ("locator_kind", "unknown"),
])
def test_mismatched_scoped_identity_or_schema_is_rejected(
    field: str, value: str
) -> None:
    row = encode_anchor_projection(anchor(LOCATORS[0]), parent())
    row[field] = value
    with pytest.raises(StoredLocatorError):
        decode_anchor_projection(row, parent())


def test_projection_extra_or_missing_field_and_unsafe_parent() -> None:
    row = encode_anchor_projection(anchor(LOCATORS[0]), parent())
    with pytest.raises(StoredLocatorError):
        decode_anchor_projection({**row, "human_authenticated": True}, parent())
    missing = dict(row)
    del missing["source_sha256_hex"]
    with pytest.raises(StoredLocatorError):
        decode_anchor_projection(missing, parent())
    with pytest.raises(StoredLocatorError):
        encode_anchor_projection(anchor(LOCATORS[0], representation_id="ocr-2"), parent())
    with pytest.raises(StoredLocatorError):
        replace(parent(), case_id=UUID(int=0))


def test_unicode_offsets_are_codepoints_not_bytes() -> None:
    a = anchor(TextSpan(start=0, end=len(UNICODE)))
    validate_against_verified_bytes(
        a, source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
        coordinate_basis=TEXT_BASIS,
    )
    assert len(TEXT_BYTES) > len(UNICODE)
    with pytest.raises(StoredLocatorError):
        validate_against_verified_bytes(
            anchor(TextSpan(start=0, end=len(TEXT_BYTES))),
            source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
            coordinate_basis=TEXT_BASIS,
        )
    with pytest.raises(StoredLocatorError):
        validate_against_verified_bytes(
            a, source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
            coordinate_basis=PDF_BASIS,
        )


def test_normalization_and_exact_byte_digests_are_rechecked() -> None:
    a = anchor(TextSpan(start=0, end=4, normalization="NFC"))
    validate_against_verified_bytes(
        a, source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
        coordinate_basis=TEXT_BASIS,
    )
    for s, rep in ((ORIGINAL + b"x", TEXT_BYTES), (ORIGINAL, TEXT_BYTES + b"x")):
        with pytest.raises(StoredLocatorError):
            validate_against_verified_bytes(
                a, source_bytes=s, representation_bytes=rep,
                coordinate_basis=TEXT_BASIS,
            )
    decomposed = "cafe\u0301".encode()
    with pytest.raises(StoredLocatorError):
        validate_against_verified_bytes(
            anchor(
                TextSpan(0, 4, normalization="NFC"),
                rep_hash=hashlib.sha256(decomposed).hexdigest(),
            ),
            source_bytes=ORIGINAL, representation_bytes=decomposed,
            coordinate_basis=TEXT_BASIS,
        )


def test_pdf_page_layout_is_required_and_exact() -> None:
    a = anchor(LOCATORS[1])
    page = PdfPage(
        page_index=0, width=Decimal("595.00"),
        height=Decimal("842"), rotation=90,
    )
    layout = PdfLayout(pages=(page,))
    with pytest.raises(StoredLocatorError):
        validate_against_verified_bytes(
            a, source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
            coordinate_basis=PDF_BASIS,
        )
    validate_against_verified_bytes(
        a, source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
        coordinate_basis=PDF_BASIS, trusted_layout=layout,
    )
    wrong = PdfLayout(pages=(replace(page, rotation=0),))
    with pytest.raises(StoredLocatorError):
        validate_against_verified_bytes(
            a, source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
            coordinate_basis=PDF_BASIS, trusted_layout=wrong,
        )


def test_workbook_sheet_and_table_are_checked() -> None:
    a = anchor(LOCATORS[2])
    sheet = WorkbookSheet(
        sheet_id="sheet-stable-id", max_row=10,
        max_column=29, table_ids=("t-1",),
    )
    layout = WorkbookLayout(sheets=(sheet,))
    validate_against_verified_bytes(
        a, source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
        coordinate_basis=SHEET_BASIS, trusted_layout=layout,
    )
    for bad in (
        WorkbookLayout(sheets=(replace(sheet, max_column=28),)),
        WorkbookLayout(sheets=(replace(sheet, table_ids=()),)),
        WorkbookLayout(sheets=(replace(sheet, sheet_id="moved"),)),
    ):
        with pytest.raises(StoredLocatorError):
            validate_against_verified_bytes(
                a, source_bytes=ORIGINAL, representation_bytes=TEXT_BYTES,
                coordinate_basis=SHEET_BASIS, trusted_layout=bad,
            )


def test_structured_field_path_and_duplicate_json_are_checked() -> None:
    record = b'{"lines":[{"total":[3]},{"total":[7]}]}'
    a = anchor(
        StructuredField(schema_id="invoice-v3", path=("lines", 1, "total", 0)),
        rep_hash=hashlib.sha256(record).hexdigest(),
    )
    validate_against_verified_bytes(
        a, source_bytes=ORIGINAL, representation_bytes=record,
        coordinate_basis=JSON_BASIS,
        trusted_layout=StructuredLayout(schema_id="invoice-v3"),
    )
    with pytest.raises(StoredLocatorError):
        validate_against_verified_bytes(
            a, source_bytes=ORIGINAL, representation_bytes=record,
            coordinate_basis=JSON_BASIS,
            trusted_layout=StructuredLayout(schema_id="invoice-v4"),
        )
    missing = anchor(
        StructuredField(schema_id="invoice-v3", path=("lines", 10, "total")),
        rep_hash=hashlib.sha256(record).hexdigest(),
    )
    with pytest.raises(StoredLocatorError):
        validate_against_verified_bytes(
            missing, source_bytes=ORIGINAL, representation_bytes=record,
            coordinate_basis=JSON_BASIS,
            trusted_layout=StructuredLayout(schema_id="invoice-v3"),
        )
    duplicate = b'{"lines":0,"lines":[2]}'
    with pytest.raises(StoredLocatorError):
        validate_against_verified_bytes(
            anchor(
                StructuredField("invoice-v3", ("lines", 0)),
                rep_hash=hashlib.sha256(duplicate).hexdigest(),
            ),
            source_bytes=ORIGINAL, representation_bytes=duplicate,
            coordinate_basis=JSON_BASIS,
            trusted_layout=StructuredLayout(schema_id="invoice-v3"),
        )


def test_does_not_wire_database_or_enable_approval_api() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / "apps/api/main.py").read_text(encoding="utf-8")
    code = (root / "apps/api/evidence_locator_codec.py").read_text(encoding="utf-8")
    assert "/v2/" not in app
    assert "evidence_locator_codec" not in app
    assert "supabase" not in code
    assert "sqlalchemy" not in code
    assert {p.name for p in (root / "supabase/migrations").glob("*.sql")} == {
        "20261031112127_signed_page_worker.sql",
        "20261031234906_dossier_draft_revisions.sql",
        "20261031235117_dossier_draft_revision_fk_indexes.sql",
        "20261101004423_dossier_draft_revision_scoped_cleanup.sql",
        "20261101205446_workspace_f1_report_catalog.sql",
        "20261030140000_caseproof_phase3_private_ocr_geometry.sql",
        "20261030141500_caseproof_phase3_geometry_text_payload.sql",
        "20261030143000_caseproof_phase3_atomic_ocr_ingest.sql",
        "20261030150000_caseproof_phase3_signed_geometry_read.sql",
        "20261030153000_caseproof_phase3_four_source_draft_bundle.sql",
        "20261022001009_caseproof_tenant_foundation.sql",
        "20261027160745_caseproof_m1_dev_atomic_private_grants.sql",
        "20261027195417_caseproof_m2_dev_atomic_private_review.sql",
        "20261027195451_caseproof_m1_signed_invoker_read_views.sql",
            "20261027202734_caseproof_m1_private_originals_storage.sql",
            "20261027204343_caseproof_m1_storage_upload_action_correction.sql",
            "20261027214851_caseproof_m1_dev_live_positive_fixture_rpc.sql",
            "20261028065430_caseproof_m1_private_exhibit_storage.sql",
            "20261028070156_caseproof_dev_signed_review_roundtrip.sql",
            "20261028070231_caseproof_dev_scoped_review_cleanup.sql",
            "20261028071554_caseproof_dev_signed_review_security_hardening.sql",
            "20261028081227_caseproof_dev_signed_matter_txt_ingestion.sql",
            "20261028081347_caseproof_dev_txt_review_binding.sql",
            "20261028081408_caseproof_dev_txt_revocation_cleanup.sql",
            "20261028081528_caseproof_dev_signed_create_org_discovery.sql",
            "20261028082143_caseproof_dev_txt_cleanup_uuid_fix.sql",
            "20261028083533_caseproof_dev_close_client_ingest_bypass.sql",
            "20261028083622_caseproof_dev_trusted_ingest_verified_promotion.sql",
            "20261028083747_caseproof_dev_cleanup_actor_isolation.sql",
            "20261028105942_caseproof_dev_separate_draft_write_grant.sql",
            "20261028110031_caseproof_dev_signed_reviewed_draft_correction.sql",
            "20261028110102_caseproof_dev_reversible_draft_cleanup.sql",
            "20261028110233_caseproof_dev_ordered_revised_brief_state.sql",
            "20261028110604_caseproof_dev_correction_review_head_fence.sql",
            "20261028111543_caseproof_dev_correct_owner_write_and_read_separation.sql",
            "20261028111744_caseproof_dev_require_org_write_for_brief.sql",
            "20261028111820_caseproof_dev_org_only_revoke_test_rpc.sql",
            "20261028114522_caseproof_dev_signed_pdf_docx_register_parse_manifest.sql",
            "20261028114616_caseproof_dev_service_verified_binary_parser_promotion.sql",
            "20261028114940_caseproof_dev_m2_preserve_partial_pdf_docx_unknown.sql",
            "20261028114956_caseproof_dev_cleanup_verified_binary_source.sql",
            "20261030095000_caseproof_dev_bundle_cleanup.sql",
            "20261030101500_caseproof_dev_bundle_manifest.sql",
            "20261030103000_caseproof_durable_bundle_roles.sql",
            "20261030110000_caseproof_dev_atomic_bundle_registration.sql",
        "20261030113000_m05_test_run_registry.sql",
        "20261030114000_m05_ocr_sidecar_cleanup_fk.sql",
        "20261030115000_m05_protected_registry_rpc.sql",
        "20261030120000_m05_verify_empty.sql",
        "20261030155817_matter_retention.sql",
        "20261030160341_retention_storage_fence.sql",
        "20261030161844_complete_dossier_journey.sql",
            "20261030235107_representation_snapshot_read.sql",
            "20261030235456_regional_review_attestation.sql",
    }
