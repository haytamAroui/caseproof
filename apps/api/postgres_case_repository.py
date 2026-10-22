"""S2-005 — tenant-authorized read-only Postgres adapter for CaseAccessRepository.

No database connection is configured here. Production composition must provide
a reviewed least-privilege connection factory, and a signed-token verifier.
Client-supplied org/tenant/role fields are never accepted or interpolated.
The single parameterized SQL query joins current membership to case ownership;
a foreign or unknown case both produce None. No writes or v2 HTTP routes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, Self
from uuid import UUID

from apps.api.access_control import (
    AccessStoreUnavailable,
    CaseAction,
    StoredCase,
    StoredMembership,
)

# DB API placeholders are data-only; NEVER interpolate a token, UUID, tenant,
# case ID or subject into the query's SQL source text.
JOINED_CASE_MEMBERSHIP_SQL = """
select c.id, c.org_id, c.case_revision, c.created_by_user,
       m.user_id, m.org_id, m.active, m.actions
from caseproof.cases as c
inner join caseproof.organization_members as m
    on m.org_id = c.org_id and m.user_id = %s and m.active = true
where c.id = %s
limit 2
"""

class Cursor(Protocol):
    def execute(self, statement: str, parameters: tuple[str, str]) -> object: ...
    def fetchall(self) -> Sequence[Sequence[object]]: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...


def _uuid(value: object) -> str:
    if not isinstance(value, (str, UUID)):
        raise ValueError("Expected server-owned UUID")
    return str(UUID(str(value)))


def _row_to_models(
    row: Sequence[object], subject: str, case_id: str
) -> tuple[StoredCase, StoredMembership]:
    if isinstance(row, (str, bytes)) or len(row) != 8:
        raise ValueError("Unexpected joined case/membership record")
    case_uuid, case_org, revision, creator, member_user, member_org, active, actions = row
    if (
        _uuid(case_uuid) != case_id
        or _uuid(member_user) != subject
        or _uuid(case_org) != _uuid(member_org)
        or active is not True
        or type(revision) is not int
        or not isinstance(actions, (tuple, list))
    ):
        raise ValueError("Joined record violates tenant/identity invariants")
    permissions: list[CaseAction] = []
    for action in actions:
        if type(action) is not str:
            raise ValueError("Invalid stored permission value")
        permissions.append(CaseAction(action))
    # Duplicates are schema-valid under the installed Postgres actions <@
    # check. Idempotently normalize permitted grants to a set.
    stored = StoredCase(
        case_id=_uuid(case_uuid),
        owner_org_id=_uuid(case_org),
        revision=revision,
        created_by_subject=_uuid(creator),
    )
    member = StoredMembership(
        subject_id=_uuid(member_user),
        org_id=_uuid(member_org),
        active=True,
        actions=frozenset(permissions),
    )
    return stored, member


@dataclass(frozen=True, slots=True)
class PostgresCaseAccessRepository:
    """No credentials or active connection embedded in this value.

    Only a server-controlled connection factory can supply trusted database
    privilege. This adapter does NOT implement transaction-level review
    authorization and must never be used as a writer.
    """

    connection_factory: Callable[[], Connection]

    def lookup_case_membership(
        self, subject_id: str, case_id: str
    ) -> tuple[StoredCase, StoredMembership] | None:
        # UUIDs are expected as canonical strings, never user-controlled SQL.
        try:
            subject = _uuid(subject_id)
            case = _uuid(case_id)
        except (TypeError, ValueError):
            return None
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(JOINED_CASE_MEMBERSHIP_SQL, (subject, case))
                    rows = cursor.fetchall()
            if len(rows) == 0:
                return None
            if len(rows) != 1:
                raise ValueError("Ambiguous joined access record")
            return _row_to_models(rows[0], subject, case)
        except Exception:
            # Never disclose table existence, SQL syntax, connection hints,
            # credentials or membership data through this interface.
            raise AccessStoreUnavailable("Case membership read unavailable") from None
