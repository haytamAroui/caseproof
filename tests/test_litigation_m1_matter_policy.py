"""M1-A private-matter policy unit contracts; not a signed-session or live RLS claim."""
from dataclasses import replace

import pytest

from application.litigation.matter_policy import (
    CurrentMatterGrant,
    CurrentOrganizationGrant,
    MatterPermission,
    MatterPolicyError,
    OrganizationPermission,
    authorize_matter,
    authorize_organization,
)

ORG = "org-a"
CASE = "case-a"
USER = "alice"


def contexts():
    membership = CurrentOrganizationGrant(
        USER, ORG, True, frozenset({
            OrganizationPermission.CASE_READ,
            OrganizationPermission.EVIDENCE_READ,
            OrganizationPermission.REVIEW_REQUEST,
            OrganizationPermission.FINDING_WRITE,
            OrganizationPermission.CASE_LIST,
        }), 7,
    )
    grant = CurrentMatterGrant(
        USER, ORG, CASE, True, frozenset({
            MatterPermission.READ, MatterPermission.EVIDENCE_READ,
            MatterPermission.EXHIBIT_CONFIRM,
            MatterPermission.DRAFT_CHECK,
        }), 2,
    )
    return membership, grant


def decision(action, membership=None, grant=None):
    baseline = contexts()
    return authorize_matter(
        actor_id=USER, org_id=ORG, case_id=CASE, action=action,
        membership=baseline[0] if membership is None else membership,
        grant=baseline[1] if grant is None else grant,
    )


def test_member_can_read_confirm_or_check_only_explicit_granted_case():
    for action in (MatterPermission.READ, MatterPermission.EVIDENCE_READ,
                   MatterPermission.EXHIBIT_CONFIRM, MatterPermission.DRAFT_CHECK):
        allowed = decision(action)
        assert allowed.allowed and allowed.grant_revision == 2 and allowed.membership_revision == 7


def test_org_member_no_matter_grant_does_not_read_same_org_other_case():
    m, g = contexts()
    result = authorize_matter(
        actor_id=USER, org_id=ORG, case_id="case-b", action=MatterPermission.READ,
        membership=m, grant=g,
    )
    assert not result.allowed and result.reason == "masked"


@pytest.mark.parametrize("alter", [
    lambda m,g: (replace(m, active=False), g),
    lambda m,g: (m, replace(g, active=False)),
    lambda m,g: (replace(m, actor_id="bob"), g),
    lambda m,g: (m, replace(g, actor_id="bob")),
    lambda m,g: (replace(m, org_id="org-b"), g),
    lambda m,g: (m, replace(g, org_id="org-b")),
    lambda m,g: (m, replace(g, case_id="case-b")),
])
def test_revoked_or_other_actor_scope_is_masked(alter):
    m, g = alter(*contexts())
    result = authorize_matter(
        actor_id=USER, org_id=ORG, case_id=CASE, action=MatterPermission.READ,
        membership=m, grant=g,
    )
    assert not result.allowed and result.reason == "masked"


def test_read_does_not_imply_upload_index_confirm_or_write_check():
    assert decision(MatterPermission.EVIDENCE_READ).allowed
    for action in (MatterPermission.EVIDENCE_UPLOAD, MatterPermission.EVIDENCE_INDEX):
        assert decision(action).reason == "permission_denied"


def test_org_cap_is_independent_of_case_grant():
    m, g = contexts()
    assert authorize_matter(
        actor_id=USER, org_id=ORG, case_id=CASE,
        action=MatterPermission.EXHIBIT_CONFIRM,
        membership=replace(m, permissions=frozenset({OrganizationPermission.CASE_READ})),
        grant=g,
    ).reason == "permission_denied"


def test_worker_is_not_authorized_by_user_grants_only():
    m, g = contexts()
    g = replace(g, permissions=g.permissions | {MatterPermission.WORKER_PROCESS})
    assert authorize_matter(
        actor_id=USER, org_id=ORG, case_id=CASE,
        action=MatterPermission.WORKER_PROCESS, membership=m, grant=g,
    ).reason == "delegated_worker_contract_not_installed"


def test_org_level_list_create_are_not_matter_grants():
    m, _ = contexts()
    assert authorize_organization(
        actor_id=USER, org_id=ORG, action=OrganizationPermission.CASE_LIST, membership=m,
    )
    assert not authorize_organization(
        actor_id=USER, org_id=ORG, action=OrganizationPermission.CASE_CREATE, membership=m,
    )
    with pytest.raises(MatterPolicyError):
        authorize_organization(
            actor_id=USER, org_id=ORG, action=OrganizationPermission.CASE_READ, membership=m,
        )


def test_invalid_typed_permissions_fail_closed():
    with pytest.raises(MatterPolicyError):
        CurrentMatterGrant(USER, ORG, CASE, True, frozenset({"evidence:read"}), 1)
    with pytest.raises(MatterPolicyError):
        CurrentOrganizationGrant(USER, ORG, True, frozenset({"case:read"}), 1)
    with pytest.raises(MatterPolicyError):
        decision("exhibit:confirm")
