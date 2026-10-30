"""S2-004 non-approval fingerprint tests; PostgreSQL integration lives in CI.

No test in this module authenticates a user or proves durable execution.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from apps.api.internal_observation_contract import (
    InternalObservation,
    semantic_input_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/proposals/S2-004_disposable_observation.sql").read_text(
    encoding="utf-8"
)
A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
CASE = UUID("aaaaaaaa-1111-4111-8111-111111111111")


def command() -> InternalObservation:
    return InternalObservation(
        case_id=CASE,
        expected_case_revision=2,
        expected_scope_version=1,
        expected_manifest_revision=1,
        expected_policy_version="test-v1",
        idempotency_key="review-note-request-A",
        observation_sha256="a" * 64,
    )


def test_fingerprint_is_deterministic_replayable_and_actor_scoped() -> None:
    c = command()
    first = semantic_input_sha256(A, c)
    assert first == semantic_input_sha256(A, c)
    assert re.fullmatch(r"[0-9a-f]{64}", first)
    assert first != semantic_input_sha256(B, c)
    assert first != semantic_input_sha256(A, replace(c, observation_sha256="b" * 64))
    assert first != semantic_input_sha256(A, replace(c, idempotency_key="other"))
    assert first != semantic_input_sha256(A, replace(c, expected_case_revision=3))
    assert first != semantic_input_sha256(A, replace(c, expected_scope_version=2))
    assert first != semantic_input_sha256(A, replace(c, expected_manifest_revision=2))
    assert first != semantic_input_sha256(A, replace(c, expected_policy_version="test-v2"))


@pytest.mark.parametrize(("field", "value"), [
    ("case_id", UUID(int=0)),
    ("case_id", "not-a-uuid"),
    ("expected_case_revision", 0),
    ("expected_case_revision", True),
    ("expected_scope_version", -1),
    ("expected_manifest_revision", 1.0),
    ("expected_policy_version", ""),
    ("expected_policy_version", " " * 3),
    ("expected_policy_version", "x" * 129),
    ("idempotency_key", ""),
    ("idempotency_key", " leading-space"),
    ("idempotency_key", "x" * 129),
    ("observation_sha256", "G" * 64),
    ("observation_sha256", "a" * 63),
])
def test_untrusted_invalid_semantic_inputs_are_rejected(
    field: str, value: object
) -> None:
    with pytest.raises(ValueError):
        replace(command(), **{field: value})


def test_non_uuid_subject_and_non_strict_command_fail() -> None:
    with pytest.raises(ValueError):
        semantic_input_sha256(UUID(int=0), command())
    with pytest.raises(ValueError):
        semantic_input_sha256("unverified user", command())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        semantic_input_sha256(A, {})  # type: ignore[arg-type]


def test_sql_is_disposable_only_non_approval_without_runtime_grants() -> None:
    assert "create function caseproof._s2_004_disposable_observation" in SQL.lower()
    assert "security invoker" in SQL.lower()
    assert "security definer" not in SQL.lower()
    assert "revoke all on function" in SQL.lower()
    assert "from public, anon, authenticated;" in SQL.lower()
    assert "grant execute" not in SQL.lower()
    assert "set search_path = pg_catalog, pg_temp" in SQL.lower()
    assert "for update of m" in SQL.lower()
    assert "for update;" in SQL.lower()
    assert "case_revision = c.case_revision + 1" in SQL
    assert "input_sha256_hex" in SQL
    assert "caseproof.idempotency_records" in SQL
    assert "caseproof.audit_events" in SQL
    assert "caseproof._s2_004_disposable_event_revisions" in SQL
    assert "and er.committed_revision = v_next" in SQL
    assert "and er.committed_revision <= v_case.case_revision" in SQL
    assert "and 'case:read' = any(m.actions)" in SQL
    assert "audit" in SQL and "receipt" in SQL
    assert "set state=" not in SQL.lower()
    assert "approved_conclusion" not in re.sub(r"--[^\n]*", "", SQL.lower())


def test_no_new_live_route_or_staged_migration() -> None:
    app = (ROOT / "apps/api/main.py").read_text(encoding="utf-8")
    assert "/v2/" not in app
    assert "internal_observation_contract" not in app
    assert "S2-004_disposable_observation.sql" not in (
        ROOT / "scripts/verify_s2_002_database.py"
    ).read_text(encoding="utf-8")
    assert {p.name for p in (ROOT / "supabase/migrations").glob("*.sql")} == {
        "20261022001009_caseproof_tenant_foundation.sql",
        "20261030110000_caseproof_dev_atomic_bundle_registration.sql",
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


def test_ci_runs_real_disposable_postgres_function_proof() -> None:
    workflow = (ROOT / ".github/workflows/kernel-boundary.yml").read_text(
        encoding="utf-8"
    )
    harness = (ROOT / "scripts/verify_s2_004_database.py").read_text(
        encoding="utf-8"
    )
    assert "python -m scripts.verify_s2_004_database" in workflow
    assert "from scripts.verify_s2_002_database import _cmd, _env, _run" in harness
    assert "env = _env()" in harness
    guard = (ROOT / "scripts/verify_s2_002_database.py").read_text(encoding="utf-8")
    assert 'os.environ.get("CASEPROOF_DISPOSABLE_DB") != "YES"' in guard
    assert 'not in {"127.0.0.1", "localhost"}' in guard
    assert "S2-004_DISPOSABLE_ATOMIC_OBSERVATION_PASSED" in harness
    assert "subprocess.Popen(" in harness
    assert "AUDIT_FAILURE" in harness
    assert "RECEIPT_FAILURE" in harness
    assert "CONCURRENT_REPLAY" in harness
    assert "STRUCTURALLY_VALID_FORGED_REVISION" in harness
    assert "masked(base)" in harness
    assert "caseproof._s2_004_disposable_event_revisions" in harness
