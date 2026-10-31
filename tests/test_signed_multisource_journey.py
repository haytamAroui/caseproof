"""Signed multi-source journey integration using the existing Storage interface."""

from hashlib import sha256
from uuid import uuid4

import pytest

from apps.api.signed_multisource_journey import SignedMultiSourceJourney
from apps.api.signed_supabase_originals import (
    OriginalRef,
    PrivateStorageDenied,
    PrivateStorageExists,
    PrivateStorageIntegrityError,
    PrivateStorageOutcomeUnknown,
)
from domains.disputes.multisource_manifest import MultiSourceManifest, SourceItem, SourceRole


class FakeSignedStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.revoked = False

    def put_once(self, ref: OriginalRef, bearer: str, payload: bytes) -> None:
        if self.revoked or bearer != "owner":
            raise PrivateStorageDenied("denied")
        if sha256(payload).hexdigest() != ref.sha256_hex:
            raise ValueError("tampered")
        self.objects[ref.path] = payload

    def get_verified(self, ref: OriginalRef, bearer: str) -> bytes:
        if self.revoked or bearer != "owner":
            raise PrivateStorageDenied("denied")
        return self.objects[ref.path]


def fixture():
    org, case = uuid4(), uuid4()
    refs: dict[str, OriginalRef] = {}
    payloads: dict[str, bytes] = {}
    items = []
    for role, data in ((SourceRole.INVENTORY, b"inventory"), (SourceRole.EXHIBIT, b"pdf one"), (SourceRole.EXHIBIT, b"scan two")):
        doc, version = uuid4(), uuid4()
        digest = sha256(data).hexdigest()
        ref = OriginalRef(org, case, doc, version, digest, "text/plain")
        refs[str(version)] = ref
        payloads[str(version)] = data
        items.append(SourceItem(str(version), role, digest))
    return MultiSourceManifest(str(case), items[0], tuple(items[1:])), refs, payloads


def test_signed_upload_and_reopen_multiple_originals() -> None:
    manifest, refs, payloads = fixture()
    storage = FakeSignedStorage()
    journey = SignedMultiSourceJourney(storage)
    journey.upload_and_verify(manifest=manifest, refs=refs, payloads=payloads, bearer="owner")
    assert journey.reopen_verified(manifest=manifest, refs=refs, bearer="owner") == tuple(payloads.values())
    storage.revoked = True
    with pytest.raises(PrivateStorageDenied):
        journey.reopen_verified(manifest=manifest, refs=refs, bearer="owner")


def test_cross_matter_reference_fails_before_any_write() -> None:
    manifest, refs, payloads = fixture()
    first = next(iter(refs))
    ref = refs[first]
    refs[first] = OriginalRef(ref.org_id, uuid4(), ref.document_id, ref.version_id, ref.sha256_hex, ref.content_type)
    storage = FakeSignedStorage()
    with pytest.raises(ValueError, match="bound"):
        SignedMultiSourceJourney(storage).upload_and_verify(manifest=manifest, refs=refs, payloads=payloads, bearer="owner")
    assert not storage.objects


def test_missing_exhibit_rejected_before_upload() -> None:
    manifest, refs, payloads = fixture()
    payloads.pop(next(reversed(payloads)))
    storage = FakeSignedStorage()
    with pytest.raises(ValueError, match="exact"):
        SignedMultiSourceJourney(storage).upload_and_verify(manifest=manifest, refs=refs, payloads=payloads, bearer="owner")
    assert not storage.objects


def test_tampered_last_exhibit_never_writes_earlier_objects() -> None:
    manifest, refs, payloads = fixture()
    last = next(reversed(payloads))
    payloads[last] += b"tampered"
    storage = FakeSignedStorage()
    with pytest.raises(PrivateStorageIntegrityError, match="source bytes disagree"):
        SignedMultiSourceJourney(storage).upload_and_verify(
            manifest=manifest, refs=refs, payloads=payloads, bearer="owner",
        )
    assert storage.objects == {}


def test_wrong_payload_type_fails_before_first_write() -> None:
    manifest, refs, payloads = fixture()
    last = next(reversed(payloads))
    payloads[last] = "not bytes"  # type: ignore[assignment]
    storage = FakeSignedStorage()
    with pytest.raises(PrivateStorageIntegrityError, match="byte bounds"):
        SignedMultiSourceJourney(storage).upload_and_verify(
            manifest=manifest, refs=refs, payloads=payloads, bearer="owner",
        )
    assert storage.objects == {}


