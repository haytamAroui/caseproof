"""S2-002: static migration-review guards, alongside real rollback-only PG test.

These assertions DO NOT simulate or claim to test PostgreSQL RLS semantics.
The actual role/tenant/FK negative matrix lives in db/proposals/ and must
run against a disposable real PostgreSQL/Supabase database transaction.
"""

from __future__ import annotations

import re
from pathlib import Path

SQL = (
    Path(__file__).resolve().parents[1]
    / "db" / "proposals" / "S2-002_tenant_foundation.sql"
).read_text(encoding="utf-8")
NEGATIVE_SQL = (
    Path(__file__).resolve().parents[1]
    / "db" / "proposals" / "S2-002_rls_rollback_test.sql"
).read_text(encoding="utf-8")

EXPECTED_TABLES = {
    "organizations", "organization_members", "cases", "documents",
    "document_versions", "audit_events", "idempotency_records",
}


def table_names(statement: str) -> set[str]:
    return set(re.findall(r"create table caseproof\.([a-z_]+)\s*\(", statement))


def rls_tables(statement: str) -> set[str]:
    return set(re.findall(
        r"alter table caseproof\.([a-z_]+) enable row level security\s*;",
        statement,
    ))


def test_complete_named_s2_002_schema_has_rls_for_every_application_table() -> None:
    assert table_names(SQL) == EXPECTED_TABLES
    assert rls_tables(SQL) == EXPECTED_TABLES
    assert "create schema caseproof;" in SQL
    assert "create schema public" not in SQL.lower()


def test_privilege_budget_is_read_only_and_has_no_exposed_audit_writes() -> None:
    normalized = SQL.lower()
    assert "revoke all on schema caseproof from public, anon, authenticated;" in normalized
    assert "revoke all on all tables in schema caseproof from public, anon, authenticated;" in normalized
    assert "grant usage on schema caseproof to authenticated;" in normalized
    assert "grant select on caseproof.organizations," in normalized
    assert "caseproof.document_versions\nto authenticated;" in normalized
    assert re.search(r"\bgrant\s+(insert|update|delete|all)\b", normalized) is None
    assert "grant select on caseproof.audit_events" not in normalized
    assert "grant select on caseproof.idempotency_records" not in normalized
    assert "security definer" not in re.sub(r"--[^\n]*", "", normalized)
    assert "service_role" not in re.sub(r"--[^\n]*", "", normalized)


def test_membership_comes_from_auth_uid_and_server_owned_active_membership() -> None:
    assert "references auth.users(id)" in SQL
    assert "user_id = (select auth.uid())" in SQL
    assert "using (active and user_id = (select auth.uid()))" in SQL
    assert SQL.count("m.active") >= 4
    assert SQL.count("m.user_id = (select auth.uid())") >= 4
    assert "user_metadata" not in re.sub(r"--[^\n]*", "", SQL.lower())


def test_composite_tenant_foreign_keys_guard_cross_org_links() -> None:
    assert "foreign key (org_id, case_id) references caseproof.cases(org_id, id)" in SQL
    assert "foreign key (org_id, document_id) references caseproof.documents(org_id, id)" in SQL
    assert "foreign key (org_id, created_by_user)" in SQL
    assert SQL.count("unique (org_id, id)") >= 3
    assert "unique (org_id, case_id, operation, idempotency_key)" in SQL
    assert "check (original_sha256_hex ~ '^[0-9a-f]{64}$')" in SQL


def test_real_database_script_covers_roles_revocation_and_rollback_is_required() -> None:
    assert "S2-002_ROLLBACK_ONLY_RLS_TEST_PASSED" in NEGATIVE_SQL
    assert "set local role authenticated;" in NEGATIVE_SQL
    assert "reset role;" in NEGATIVE_SQL
    assert "update caseproof.organization_members" in NEGATIVE_SQL
    assert "set_config('request.jwt.claim.sub'" in NEGATIVE_SQL
    assert "cross-tenant composite case foreign key unexpectedly accepted" in NEGATIVE_SQL
    assert "tenant A could read tenant B" in NEGATIVE_SQL
    assert "tenant B could read tenant A" in NEGATIVE_SQL
    assert "revoked membership retained access" in NEGATIVE_SQL
    assert "grant insert" not in NEGATIVE_SQL.lower()
    # Scripts must NOT silently apply themselves on CI or open a live connection.
    assert "BEGIN;" not in SQL
    assert "COMMIT;" not in SQL
    assert "ROLLBACK;" not in NEGATIVE_SQL


