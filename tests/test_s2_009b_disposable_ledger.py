"""S2-009b reference-only PostgreSQL ledger contract guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_s2_009b_database import (
    OBJECT_KEY,
    SQL,
    call,
)

ROOT = Path(__file__).resolve().parents[1]


def test_sql_is_disposable_and_enforces_scoped_source_identity() -> None:
    assert "NEVER apply to Supabase" in SQL
    assert "create table caseproof._s2_009b_vault_intents" in SQL
    assert "create table caseproof._s2_009b_availability_events" in SQL
    assert "foreign key (org_id, case_id, document_id)" in SQL
    assert "foreign key (org_id, document_id, document_version_id, sha256_hex)" in SQL
    assert "references caseproof.document_versions(" in SQL
    assert "unique (object_key)" in SQL
    assert "check (state in ('pending','verified','unavailable'))" in SQL
    assert "before update or delete" in SQL


def test_atomic_audit_idempotency_and_rollback_faults_remain_required() -> None:
    assert "security invoker" in SQL.lower()
    assert "set search_path=pg_catalog,pg_temp" in SQL
    assert "for update of m" in SQL
    assert "for update;" in SQL
    assert "case_revision=c.case_revision+1" in SQL
    assert "insert into caseproof.audit_events" in SQL
    assert "insert into caseproof.idempotency_records" in SQL
    assert "insert into caseproof._s2_009b_availability_events" in SQL
    assert "p_fault='audit'" in SQL
    assert "p_fault='receipt'" in SQL
    assert "p_fault='availability'" in SQL
    assert "stored receipt inconsistent with durable event" in SQL
    assert "invalid randomized object key format" in SQL
    assert SQL.count("enable row level security") == 2
    assert "from public,anon,authenticated" in SQL
    assert "grant execute" not in SQL.lower()
    assert "security definer" not in SQL.lower()


def test_only_synthetic_fixed_values_can_enter_psql_fixture() -> None:
    query = call("stage")
    assert "caseproof._s2_009b_disposable_command" in query
    assert "s2_009b_vault_" not in query  # operation determined only server-side
    assert OBJECT_KEY in query
    for invalid in (
        "invalid'; DROP TABLE caseproof.cases;--",
        "unsafe key",
        "bad/path",
    ):
        with pytest.raises(ValueError):
            call("stage", key=invalid)
    with pytest.raises(ValueError):
        call("not-an-operation")
    with pytest.raises(ValueError):
        call("stage", intent="not-a-uuid")


def test_ci_has_ephemeral_fixture_only_and_no_remote_migration() -> None:
    workflow = (ROOT / ".github/workflows/kernel-boundary.yml").read_text(encoding="utf-8")
    assert "uv run --locked python -m scripts.verify_s2_009b_database" in workflow
    assert "CASEPROOF_DISPOSABLE_DB: \"YES\"" in workflow
    assert "postgres:17" in workflow
    runner = (ROOT / "scripts/verify_s2_009b_database.py").read_text(encoding="utf-8")
    assert "env = _isolated_postgres_env()" in runner
    for gate in ("AUDIT_STAGE", "RECEIPT_STAGE", "VERIFICATION_FAILURE_ROLLBACK",
                 "UNAVAILABLE_FAILURE_ROLLBACK", "FORGED_RECEIPT"):
        assert gate in runner
    assert {p.name for p in (ROOT / "supabase/migrations").glob("*.sql")} == {
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
    }
    assert not (ROOT / "apps/api/vault_repository.py").exists()
    assert "evidence_vault_protocol" not in (ROOT / "apps/api/main.py").read_text()
