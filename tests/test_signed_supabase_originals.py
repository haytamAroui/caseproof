"""Isolated transport contract checks (no remote Supabase traffic)."""
from __future__ import annotations

import hashlib
import http.client
from uuid import uuid4

import pytest

from apps.api.signed_supabase_originals import (
    BUCKET,
    MAX_BYTES,
    OriginalRef,
    PrivateStorageDenied,
    PrivateStorageExists,
    PrivateStorageIntegrityError,
    PrivateStorageFailure,
    PrivateStorageOutcomeUnknown,
    SignedOriginalsStorage,
)

DATA = b"caseproof: original file bytes are immutable\n"
HASH = hashlib.sha256(DATA).hexdigest()
KEY = "sb_publishable_fixture_only"


def _ref() -> OriginalRef:
    return OriginalRef(uuid4(), uuid4(), uuid4(), uuid4(), HASH, "text/plain")


class FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body

    def read(self, size: int) -> bytes:
        return self.body[:size]


class FakeConnection:
    def __init__(self, host: str, *, timeout: float, results: list[tuple[int, bytes]],
                 requests: list[tuple[str, str, bytes | None, dict[str, str]]]) -> None:
        assert host == "ldwmocpxwskvhoojndrd.supabase.co"
        assert timeout == 12.0
        self.results = results
        self.requests = requests

    def request(
        self, method: str, path: str, body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.requests.append((method, path, body, headers or {}))

    def getresponse(self) -> FakeResponse:
        status, body = self.results.pop(0)
        return FakeResponse(status, body)

    def close(self) -> None:
        pass


def _fake(monkeypatch: pytest.MonkeyPatch, results: list[tuple[int, bytes]]) -> list:
    requests: list[tuple[str, str, bytes | None, dict[str, str]]] = []

    def build(host: str, timeout: float) -> FakeConnection:
        return FakeConnection(host, timeout=timeout, results=results, requests=requests)

    monkeypatch.setattr(http.client, "HTTPSConnection", build)
    return requests


def test_real_api_upload_and_verified_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    ref = _ref()
    requests = _fake(monkeypatch, [(200, b'{"Key":"ok"}'), (200, DATA)])
    storage = SignedOriginalsStorage(KEY)
    storage.put_once(ref, "signed-fixture", DATA)
    assert storage.get_verified(ref, "signed-fixture") == DATA
    assert [r[0] for r in requests] == ["POST", "GET"]
    assert all(r[1] == "/storage/v1/object/" + BUCKET + "/" + ref.path for r in requests)
    assert requests[0][2] == DATA
    assert requests[0][3]["x-upsert"] == "false"
    assert requests[0][3]["Authorization"] == "Bearer signed-fixture"
    assert "sb_secret_" not in repr(storage)
    assert requests[1][2] is None


@pytest.mark.parametrize("status,expected", [
    (409, PrivateStorageExists),
    (400, PrivateStorageDenied), (401, PrivateStorageDenied),
    (403, PrivateStorageDenied), (404, PrivateStorageDenied),
    (422, PrivateStorageDenied),
    (502, PrivateStorageOutcomeUnknown),
])
def test_put_fail_closed(monkeypatch: pytest.MonkeyPatch, status: int, expected: type) -> None:
    _fake(monkeypatch, [(status, b"SENSITIVE_ERROR_NO_LEAK")])
    with pytest.raises(expected) as caught:
        SignedOriginalsStorage(KEY).put_once(_ref(), "signed-fixture", DATA)
    assert "SENSITIVE_ERROR" not in str(caught.value)


@pytest.mark.parametrize("status,expected", [
    (401, PrivateStorageDenied), (403, PrivateStorageDenied),
    (404, PrivateStorageDenied), (500, PrivateStorageOutcomeUnknown),
])
def test_read_fail_closed(monkeypatch: pytest.MonkeyPatch, status: int, expected: type) -> None:
    _fake(monkeypatch, [(status, b"SENSITIVE_RESPONSE")])
    with pytest.raises(expected):
        SignedOriginalsStorage(KEY).get_verified(_ref(), "signed-fixture")


@pytest.mark.parametrize("body", [b"", b"tampered", b"x" * (MAX_BYTES + 1)])
def test_read_checksum_and_size_guard(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    _fake(monkeypatch, [(200, body)])
    with pytest.raises((PrivateStorageIntegrityError, PrivateStorageFailure)):
        SignedOriginalsStorage(KEY).get_verified(_ref(), "signed-fixture")


def test_refuses_wrong_digest_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _fake(monkeypatch, [])
    with pytest.raises(PrivateStorageIntegrityError):
        SignedOriginalsStorage(KEY).put_once(_ref(), "signed-fixture", b"changed")
    assert requests == []


@pytest.mark.parametrize("invalid", ["sb_secret_123", "service_role", "", "anon"])
def test_forbids_privileged_and_unpinned_keys(invalid: str) -> None:
    with pytest.raises(ValueError):
        SignedOriginalsStorage(invalid)


@pytest.mark.parametrize("invalid", ["bad\r\ninjection", "", "a" * 8193])
def test_no_untrusted_bearer_transport(invalid: str) -> None:
    with pytest.raises(ValueError):
        SignedOriginalsStorage(KEY).get_verified(_ref(), invalid)


def test_upload_rejects_oversize_and_empty_before_io(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _fake(monkeypatch, [])
    for data in (b"", b"x" * (MAX_BYTES + 1)):
        with pytest.raises(ValueError):
            SignedOriginalsStorage(KEY).put_once(_ref(), "user", data)
    assert requests == []


def test_object_path_is_bound_to_four_uuids_and_one_digest() -> None:
    ref = _ref()
    assert ref.path.count("/") == 4
    assert ref.path.endswith(HASH)
    with pytest.raises(ValueError):
        OriginalRef(uuid4(), uuid4(), uuid4(), uuid4(), HASH.upper(), "text/plain")
    with pytest.raises(ValueError):
        OriginalRef(uuid4(), uuid4(), uuid4(), uuid4(), HASH, "application/octet-stream")
