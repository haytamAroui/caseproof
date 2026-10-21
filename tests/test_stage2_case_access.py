"""S2-001 — trusted boundary denial tests; no simulated JWT claimed as live auth."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from apps.api.access_control import (
    AccessFailure,
    AccessRejected,
    AccessStoreUnavailable,
    AuthorizedCase,
    CaseAccessService,
    CaseAction,
    IdentityServiceUnavailable,
    InvalidBearer,
    StoredCase,
    StoredMembership,
    UnavailableBearerVerifier,
    VerifiedSubject,
)
from apps.api.main import create_app

NOW = datetime(2026, 10, 21, 21, tzinfo=UTC)
ALL_ACTIONS = frozenset(CaseAction)


@dataclass
class FakeVerifiedTokenProvider:
    """No crypto. Replaces an IdP verifier ONLY inside these pure unit tests."""

    subjects: dict[str, VerifiedSubject] = field(default_factory=dict)
    unavailable: bool = False
    calls: list[str] = field(default_factory=list)

    def verify_bearer(self, token: str) -> VerifiedSubject:
        self.calls.append(token)
        if self.unavailable:
            raise IdentityServiceUnavailable("offline")
        subject = self.subjects.get(token)
        if subject is None:
            raise InvalidBearer("bad token")
        return subject


@dataclass
class FakeServerRepository:
    """One SHARED source of record for overlapping tenant/user names."""

    cases: dict[str, StoredCase] = field(default_factory=dict)
    memberships: dict[tuple[str, str], StoredMembership] = field(default_factory=dict)
    calls: list[tuple[str, ...]] = field(default_factory=list)
    unavailable: bool = False

    def lookup_case_membership(
        self, subject_id: str, case_id: str
    ) -> tuple[StoredCase, StoredMembership] | None:
        self.calls.append(("lookup", subject_id, case_id))
        if self.unavailable:
            raise AccessStoreUnavailable("offline")
        resource = self.cases.get(case_id)
        if resource is None:
            return None
        membership = self.memberships.get((subject_id, resource.owner_org_id))
        if membership is None:
            return None
        return resource, membership


def identity(
    user: str,
    *,
    expires_at: datetime = NOW + timedelta(minutes=15),
    human: bool = True,
    verified_at: datetime = NOW - timedelta(minutes=5),
) -> VerifiedSubject:
    return VerifiedSubject(
        user, "https://auth.example.test", "caseproof-api", verified_at,
        expires_at, human,
    )


def rig() -> tuple[CaseAccessService, FakeVerifiedTokenProvider, FakeServerRepository]:
    verifier = FakeVerifiedTokenProvider({
        "alice-token": identity("alice"),
        "bob-token": identity("bob"),
        "carol-token": identity("carol"),
        "model-token": identity("model-service", human=False),
    })
    repository = FakeServerRepository(
        cases={
            "case-a": StoredCase("case-a", "org-a", 1, "alice"),
            "case-b": StoredCase("case-b", "org-b", 4, "bob"),
        },
        memberships={
            ("alice", "org-a"): StoredMembership("alice", "org-a", True, ALL_ACTIONS),
            ("bob", "org-b"): StoredMembership("bob", "org-b", True, ALL_ACTIONS),
            ("carol", "org-a"): StoredMembership(
                "carol", "org-a", True,
                frozenset({CaseAction.READ_CASE, CaseAction.READ_COVERAGE}),
            ),
            ("model-service", "org-a"): StoredMembership(
                "model-service", "org-a", True,
                frozenset({CaseAction.READ_CASE, CaseAction.REQUEST_APPROVAL}),
            ),
        },
    )
    return CaseAccessService(verifier, repository, "https://auth.example.test", "caseproof-api", lambda: NOW), verifier, repository


def failure(
    service: CaseAccessService, token: str | None, case_id: str, action: CaseAction,
    expected: AccessFailure,
) -> None:
    with pytest.raises(AccessRejected) as error:
        service.authorize(token, case_id, action)
    assert error.value.code is expected
    assert error.value.http_status == {
        AccessFailure.AUTHENTICATION_REQUIRED: 401,
        AccessFailure.RESOURCE_MASKED: 404,
        AccessFailure.PERMISSION_DENIED: 403,
        AccessFailure.SERVICE_UNAVAILABLE: 503,
    }[expected]
    assert "case-" not in str(error.value)
    assert "token" not in str(error.value)
    assert "org-" not in str(error.value)


@pytest.mark.parametrize("action", [
    CaseAction.READ_CASE,
    CaseAction.READ_COVERAGE,
    CaseAction.READ_EVIDENCE,
    CaseAction.PROPOSE_FINDING,
    CaseAction.PROPOSE_REVIEW,
])
def test_active_member_gets_only_server_derived_case_ownership(action: CaseAction) -> None:
    service, _, _ = rig()
    access = service.authorize("alice-token", "case-a", action)
    assert access == AuthorizedCase("case-a", "org-a", "alice", action, 1, True)
    assert not hasattr(access, "approved")
    assert not hasattr(service, "promote")
    assert not hasattr(service, "commit")


@pytest.mark.parametrize("bearer", [None, "", " ", "forged-jwt", "bob-token-nonsense"])
def test_missing_or_invalid_bearer_is_401_before_case_lookup(bearer: str | None) -> None:
    service, verifier, store = rig()
    failure(service, bearer, "case-a", CaseAction.READ_CASE,
            AccessFailure.AUTHENTICATION_REQUIRED)
    assert store.calls == []
    if bearer is None or not bearer.strip():
        assert verifier.calls == []


def test_unconfigured_verifier_never_claims_to_authenticate() -> None:
    _, _, store = rig()
    service = CaseAccessService(UnavailableBearerVerifier(), store, "https://auth.example.test", "caseproof-api", lambda: NOW)
    failure(service, "any-token", "case-a", CaseAction.READ_CASE,
            AccessFailure.SERVICE_UNAVAILABLE)
    assert store.calls == []


def test_verifier_service_outage_is_503_and_never_grants_access() -> None:
    service, verifier, store = rig()
    verifier.unavailable = True
    failure(service, "alice-token", "case-a", CaseAction.READ_CASE,
            AccessFailure.SERVICE_UNAVAILABLE)
    assert store.calls == []


@pytest.mark.parametrize("issued_at,expires", [
    (NOW - timedelta(minutes=5), NOW),
    (NOW - timedelta(minutes=5), NOW - timedelta(seconds=1)),
    (NOW + timedelta(seconds=1), NOW + timedelta(minutes=10)),
])
def test_expired_or_not_yet_verified_token_denied_even_if_provider_bugs(
    issued_at: datetime, expires: datetime,
) -> None:
    service, verifier, store = rig()
    verifier.subjects["alice-token"] = identity(
        "alice", verified_at=issued_at, expires_at=expires
    )
    failure(service, "alice-token", "case-a", CaseAction.READ_CASE,
            AccessFailure.AUTHENTICATION_REQUIRED)
    assert store.calls == []


def test_cross_tenant_case_access_is_404_not_permission_metadata_leak() -> None:
    service, _, store = rig()
    failure(service, "alice-token", "case-b", CaseAction.READ_CASE,
            AccessFailure.RESOURCE_MASKED)
    failure(service, "alice-token", "unknown-case", CaseAction.READ_CASE,
            AccessFailure.RESOURCE_MASKED)
    assert store.calls[-1] == ("lookup", "alice", "unknown-case")
    assert "org-b" not in str(store.calls[-1])
    assert service.authorize("bob-token", "case-b", CaseAction.READ_CASE).org_id == "org-b"


def test_access_to_shared_stores_uses_current_membership_not_user_metadata() -> None:
    service, verifier, store = rig()
    # A token returned from the stub carries no tenant, role or permissions.
    assert "role" not in VerifiedSubject.__dataclass_fields__
    assert "org_id" not in VerifiedSubject.__dataclass_fields__
    assert "permissions" not in VerifiedSubject.__dataclass_fields__
    failure(service, "alice-token", "case-b", CaseAction.READ_CASE,
            AccessFailure.RESOURCE_MASKED)
    store.memberships[("alice", "org-b")] = StoredMembership(
        "alice", "org-b", True, frozenset({CaseAction.READ_CASE})
    )
    allowed = service.authorize("alice-token", "case-b", CaseAction.READ_CASE)
    assert allowed.org_id == "org-b"
    failure(service, "alice-token", "case-b", CaseAction.READ_EVIDENCE,
            AccessFailure.PERMISSION_DENIED)
    assert verifier.calls == ["alice-token", "alice-token", "alice-token"]


def test_revocation_is_observed_on_the_next_authorization() -> None:
    service, _, store = rig()
    first = service.authorize("alice-token", "case-a", CaseAction.READ_CASE)
    store.memberships[("alice", "org-a")] = StoredMembership("alice", "org-a", False)
    failure(service, "alice-token", "case-a", CaseAction.READ_CASE,
            AccessFailure.RESOURCE_MASKED)
    assert first.org_id == "org-a"  # old context alone is NOT a future permit


def test_permission_downgrade_is_403_even_with_same_signed_identity() -> None:
    service, _, store = rig()
    service.authorize("alice-token", "case-a", CaseAction.READ_EVIDENCE)
    store.memberships[("alice", "org-a")] = StoredMembership(
        "alice", "org-a", True, frozenset({CaseAction.READ_CASE})
    )
    failure(service, "alice-token", "case-a", CaseAction.READ_EVIDENCE,
            AccessFailure.PERMISSION_DENIED)
    assert service.authorize("alice-token", "case-a", CaseAction.READ_CASE).action == (
        CaseAction.READ_CASE
    )


def test_member_with_only_read_permission_cannot_write_or_request_approval() -> None:
    service, _, _ = rig()
    failure(service, "carol-token", "case-a", CaseAction.PROPOSE_FINDING,
            AccessFailure.PERMISSION_DENIED)
    failure(service, "carol-token", "case-a", CaseAction.REQUEST_APPROVAL,
            AccessFailure.PERMISSION_DENIED)
    assert service.authorize("carol-token", "case-a", CaseAction.READ_CASE).subject_id == (
        "carol"
    )


def test_request_approval_enforces_human_and_no_self_approval_but_does_not_approve() -> None:
    service, _, store = rig()
    failure(service, "alice-token", "case-a", CaseAction.REQUEST_APPROVAL,
            AccessFailure.PERMISSION_DENIED)
    failure(service, "model-token", "case-a", CaseAction.REQUEST_APPROVAL,
            AccessFailure.PERMISSION_DENIED)
    store.memberships[("bob", "org-a")] = StoredMembership(
        "bob", "org-a", True, frozenset({CaseAction.REQUEST_APPROVAL})
    )
    request = service.authorize("bob-token", "case-a", CaseAction.REQUEST_APPROVAL)
    assert request.subject_id == "bob"
    assert request.action is CaseAction.REQUEST_APPROVAL
    assert not hasattr(request, "authorization_to_approve")
    assert not hasattr(service, "approved_conclusion")


def test_missing_case_and_unknown_membership_are_access_masked() -> None:
    service, _, store = rig()
    failure(service, "alice-token", "case-not-stored", CaseAction.READ_CASE,
            AccessFailure.RESOURCE_MASKED)
    del store.memberships[("alice", "org-a")]
    failure(service, "alice-token", "case-a", CaseAction.READ_CASE,
            AccessFailure.RESOURCE_MASKED)


def test_repositories_fail_closed_on_outage() -> None:
    service, _, store = rig()
    store.unavailable = True
    failure(service, "alice-token", "case-a", CaseAction.READ_CASE,
            AccessFailure.SERVICE_UNAVAILABLE)


def test_user_cannot_override_tenant_or_role_via_method_signature() -> None:
    service, _, _ = rig()
    with pytest.raises(TypeError):
        service.authorize(
            "alice-token", "case-b", CaseAction.READ_CASE, tenant_id="org-b"
        )
    with pytest.raises(TypeError):
        service.authorize(
            "alice-token", "case-b", CaseAction.READ_CASE, role="owner"
        )
    with pytest.raises(TypeError):
        service.authorize(
            "alice-token", "case-b", CaseAction.READ_CASE, authorized=True
        )


def test_invalid_actions_and_empty_resource_ids_do_not_trigger_storage() -> None:
    service, _, store = rig()
    with pytest.raises(TypeError):
        service.authorize("alice-token", "case-a", "case:read")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        service.authorize("alice-token", "", CaseAction.READ_CASE)
    assert store.calls == []


@pytest.mark.parametrize("invalid", [
    {"subject_id": ""},
    {"issuer": ""},
    {"audience": ""},
    {"verified_at": datetime(2026, 10, 21)},
    {"expires_at": NOW - timedelta(days=1)},
    {"human_authenticated": "yes"},
])
def test_bad_verified_identity_contracts_are_rejected(invalid: dict[str, object]) -> None:
    baseline = identity("alice")
    with pytest.raises(ValueError):
        replace(baseline, **invalid)


def test_membership_permissions_cannot_be_mutable_or_untyped() -> None:
    with pytest.raises(ValueError):
        StoredMembership("alice", "org-a", True, {CaseAction.READ_CASE})  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        StoredMembership("alice", "org-a", True, frozenset({"case:read"}))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        StoredMembership("alice", "org-a", "yes")  # type: ignore[arg-type]


def test_malformed_stored_case_revision_and_owner_are_rejected() -> None:
    with pytest.raises(ValueError):
        StoredCase("case-a", "org-a", True, "alice")
    with pytest.raises(ValueError):
        StoredCase("case-a", "", 1, "alice")


def test_failed_authentication_is_not_a_v2_http_route() -> None:
    # No trust on an X-Tenant header. The legacy v1 demonstration still exists;
    # v2 remains inaccessible until a real signed IdP adapter and DB/RLS exist.
    app = create_app()
    client = TestClient(app)
    assert not any(path.startswith("/v2/") for path in app.openapi()["paths"])
    assert client.get("/v2/cases/case-a/coverage", headers={
        "X-Tenant-Id": "org-a", "X-Role": "owner", "Authorization": "Bearer forged"
    }).status_code == 404


@pytest.mark.parametrize(
    ("change", "label"),
    [
        ({"issuer": "https://other-issuer.test"}, "issuer"),
        ({"audience": "unrelated-service"}, "audience"),
    ],
)
def test_wrong_issuer_or_audience_never_authorizes(
    change: dict[str, object], label: str
) -> None:
    service, verifier, store = rig()
    verifier.subjects["alice-token"] = replace(identity("alice"), **change)
    failure(service, "alice-token", "case-a", CaseAction.READ_CASE,
            AccessFailure.AUTHENTICATION_REQUIRED)
    assert store.calls == [], label


def test_empty_configured_identity_trust_values_are_rejected() -> None:
    _, verifier, store = rig()
    for iss, aud in (("", "caseproof-api"), ("https://auth.example.test", "")):
        with pytest.raises(ValueError):
            CaseAccessService(verifier, store, iss, aud, lambda: NOW)


def test_foreign_and_unknown_case_have_same_response_on_membership_store_outage() -> None:
    service, _, repository = rig()
    repository.unavailable = True
    failure(service, "alice-token", "case-b", CaseAction.READ_CASE,
            AccessFailure.SERVICE_UNAVAILABLE)
    failure(service, "alice-token", "unknown-case", CaseAction.READ_CASE,
            AccessFailure.SERVICE_UNAVAILABLE)
    assert repository.calls == [
        ("lookup", "alice", "case-b"),
        ("lookup", "alice", "unknown-case"),
    ]


def test_foreign_and_unknown_case_have_identical_masked_response_without_outage() -> None:
    service, _, repository = rig()
    failure(service, "alice-token", "case-b", CaseAction.READ_CASE,
            AccessFailure.RESOURCE_MASKED)
    failure(service, "alice-token", "unknown-case", CaseAction.READ_CASE,
            AccessFailure.RESOURCE_MASKED)
    assert repository.calls == [
        ("lookup", "alice", "case-b"),
        ("lookup", "alice", "unknown-case"),
    ]