def test_cross_organization_reference_fails_before_writing() -> None:
    manifest, refs, payloads = fixture()
    last = next(reversed(refs))
    ref = refs[last]
    refs[last] = OriginalRef(uuid4(), ref.case_id, ref.document_id, ref.version_id,
                             ref.sha256_hex, ref.content_type)
    storage = FakeSignedStorage()
    with pytest.raises(ValueError, match="multiple organizations"):
        SignedMultiSourceJourney(storage).upload_and_verify(
            manifest=manifest, refs=refs, payloads=payloads, bearer="owner",
        )
    assert storage.objects == {}


def test_signed_m1_upload_revocation_prevents_write() -> None:
    manifest, refs, payloads = fixture()
    storage = FakeSignedStorage()
    storage.revoked = True
    with pytest.raises(PrivateStorageDenied):
        SignedMultiSourceJourney(storage).upload_and_verify(
            manifest=manifest, refs=refs, payloads=payloads, bearer="owner",
        )
    assert storage.objects == {}



class InterruptedSignedStorage(FakeSignedStorage):
    def __init__(self) -> None:
        super().__init__()
        self.fail_once = True
        self.replays = 0
        self.corrupt_on_read = False

    def put_once(self, ref: OriginalRef, bearer: str, payload: bytes) -> None:
        if ref.path in self.objects:
            self.replays += 1
            raise PrivateStorageExists("already stored")
        super().put_once(ref, bearer, payload)
        if self.fail_once:
            self.fail_once = False
            raise PrivateStorageOutcomeUnknown("write may have committed")

    def get_verified(self, ref: OriginalRef, bearer: str) -> bytes:
        value = super().get_verified(ref, bearer)
        if self.corrupt_on_read or sha256(value).hexdigest() != ref.sha256_hex:
            raise PrivateStorageIntegrityError("invalid signed original")
        return value


def test_unknown_write_outcome_recovers_only_with_verified_readback() -> None:
    manifest, refs, payloads = fixture()
    storage = InterruptedSignedStorage()
    journey = SignedMultiSourceJourney(storage)
    journey.upload_and_verify(manifest=manifest, refs=refs, payloads=payloads, bearer="owner")
    assert len(storage.objects) == 3
    journey.upload_and_verify(manifest=manifest, refs=refs, payloads=payloads, bearer="owner")
    assert len(storage.objects) == 3
    assert storage.replays == 3  # no overwrites when re-running
    assert journey.reopen_verified(manifest=manifest, refs=refs, bearer="owner") == (
        tuple(payloads.values())
    )


def test_existing_object_mismatched_sha_never_marks_upload_complete() -> None:
    manifest, refs, payloads = fixture()
    storage = InterruptedSignedStorage()
    storage.fail_once = False
    first = next(iter(refs))
    storage.objects[refs[first].path] = b"wrong bytes from stale write"
    with pytest.raises(PrivateStorageIntegrityError):
        SignedMultiSourceJourney(storage).upload_and_verify(
            manifest=manifest, refs=refs, payloads=payloads, bearer="owner",
        )
    assert len(storage.objects) == 1  # corruption does not cause later writes


def test_unknown_write_without_authorized_readback_is_not_a_success() -> None:
    manifest, refs, payloads = fixture()

    class GoneStorage(InterruptedSignedStorage):
        def get_verified(self, ref: OriginalRef, bearer: str) -> bytes:
            raise PrivateStorageDenied("revoked or absent")

    storage = GoneStorage()
    with pytest.raises(PrivateStorageDenied):
        SignedMultiSourceJourney(storage).upload_and_verify(
            manifest=manifest, refs=refs, payloads=payloads, bearer="owner",
        )


def test_revocation_during_reconcile_fails_closed() -> None:
    manifest, refs, payloads = fixture()

    class RevokedOnRead(InterruptedSignedStorage):
        def get_verified(self, ref: OriginalRef, bearer: str) -> bytes:
            self.revoked = True
            return super().get_verified(ref, bearer)

    storage = RevokedOnRead()
    with pytest.raises(PrivateStorageDenied):
        SignedMultiSourceJourney(storage).upload_and_verify(
            manifest=manifest, refs=refs, payloads=payloads, bearer="owner",
        )
