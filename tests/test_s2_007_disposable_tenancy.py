"""S2-007 contract tests; live session proof remains manual-only."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from scripts.verify_s2_007_disposable_tenancy import (
    CASE_A,
    CASE_B,
    _fixture_sql,
    _isolated_postgres_env,
    DOC_A, DOC_B, VER_A, VER_B,
    _no_claim_after_rollback,
    _session_sql,
    pseudonymous_fixture_subjects,
)

ROOT = Path(__file__).resolve().parents[1]
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


def test_pseudonyms_unique_and_per_run() -> None:
    pair = pseudonymous_fixture_subjects(A, B, nonce=b"x" * 32)
    assert pair == pseudonymous_fixture_subjects(A, B, nonce=b"x" * 32)
    assert pair != pseudonymous_fixture_subjects(A, B, nonce=b"y" * 32)
    assert pair[0] != pair[1]
    assert pair[0] != A and pair[1] != B
    assert all(UUID(value).version == 4 for value in pair)


@pytest.mark.parametrize(("a", "b", "nonce"), [
    (A, A, b"x" * 32),
    ("invalid", B, b"x" * 32),
    (A, "invalid", b"x" * 32),
    (A, B, b"weak"),
])
def test_pseudonyms_fail_closed(a: str, b: str, nonce: bytes) -> None:
    with pytest.raises(ValueError):
        pseudonymous_fixture_subjects(a, b, nonce=nonce)


def test_case_and_subject_sql_are_uuid_only() -> None:
    with pytest.raises(ValueError):
        _fixture_sql("x');DROP TABLE auth.users;--", B)
    with pytest.raises(ValueError):
        _session_sql(A, "invalid", CASE_B)
    with pytest.raises(ValueError):
        _no_claim_after_rollback("invalid", CASE_A)


def test_rls_positive_negative_and_transaction_isolation_contract() -> None:
    own = _session_sql(A, CASE_A, CASE_B)
    foreign = _session_sql(A, CASE_B, CASE_A, expected_own=0, expected_other=1)
    no_claim = _session_sql(A, CASE_A, CASE_B, expected_own=0, claim=False)
    reset = _no_claim_after_rollback(A, CASE_A)
    assert "set local role authenticated" in own
    assert "perform set_config('request.jwt.claim.sub'" in own
    assert own.endswith("\nrollback;\n")
    assert " <> 1" in own and " <> 0" in own
    assert " <> 1" in foreign and " <> 0" in foreign
    assert "set_config" not in no_claim
    assert reset.count("rollback;") == 2
    assert reset.count("set local role authenticated;") == 2


def test_live_probe_is_explicit_and_never_connects_to_dev_db() -> None:
    script = (ROOT / "scripts/verify_s2_007_disposable_tenancy.py").read_text()
    assert "env = _isolated_postgres_env()" in script
    assert "run_live_auth_probe(" in script
    assert "secrets.token_bytes(32)" in script
    assert 'CASEPROOF_S2_007_REAL_AUTH' in script
    assert 'CASEPROOF_S2_007_SYNTHETIC' in script
    assert "CASEPROOF_DEV_AUTH_A_PASSWORD" in script



def test_explicit_document_and_version_ids_detect_independent_rls_drift() -> None:
    # Each principal must access *both* direct own + foreign version IDs.
    # A subquery through already-filtered documents would hide a broken
    # document_versions policy, falsely passing the foreign-version proof.
    for own, other, own_doc, other_doc, own_version, other_version in (
        (CASE_A, CASE_B, DOC_A, DOC_B, VER_A, VER_B),
        (CASE_B, CASE_A, DOC_B, DOC_A, VER_B, VER_A),
    ):
        sql = _session_sql(A, own, other)
        assert "document_id in (select" not in sql
        assert f"caseproof.documents where id='{own_doc}'" in sql
        assert f"caseproof.documents where id='{other_doc}'" in sql
        assert f"caseproof.document_versions where id='{own_version}'" in sql
        assert f"caseproof.document_versions where id='{other_version}'" in sql


@pytest.fixture()
def disposable_pg_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEPROOF_DISPOSABLE_DB", "YES")
    monkeypatch.setenv("PGHOST", "127.0.0.1")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.setenv("PGDATABASE", "caseproof_s2_ci")
    monkeypatch.setenv("PGUSER", "postgres")
    monkeypatch.setenv("PGPASSWORD", "caseproof_ephemeral_ci")
    monkeypatch.delenv("PGHOSTADDR", raising=False)


def test_disposable_env_strips_pgservice_pgoptions_and_all_other_libpq(
    disposable_pg_env: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PGSERVICE", "external-service")
    monkeypatch.setenv("PGOPTIONS", "-c search_path=public")
    monkeypatch.setenv("PGSERVICEFILE", "/tmp/untrusted.conf")
    monkeypatch.setenv("PGSSLMODE", "require")
    env = _isolated_postgres_env()
    assert env["PGHOST"] == "127.0.0.1"
    assert env["PGPORT"] == "5432"
    assert env["PGDATABASE"] == "caseproof_s2_ci"
    assert env["PGUSER"] == "postgres"
    assert env["PGCONNECT_TIMEOUT"] == "5"
    assert env["PGPASSWORD"] == "caseproof_ephemeral_ci"
    for forbidden in ("PGHOSTADDR", "PGSERVICE", "PGOPTIONS", "PGSERVICEFILE", "PGSSLMODE"):
        assert forbidden not in env


@pytest.mark.parametrize(("name", "value"), [
    ("PGHOSTADDR", "198.51.100.2"),
    ("PGHOSTADDR", "127.0.0.1"),
    ("PGHOST", "localhost"),
    ("PGHOST", "localhost,host.example"),
    ("PGPORT", "6432"),
    ("PGDATABASE", "other"),
    ("PGUSER", "other"),
    ("PGPASSWORD", "other"),
    ("CASEPROOF_DISPOSABLE_DB", "NO"),
])
def test_disposable_env_rejects_destination_credential_or_role_override(
    disposable_pg_env: None,
    monkeypatch: pytest.MonkeyPatch, name: str, value: str,
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        _isolated_postgres_env()


def test_manual_workflow_uses_main_only_and_environment_only_secrets() -> None:
    path = ROOT / ".github/workflows/s2-007-signed-tenancy.yml"
    data = json.loads(path.read_text())
    assert data["on"] == {"workflow_dispatch": {}}
    assert data["permissions"] == {"contents": "read"}
    job = data["jobs"]["verify"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.repository == 'haytamAroui/caseproof'" in job["if"]
    assert job["environment"] == "caseproof-dev-live-auth"
    assert job["services"]["postgres"]["image"] == "postgres:17"
    assert job["env"]["CASEPROOF_DISPOSABLE_DB"] == "YES"
    assert job["env"]["PGHOST"] == "127.0.0.1"
    assert job["env"]["PGDATABASE"] == "caseproof_s2_ci"
    assert job["env"]["PGUSER"] == "postgres"
    steps = job["steps"]
    assert steps[0]["with"]["ref"] == "main"
    assert steps[0]["with"]["persist-credentials"] is False
    assert "secrets" not in json.dumps(steps[:-1])
    final = steps[-1]
    assert final["run"] == "python3 -m scripts.verify_s2_007_disposable_tenancy"
    assert final["env"]["CASEPROOF_LIVE_AUTH_TEST"] == "YES"
    assert final["env"]["CASEPROOF_S2_007_REAL_AUTH"] == "YES"
    for key in (
        "CASEPROOF_DEV_PUBLISHABLE_KEY",
        "CASEPROOF_DEV_AUTH_A_EMAIL", "CASEPROOF_DEV_AUTH_A_PASSWORD",
        "CASEPROOF_DEV_AUTH_B_EMAIL", "CASEPROOF_DEV_AUTH_B_PASSWORD",
    ):
        assert final["env"][key] == "$" + "{{ secrets." + key + " }}"


def test_normal_ci_only_uses_synthetic_subjects() -> None:
    workflow = (ROOT / ".github/workflows/kernel-boundary.yml").read_text()
    assert "CASEPROOF_S2_007_SYNTHETIC=YES" in workflow
    assert "scripts.verify_s2_007_disposable_tenancy" in workflow
    assert "CASEPROOF_DEV_AUTH" not in workflow
