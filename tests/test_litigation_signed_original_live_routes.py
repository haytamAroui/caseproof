"""Loopback API actually calls the signed PostgREST + Storage composition port.

This does not grant client-derived org access. The real signed source library
is exercised separately with fake HTTPS and in protected live Auth smoke.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.signed_supabase_originals import PrivateStorageDenied


@dataclass
class StubSigned:
    calls: list[tuple[str, dict]] = field(default_factory=list)
    deny: bool = False

    def read(self, **kwargs: object) -> bytes:
        self.calls.append(("read", kwargs))
        if self.deny:
            raise PrivateStorageDenied("Masked")
        return b"authorized test source"

    def put_once(self, **kwargs: object) -> None:
        self.calls.append(("put_once", kwargs))
        if self.deny:
            raise PrivateStorageDenied("Masked")


URL = "/dev/signed/matters/matter/documents/document/versions/version/original"
HEADERS = {"Authorization": "Bearer signed-by-supabase"}


def test_loopback_read_and_upload_use_exact_signed_context() -> None:
    port = StubSigned()
    client = TestClient(
        create_litigation_development_app(signed_originals=port),
        client=("127.0.0.1", 50000),
    )
    saved = client.put(URL, headers=HEADERS, content=b"authorized test source")
    opened = client.get(URL, headers=HEADERS)
    assert saved.status_code == 201
    assert opened.status_code == 200
    assert opened.content == b"authorized test source"
    assert opened.headers["content-disposition"].startswith("attachment")
    assert opened.headers["cache-control"] == "no-store"
    assert [x[0] for x in port.calls] == ["put_once", "read"]
    assert port.calls[0][1] == {
        "bearer": "signed-by-supabase",
        "case_id": "matter", "document_id": "document",
        "version_id": "version", "data": b"authorized test source",
    }
    assert port.calls[1][1]["bearer"] == "signed-by-supabase"


def test_denied_signed_original_is_masked_without_exposing_storage() -> None:
    port = StubSigned(deny=True)
    client = TestClient(
        create_litigation_development_app(signed_originals=port),
        client=("127.0.0.1", 50000),
    )
    for response in (
        client.get(URL, headers=HEADERS),
        client.put(URL, headers=HEADERS, content=b"fixture"),
    ):
        assert response.status_code == 404
        assert "Masked" not in response.text
    assert len(port.calls) == 2


def test_no_injected_storage_and_no_auth_denied() -> None:
    client = TestClient(
        create_litigation_development_app(),
        client=("127.0.0.1", 50000),
    )
    assert client.get(URL, headers=HEADERS).status_code == 503
    assert client.put(URL, headers=HEADERS, content=b"fixture").status_code == 503
    secured = TestClient(
        create_litigation_development_app(signed_originals=StubSigned()),
        client=("127.0.0.1", 50000),
    )
    assert secured.get(URL).status_code == 401


def test_non_loopback_remote_client_is_denied() -> None:
    client = TestClient(
        create_litigation_development_app(signed_originals=StubSigned()),
        client=("203.0.113.1", 50000),
    )
    assert client.get(URL, headers=HEADERS).status_code == 403


def test_empty_upload_rejected_before_storage_write() -> None:
    port = StubSigned()
    client = TestClient(
        create_litigation_development_app(signed_originals=port),
        client=("127.0.0.1", 50000),
    )
    assert client.put(URL, headers=HEADERS, content=b"").status_code == 422
    assert port.calls == []
