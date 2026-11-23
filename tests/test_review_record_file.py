"""Offline review-record replay: synthetic records only, no server involved."""
from hashlib import sha256

import pytest

from scripts.verify_review_record_file import (
    RecordVerificationError,
    verify_record_document,
)


def _canonical(value):
    import json
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def valid_record():
    run = {"schema": "check-run", "snapshot": "x", "observations": []}
    snapshot = _digest("snapshot-a")
    decision = {"actor_id": "11111111-1111-4111-8111-111111111111",
                "disposition": "verified", "rationale": "synthetique"}
    event = {
        "run": snapshot,
        "revision": 1,
        "request": "22222222-2222-4222-8222-222222222222",
        "actor": decision["actor_id"],
        "previous_sha": "0" * 64,
        "decision": decision,
    }
    event_sha = _digest(_canonical(event))
    body = {
        "schema": "caseproof-review-record-v1",
        "case_id": "case-a",
        "document_role": "own_draft",
        "brief": {
            "brief_id": "b", "head_revision": 1, "head_version_id": "v",
            "graph_sha256": _digest("g"), "original_sha256": _digest("o"),
            "document_id": "d", "document_version_id": "dv",
            "case_revision": 1, "exhibit_revision": 1,
        },
        "checks": [{
            "snapshot_sha256": snapshot, "payload_sha256": _digest(_canonical(run)),
            "payload_sha256_verified": True, "case_revision": 1, "exhibit_revision": 1,
            "run": run,
        }],
        "reviews": [{
            "snapshot_sha256": snapshot, "head_sha256": event_sha, "chain_verified": True,
            "decisions": [{
                "revision": 1, "request_id": event["request"],
                "actor_id": decision["actor_id"], "event_sha256": event_sha,
                "decision": decision,
            }],
        }],
        "note": "synthetique",
    }
    body["record_sha256"] = _digest(_canonical(body))
    return body


def test_valid_record_replays_offline():
    steps = verify_record_document(valid_record())
    assert any("payload digest replayed" in s for s in steps)
    assert any("replayed from genesis" in s for s in steps)
    assert any("record body digest" in s for s in steps)


def test_tampered_decision_fails_closed():
    body = valid_record()
    body["reviews"][0]["decisions"][0]["decision"]["disposition"] = "approved"
    body["record_sha256"] = _digest(_canonical(
        {k: v for k, v in body.items() if k != "record_sha256"}))
    with pytest.raises(RecordVerificationError, match="tampered recorded review event"):
        verify_record_document(body)


def test_tampered_run_payload_fails_closed():
    body = valid_record()
    body["checks"][0]["run"]["observations"] = ["forged"]
    body["record_sha256"] = _digest(_canonical(
        {k: v for k, v in body.items() if k != "record_sha256"}))
    with pytest.raises(RecordVerificationError, match="payload digest mismatch"):
        verify_record_document(body)


def test_tampered_body_digest_fails_closed():
    body = valid_record()
    body["brief"]["head_revision"] = 2
    with pytest.raises(RecordVerificationError, match="record body digest mismatch"):
        verify_record_document(body)


def test_wrong_schema_rejected():
    with pytest.raises(RecordVerificationError, match="not a caseproof-review-record-v1"):
        verify_record_document({"schema": "other"})


def test_broken_chain_head_fails_closed():
    body = valid_record()
    body["reviews"][0]["head_sha256"] = _digest("other-head")
    body["record_sha256"] = _digest(_canonical(
        {k: v for k, v in body.items() if k != "record_sha256"}))
    with pytest.raises(RecordVerificationError, match="review head mismatch"):
        verify_record_document(body)
