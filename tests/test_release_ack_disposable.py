"""Protect the exact PR204 release acknowledgment contract and DB boundary."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.verify_release_ack_disposable import (
    ACTOR,
    DIGEST,
    SQL,
    ack,
    insert_release,
    invalid_receipts,
    release_id,
)


def test_14_invalid_release_payloads_have_distinct_cases() -> None:
    invalid = invalid_receipts(datetime.now(UTC))
    assert len(invalid) == 14
    names = [name for name, _ in invalid]
    assert len(names) == len(set(names))
    assert {"missing", "actor_mismatch", "release_id_mismatch", "snapshot_mismatch",
            "scope_mismatch", "expired_timestamp", "future_timestamp",
            "extra_manifest_key"} <= set(names)


def test_valid_receipt_contract_matches_api_and_sql() -> None:
    value = ack(1, datetime.now(UTC))
    assert len(value) == 10
    assert value["actor_id"] == ACTOR
    assert value["snapshot_hash"] == DIGEST
    assert value["release_id"] == release_id(1)
    assert value["schema"] == "caseproof-release-ack-v1"
    assert value["intent"] == "AUTHORIZE_REVIEW_RECORD_RELEASE"
    assert len(value["notice"]) >= 30
    parsed = json.loads(insert_release(1, value).split("$caseproof_payload$")[1])
    assert parsed["release_acknowledgement"] == value
    assert parsed["review_completeness"]["release_type"] == "complete_review"


def test_sql_fence_is_original_source_not_stubbed_logic() -> None:
    source = SQL.read_text()
    assert "security invoker" in source
    assert "before insert on caseproof.dossier_releases" in source
    assert "revoke all on function caseproof.release_acknowledgement_fence()" in source
    assert "new.actor_id::text" in source
    assert "new.snapshot_hash" in source
    assert "42501" in source
    assert "ack->>'release_type'" in source


def test_workflow_isolation_and_no_live_deployment() -> None:
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/release-ack-fence-disposable.yml").read_text()
    assert "postgres:17" in workflow
    assert "CASEPROOF_DISPOSABLE_DB" in workflow
    assert "caseproof_s2_ci" in workflow
    assert "secrets." not in workflow
    assert "pull_request:" in workflow
    assert "scripts.verify_release_ack_disposable" in workflow


def test_disposable_verifier_does_not_authorize_pilot() -> None:
    source = (Path(__file__).resolve().parents[1] /
              "scripts/verify_release_ack_disposable.py").read_text()
    assert '"signed_live_export_verified": False' in source
    assert '"pilot_deployment_authorized": False' in source
    assert '"live_database_modified": False' in source
