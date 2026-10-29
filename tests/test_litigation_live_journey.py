"""TXT journey is a signed development boundary, not a privileged fixture API."""
from __future__ import annotations

import base64
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.access_control import AccessRejected
from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.litigation_live_journey import JourneyClient
from apps.api.signed_supabase_originals import OriginalRef, PrivateStorageIntegrityError


class Response:
    def __init__(self, status=200, body=None):
        self.status = status
        self.body = body if body is not None else {"case_id": str(uuid4())}

    def read(self, _limit):
        return json.dumps(self.body).encode()


class Connection:
    def __init__(self):
        self.sent = None
        self.reply = Response()

    def request(self, method, path, body, headers):
        self.sent = (method, path, json.loads(body), headers)

    def getresponse(self):
        return self.reply

    def close(self):
        pass


class Source:
    def __init__(self, data):
        self.data = data
        self.sha = hashlib.sha256(data).hexdigest()
        self.put_count = 0

    def source(self, **_kwargs):
        return OriginalRef(
            uuid4(), uuid4(), uuid4(), uuid4(), self.sha, "text/plain",
        ), len(self.data)

    def put_once(self, *, data, **_kwargs):
        if hashlib.sha256(data).hexdigest() != self.sha:
            raise PrivateStorageIntegrityError("mismatch")
        self.put_count += 1

    def read(self, **_kwargs):
        return self.data


def test_signed_rpc_never_trusts_actor_organization_or_secret(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(
        "apps.api.litigation_live_journey.http.client.HTTPSConnection",
        lambda *_args, **_kwargs: connection,
    )
    api = JourneyClient("sb_publishable_test")
    matter = str(uuid4())
    request = str(uuid4())
    actual = api.call("signed-token", "register", case_id=matter, request_id=request,
                      data={"filename": "test.txt", "sha256": "a" * 64})
    assert actual == connection.reply.body
    method, route, body, headers = connection.sent
    assert method == "POST"
    assert route == "/rest/v1/rpc/caseproof_dev_journey"
    assert body == {"p_action": "register", "p_case": matter, "p_request": request,
                    "p_data": {"filename": "test.txt", "sha256": "a" * 64}}
    assert headers["Authorization"] == "Bearer signed-token"
    assert headers["apikey"] == "sb_publishable_test"
    with pytest.raises(ValueError):
        JourneyClient("sb_secret_not_a_browser_key")
    with pytest.raises(AccessRejected):
        api.call("signed-token", "delete", case_id=matter)
    with pytest.raises(AccessRejected):
        api.call("signed-token", "ingest", case_id=matter)
    with pytest.raises(AccessRejected):
        api.call("signed-token", "register", case_id="../other")


def test_upload_verifies_digest_and_refuses_changed_bytes():
    source = Source(b"valid strict UTF-8\n")
    api = JourneyClient("sb_publishable_test")
    api.library = source
    ids = [str(uuid4()) for _ in range(3)]
    data = base64.b64encode(source.data).decode()
    result = api.upload("signed-token", *ids, data)
    assert result["verified"] and result["sha256"] == source.sha
    assert source.put_count == 1
    with pytest.raises(AccessRejected):
        api.upload("signed-token", *ids, base64.b64encode(b"wrong").decode())
    with pytest.raises(AccessRejected):
        api.upload("signed-token", *ids, base64.b64encode(b"").decode())
    with pytest.raises(AccessRejected):
        api.upload("signed-token", *ids, "$bad")


def test_ingestion_uses_verified_bytes_not_caller_text(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(
        "apps.api.litigation_live_journey.http.client.HTTPSConnection",
        lambda *_args, **_kwargs: connection,
    )
    api = JourneyClient("sb_publishable_testing123", "sb_secret_internal_only")
    api._verifier = SimpleNamespace(verify_bearer=lambda _bearer: SimpleNamespace(subject_id=str(uuid4())))
    api.library = Source("Résumé 125 EUR".encode())
    ids = [str(uuid4()) for _ in range(3)]
    output = api.ingest("signed-token", *ids, str(uuid4()))
    assert output == connection.reply.body
    assert connection.sent[1] == "/rest/v1/rpc/caseproof_dev_ingest_verified"
    assert connection.sent[2]["p_actor"]
    assert base64.b64decode(connection.sent[2]["p_content_base64"]) == api.library.data
    assert connection.sent[3]["apikey"] == "sb_secret_internal_only"
    assert "Authorization" not in connection.sent[3]
    api.library = Source(b"\xff\xfe")
    with pytest.raises(AccessRejected):
        api.ingest("signed-token", *ids, str(uuid4()))
    api.library = Source(b"")
    with pytest.raises(AccessRejected):
        api.ingest("signed-token", *ids, str(uuid4()))


def test_live_routes_loopback_only_and_unconfigured_denied():
    local = TestClient(create_litigation_development_app(), client=("127.0.0.1", 50000))
    remote = TestClient(create_litigation_development_app(), client=("203.0.113.2", 50000))
    path = "/dev/live/matters"
    body = {"org_id": str(uuid4()), "name": "test", "request_id": str(uuid4())}
    assert local.post(path, json=body).status_code == 503
    assert remote.post(path, json=body).status_code == 403
    assert local.get("/dev/live/create-organizations").status_code == 503
    assert local.post(path, json={**body, "name": ""}).status_code == 422


def test_client_cannot_self_certify_ingestion_without_server_key():
    api = JourneyClient("sb_publishable_testing123")
    api.library = Source(b"supported 125 EUR")
    ids = [str(uuid4()) for _ in range(3)]
    with pytest.raises(AccessRejected):
        api.ingest("signed-token", *ids, str(uuid4()))


def test_bad_verified_actor_fails_closed_before_service_write(monkeypatch):
    from apps.api.access_control import InvalidBearer

    class FailVerifier:
        def verify_bearer(self, _token):
            raise InvalidBearer("not signed")

    connection = Connection()
    monkeypatch.setattr(
        "apps.api.litigation_live_journey.http.client.HTTPSConnection",
        lambda *_args, **_kwargs: connection,
    )
    api = JourneyClient("sb_publishable_testing123", "sb_secret_internal_only")
    api._verifier = FailVerifier()
    api.library = Source(b"supported 125 EUR")
    ids = [str(uuid4()) for _ in range(3)]
    with pytest.raises(AccessRejected):
        api.ingest("invalid", *ids, str(uuid4()))
    assert connection.sent is None
