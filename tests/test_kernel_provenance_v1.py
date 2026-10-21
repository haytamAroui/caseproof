"""Stage 1 provenance invariants, including negative controls."""
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.evidence_kernel.domain.provenance import (
    InMemoryProvenanceLedger,
    ProvenanceConflict,
    ProvenanceIntegrityError,
)


def ledger():
    return InMemoryProvenanceLedger()


def add(store, tenant="a", event="evt-1", subject="claim-1"):
    return store.append(
        tenant, event, "claim.extracted", subject, "agent-1",
        {"quote": "Hello", "source_version": "v1"},
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_deterministic_chain_and_sequence():
    store = ledger()
    first = add(store)
    second = add(store, event="evt-2")
    assert first.sequence == 1 and second.sequence == 2
    assert first.previous_hash == "0" * 64
    assert second.previous_hash == first.event_hash
    assert store.verify("a")
    assert add(ledger()).event_hash == first.event_hash


def test_tenant_isolation_and_same_event_id_per_tenant():
    store = ledger()
    add(store, "a")
    add(store, "b")
    assert len(store.history("a")) == len(store.history("b")) == 1
    assert store.history("a")[0].event_hash != store.history("b")[0].event_hash


def test_duplicate_id_rejected_without_mutation():
    store = ledger()
    add(store)
    with pytest.raises(ProvenanceConflict):
        add(store)
    assert len(store.history("a")) == 1


def test_tampering_detected_and_future_appends_blocked():
    store = ledger()
    add(store)
    event = store._events["a"][0]
    store._events["a"] = (replace(event, actor_id="attacker"),)
    assert not store.verify("a")
    with pytest.raises(ProvenanceIntegrityError):
        store.history("a")
    with pytest.raises(ProvenanceIntegrityError):
        add(store, event="evt-2")


def test_timestamp_and_identifier_fail_closed():
    store = ledger()
    with pytest.raises(ValueError):
        store.append("a", "e", "kind", "s", "actor", {}, occurred_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        store.append("", "e", "kind", "s", "actor", {})
    assert store.history("a") == ()


def test_payload_snapshot_not_mutated_by_caller():
    store = ledger()
    payload = {"nested": {"value": "original"}}
    event = store.append("a", "e", "kind", "s", "actor", payload)
    payload["nested"]["value"] = "changed"
    assert "original" in event.payload_json
    assert "changed" not in event.payload_json


def test_subject_filter_does_not_break_chain_verification():
    store = ledger()
    add(store)
    add(store, event="evt-2", subject="claim-2")
    assert len(store.history("a", "claim-1")) == 1
    assert store.verify("a")
