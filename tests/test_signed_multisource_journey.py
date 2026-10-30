"""Signed multi-source journey integration using the existing Storage interface."""

from hashlib import sha256
from uuid import uuid4

import pytest

from apps.api.signed_multisource_journey import SignedMultiSourceJourney
from apps.api.signed_supabase_originals import OriginalRef, PrivateStorageDenied
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
