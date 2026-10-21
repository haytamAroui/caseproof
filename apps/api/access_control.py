"""S2-001 — fail-closed case authorization boundary; no HTTP routes or DB writes.

Only a configured, external cryptographic verifier may turn a bearer token
into VerifiedSubject. Memberships, case ownership and effective permissions
are read from trusted server repositories, NEVER the token's user metadata,
an X-Tenant header, an LLM output, or an API request body.

These protocols do not implement Supabase verification, PostgreSQL/RLS, audit
transactions or durable persistence. Until such adapters are configured,
UnavailableBearerVerifier denies all authenticated access.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol


class CaseAction(StrEnum):
    READ_CASE = "case:read"
    READ_COVERAGE = "coverage:read"
    READ_EVIDENCE = "evidence:read"
    PROPOSE_FINDING = "finding:write"
    PROPOSE_REVIEW = "review:request"
    REQUEST_APPROVAL = "conclusion:request_approval"
    REQUEST_EXCEPTION = "exception:request"


class AccessFailure(StrEnum):
    AUTHENTICATION_REQUIRED = "authentication_required"
    RESOURCE_MASKED = "not_found"
    PERMISSION_DENIED = "permission_denied"
    SERVICE_UNAVAILABLE = "service_unavailable"


_STATUS = {
    AccessFailure.AUTHENTICATION_REQUIRED: 401,
    AccessFailure.RESOURCE_MASKED: 404,
    AccessFailure.PERMISSION_DENIED: 403,
    AccessFailure.SERVICE_UNAVAILABLE: 503,
}


class AccessRejected(Exception):
    """An intentionally sanitized failure; never includes IDs or tokens."""

    def __init__(self, code: AccessFailure) -> None:
        self.code = code
        self.http_status = _STATUS[code]
        super().__init__(code.value)


class InvalidBearer(Exception):
    """Verifier says token is invalid or no longer trusted; maps to 401."""


class IdentityServiceUnavailable(Exception):
    """Configured verifier cannot verify a token; maps to 503, not allow."""


class AccessStoreUnavailable(Exception):
    """Case or membership store cannot validate ownership/permissions."""


def _identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} required")


def _utc(value: object, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be UTC")
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError(f"{label} must be UTC")


@dataclass(frozen=True, slots=True)
class VerifiedSubject:
    """ONLY an authenticated verifier adapter may supply this value.

    A Python caller can fabricate this dataclass; do not expose an endpoint
    that deserializes it or permits a client to supply one.
    """

    subject_id: str
    issuer: str
    audience: str
    verified_at: datetime
    expires_at: datetime
    human_authenticated: bool

    def __post_init__(self) -> None:
        for key in ("subject_id", "issuer", "audience"):
            _identifier(getattr(self, key), key)
        _utc(self.verified_at, "verified_at")
        _utc(self.expires_at, "expires_at")
        if self.expires_at <= self.verified_at:
            raise ValueError("verified token validity interval must be positive")
        if type(self.human_authenticated) is not bool:
            raise ValueError("human_authenticated requires trusted boolean")


@dataclass(frozen=True, slots=True)
class StoredCase:
    """Server-retrieved, globally unique case identifier and tenant ownership."""

    case_id: str
    owner_org_id: str
    revision: int
    created_by_subject: str

    def __post_init__(self) -> None:
        for key in ("case_id", "owner_org_id", "created_by_subject"):
            _identifier(getattr(self, key), key)
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("case revision must be a positive integer")


@dataclass(frozen=True, slots=True)
class StoredMembership:
    """Server-owned authorization record, not JWT user-editable metadata."""

    subject_id: str
    org_id: str
    active: bool
    actions: frozenset[CaseAction] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _identifier(self.subject_id, "member subject")
        _identifier(self.org_id, "member organization")
        if type(self.active) is not bool:
            raise ValueError("active must be boolean")
        if not isinstance(self.actions, frozenset) or any(
            not isinstance(action, CaseAction) for action in self.actions
        ):
            raise ValueError("typed immutable action permissions required")


class BearerIdentityVerifier(Protocol):
    def verify_bearer(self, token: str) -> VerifiedSubject:
        """Must verify signature, issuer, audience, expiry and revocation."""


class CaseAccessRepository(Protocol):
    def lookup_case_membership(
        self, subject_id: str, case_id: str
    ) -> tuple[StoredCase, StoredMembership] | None:
        """One trusted, atomic, joined read of case and CURRENT membership.

        Unknown and foreign cases MUST return the same None, including on
        partial membership-store failure. A SQL adapter must execute one
        scoped query, never read case existence before checking membership.
        On ANY query failure raise AccessStoreUnavailable, for both known
        and unknown case IDs. The check is still not a durable authorization
        or state-changing transaction.
        """


@dataclass(frozen=True, slots=True)
class AuthorizedCase:
    """Authorization snapshot, NOT a durable approval or DB transaction."""

    case_id: str
    org_id: str
    subject_id: str
    action: CaseAction
    case_revision: int
    authenticated_human: bool


class UnavailableBearerVerifier:
    """Safe default: never mistake an unconfigured auth adapter for anonymous access."""

    def verify_bearer(self, token: str) -> VerifiedSubject:
        raise IdentityServiceUnavailable("identity verifier not configured")


@dataclass(frozen=True, slots=True)
class CaseAccessService:
    verifier: BearerIdentityVerifier
    repository: CaseAccessRepository
    trusted_issuer: str
    trusted_audience: str
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _identifier(self.trusted_issuer, "trusted issuer")
        _identifier(self.trusted_audience, "trusted audience")

    def authorize(
        self, bearer_token: str | None, case_id: str, action: CaseAction
    ) -> AuthorizedCase:
        """Return access context only after authenticated, tenant-owned permission checks.

        No request tenant, user ID, role or authorization flag is accepted.
        Case lookups occur only after authentication to limit probing.
        """
        if not isinstance(action, CaseAction):
            raise TypeError("supported typed action required")
        _identifier(case_id, "case_id")
        if not isinstance(bearer_token, str) or not bearer_token.strip():
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        try:
            verified = self.verifier.verify_bearer(bearer_token)
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not isinstance(verified, VerifiedSubject):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if verified.issuer != self.trusted_issuer or verified.audience != self.trusted_audience:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        now = self.clock()
        _utc(now, "server clock")
        if verified.verified_at > now or verified.expires_at <= now:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)

        try:
            case_membership = self.repository.lookup_case_membership(
                verified.subject_id, case_id
            )
        except AccessStoreUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if case_membership is None:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        resource, membership = case_membership

        # The repository is trusted but we still verify its returned values.
        if (
            resource.case_id != case_id
            or membership is None
            or membership.subject_id != verified.subject_id
            or membership.org_id != resource.owner_org_id
            or not membership.active
        ):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)

        if action not in membership.actions:
            raise AccessRejected(AccessFailure.PERMISSION_DENIED)
        if action is CaseAction.REQUEST_APPROVAL and (
            not verified.human_authenticated
            or resource.created_by_subject == verified.subject_id
        ):
            # Separation of duties in this reference policy: no self-approval.
            # Still only a request capability, not approval permission.
            raise AccessRejected(AccessFailure.PERMISSION_DENIED)

        return AuthorizedCase(
            case_id=resource.case_id,
            org_id=resource.owner_org_id,
            subject_id=verified.subject_id,
            action=action,
            case_revision=resource.revision,
            authenticated_human=verified.human_authenticated,
        )
