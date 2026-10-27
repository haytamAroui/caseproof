"""M1-A: pure, default-private litigation authorization decision (ADR-0017).

Not a verifier, HTTP middleware, signed JWT or SQL transaction. Context MUST
come from current trusted repositories; never deserialize these records from
client input, provider text, or JWT user_metadata. The legacy finance case
authorization remains intact until migration/security review.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MatterPermission(StrEnum):
    READ = "case:read"
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_UPLOAD = "evidence:upload"
    EVIDENCE_INDEX = "evidence:index"
    EXHIBIT_CONFIRM = "exhibit:confirm"
    DRAFT_CHECK = "draft:check"
    WORKER_PROCESS = "worker:process"


class OrganizationPermission(StrEnum):
    CASE_LIST = "case:list"
    CASE_CREATE = "case:create"
    CASE_READ = "case:read"
    EVIDENCE_READ = "evidence:read"
    REVIEW_REQUEST = "review:request"
    FINDING_WRITE = "finding:write"


class MatterPolicyError(ValueError):
    """Untrusted, incoherent or stale authorization input."""


def _id(value: object) -> None:
    if type(value) is not str or not value.strip() or len(value) > 128:
        raise MatterPolicyError("trusted bounded resource identity required")


@dataclass(frozen=True, slots=True)
class CurrentOrganizationGrant:
    actor_id: str
    org_id: str
    active: bool
    permissions: frozenset[OrganizationPermission]
    revision: int

    def __post_init__(self) -> None:
        _id(self.actor_id)
        _id(self.org_id)
        if type(self.active) is not bool or type(self.revision) is not int or self.revision < 1:
            raise MatterPolicyError("invalid current organization membership")
        if type(self.permissions) is not frozenset or any(
            not isinstance(p, OrganizationPermission) for p in self.permissions
        ):
            raise MatterPolicyError("typed organization permissions required")


@dataclass(frozen=True, slots=True)
class CurrentMatterGrant:
    actor_id: str
    org_id: str
    case_id: str
    active: bool
    permissions: frozenset[MatterPermission]
    revision: int

    def __post_init__(self) -> None:
        _id(self.actor_id)
        _id(self.org_id)
        _id(self.case_id)
        if type(self.active) is not bool or type(self.revision) is not int or self.revision < 1:
            raise MatterPolicyError("invalid current matter grant")
        if type(self.permissions) is not frozenset or any(
            not isinstance(p, MatterPermission) for p in self.permissions
        ):
            raise MatterPolicyError("typed matter permissions required")


_ORG_REQUIRED: dict[MatterPermission, frozenset[OrganizationPermission]] = {
    MatterPermission.READ: frozenset({OrganizationPermission.CASE_READ}),
    MatterPermission.EVIDENCE_READ: frozenset({
        OrganizationPermission.CASE_READ, OrganizationPermission.EVIDENCE_READ,
    }),
    MatterPermission.EVIDENCE_UPLOAD: frozenset({
        OrganizationPermission.CASE_READ, OrganizationPermission.EVIDENCE_READ,
    }),
    MatterPermission.EVIDENCE_INDEX: frozenset({
        OrganizationPermission.CASE_READ, OrganizationPermission.EVIDENCE_READ,
    }),
    MatterPermission.EXHIBIT_CONFIRM: frozenset({
        OrganizationPermission.CASE_READ, OrganizationPermission.REVIEW_REQUEST,
    }),
    MatterPermission.DRAFT_CHECK: frozenset({
        OrganizationPermission.CASE_READ, OrganizationPermission.FINDING_WRITE,
    }),
    # A worker MUST also carry a case/version/lease-bound delegation. This
    # pure membership check is only one necessary predicate, never sufficient.
    MatterPermission.WORKER_PROCESS: frozenset({
        OrganizationPermission.CASE_READ, OrganizationPermission.EVIDENCE_READ,
    }),
}


@dataclass(frozen=True, slots=True)
class MatterDecision:
    allowed: bool
    reason: str
    grant_revision: int | None = None
    membership_revision: int | None = None


def authorize_matter(
    *,
    actor_id: str,
    org_id: str,
    case_id: str,
    action: MatterPermission,
    membership: CurrentOrganizationGrant | None,
    grant: CurrentMatterGrant | None,
) -> MatterDecision:
    """Default deny unless exact current actor, org, matter, scope and action match."""
    for value in (actor_id, org_id, case_id):
        _id(value)
    if not isinstance(action, MatterPermission):
        raise MatterPolicyError("typed requested action required")
    if (
        membership is None or grant is None
        or not membership.active or not grant.active
        or membership.actor_id != actor_id or grant.actor_id != actor_id
        or membership.org_id != org_id or grant.org_id != org_id
        or grant.case_id != case_id
    ):
        return MatterDecision(False, "masked")
    if action not in grant.permissions or not _ORG_REQUIRED[action].issubset(membership.permissions):
        return MatterDecision(False, "permission_denied")
    if action is MatterPermission.WORKER_PROCESS:
        return MatterDecision(False, "delegated_worker_contract_not_installed")
    return MatterDecision(True, "allowed", grant.revision, membership.revision)


def authorize_organization(
    *,
    actor_id: str,
    org_id: str,
    action: OrganizationPermission,
    membership: CurrentOrganizationGrant | None,
) -> bool:
    """List/create are organization operations, not case-existence oracles."""
    _id(actor_id)
    _id(org_id)
    if action not in {OrganizationPermission.CASE_LIST, OrganizationPermission.CASE_CREATE}:
        raise MatterPolicyError("only list/create supported here")
    return bool(
        membership is not None and membership.active
        and membership.actor_id == actor_id and membership.org_id == org_id
        and action in membership.permissions
    )
