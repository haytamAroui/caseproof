"""Live reviewed-correction API must preserve actor scoping and exact CAS inputs."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.access_control import AccessRejected
from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.litigation_live_roundtrip import LiveCorrectionRequest, SignedLiveReview


class Response:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def read(self, _size: int) -> bytes:
        return json.dumps({"schema": "dev-signed-draft-correction-v1",
                           "committed": False, "release_authorized": False}).encode()


class Connection:
    def __init__(self) -> None:
        self.sent: tuple[object, ...] | None = None
        self.status = 200

    def request(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> None:
        self.sent = (method, path, json.loads(body), headers)

    def getresponse(self) -> Response:
        return Response(self.status)

    def close(self) -> None:
        pass


@pytest.mark.parametrize("operation", ["preview_correction", "commit_correction"])
def test_signed_exact_correction_bound_to_version_and_review(monkeypatch, operation):
    con = Connection()
    monkeypatch.setattr(
        "apps.api.litigation_live_roundtrip.http.client.HTTPSConnection",
        lambda *_args, **_kwargs: con,
    )
    api = SignedLiveReview("sb_publishable_test")
    case_id, version_id = str(uuid4()), str(uuid4())
    snapshot, request_id = "a" * 64, str(uuid4())
    result = api.call(
        "signed-token", case_id=case_id, brief_version_id=version_id,
        action=operation, p_snapshot=snapshot, p_expected_review=1,
        p_before="125 EUR", p_after="126 EUR", p_request=request_id,
    )
    assert result["release_authorized"] is False
    assert con.sent is not None
    method, path, payload, headers = con.sent
    assert method == "POST"
    assert path == "/rest/v1/rpc/caseproof_dev_correct_brief"
    assert payload == {
        "p_case": case_id, "p_version": version_id,
        "p_action": operation.removesuffix("_correction"),
        "p_snapshot": snapshot, "p_expected_review": 1,
        "p_before": "125 EUR", "p_after": "126 EUR", "p_request": request_id,
    }
    assert headers["Authorization"] == "Bearer signed-token"
    assert headers["apikey"] == "sb_publishable_test"
    assert "p_actor" not in payload and "p_org" not in payload


def test_request_rejects_unbounded_unsigned_or_unreviewed_changes():
    valid = {
        "snapshot_hash": "a" * 64, "expected_review_revision": 1,
        "before": "125 EUR", "after": "126 EUR", "request_id": str(uuid4()),
    }
    LiveCorrectionRequest(**valid)
    for mutation in (
        {"expected_review_revision": 0}, {"before": ""}, {"after": "x" * 101},
        {"snapshot_hash": "not-digest"}, {"request_id": "not-uuid"}, {"actor_id": str(uuid4())},
    ):
        with pytest.raises(ValidationError):
            LiveCorrectionRequest(**(valid | mutation))


def test_wrong_signed_identity_and_remote_access_denied():
    local = TestClient(create_litigation_development_app(), client=("127.0.0.1", 56000))
    remote = TestClient(create_litigation_development_app(), client=("203.0.113.4", 56000))
    base = f"/dev/live/matters/{uuid4()}/briefs/{uuid4()}/corrections"
    body = {
        "snapshot_hash": "a" * 64, "expected_review_revision": 1,
        "before": "125 EUR", "after": "126 EUR", "request_id": str(uuid4()),
    }
    assert local.post(base + "/preview", json=body).status_code == 503
    assert local.post(base + "/commit", json=body).status_code == 503
    assert remote.post(base + "/commit", json=body).status_code == 403


def test_malformed_case_or_explicit_wrong_operation_fails_closed(monkeypatch):
    con = Connection()
    monkeypatch.setattr(
        "apps.api.litigation_live_roundtrip.http.client.HTTPSConnection",
        lambda *_args, **_kwargs: con,
    )
    api = SignedLiveReview("sb_publishable_test")
    with pytest.raises(AccessRejected):
        api.call("signed-token", case_id="../escape", brief_version_id=str(uuid4()),
                 action="commit_correction")
    with pytest.raises(AccessRejected):
        api.call("signed-token", case_id=str(uuid4()), brief_version_id=str(uuid4()),
                 action="release")
    assert con.sent is None


def test_org_and_matter_permissions_keep_read_separate_from_edit():
    from pathlib import Path

    sql = (Path("supabase/migrations")
        / "20261028111543_caseproof_dev_correct_owner_write_and_read_separation.sql"
    ).read_text()
    assert (
        "g.permissions @> array['case:read','evidence:read','evidence:upload',"
        "'draft:check','review:request']::text[]" in sql
    )
    assert (
        "values(v_org,v_doc,v_actor,'reviewer',\n"
        "      array['case:read','evidence:read','evidence:upload',"
        "'draft:check','draft:write','review:request']::text[])" in sql
    )
    assert "if p_action='ingest' then raise exception 'trusted server verifier required'" in sql


def test_latest_signed_journey_requires_org_and_matter_draft_write():
    from pathlib import Path

    final = (Path("supabase/migrations")
        / "20261028111744_caseproof_dev_require_org_write_for_brief.sql"
    ).read_text()
    assert "if p_action='brief' and not exists(" in final
    assert "'draft:write'=any(m.actions) and 'draft:write'=any(g.permissions)" in final
    assert "case when exists(" in final
    assert "g.permissions @> array['case:read','evidence:read','evidence:upload'," in final
    assert "trusted server verifier required" in final

    toggle = (Path("supabase/migrations")
        / "20261028111820_caseproof_dev_org_only_revoke_test_rpc.sql"
    ).read_text()
    assert "to service_role" in toggle
    assert "from public,anon,authenticated" in toggle