def test_disposable_ci_database_job_runs_real_concurrent_and_audit_negative_cases() -> None:
    root = Path(__file__).resolve().parents[1]
    harness = (root / "scripts/verify_s2_002_database.py").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/kernel-boundary.yml").read_text(encoding="utf-8")
    assert "CASEPROOF_DISPOSABLE_DB" in harness
    assert 'not in {"127.0.0.1", "localhost"}' in harness
    assert 'caseproof_s2_ci' in harness
    assert "subprocess.Popen(" in harness
    assert "LOCK_ACQUIRED_BY_A" in harness
    assert "case_revision=1" in harness
    assert "if second != \"0\":" in harness
    assert "insert into caseproof.audit_events" in harness
    assert "when check_violation then" in harness
    assert "AUDIT_FAILURE_ROLLBACK_PASSED" in harness
    assert "S2-002_DISPOSABLE_POSTGRES_NEGATIVE_TESTS_PASSED" in harness
    assert "database-security:" in workflow
    assert "image: postgres:17" in workflow
    assert "CASEPROOF_DISPOSABLE_DB: \"YES\"" in workflow
    assert "uv run --locked python scripts/verify_s2_002_database.py" in workflow



def test_cli_generated_canonical_migration_is_identical_to_reviewed_sql() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "supabase/migrations/20261022001009_caseproof_tenant_foundation.sql"
    )
    proposal = root / "db/proposals/S2-002_tenant_foundation.sql"
    assert migration.exists()
    assert migration.read_bytes() == proposal.read_bytes()
    assert {p.name for p in (root / "supabase/migrations").glob("*.sql")} == {
        "20261030140000_caseproof_phase3_private_ocr_geometry.sql",
        "20261030141500_caseproof_phase3_geometry_text_payload.sql",
        "20261030143000_caseproof_phase3_atomic_ocr_ingest.sql",
        "20261030150000_caseproof_phase3_signed_geometry_read.sql",
        "20261030153000_caseproof_phase3_four_source_draft_bundle.sql",
        "20261022001009_caseproof_tenant_foundation.sql",
        "20261030110000_caseproof_dev_atomic_bundle_registration.sql",
        "20261030113000_m05_test_run_registry.sql",
        "20261030114000_m05_ocr_sidecar_cleanup_fk.sql",
        "20261030115000_m05_protected_registry_rpc.sql",
        "20261030120000_m05_verify_empty.sql",
        "20261030155817_matter_retention.sql",
        "20261030160341_retention_storage_fence.sql",
        "20261030161346_complete_dossier_journey.sql",
        "20261030095000_caseproof_dev_bundle_cleanup.sql",
        "20261030101500_caseproof_dev_bundle_manifest.sql",
        "20261030103000_caseproof_durable_bundle_roles.sql",
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
    integration = (root / "scripts/verify_s2_002_database.py").read_text(
        encoding="utf-8"
    )
    assert "PROPOSAL = MIGRATION.read_text" in integration
    assert "MIGRATION.read_bytes() != PROPOSAL_PATH.read_bytes()" in integration



def test_human_audit_actor_is_bound_to_event_tenant() -> None:
    root = Path(__file__).resolve().parents[1]
    sql = (root / "supabase/migrations/20261022001009_caseproof_tenant_foundation.sql").read_text(
        encoding="utf-8"
    )
    assert "foreign key (org_id, actor_user_id)" in sql
    assert "references caseproof.organization_members(org_id, user_id)" in sql
    assert "(actor_type = 'service' and actor_user_id is null)" in sql
    negative = (root / "db/proposals/S2-002_rls_rollback_test.sql").read_text(
        encoding="utf-8"
    )
    assert "cross-tenant audit actor unexpectedly accepted" in negative
    assert "service audit event with human actor unexpectedly accepted" in negative
    assert "valid-tenant-actor" in negative
    assert "valid-service-actor" in negative
