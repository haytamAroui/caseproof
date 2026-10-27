"""Combined API tests use synthetic identity and source bytes only."""
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from apps.api.access_control import AccessRejected
from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.litigation_original_reader import AuthorizedOriginalReader, Original
from tests.test_litigation_evidence_search import ACTOR, CASE, DRAFT, search_rig


class Originals:
    calls = 0
    tamper = False

    def read(self, *, access, source_id, version_id):
        self.calls += 1
        raw = b"De betaling is vastgesteld."
        return Original(b"tampered" if self.tamper else raw, sha256(raw).hexdigest(), "text/plain")


def client_rig():
    search, store = search_rig()
    originals = Originals()
    reader = AuthorizedOriginalReader(search.checker, originals)
    client = TestClient(create_litigation_development_app(checker=search.checker, originals=reader),
                        client=("127.0.0.1", 50000))
    return client, search, store, originals


def test_one_composed_api_checks_searches_and_downloads_same_snapshot():
    client, _, _, _ = client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    root = f"/v2/matters/{CASE}/briefs/{DRAFT}"
    checked = client.post(f"{root}/check", headers=headers)
    search = client.post(f"{root}/evidence/search", headers=headers, json={"query": "betaling"})
    original = client.get(f"{root}/evidence/s1/versions/v1/original", headers=headers)
    assert checked.status_code == search.status_code == original.status_code == 200
    assert checked.json()["case_id"] == search.json()["case_id"] == CASE
    assert search.json()["hits"][0]["source_version_id"] == "v1"
    assert original.content == b"De betaling is vastgesteld."
    assert original.headers["x-caseproof-original-sha256"] == sha256(original.content).hexdigest()
    assert original.headers["content-disposition"].startswith("attachment")
    assert original.headers["cache-control"] == "no-store"


def test_denies_unverified_and_out_of_scope_originals_before_reading():
    client, _, _, originals = client_rig()
    root = f"/v2/matters/{CASE}/briefs/{DRAFT}/evidence"
    assert client.get(f"{root}/s1/versions/v1/original").status_code == 401
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    assert client.get(f"{root}/foreign/versions/v1/original", headers=headers).status_code == 404
    assert originals.calls == 0
    assert client.get(f"{root}/s1/versions/v2/original", headers=headers).status_code == 404
    assert originals.calls == 0


def test_stale_and_tampered_source_never_return_original():
    client, _, store, originals = client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    path = f"/v2/matters/{CASE}/briefs/{DRAFT}/evidence/s1/versions/v1/original"
    originals.tamper = True
    assert client.get(path, headers=headers).status_code == 503
    originals.tamper = False
    store.snapshot_current = False
    assert client.get(path, headers=headers).status_code == 503


def test_loopback_boundary_and_unconfigured_composition_fail_closed():
    client, search, _, originals = client_rig()
    remote = TestClient(create_litigation_development_app(
        checker=search.checker, originals=AuthorizedOriginalReader(search.checker, originals)),
        client=("192.0.2.1", 50000))
    assert remote.post(f"/v2/matters/{CASE}/briefs/{DRAFT}/check").status_code == 403
    unconfigured = TestClient(create_litigation_development_app(), client=("127.0.0.1", 50000))
    assert unconfigured.post(f"/v2/matters/{CASE}/briefs/{DRAFT}/check").status_code == 503


def test_original_reader_requires_explicit_evidence_grant():
    _, search, store, originals = client_rig()
    original = store.current_access
    def deny_evidence(subject_id, case_id):
        from application.litigation.matter_policy import CurrentMatterGrant, MatterPermission
        from apps.api.litigation_check_service import PrivateMatterAccess
        scope = original(subject_id, case_id)
        assert scope is not None
        grant = CurrentMatterGrant(ACTOR, scope.org_id, scope.case_id, True,
                                   frozenset({MatterPermission.READ, MatterPermission.DRAFT_CHECK}), 1)
        return PrivateMatterAccess(scope.case_id, scope.org_id, scope.member, grant, 1)
    store.current_access = deny_evidence
    with pytest.raises(AccessRejected):
        AuthorizedOriginalReader(search.checker, originals).read(
            bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT, source_id="s1", version_id="v1")
    assert originals.calls == 0
