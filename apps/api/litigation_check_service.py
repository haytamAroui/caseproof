"""Opt-in M2 headless authenticated review check. No production mount or writes.

The application composes current signed Supabase identity with explicit private
matter action grants (ADR-0017). Never trust HTTP tenant IDs, asserted roles,
client-selected source bytes, review approval or a request-provided JWT subject.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from application.litigation.matter_policy import (
    CurrentMatterGrant, CurrentOrganizationGrant, MatterPermission, authorize_matter,
)
from application.litigation.unified_review import (
    BriefRepresentation, SourceScope, VerificationRun, run_unified_check,
)
from application.litigation.library import EvidencePreview
from apps.api.access_control import (
    AccessFailure, AccessRejected, BearerIdentityVerifier, IdentityServiceUnavailable,
    InvalidBearer, VerifiedSubject,
)
from domains.disputes.exhibits import ExhibitRegister


class MatterCheckUnavailable(Exception):
    """Unavailable trusted matter snapshot; never reveal source existence."""


@dataclass(frozen=True, slots=True)
class PrivateMatterAccess:
    case_id: str
    org_id: str
    member: CurrentOrganizationGrant
    grant: CurrentMatterGrant
    case_revision: int


@dataclass(frozen=True, slots=True)
class CheckBundle:
    representation: BriefRepresentation
    register: ExhibitRegister
    previews: tuple[EvidencePreview, ...]
    source_scope: SourceScope


class PrivateMatterCheckStore(Protocol):
    def current_access(self, subject_id: str, case_id: str) -> PrivateMatterAccess | None:
        """One server-owned current membership+case-grant read, not claims/body."""

    def load_bundle(
        self, *, case_id: str, brief_version_id: str,
        access: PrivateMatterAccess,
    ) -> CheckBundle:
        """Load only approved, verified immutable bytes and exact case/source versions."""

    def still_current(
        self, *, access: PrivateMatterAccess, bundle: CheckBundle,
    ) -> bool:
        """Revalidate case/source/brief/register snapshot and active grants after check."""


class AuthorizedLitigationChecker:
    """App boundary; shipped only as an injectable testable port, not live API wiring."""

    def __init__(
        self, *, verifier: BearerIdentityVerifier, store: PrivateMatterCheckStore,
        issuer: str, audience: str, clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not issuer or not audience:
            raise ValueError("trusted Supabase issuer and audience required")
        self.verifier = verifier
        self.store = store
        self.issuer = issuer
        self.audience = audience
        self.clock = clock or (lambda: datetime.now(UTC))

    def _verified(self, bearer: str) -> VerifiedSubject:
        if not bearer or len(bearer) > 8192:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        try:
            token = self.verifier.verify_bearer(bearer)
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if (not isinstance(token, VerifiedSubject) or token.issuer != self.issuer
                or token.audience != self.audience
                or token.verified_at > self.clock()
                or token.expires_at <= self.clock()):
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        return token

    def _scope(self, subject: VerifiedSubject, case_id: str) -> PrivateMatterAccess:
        try:
            scope = self.store.current_access(subject.subject_id, case_id)
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if (not isinstance(scope, PrivateMatterAccess)
                or scope.case_id != case_id or scope.case_revision < 1):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        decision = authorize_matter(
            actor_id=subject.subject_id, org_id=scope.org_id, case_id=case_id,
            action=MatterPermission.DRAFT_CHECK,
            membership=scope.member, grant=scope.grant,
        )
        if not decision.allowed:
            raise AccessRejected(
                AccessFailure.RESOURCE_MASKED if decision.reason == "masked"
                else AccessFailure.PERMISSION_DENIED
            )
        return scope

    def check(self, *, bearer: str, case_id: str, brief_version_id: str) -> VerificationRun:
        if (not isinstance(case_id, str) or len(case_id) > 128 or not case_id
                or not isinstance(brief_version_id, str) or not 0 < len(brief_version_id) <= 128):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        subject = self._verified(bearer)
        scope = self._scope(subject, case_id)
        try:
            bundle = self.store.load_bundle(
                case_id=case_id, brief_version_id=brief_version_id, access=scope,
            )
            if not isinstance(bundle, CheckBundle) or bundle.representation.brief.version_id != brief_version_id:
                raise MatterCheckUnavailable()
            report = run_unified_check(
                representation=bundle.representation, register=bundle.register,
                previews=bundle.previews, source_scope=bundle.source_scope,
                authorized_case_id=scope.case_id,
                authorized_register_revision=bundle.register.revision,
            )
            # Prevent accidental use of a revoked/grant-changed or source-stale result.
            current = self._scope(self._verified(bearer), case_id)
            if current != scope or not self.store.still_current(access=current, bundle=bundle):
                raise MatterCheckUnavailable()
            return report
        except AccessRejected:
            raise
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
