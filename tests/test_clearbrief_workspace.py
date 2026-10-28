"""Product-facing workbench contract on a loopback injected development application.

Uses existing signed M2 fixture service and synthetic source bytes. The HTTP
commands are real but do not claim an installed live reviewer/Word backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from application.litigation.review_cycle import ReviewPacket
from application.litigation.matter_policy import (
    CurrentMatterGrant, CurrentOrganizationGrant,
    MatterPermission, OrganizationPermission,
)
from application.litigation.unified_review import ObservationReview, ReviewDisposition
from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.access_control import VerifiedSubject, InvalidBearer
from apps.api.litigation_check_service import PrivateMatterAccess
from apps.api.litigation_review_workspace import SignedReviewWorkspace
from tests.test_litigation_evidence_search import ACTOR, CASE, DRAFT, search_rig
from tests.test_litigation_m2_headless_api import NOW


HEADERS = {"Authorization": "Bearer signed-dev-fixture"}
BASE = f"/v2/matters/{CASE}/briefs/{DRAFT}"


@dataclass
class ReviewState:
    revision: int
    packet: ReviewPacket


class Ledger:
    def __init__(self):
        self.runs = {}
        self.decisions = {}
        self.revision = 0
        self.requests = {}

    def publish(self, *, org_id, actor_id, run):
        self.runs[run.snapshot_hash] = run
        return True

    def state(self, *, org_id, actor_id, run):
        if run.snapshot_hash not in self.runs:
            raise ValueError("unpublished")
        return ReviewState(self.revision, ReviewPacket(
            run.snapshot_hash, self.revision, tuple(self.decisions.values())
        ))

    def record(self, *, org_id, actor_id, run, request_id, expected_revision, decision):
        key = str(request_id)
        if key in self.requests:
            if self.requests[key] != (run.snapshot_hash, decision, expected_revision):
                raise ValueError("changed idempotency request")
            return self.state(org_id=org_id, actor_id=actor_id, run=run), True
        if str(actor_id) != decision.actor_id or expected_revision != self.revision:
            raise ValueError("stale or forged reviewer")
        valid = {f"citation:{x.reference_id}" for x in run.citation_observations}
        valid |= {f"fact:{x.claim_id}" for x in run.factual_observations}
        if decision.observation_id not in valid:
            raise ValueError("observation outside checked version")
        self.decisions[decision.observation_id] = decision
        self.revision += 1
        self.requests[key] = (run.snapshot_hash, decision, expected_revision)
        return self.state(org_id=org_id, actor_id=actor_id, run=run), False


def make_client():
    search, _store = search_rig()
    ledger = Ledger()
    checker = search.checker
    # The legacy headless fixture uses non-UUID names; the actual reviewer
    # ledger must receive canonical Supabase actor and organization UUIDs.
    uuid_actor, uuid_org = str(uuid4()), str(uuid4())

    class CanonicalVerifier:
        def verify_bearer(self, token):
            if token != "signed-dev-fixture":
                raise InvalidBearer("not a signed fixture")
            return VerifiedSubject(
                uuid_actor, "synthetic-issuer", "authenticated",
                NOW - timedelta(minutes=1), NOW + timedelta(hours=1), False,
            )

    def current_access(subject_id, case_id):
        if subject_id != uuid_actor or case_id != CASE:
            return None
        member = CurrentOrganizationGrant(
            uuid_actor, uuid_org, True,
            frozenset({OrganizationPermission.CASE_READ,
                       OrganizationPermission.FINDING_WRITE,
                       OrganizationPermission.REVIEW_REQUEST}), 1,
        )
        grant = CurrentMatterGrant(
            uuid_actor, uuid_org, CASE, True,
            frozenset({MatterPermission.READ, MatterPermission.DRAFT_CHECK}), 1,
        )
        return PrivateMatterAccess(CASE, uuid_org, member, grant, 1)

    checker.verifier = CanonicalVerifier()
    checker.store.current_access = current_access
    checker.publisher = ledger
    review = SignedReviewWorkspace(checker, ledger)
    app = create_litigation_development_app(checker=checker, reviews=review)
    return TestClient(app, client=("127.0.0.1", 50000)), ledger


def test_workbench_serves_real_assets_only_from_loopback():
    client, _ = make_client()
    page = client.get("/dev/clearbrief")
    assert page.status_code == 200
    assert "ClearBrief" in page.text
    assert "stale" not in page.headers.get("content-security-policy", "")
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["cache-control"] == "no-store"
    for path, content_type in [
        ("/dev/clearbrief/workspace.js", "javascript"),
        ("/dev/clearbrief/workspace.css", "text/css"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]
    assert client.get("/dev/clearbrief/.env").status_code == 404
    assert client.get("/dev/clearbrief/config").json()["publishable_key"] is None
    remote = TestClient(create_litigation_development_app(), client=("192.0.2.1", 50000))
    assert remote.get("/dev/clearbrief").status_code == 403


def test_no_credentials_and_missing_composition_fail_closed():
    client = TestClient(create_litigation_development_app(), client=("127.0.0.1", 50000))
    assert client.get(BASE + "/review", headers=HEADERS).status_code == 503
    assert client.post(BASE + "/review", headers=HEADERS, json={}).status_code == 422
    ok, _ = make_client()
    assert ok.get(BASE + "/review").status_code == 401
    assert ok.get(BASE + "/review", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert ok.get(f"/v2/matters/foreign/briefs/{DRAFT}/review", headers=HEADERS).status_code == 404


def test_signed_checked_snapshot_reopened_and_review_is_revision_bound():
    client, _ = make_client()
    check = client.post(BASE + "/check", headers=HEADERS)
    assert check.status_code == 200
    snapshot = check.json()
    assert snapshot["snapshot_hash"] and snapshot["case_id"] == CASE
    first = client.get(BASE + "/review", headers=HEADERS)
    assert first.status_code == 200
    assert first.json()["revision"] == 0
    assert first.json()["snapshot_hash"] == snapshot["snapshot_hash"]
    assert first.json()["release_authorized"] is False
    observation = snapshot["citation_observations"][0]["reference_id"]
    request_id = str(uuid4())
    command = {
        "snapshot_hash": snapshot["snapshot_hash"],
        "observation_id": "citation:" + observation,
        "request_id": request_id, "expected_revision": 0,
        "disposition": "needs_information",
        "rationale": "The exact source context needs human assessment.",
    }
    saved = client.post(BASE + "/review", headers=HEADERS, json=command)
    assert saved.status_code == 200
    assert saved.json()["revision"] == 1
    assert saved.json()["release_authorized"] is False
    repeated = client.post(BASE + "/review", headers=HEADERS, json=command)
    assert repeated.status_code == 200
    assert repeated.json()["replayed"] is True
    reopened = client.get(BASE + "/review", headers=HEADERS)
    assert reopened.json()["revision"] == 1
    assert reopened.json()["decisions"][0]["observation_id"] == command["observation_id"]
    changed = dict(command, request_id=str(uuid4()), expected_revision=0)
    assert client.post(BASE + "/review", headers=HEADERS, json=changed).status_code == 503
    stale = dict(command, request_id=str(uuid4()), snapshot_hash="a" * 64)
    assert client.post(BASE + "/review", headers=HEADERS, json=stale).status_code == 404
    spoof = dict(command, request_id=str(uuid4()), actor_id=ACTOR)
    assert client.post(BASE + "/review", headers=HEADERS, json=spoof).status_code == 422


def test_unknown_observation_and_invalid_uuid_refused():
    client, _ = make_client()
    run = client.post(BASE + "/check", headers=HEADERS).json()
    cmd = {
        "snapshot_hash": run["snapshot_hash"], "observation_id": "fact:made-up",
        "request_id": str(uuid4()), "expected_revision": 0,
        "disposition": "dismissed", "rationale": "Not supported by the checked scope.",
    }
    assert client.post(BASE + "/review", headers=HEADERS, json=cmd).status_code == 503
    assert client.post(BASE + "/review", headers=HEADERS, json={
        **cmd, "request_id": str(UUID(int=0))
    }).status_code == 422


def test_public_key_is_opt_in_and_never_accepts_secret():
    try:
        create_litigation_development_app(publishable_key="sb_secret_unsafe")
        raise AssertionError("secret accepted")
    except ValueError:
        pass
    key="sb_publishable_test_only"
    client=TestClient(create_litigation_development_app(publishable_key=key),
                      client=("127.0.0.1", 50000))
    assert client.get("/dev/clearbrief/config").json()["publishable_key"] == key
    assert "connect-src 'self' https://ldwmocpxwskvhoojndrd.supabase.co" in (
        client.get("/dev/clearbrief").headers["content-security-policy"]
    )


def test_unconnected_review_is_not_a_successful_decision():
    repo = Path(__file__).resolve().parents[1]
    page = (repo / "apps/web/clearbrief/index.html").read_text()
    script = (repo / "apps/web/clearbrief/workspace.js").read_text()
    assert "Release package · not enabled" in page
    assert "window.caseproofSession" in script
    assert 'credentials:"omit"' in script
    assert "localStorage" not in script and "sessionStorage" not in script
    assert "innerHTML" not in script and "document.write" not in script
    assert 'getBearer' in script
