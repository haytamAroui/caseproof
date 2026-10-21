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
        root / "supabase/migrations/20261021232955_caseproof_tenant_foundation.sql"
    )
    proposal = root / "db/proposals/S2-002_tenant_foundation.sql"
    assert migration.exists()
    assert migration.read_bytes() == proposal.read_bytes()
    assert len(list((root / "supabase/migrations").glob("*.sql"))) == 1
    integration = (root / "scripts/verify_s2_002_database.py").read_text(
        encoding="utf-8"
    )
    assert "PROPOSAL = MIGRATION.read_text" in integration
    assert "MIGRATION.read_bytes() != PROPOSAL_PATH.read_bytes()" in integration
