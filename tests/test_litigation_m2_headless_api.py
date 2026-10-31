"""M2 opt-in HTTP and signed-private-matter boundary — synthetic identity only."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.matter_policy import (
    CurrentMatterGrant,
    CurrentOrganizationGrant,
    MatterPermission,
    OrganizationPermission,
)
from application.litigation.unified_review import BriefRepresentation, SourceScope
from apps.api.access_control import AccessRejected, InvalidBearer, VerifiedSubject
from apps.api.litigation_check_app import create_litigation_check_app
from apps.api.litigation_check_service import (
    AuthorizedLitigationChecker,
    CheckBundle,
    PrivateMatterAccess,
)
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister

NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
ACTOR = "user-a"
ORG = "org-a"
CASE = "case-a"
DRAFT = "draft-1"


class FakeVerifier:
    calls = 0

    def verify_bearer(self, token: str) -> VerifiedSubject:
        self.calls += 1
        if token != "signed-dev-fixture":
            raise InvalidBearer("not an actual cryptographically signed session")
        return VerifiedSubject(ACTOR, "synthetic-issuer", "authenticated",
                               NOW - timedelta(minutes=1), NOW + timedelta(hours=1), False)


class FakeStore:
    active = True
    grant_check = True
    revision = 1
    case_exists = True
    current_calls = 0
    load_calls = 0
    snapshot_current = True
    revokes_after_load = False

    def current_access(self, subject_id: str, case_id: str) -> PrivateMatterAccess | None:
        self.current_calls += 1
        if subject_id != ACTOR or case_id != CASE or not self.case_exists:
            return None
        member = CurrentOrganizationGrant(
            ACTOR, ORG, self.active,
            frozenset({OrganizationPermission.CASE_READ, OrganizationPermission.FINDING_WRITE}), 1,
        )
        grant = CurrentMatterGrant(
            ACTOR, ORG, case_id, self.active,
            frozenset({MatterPermission.READ, MatterPermission.DRAFT_CHECK})
            if self.grant_check else frozenset({MatterPermission.READ}),
            self.revision,
        )
        return PrivateMatterAccess(case_id, ORG, member, grant, self.revision)

    def load_bundle(
        self, *, case_id: str, brief_version_id: str, access: PrivateMatterAccess,
    ) -> CheckBundle:
        self.load_calls += 1
        if self.revokes_after_load:
            self.active = False
        raw = b"De betaling is vastgesteld."
        brief = VersionedBrief(case_id, brief_version_id, sha256(raw).hexdigest(),
                               (DraftReference("r1", "Stuk 1", None, 1),))
        representation = BriefRepresentation(
            brief, raw.decode(), sha256(raw).hexdigest(), "fixture-parser", (),
        )
        registered = ExhibitRegister(1, (
            ExhibitEntry("e1", "Stuk 1", (ExhibitPage("s1", "v1", 1),), confirmed=True),
        ))
        row = EvidenceRow("s1", "d1", "v1", sha256(raw).hexdigest(),
                          "application/pdf", "ready", "fixture-parser", "rep1", (), ())
        preview = EvidencePreview(row, raw.decode(), ((0, len(raw.decode()), "pdf", 0),))
        return CheckBundle(representation, registered, (preview,), SourceScope((("s1", "v1"),)))

    def still_current(self, *, access: PrivateMatterAccess, bundle: CheckBundle) -> bool:
        return self.snapshot_current


def rig():
    verifier, store = FakeVerifier(), FakeStore()
    service = AuthorizedLitigationChecker(
        verifier=verifier, store=store,
        issuer="synthetic-issuer", audience="authenticated", clock=lambda: NOW,
    )
    return service, verifier, store


def test_headless_post_authorized_private_case_returns_source_linked_check():
    service, verifier, store = rig()
    client = TestClient(create_litigation_check_app(service))
    response = client.post(f"/v2/matters/{CASE}/briefs/{DRAFT}/check",
                           headers={"Authorization": "Bearer signed-dev-fixture"})
    assert response.status_code == 200
    data = response.json()
    assert data["schema"] == "caseproof-m2-check-headless-v1"
    observation = data["citation_observations"][0]
    assert observation["visual_comparison_supplied"] is False
    assert observation["visual_coverage"] == "not_supplied"
    assert observation["visual_assessment"] == "not_assessed"
    assert observation["fidelity_rules_version"] == "representation-gate-v2"
    assert data["citation_observations"][0]["state"] == "reference_checked_no_quotation"
    assert data["case_id"] == CASE and len(data["snapshot_hash"]) == 64
    assert store.current_calls == 2 and verifier.calls == 2
    assert "De betaling" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_unmounted_service_is_unavailable_not_anonymous():
    client = TestClient(create_litigation_check_app())
    response = client.post(f"/v2/matters/{CASE}/briefs/{DRAFT}/check",
                           headers={"Authorization": "Bearer signed-dev-fixture"})
    assert response.status_code == 503
    assert response.json() == {"error": "service_unavailable"}


def test_missing_and_bad_tokens_denied_before_source_access():
    service, _, store = rig()
    client = TestClient(create_litigation_check_app(service))
    for h in ({}, {"Authorization": "Bearer bad"}, {"Authorization": "bearer signed-dev-fixture"}):
        response = client.post(f"/v2/matters/{CASE}/briefs/{DRAFT}/check", headers=h)
        assert response.status_code == 401
    assert store.load_calls == 0


def test_same_org_without_exact_case_action_is_forbidden():
    service, _, store = rig()
    store.grant_check = False
    with pytest.raises(AccessRejected) as failure:
        service.check(bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT)
    assert failure.value.http_status == 403
    assert store.load_calls == 0


def test_foreign_or_unknown_case_masks_resource_not_auth_oracle():
    service, _, store = rig()
    with pytest.raises(AccessRejected) as failure:
        service.check(bearer="signed-dev-fixture", case_id="foreign", brief_version_id=DRAFT)
    assert failure.value.http_status == 404
    assert store.load_calls == 0


def test_revoked_during_processing_rejected_and_not_returned():
    service, _, store = rig()
    store.revokes_after_load = True
    with pytest.raises(AccessRejected) as failure:
        service.check(bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT)
    assert failure.value.http_status in {403, 404}


def test_grant_revision_changed_after_load_prevents_stale_result():
    service, _, store = rig()

    def changed(*, access: PrivateMatterAccess, bundle: CheckBundle) -> bool:
        return False

    store.still_current = changed  # type: ignore[method-assign]
    with pytest.raises(AccessRejected) as failure:
        service.check(bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT)
    assert failure.value.http_status == 503


def test_body_supplied_authorization_bypass_does_not_work():
    service, _, store = rig()
    client = TestClient(create_litigation_check_app(service))
    response = client.post(
        f"/v2/matters/{CASE}/briefs/{DRAFT}/check",
        json={"subject_id": ACTOR, "org_id": ORG, "role": "owner"},
        headers={"X-Tenant-Id": ORG},
    )
    assert response.status_code == 401 and store.load_calls == 0


def test_legacy_org_wide_grant_cannot_substitute_for_case_grant():
    service, _, store = rig()
    scope = store.current_access(ACTOR, CASE)
    assert scope is not None
    store.grant_check = False
    assert scope.member.active and OrganizationPermission.FINDING_WRITE in scope.member.permissions
    with pytest.raises(AccessRejected):
        service.check(bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT)
    assert store.load_calls == 0

class FakeRunPublisher:
    def __init__(self):
        self.calls = []
        self.broken = False

    def publish(self, *, org_id: str, actor_id: str, run) -> bool:
        self.calls.append((org_id, actor_id, run.snapshot_hash))
        if self.broken:
            raise RuntimeError("synthetic database outage")
        return True


def test_optional_run_publisher_uses_verified_actor_after_fresh_scope_check():
    service, _, store = rig()
    publisher = FakeRunPublisher()
    service.publisher = publisher
    run = service.check(bearer="signed-dev-fixture",
                        case_id=CASE, brief_version_id=DRAFT)
    assert publisher.calls == [(ORG, ACTOR, run.snapshot_hash)]
    store.snapshot_current = False
    with pytest.raises(AccessRejected) as error:
        service.check(bearer="signed-dev-fixture",
                      case_id=CASE, brief_version_id=DRAFT)
    assert error.value.http_status == 503
    assert publisher.calls == [(ORG, ACTOR, run.snapshot_hash)]


def test_optional_publisher_failure_withheld_and_no_unsafe_fallback():
    service, _, store = rig()
    publisher = FakeRunPublisher()
    publisher.broken = True
    service.publisher = publisher
    with pytest.raises(AccessRejected) as error:
        service.check(bearer="signed-dev-fixture",
                      case_id=CASE, brief_version_id=DRAFT)
    assert error.value.http_status == 503
    assert store.load_calls == 1
    assert len(publisher.calls) == 1
