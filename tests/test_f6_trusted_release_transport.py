"""F6 trusted write transport: a browser can read but never forge a release."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from apps.api.access_control import AccessRejected, InvalidBearer
from apps.api.dossier_journey import DossierStore

PUBLISHABLE = "sb_publishable_" + "a" * 40
SERVICE = "sb_secret_" + "b" * 40


class FakeResponse:
    status = 200

    def read(self, _: int) -> bytes:
        return b'{"state":"released"}'


class Connection:
    calls: list[tuple[str, str, dict]] = []

    def __init__(self, *_args, **_kwargs):
        pass

    def request(self, method, path, body, headers):
        self.calls.append((method, path, {"payload": json.loads(body), "headers": headers}))

    def getresponse(self):
        return FakeResponse()

    def close(self):
        pass


def test_f6_release_only_via_verified_actor_and_trusted_backend_key():
    actor = str(uuid4())
    store = DossierStore(PUBLISHABLE, receipt_secret=SERVICE)
    verifier = Mock()
    verifier.verify_bearer.return_value = SimpleNamespace(subject_id=actor)
    store.revisions.verifier = verifier
    Connection.calls = []
    with patch("apps.api.dossier_journey.http.client.HTTPSConnection", Connection):
        assert store.export_rpc("signed-user-jwt", str(uuid4()), "release", str(uuid4()), {})["state"] == "released"
        assert store.export_rpc("signed-user-jwt", str(uuid4()), "status", str(uuid4()), {})["state"] == "released"
    verifier.verify_bearer.assert_called_once_with("signed-user-jwt")
    write, read = Connection.calls
    assert write[2]["headers"]["apikey"] == SERVICE
    assert "Authorization" not in write[2]["headers"]
    assert write[2]["payload"]["p_actor"] == actor
    assert read[2]["headers"]["apikey"] == PUBLISHABLE
    assert read[2]["headers"]["Authorization"] == "Bearer signed-user-jwt"
    assert "p_actor" not in read[2]["payload"]


def test_f6_denies_trusted_write_when_server_key_or_user_verification_missing():
    store = DossierStore(PUBLISHABLE, receipt_secret=None)
    with pytest.raises(AccessRejected):
        store.export_rpc("signed-user-jwt", str(uuid4()), "release", str(uuid4()), {})
    store.revisions.trusted_key = SERVICE
    store.revisions.verifier = Mock()
    store.revisions.verifier.verify_bearer.side_effect = InvalidBearer("untrusted")
    with pytest.raises(AccessRejected):
        store.export_rpc("not-a-valid-jwt", str(uuid4()), "release", str(uuid4()), {})


@pytest.mark.parametrize("payload", [b'{', b'\xff', b'[]', b'null', b'"text"'])
def test_dossier_rpc_rejects_malformed_success_response_without_retry(payload):
    response = Mock(status=200)
    response.read.return_value = payload
    connection = Mock()
    connection.getresponse.return_value = response
    with patch("apps.api.dossier_journey.http.client.HTTPSConnection", return_value=connection):
        with pytest.raises(AccessRejected):
            DossierStore(PUBLISHABLE).rpc("signed-user-jwt", str(uuid4()), "read")
    connection.request.assert_called_once()
    connection.close.assert_called_once()
