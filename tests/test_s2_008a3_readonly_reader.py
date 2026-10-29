"""S2-008a3 DB-API read contract; real PostgreSQL query also runs in CI."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from apps.api.evidence_locator_codec import (
    ExpectedEvidenceParent,
    StoredLocatorError,
)
from apps.api.postgres_evidence_reader import (
    SQL_SELECT_EXACT_ANCHOR,
    EvidenceRowNotFound,
    get_exact_anchor_metadata,
)
from scripts.verify_s2_008a3_reader import _DisposablePsqlReader

ORG = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CASE = UUID("aaaaaaaa-1111-4111-8111-111111111111")
DOC = "invoice/source-A"
SOURCE_SHA = "a" * 64
REP_SHA = "c" * 64


def parent() -> ExpectedEvidenceParent:
    return ExpectedEvidenceParent(
        org_id=ORG, case_id=CASE, document_id=DOC,
        version_id="v1", representation_id="ocr-1",
        source_sha256_hex=SOURCE_SHA, representation_sha256_hex=REP_SHA,
    )


def payload() -> dict[str, Any]:
    return {
        "org_id": str(ORG), "case_id": str(CASE),
        "kernel_anchor_id": "span:1", "kernel_document_id": DOC,
        "kernel_version_id": "v1", "kernel_representation_id": "ocr-1",
        "source_sha256_hex": SOURCE_SHA,
        "representation_sha256_hex": REP_SHA,
        "locator_kind": "text_span",
        "locator_schema_version": "krn102-locator-v1",
        "locator": {
            "start": 0, "end": 10,
            "encoding": "utf-8", "normalization": "none",
        },
        "coordinate_basis": "unicode_codepoint_zero_based_half_open",
        "layout_kind": "text",
    }


class FakeCursor:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.calls = 0

    def execute(self, query: str, params: dict[str, str]) -> None:
        assert query == SQL_SELECT_EXACT_ANCHOR
        assert set(params) == {
            "org_id", "case_id", "anchor_id", "document_id",
            "version_id", "representation_id",
            "source_sha256_hex", "representation_sha256_hex",
        }
        assert params["org_id"] == str(ORG)
        assert params["case_id"] == str(CASE)
        assert params["document_id"] == DOC
        assert params["anchor_id"] == "span:1"
        self.calls += 1

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


def test_positive_typed_read_never_claims_evidence_eligibility() -> None:
    cursor = FakeCursor(payload())
    result = get_exact_anchor_metadata(
        cursor, expected=parent(), anchor_id="span:1"
    )
    assert cursor.calls == 1
    assert result.anchor.anchor_id == "span:1"
    assert result.anchor.version_id == "v1"
    assert result.anchor.locator.start == 0  # type: ignore[union-attr]
    assert result.anchor.locator.end == 10  # type: ignore[union-attr]
    assert result.eligibility_established is False


def test_missing_or_foreign_row_masked() -> None:
    with pytest.raises(EvidenceRowNotFound):
        get_exact_anchor_metadata(FakeCursor(None), expected=parent(), anchor_id="span:1")


@pytest.mark.parametrize(("key", "corruption"), [
    ("org_id", "cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
    ("case_id", "dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
    ("kernel_anchor_id", "another-anchor"),
    ("kernel_document_id", "other-doc"),
    ("kernel_version_id", "v2"),
    ("kernel_representation_id", "ocr-2"),
    ("source_sha256_hex", "f" * 64),
    ("representation_sha256_hex", "f" * 64),
    ("locator_kind", "pdf_region"),
    ("locator_schema_version", "krn102-locator-v9"),
    ("coordinate_basis", "pdf_points_unrotated_bottom_left"),
    ("layout_kind", "structured"),
    ("locator", {"start": True, "end": 10, "encoding": "utf-8",
                 "normalization": "none"}),
])
def test_stale_corrupt_cross_tenant_or_wrong_layout_fails(
    key: str, corruption: object
) -> None:
    p = payload()
    p[key] = corruption
    with pytest.raises(StoredLocatorError):
        get_exact_anchor_metadata(FakeCursor(p), expected=parent(), anchor_id="span:1")


def test_db_json_column_duplicate_and_unknown_projection_rejected() -> None:
    p = payload()
    p["unexpected_column"] = "do not read"
    with pytest.raises(StoredLocatorError):
        get_exact_anchor_metadata(FakeCursor(p), expected=parent(), anchor_id="span:1")
    p = payload()
    p["locator"] = '{"start":0,"start":1,"end":10,"encoding":"utf-8","normalization":"none"}'
    with pytest.raises(StoredLocatorError):
        get_exact_anchor_metadata(FakeCursor(p), expected=parent(), anchor_id="span:1")


def test_explicit_independent_expected_scope_required() -> None:
    with pytest.raises(StoredLocatorError):
        get_exact_anchor_metadata(FakeCursor(payload()), expected=None, anchor_id="span:1")  # type: ignore[arg-type]
    with pytest.raises(StoredLocatorError):
        get_exact_anchor_metadata(FakeCursor(payload()), expected=parent(), anchor_id="")
    with pytest.raises(StoredLocatorError):
        get_exact_anchor_metadata(FakeCursor(payload()), expected=parent(), anchor_id="x" * 257)


def test_query_is_read_only_composite_scoped_and_parameterized() -> None:
    sql = SQL_SELECT_EXACT_ANCHOR.lower()
    assert sql.lstrip().startswith("select")
    assert "insert into" not in sql and "update " not in sql
    assert "delete from" not in sql and "security definer" not in sql
    assert "a.org_id = %(org_id)s::uuid" in sql
    assert "a.case_id = %(case_id)s::uuid" in sql
    assert "a.kernel_anchor_id = %(anchor_id)s" in sql
    assert "physical_doc.case_id = a.case_id" in sql
    assert "physical_version.original_sha256_hex = a.source_sha256_hex" in sql
    assert "d.kernel_document_id = %(document_id)s" in sql
    assert "v.kernel_version_id = %(version_id)s" in sql
    assert "r.kernel_representation_id = %(representation_id)s" in sql


def test_disposable_sql_adapter_never_accepts_user_supplied_sql_or_secrets() -> None:
    fake = _DisposablePsqlReader({})
    with pytest.raises(AssertionError):
        fake.execute("select * from auth.users", {"org_id": "untrusted"})
    assert fake.query_count == 0
    assert "CASEPROOF_DEV_AUTH" not in SQL_SELECT_EXACT_ANCHOR


def test_all_new_code_is_unwired_and_migration_unchanged() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / "apps/api/main.py").read_text(encoding="utf-8")
    assert "postgres_evidence_reader" not in app
    assert "/v2/" not in app
    assert {p.name for p in (root / "supabase/migrations").glob("*.sql")} == {
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
    }
    workflow = (root / ".github/workflows/kernel-boundary.yml").read_text()
    assert "scripts.verify_s2_008a3_reader" in workflow
