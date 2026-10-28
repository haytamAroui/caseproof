"""Signed dev live-review transport never accepts an API actor/org or broad RPC."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from apps.api.access_control import AccessRejected
from apps.api.litigation_live_roundtrip import SignedLiveReview


class Response:
    def __init__(self, status: int, body: dict[str, object]) -> None:
        self.status = status
        self._body = body

    def read(self, _size: int) -> bytes:
        return json.dumps(self._body).encode()


class Connection:
    def __init__(self, host: str, timeout: int) -> None:
        assert host == "ldwmocpxwskvhoojndrd.supabase.co"
        assert timeout == 12
        self.response = Response(200, {"schema": "caseproof-dev-signed-roundtrip-v1"})
        self.sent: tuple[object, ...] | None = None

    def request(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> None:
        assert method == "POST" and path == "/rest/v1/rpc/caseproof_dev_live_review"
        assert headers["apikey"] == "sb_publishable_test"
        assert headers["Authorization"] == "Bearer signed-token"
        data = json.loads(body)
        assert set(data) == {"p_case", "p_version", "p_action"}
        self.sent = (method, path, data)

    def getresponse(self) -> Response:
        return self.response

    def close(self) -> None:
        pass


def test_sends_exact_signed_payload_only(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = Connection("ldwmocpxwskvhoojndrd.supabase.co", 12)
    monkeypatch.setattr(
        "apps.api.litigation_live_roundtrip.http.client.HTTPSConnection",
        lambda *args, **kwargs: connection,
    )
    adapter = SignedLiveReview("sb_publishable_test")
    case = str(uuid4())
    version = str(uuid4())
    assert adapter.call("signed-token", case_id=case, brief_version_id=version, action="check") == {
        "schema": "caseproof-dev-signed-roundtrip-v1"
    }
    assert connection.sent == ("POST", "/rest/v1/rpc/caseproof_dev_live_review", {
        "p_case": case, "p_version": version, "p_action": "check",
    })


def test_denied_and_invalid_scope_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = Connection("ldwmocpxwskvhoojndrd.supabase.co", 12)
    connection.response = Response(403, {"error": "private"})
    monkeypatch.setattr(
        "apps.api.litigation_live_roundtrip.http.client.HTTPSConnection",
        lambda *args, **kwargs: connection,
    )
    adapter = SignedLiveReview("sb_publishable_test")
    with pytest.raises(AccessRejected):
        adapter.call("signed-token", case_id=str(uuid4()), brief_version_id=str(uuid4()), action="state")
    with pytest.raises(AccessRejected):
        adapter.call("signed-token", case_id="../other", brief_version_id=str(uuid4()), action="check")
    with pytest.raises(AccessRejected):
        adapter.call("signed-token", case_id=str(uuid4()), brief_version_id=str(uuid4()), action="invent")
    with pytest.raises(ValueError):
        SignedLiveReview("sb_secret_must_never_be_used")
