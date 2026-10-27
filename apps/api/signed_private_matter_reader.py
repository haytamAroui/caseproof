"""M1-B signed-subject → least-privilege private-matter PostgreSQL reader.

Production CANDIDATE; no public API mount and no live DB credentials.
Only a trusted remote Auth verifier can bind a Supabase JWT to a short-lived
DB transaction. The login must be a pinned non-owner, non-BYPASSRLS role with
only inherited authenticated SELECT grants; the request cannot set a subject.

This does not create users, sign JWTs, authorize human legal decisions, read
private original bytes, or validate RLS migration deployment.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from apps.api.access_control import (
    AccessFailure,
    AccessRejected,
    BearerIdentityVerifier,
    IdentityServiceUnavailable,
    InvalidBearer,
    VerifiedSubject,
)

APP_DB_ROLE = "caseproof_m1_reader"


@dataclass(frozen=True, slots=True)
class MatterReceipt:
    case_id: str
    case_revision: int
    org_id: str
    # This is a confidential server-side value; do not expose to an HTTP
    # caller until a separate API response policy is approved.


@dataclass(frozen=True, slots=True)
class DocumentVersionReceipt:
    case_id: str
    document_id: str
    version_id: str
    sha256_hex: str
    media_type: str


def _canonical_uuid(raw: str) -> str:
    try:
        parsed = UUID(raw)
        if parsed.int == 0 or str(parsed) != raw:
            raise ValueError("noncanonical")
        return str(parsed)
    except (TypeError, ValueError, AttributeError):
        raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None


class SignedPrivateMatterReader:
    """One bearer + exactly one trusted DB session per read operation."""

    def __init__(
        self, *,
        verifier: BearerIdentityVerifier,
        connection_factory: Callable[[], Any],
        issuer: str,
        audience: str = "authenticated",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not issuer or audience != "authenticated":
            raise ValueError("Pinned Auth issuer and authenticated audience required")
        self._verifier = verifier
        self._connect = connection_factory
        self._issuer = issuer
        self._audience = audience
        self._clock = clock or (lambda: datetime.now(UTC))

    def _identity(self, bearer: str) -> str:
        if type(bearer) is not str or not 0 < len(bearer) <= 8192:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        try:
            subject = self._verifier.verify_bearer(bearer)
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        now = self._clock()
        if (
            not isinstance(subject, VerifiedSubject)
            or subject.issuer != self._issuer
            or subject.audience != self._audience
            or subject.verified_at > now
            or subject.expires_at <= now
        ):
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        try:
            actor = _canonical_uuid(subject.subject_id)
        except AccessRejected:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        return actor

    @staticmethod
    def _start_bound_read(conn: Any, actor: str) -> None:
        # The role is a LOCAL, unprivileged login created by a reviewed DBA,
        # NEVER postgres, service_role, table owner, or a direct user login.
        row = conn.execute(
            "select current_user,session_user,"
            "coalesce((select rolsuper from pg_roles where rolname=current_user),true),"
            "coalesce((select rolbypassrls from pg_roles where rolname=current_user),true)"
        ).fetchone()
        if (row is None or len(row) != 4
                or row[0] != APP_DB_ROLE or row[1] != APP_DB_ROLE
                or row[2] is not False or row[3] is not False):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        # Fail closed if role owns protected relations: owners bypass RLS
        # unless FORCE ROW LEVEL SECURITY is separately configured.
        owner = conn.execute(
            "select exists(select 1 from pg_tables where schemaname='caseproof' "
            "and tablename in ('cases','documents','document_versions',"
            "'organization_members','_m1_matter_grants') "
            "and tableowner=current_user)"
        ).fetchone()
        if owner is None or owner[0] is not False:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        # Reject inherited privileged or owning roles too: a login can SET ROLE
        # even when its own pg_roles flags look safe. Verify the expected RLS
        # tables exist and are enabled and the effective role is read-only.
        unsafe = conn.execute(
            "select "
            "exists(select 1 from pg_roles r where r.oid <> (select oid from pg_roles "
            "where rolname=current_user) and (r.rolsuper or r.rolbypassrls) "
            "and pg_has_role(current_user,r.oid,'MEMBER')), "
            "(select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='caseproof' and c.relname in "
            "('cases','documents','document_versions','organization_members','_m1_matter_grants') "
            "and c.relkind in ('r','p') and c.relrowsecurity), "
            "exists(select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='caseproof' and c.relname in "
            "('cases','documents','document_versions','organization_members','_m1_matter_grants') "
            "and (pg_has_role(current_user,c.relowner,'MEMBER') or "
            "has_table_privilege(current_user,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')))"
        ).fetchone()
        if unsafe is None or tuple(unsafe) != (False, 5, False):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        # Config is strictly LOCAL to the transaction and comes only from
        # the REMOTELY VERIFIED subject (never body/header/tenant metadata).
        conn.execute("select set_config('request.jwt.claim.sub',%s,true)", (actor,))
        scoped = conn.execute("select auth.uid()::text").fetchone()
        if scoped is None or scoped[0] != actor:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)

    def read_case(self, *, bearer: str, case_id: str) -> MatterReceipt:
        actor, case = self._identity(bearer), _canonical_uuid(case_id)
        try:
            with self._connect() as conn:
                self._start_bound_read(conn, actor)
                rows = conn.execute(
                    "select c.id::text,c.case_revision,c.org_id::text "
                    "from caseproof.cases c "
                    "join caseproof.organization_members m "
                    "on m.org_id=c.org_id and m.user_id=auth.uid() and m.active "
                    "join caseproof._m1_matter_grants g "
                    "on g.org_id=c.org_id and g.case_id=c.id "
                    "and g.user_id=m.user_id and g.active "
                    "where c.id=%s and 'case:read'=any(m.actions) "
                    "and 'case:read'=any(g.permissions)",
                    (UUID(case),),
                ).fetchall()
                if len(rows) != 1:
                    raise AccessRejected(AccessFailure.RESOURCE_MASKED)
                cid, revision, org = rows[0]
                if cid != case or type(revision) is not int or revision < 1:
                    raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
                return MatterReceipt(cid, revision, str(org))
        except AccessRejected:
            raise
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    def read_version(
        self, *, bearer: str, case_id: str,
        document_id: str, version_id: str,
    ) -> DocumentVersionReceipt:
        actor = self._identity(bearer)
        case, document, version = (
            _canonical_uuid(case_id),
            _canonical_uuid(document_id),
            _canonical_uuid(version_id),
        )
        try:
            with self._connect() as conn:
                self._start_bound_read(conn, actor)
                rows = conn.execute(
                    "select d.case_id::text,d.id::text,v.id::text,"
                    "v.original_sha256_hex,v.media_type "
                    "from caseproof.document_versions v "
                    "join caseproof.documents d on d.org_id=v.org_id "
                    "and d.id=v.document_id "
                    "join caseproof.organization_members m on m.org_id=d.org_id "
                    "and m.user_id=auth.uid() and m.active "
                    "join caseproof._m1_matter_grants g on g.org_id=d.org_id "
                    "and g.case_id=d.case_id and g.user_id=m.user_id and g.active "
                    "where d.case_id=%s and d.id=%s and v.id=%s "
                    "and m.actions @> array['case:read','evidence:read']::text[] "
                    "and g.permissions @> array['case:read','evidence:read']::text[]",
                    (UUID(case), UUID(document), UUID(version)),
                ).fetchall()
                if len(rows) != 1:
                    raise AccessRejected(AccessFailure.RESOURCE_MASKED)
                cid, did, vid, digest, media = rows[0]
                if (cid != case or did != document or vid != version
                        or type(digest) is not str or len(digest) != 64
                        or type(media) is not str):
                    raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
                return DocumentVersionReceipt(cid, did, vid, digest, media)
        except AccessRejected:
            raise
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
