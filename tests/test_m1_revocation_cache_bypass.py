"""Regression: a previously authorized private Storage read must not reuse a CDN URL after revocation."""
from __future__ import annotations

import hashlib
import http.client
from uuid import uuid4

import pytest

from apps.api.signed_supabase_originals import OriginalRef, PrivateStorageDenied, SignedOriginalsStorage
from scripts.verify_m1_live_positive_original import LiveRevocationFailure, _denied

DATA = b"synthetic-immutable-original"
KEY = "sb_publishable_test_only"


def test_post_revocation_get_uses_new_cdn_cache_key(monkeypatch: pytest.MonkeyPatch) -> None:
    ref = OriginalRef(*(uuid4() for _ in range(4)), hashlib.sha256(DATA).hexdigest(), "text/plain")
    requests: list[tuple[str, str]] = []
    cache: dict[str, bytes] = {}
    granted = True

    class FakeResponse:
        def __init__(self, status: int, data: bytes) -> None:
            self.status = status
            self.data = data

        def read(self, n: int) -> bytes:
            return self.data[:n]

    class FakeHTTPS:
        def __init__(self, host: str, timeout: float) -> None:
            assert host == "ldwmocpxwskvhoojndrd.supabase.co"
            self.path = ""

        def request(self, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> None:
            assert method == "GET"
            assert headers is not None and headers["Authorization"] == "Bearer signed-user"
            self.path = path
            requests.append((method, path))

        def getresponse(self) -> FakeResponse:
            if self.path in cache:
                return FakeResponse(200, cache[self.path])
            if not granted:
                return FakeResponse(403, b"masked")
            cache[self.path] = DATA
            return FakeResponse(200, DATA)

        def close(self) -> None:
            pass

    monkeypatch.setattr(http.client, "HTTPSConnection", FakeHTTPS)
    client = SignedOriginalsStorage(KEY)
    assert client.get_verified(ref, "signed-user") == DATA
    granted = False
    with pytest.raises(PrivateStorageDenied):
        client.get_verified(ref, "signed-user")
    assert len(requests) == 2
    first, second = (r[1] for r in requests)
    assert first != second
    assert first.split("?")[0] == second.split("?")[0]
    assert all("?cacheNonce=" in x and len(x.split("?cacheNonce=")[1]) == 32 for x in (first, second))
    assert all("signed-user" not in x for x in (first, second))


@pytest.mark.parametrize("stage", [
    "postgrest_source_still_readable_after_revoke",
    "direct_storage_still_readable_after_revoke",
    "signed_library_still_readable_after_revoke",
])
def test_revocation_failure_has_explicit_safe_stage(stage: str) -> None:
    with pytest.raises(LiveRevocationFailure) as error:
        _denied(lambda: DATA, stage=stage)
    assert error.value.stage == stage
    _denied(lambda: (_ for _ in ()).throw(PrivateStorageDenied("masked")), stage=stage)
