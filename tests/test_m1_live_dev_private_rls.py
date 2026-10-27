"""No-network guardrails for the opt-in real CaseProof dev signed-RLS probe."""
from __future__ import annotations

import pytest

from apps.api.access_control import AccessFailure, AccessRejected
from scripts.verify_dev_ephemeral_auth import PROJECT_REF
from scripts.verify_m1_live_dev_private_rls import (
    TEST_FLAG,
    _denied,
    require_protected_execution,
    validated_admin_dsn,
)


def _environment() -> dict[str, str]:
    return {
        TEST_FLAG: "YES",
        "GITHUB_REPOSITORY": "haytamAroui/caseproof",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "CASEPROOF_M1_LIVE_DB_APPROVED": "YES",
    }


def test_real_database_probe_requires_all_protected_main_guards() -> None:
    allowed = _environment()
    require_protected_execution(allowed)
    for field in allowed:
        changed = dict(allowed)
        changed.pop(field)
        with pytest.raises(RuntimeError):
            require_protected_execution(changed)
    changed = dict(allowed, GITHUB_REF="refs/heads/attacker")
    with pytest.raises(RuntimeError):
        require_protected_execution(changed)


@pytest.mark.parametrize(
    "host,user,port,expected",
    [
        (f"db.{PROJECT_REF}.supabase.co", "postgres", "5432", "direct"),
        (f"aws-0-eu-central-1.pooler.supabase.com",
         f"postgres.{PROJECT_REF}", "5432", "pool"),
    ],
)
def test_accepts_only_pinned_project_and_session_mode(
    host: str, user: str, port: str, expected: str,
) -> None:
    uri = (
        f"postgresql://{user}:placeholder-secret@{host}:{port}/postgres"
        "?sslmode=verify-full"
    )
    got, mode = validated_admin_dsn(uri)
    assert (got, mode) == (uri, expected)


@pytest.mark.parametrize(
    "uri",
    [
        "",
        "postgresql://postgres:pw@localhost:5432/postgres",
        f"postgresql://postgres:pw@db.{PROJECT_REF}.supabase.co:6543/postgres",
        f"postgresql://postgres:pw@db.{PROJECT_REF}.supabase.co:5432/not-postgres",
        f"postgresql://postgres:pw@db.{PROJECT_REF}.supabase.co:5432/postgres?options=-csearch_path%3Dpublic",
        f"postgresql://postgres:pw@db.{PROJECT_REF}.supabase.co:5432/postgres?sslmode=disable",
        f"postgresql://postgres:pw@db.notcaseproof.supabase.co:5432/postgres",
        f"postgresql://postgres.badproject:pw@aws-0-eu-central-1.pooler.supabase.com:5432/postgres",
    ],
)
def test_rejects_unpinned_or_insecure_database_connections(uri: str) -> None:
    with pytest.raises(RuntimeError):
        validated_admin_dsn(uri)


def test_negative_read_requires_expected_access_code() -> None:
    def denied() -> None:
        raise AccessRejected(AccessFailure.RESOURCE_MASKED)

    _denied(denied, AccessFailure.RESOURCE_MASKED)
    with pytest.raises(AssertionError):
        _denied(denied, AccessFailure.AUTHENTICATION_REQUIRED)
    with pytest.raises(AssertionError):
        _denied(lambda: None, AccessFailure.RESOURCE_MASKED)
