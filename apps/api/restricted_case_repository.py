"""PIV-02 restricted matter access: single server-owned grant + membership join.

This adapter is intentionally NOT wired to the existing v1 demo or public API.
Requires the separately reviewed M1 schema; fails closed until it is installed.
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

RESTRICTED_CASE_SQL = """
select c.id, c.org_id, c.case_revision, c.created_by_user,
       m.user_id, m.org_id, m.active, m.actions, g.role
from caseproof.cases c
join caseproof.organization_members m
  on m.org_id=c.org_id and m.user_id=%s and m.active=true
join caseproof._m1_matter_grants g
  on g.org_id=c.org_id and g.case_id=c.id
     and g.user_id=m.user_id and g.active=true
where c.id=%s
limit 2
"""

class Cursor(Protocol):
    def execute(self, statement: str, params: tuple[str,str]) -> object: ...
    def fetchall(self) -> Sequence[Sequence[object]]: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...

class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...

def _uuid(v: object) -> str:
    if not isinstance(v, (str, UUID)):
        raise ValueError("expected server UUID")
    return str(UUID(str(v)))

@dataclass(frozen=True)
class RestrictedPostgresCaseRepository:
    connect: Callable[[], Connection]

    def lookup_case_membership(
        self, subject_id: str, case_id: str,
    ) -> tuple[StoredCase, StoredMembership] | None:
        try:
            actor, case = _uuid(subject_id), _uuid(case_id)
        except (ValueError, TypeError):
            return None
        try:
            with self.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(RESTRICTED_CASE_SQL, (actor, case))
                    records = cur.fetchall()
            if not records:
                return None
            if len(records) != 1 or len(records[0]) != 9:
                raise ValueError("ambiguous restricted access result")
            case_id_db, org, rev, creator, user, member_org, active, actions, role = records[0]
            if (
                _uuid(case_id_db) != case
                or _uuid(user) != actor
                or _uuid(org) != _uuid(member_org)
                or active is not True or type(rev) is not int or rev < 1
                or role not in {"viewer", "reviewer"}
                or not isinstance(actions, (list, tuple))
            ):
                raise ValueError("invalid restricted matter grant")
            rights = frozenset(CaseAction(a) for a in actions)
            if role == "viewer":
                rights &= frozenset({
                    CaseAction.READ_CASE, CaseAction.READ_COVERAGE, CaseAction.READ_EVIDENCE,
                })
            return (
                StoredCase(case, _uuid(org), rev, _uuid(creator)),
                StoredMembership(actor, _uuid(org), True, rights),
            )
        except Exception:
            raise AccessStoreUnavailable("restricted matter lookup unavailable") from None
