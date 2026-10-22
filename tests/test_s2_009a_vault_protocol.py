"""S2-009a fault injection for the staged, nonproduction Evidence Vault ports."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from apps.api.evidence_vault_protocol import (
    MAX_REFERENCE_BYTES,
    UploadIntent,
    VaultConflict,
    VaultCoordinator,
    VaultMissing,
    VaultRecord,
    VaultScope,
    VaultState,
    VaultUnavailable,
    VaultUnknownOutcome,
)

ORG = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CASE = UUID("aaaaaaaa-1111-4111-8111-111111111111")
FOREIGN_ORG = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
FOREIGN_CASE = UUID("aaaaaaaa-2222-4222-8222-aaaaaaaaaaaa")
ORIGINAL = b"%PDF-1.7\nsynthetic invoice # 1\n"


class FakePrivateStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_count = 0
        self.throw_after_put = False
        self.throw_before_put = False
        self.read_outage = False
        self.on_read: None | object = None

    def put_once(self, key: str, data: bytes) -> None:
        self.put_count += 1
        if self.throw_before_put:
            raise ConnectionError("provider did not acknowledge pre-dispatch")
        if key in self.objects:
            raise RuntimeError("upsert forbidden")
        self.objects[key] = bytes(data)
        if self.throw_after_put:
            raise ConnectionError("write may have committed without acknowledgment")

    def read_exact(self, key: str) -> bytes | None:
        if self.read_outage:
            raise ConnectionError("simulated provider outage")
        if callable(self.on_read):
            self.on_read()
        return self.objects.get(key)


class FakeAtomicLedger:
    """Synthetic stand-in. It does NOT establish real SQL atomicity/RLS/identity."""

    def __init__(self) -> None:
        self.records: dict[tuple[VaultScope, UUID], VaultRecord] = {}
        self.events: list[tuple[str, UUID]] = []
        self.case_revisions: dict[VaultScope, int] = {}
        self.lose_publish_ack = False
        self.fail_audit_insertion = False

    def create_pending(self, intent: UploadIntent) -> VaultRecord:
        key = (intent.scope, intent.intent_id)
        if key in self.records:
            raise ValueError("duplicate upload intent")
        value = VaultRecord(intent, VaultState.PENDING, 1, None)
        self.records[key] = value
        return value

    def get_scoped(self, scope: VaultScope, intent_id: UUID) -> VaultRecord | None:
        return self.records.get((scope, intent_id))

    def _event(self, expected: VaultRecord, state: VaultState, op: str) -> VaultRecord:
        key = (expected.intent.scope, expected.intent.intent_id)
        if self.records.get(key) != expected:
            raise ValueError("stale availability revision")
        if self.fail_audit_insertion:
            raise ValueError("atomic event insert failed")
        aid = uuid4()
        next_record = VaultRecord(expected.intent, state, expected.revision + 1, aid)
        self.records[key] = next_record
        self.events.append((op, aid))
        self.case_revisions[expected.intent.scope] = (
            self.case_revisions.get(expected.intent.scope, 0) + 1
        )
        return next_record

    def publish_verified(self, expected: VaultRecord) -> VaultRecord:
        if expected.state != VaultState.PENDING:
            raise ValueError("only pending can become verified")
        result = self._event(expected, VaultState.VERIFIED, "verified")
        if self.lose_publish_ack:
            raise ConnectionError("commit succeeded but response was lost")
        return result

    def mark_unavailable(self, expected: VaultRecord, reason_code: str) -> VaultRecord:
        if expected.state != VaultState.VERIFIED:
            raise ValueError("only verified source availability can be invalidated")
        if reason_code not in {"missing", "digest_mismatch"}:
            raise ValueError("unknown source availability cause")
        return self._event(expected, VaultState.UNAVAILABLE, reason_code)


def scope() -> VaultScope:
    return VaultScope(ORG, CASE)


def create(
    service: VaultCoordinator, *, data: bytes = ORIGINAL, target: VaultScope | None = None,
) -> UploadIntent:
    return service.begin(
        scope=target or scope(),
        sha256_hex=hashlib.sha256(data).hexdigest(),
        byte_length=len(data),
        media_type="application/pdf",
    )


@pytest.fixture()
def setup() -> tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger]:
    store = FakePrivateStore()
    ledger = FakeAtomicLedger()
    return VaultCoordinator(store=store, ledger=ledger), store, ledger


def test_begin_creates_scoped_unpredictable_pending_intent_before_any_blob(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    a, b = create(service), create(service)
    assert a.object_key != b.object_key
    assert a.object_key.startswith(f"org/{ORG.hex}/case/{CASE.hex}/sources/")
    assert "invoice" not in a.object_key
    assert ORIGINAL.decode(errors="ignore") not in a.object_key
    assert store.put_count == 0 and store.objects == {}
    assert ledger.get_scoped(scope(), a.intent_id).state == VaultState.PENDING  # type: ignore[union-attr]
    assert ledger.events == []


def test_publish_and_read_exact_bytes_only_after_verified_receipt(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    assert service.reconcile_pending(scope=scope(), intent_id=intent.intent_id).state == VaultState.PENDING
    completed = service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)
    assert completed.state == VaultState.VERIFIED
    assert completed.revision == 2 and completed.availability_audit_id is not None
    assert store.put_count == 1
    assert ledger.events[0][0] == "verified"
    assert service.read(scope=scope(), intent_id=intent.intent_id) == ORIGINAL
    assert ledger.case_revisions[scope()] == 1
    with pytest.raises(VaultConflict):
        service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)
    assert store.put_count == 1


@pytest.mark.parametrize("bad", [
    b"", b"changed", ORIGINAL + b"x", ORIGINAL[:-1],
])
def test_wrong_bytes_never_dispatch_to_store(
    bad: bytes, setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    with pytest.raises(VaultConflict):
        service.upload(scope=scope(), intent_id=intent.intent_id, data=bad)
    assert store.put_count == 0
    assert ledger.get_scoped(scope(), intent.intent_id).state == VaultState.PENDING  # type: ignore[union-attr]


@pytest.mark.parametrize(("media", "size", "digest"), [
    ("image/png", 25, "a" * 64),
    ("application/pdf", 0, "a" * 64),
    ("application/pdf", MAX_REFERENCE_BYTES + 1, "a" * 64),
    ("application/pdf", True, "a" * 64),
    ("application/pdf", 25, "A" * 64),
    ("application/pdf", 25, "g" * 64),
])
def test_invalid_frozen_intents_are_rejected_before_storage(
    media: str, size: int, digest: str,
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, _ = setup
    with pytest.raises(ValueError):
        service.begin(scope=scope(), sha256_hex=digest, byte_length=size, media_type=media)
    assert store.put_count == 0


def test_cross_org_and_same_org_other_case_cannot_read_or_write(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, _ = setup
    intent = create(service)
    foreign = (VaultScope(FOREIGN_ORG, CASE), VaultScope(ORG, FOREIGN_CASE))
    for s in foreign:
        with pytest.raises(VaultMissing):
            service.upload(scope=s, intent_id=intent.intent_id, data=ORIGINAL)
        with pytest.raises(VaultMissing):
            service.reconcile_pending(scope=s, intent_id=intent.intent_id)
        with pytest.raises(VaultMissing):
            service.read(scope=s, intent_id=intent.intent_id)
    assert store.put_count == 0


def test_ambiguous_object_write_is_reconciled_without_second_put(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    store.throw_after_put = True
    with pytest.raises(VaultUnknownOutcome):
        service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)
    assert store.put_count == 1
    assert ledger.get_scoped(scope(), intent.intent_id).state == VaultState.PENDING  # type: ignore[union-attr]
    complete = service.reconcile_pending(scope=scope(), intent_id=intent.intent_id)
    assert complete.state == VaultState.VERIFIED
    assert store.put_count == 1
    assert service.read(scope=scope(), intent_id=intent.intent_id) == ORIGINAL


def test_missing_pending_object_stays_pending_and_is_never_marked_verified(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    store.throw_before_put = True
    with pytest.raises(VaultUnknownOutcome):
        service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)
    assert service.reconcile_pending(scope=scope(), intent_id=intent.intent_id).state == VaultState.PENDING
    assert ledger.events == []


def test_read_back_corrupt_prepublication_does_not_record_verified(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    store.objects[intent.object_key] = b"corrupted object"
    with pytest.raises(VaultUnavailable):
        service.reconcile_pending(scope=scope(), intent_id=intent.intent_id)
    assert ledger.events == []
    assert ledger.get_scoped(scope(), intent.intent_id).state == VaultState.PENDING  # type: ignore[union-attr]


def test_unknown_db_commit_is_reconciled_without_second_blob_write(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    ledger.lose_publish_ack = True
    with pytest.raises(VaultUnknownOutcome):
        service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)
    assert store.put_count == 1
    assert ledger.get_scoped(scope(), intent.intent_id).state == VaultState.VERIFIED  # type: ignore[union-attr]
    assert service.reconcile_pending(scope=scope(), intent_id=intent.intent_id).state == VaultState.VERIFIED
    assert len(ledger.events) == 1


def test_missing_published_object_revokes_availability_and_denies_all_future_reads(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)
    del store.objects[intent.object_key]
    with pytest.raises(VaultUnavailable):
        service.read(scope=scope(), intent_id=intent.intent_id)
    record = ledger.get_scoped(scope(), intent.intent_id)
    assert record is not None and record.state == VaultState.UNAVAILABLE
    assert record.revision == 3
    assert len(ledger.events) == 2
    assert ledger.case_revisions[scope()] == 2
    # Restoring equal bytes does NOT magically publish a verified head.
    store.objects[intent.object_key] = ORIGINAL
    with pytest.raises(VaultUnavailable):
        service.read(scope=scope(), intent_id=intent.intent_id)


def test_corrupt_published_object_fails_closed_even_when_audit_insert_fails(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)
    store.objects[intent.object_key] = b"tampered" + ORIGINAL
    ledger.fail_audit_insertion = True
    with pytest.raises(VaultUnavailable):
        service.read(scope=scope(), intent_id=intent.intent_id)
    assert ledger.get_scoped(scope(), intent.intent_id).state == VaultState.VERIFIED  # type: ignore[union-attr]
    assert len(ledger.events) == 1  # simulated rollback
    assert ledger.case_revisions[scope()] == 1
    ledger.fail_audit_insertion = False
    with pytest.raises(VaultUnavailable):
        service.read(scope=scope(), intent_id=intent.intent_id)
    assert ledger.get_scoped(scope(), intent.intent_id).state == VaultState.UNAVAILABLE  # type: ignore[union-attr]


def test_external_storage_outage_never_masquerades_as_confirmed_missing(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)
    store.read_outage = True
    with pytest.raises(VaultUnavailable):
        service.read(scope=scope(), intent_id=intent.intent_id)
    assert ledger.get_scoped(scope(), intent.intent_id).state == VaultState.VERIFIED  # type: ignore[union-attr]
    assert len(ledger.events) == 1


def test_changed_availability_revision_during_read_blocks_returning_stale_bytes(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    service.upload(scope=scope(), intent_id=intent.intent_id, data=ORIGINAL)

    def change_availability() -> None:
        store.on_read = None
        current = ledger.get_scoped(scope(), intent.intent_id)
        assert current is not None
        ledger.mark_unavailable(current, "missing")

    store.on_read = change_availability
    with pytest.raises(VaultUnavailable):
        service.read(scope=scope(), intent_id=intent.intent_id)


def test_forged_stale_record_and_orphan_metadata_fail_closed(
    setup: tuple[VaultCoordinator, FakePrivateStore, FakeAtomicLedger],
) -> None:
    service, store, ledger = setup
    intent = create(service)
    rec = ledger.get_scoped(scope(), intent.intent_id)
    assert rec is not None
    with pytest.raises(ValueError, match="stale availability revision"):
        ledger.publish_verified(replace(rec, revision=rec.revision + 1))
    with pytest.raises(ValueError):
        replace(intent, object_key="public/supplier-invoice.pdf")
    with pytest.raises(ValueError):
        VaultRecord(intent, VaultState.VERIFIED, 2, None)
    with pytest.raises(ValueError):
        VaultScope(UUID(int=0), CASE)
    assert store.put_count == 0


def test_no_automatic_signed_urls_or_live_sql_wiring() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "apps/api/evidence_vault_protocol.py").read_text()
    app = (root / "apps/api/main.py").read_text()
    assert "from supabase" not in source.lower()
    assert "import supabase" not in source.lower()
    assert "signed_url" not in source.lower()
    assert "service_role" not in source  # never invokes privileged storage access
    assert "evidence_vault_protocol" not in app
    assert "/v2/" not in app
    assert len(list((root / "supabase/migrations").glob("*.sql"))) == 1
