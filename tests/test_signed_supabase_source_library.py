"""The live read path actually composes signed PostgREST + private Storage.

Mocks HTTPS ONLY. The protected manual Auth step supplies actual JWTs.
"""
from __future__ import annotations

import hashlib
import http.client
import json
from uuid import uuid4

import pytest

from apps.api.signed_supabase_originals import (
    PrivateStorageDenied,
    PrivateStorageIntegrityError,
    SignedOriginalsStorage,
)
from apps.api.signed_supabase_source_library import SignedSourceLibrary

DATA = b"caseproof source version real-remote-composition-fixture"
ORG, CASE, DOC, VERSION = (uuid4() for _ in range(4))
KEY = "sb_publishable_fixture_only"


def row(*, sha: str | None = None, byte_length: int | None = None) -> dict[str, object]:
    return {
        "org_id": str(ORG), "case_id": str(CASE),
        "document_id": str(DOC), "version_id": str(VERSION),
        "original_sha256_hex": sha or hashlib.sha256(DATA).hexdigest(),
        "byte_length": len(DATA) if byte_length is None else byte_length,
        "media_type": "text/plain",
    }


class FakeResponse:
    def __init__(self, status: int, content: bytes) -> None:
        self.status, self.content = status, content

    def read(self, size: int) -> bytes:
        return self.content[:size]


def fake_http(
    monkeypatch: pytest.MonkeyPatch, responses: list[tuple[int, bytes]],
) -> list[tuple[str, str, bytes | None, dict[str, str]]]:
    requests: list[tuple[str, str, bytes | None, dict[str, str]]] = []

    class Connection:
        def __init__(self, host: str, timeout: float) -> None:
            assert host == "ldwmocpxwskvhoojndrd.supabase.co"
            assert timeout == 12.0

        def request(
            self, method: str, path: str, body: bytes | None = None,
            headers: dict[str, str] | None = None,
        ) -> None:
            requests.append((method, path, body, headers or {}))

        def getresponse(self) -> FakeResponse:
            return FakeResponse(*responses.pop(0))

        def close(self) -> None:
            pass

    monkeypatch.setattr(http.client, "HTTPSConnection", Connection)
    return requests


def library() -> SignedSourceLibrary:
    return SignedSourceLibrary(SignedOriginalsStorage(KEY))


def args() -> dict[str, str]:
    return {
        "bearer": "signed-jwt-fixture",
        "case_id": str(CASE), "document_id": str(DOC), "version_id": str(VERSION),
    }


def meta(**kwargs: object) -> tuple[int, bytes]:
    return 200, json.dumps([row(**kwargs)]).encode("utf-8")


def test_signed_metadata_to_storage_real_paths_and_recheck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = fake_http(monkeypatch, [meta(), (200, DATA), meta()])
    assert library().read(**args()) == DATA
    assert [r[0] for r in requests] == ["GET", "GET", "GET"]
    assert "caseproof_private_source_versions" in requests[0][1]
    assert "/storage/v1/object/authenticated/caseproof-originals-dev/" in requests[1][1]
    assert requests[0][3]["Authorization"] == "Bearer signed-jwt-fixture"
    assert requests[1][3]["Authorization"] == "Bearer signed-jwt-fixture"
    assert requests[2][1] == requests[0][1]
    assert "service_role" not in repr(library())


def test_put_once_uses_verified_version_and_reopens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = fake_http(monkeypatch, [
        meta(), (200, b'{"Key":"ok"}'), meta(), (200, DATA), meta(),
    ])
    library().put_once(**args(), data=DATA)
    assert [r[0] for r in requests] == ["GET", "POST", "GET", "GET", "GET"]
    assert requests[1][3]["x-upsert"] == "false"


@pytest.mark.parametrize("reply", [
    (200, b"[]"), (200, b"{}"), (200, b"[{},{}]"),
    (401, b""), (403, b""), (404, b""),
])
def test_missing_or_invalid_signed_source_is_masked(
    monkeypatch: pytest.MonkeyPatch, reply: tuple[int, bytes],
) -> None:
    fake_http(monkeypatch, [reply])
    with pytest.raises(PrivateStorageDenied):
        library().read(**args())


def test_foreign_version_metadata_is_detected_before_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foreign = row()
    foreign["case_id"] = str(uuid4())
    requests = fake_http(monkeypatch, [
        (200, json.dumps([foreign]).encode()),
    ])
    with pytest.raises(PrivateStorageIntegrityError):
        library().read(**args())
    assert len(requests) == 1


def test_stale_grant_rejected_between_read_and_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_http(monkeypatch, [meta(), (200, DATA), (200, b"[]")])
    with pytest.raises(PrivateStorageDenied):
        library().read(**args())


def test_mismatched_signed_blob_digest_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_http(monkeypatch, [meta(), (200, b"tampered")])
    with pytest.raises(PrivateStorageIntegrityError):
        library().read(**args())


def test_length_mismatch_rejected_before_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = fake_http(monkeypatch, [meta(byte_length=len(DATA) + 1)])
    with pytest.raises(PrivateStorageIntegrityError):
        library().put_once(**args(), data=DATA)
    assert len(requests) == 1


@pytest.mark.parametrize("bad", ["INVALID", "00000000-0000-0000-0000-000000000000", "a/b"])
def test_invalid_client_identifiers_never_reach_network(
    monkeypatch: pytest.MonkeyPatch, bad: str,
) -> None:
    requests = fake_http(monkeypatch, [])
    a = args()
    a["document_id"] = bad
    with pytest.raises(PrivateStorageDenied):
        library().read(**a)
    assert not requests
