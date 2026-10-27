"""Contract tests for the Supabase MCP read-only live RLS audit packet.

These tests guard the query's declared scope and project-specific expectations.
They DO NOT test a live signed user or a deployed PostgreSQL policy.
"""
from pathlib import Path

SQL = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "m1_live_mcp_readonly_audit.sql"
).read_text(encoding="utf-8")


def test_read_only_mcp_query_cannot_mutate_schema_or_fixture() -> None:
    statements = "\n".join(
        line.split("--", 1)[0] for line in SQL.splitlines()
    ).strip().lower()
    assert statements.startswith("with expected(")
    assert statements.endswith("as protected_relation_details;")
    assert statements.count(";") == 1
    assert not any(
        token in statements
        for token in (
            "create table ", "create role ", "drop table ", "drop role ",
            "alter table ", "insert into ", "update caseproof.",
            "delete from ", "truncate table ", "grant all ", "revoke all ",
            "set role ", "set_config(", "pg_sleep(",
        )
    )


def test_mcp_query_pins_expected_private_rls_and_auth_separation() -> None:
    for expected in (
        "20261027160745",
        "m1_private_case_read",
        "m1_private_document_read",
        "m1_private_document_version_read",
        "m1_own_private_grant_read",
        "authenticated",
        "anon",
        "auth.uid()",
        "case:read",
        "evidence:read",
        "rls_enabled",
        "authenticated_can_write",
        "audit_events",
        "idempotency_records",
        "no_permanent_reader_role_yet",
    ):
        assert expected in SQL


def test_no_privileged_github_database_secrets_in_mcp_audit() -> None:
    assert "CASEPROOF_DEV_DB_ADMIN_DSN" not in SQL
    assert "CASEPROOF_DEV_DB_CA_PEM" not in SQL
    assert "sb_secret_" not in SQL
