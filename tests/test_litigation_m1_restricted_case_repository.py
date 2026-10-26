"""Restricted same-org grants and SQL boundary: fixture only, no real DB session."""
from dataclasses import dataclass, field
from typing import Self
from uuid import UUID

import pytest

from apps.api.access_control import AccessStoreUnavailable, CaseAction
from apps.api.restricted_case_repository import (
    RESTRICTED_CASE_SQL,
    RestrictedPostgresCaseRepository,
)

ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CASE = "aaaaaaaa-1111-4111-8111-111111111111"
ACTOR = "11111111-1111-4111-8111-111111111111"


@dataclass
class Cursor:
    rows: list[tuple[object, ...]]
    statements: list[tuple[str, tuple[str,str]]]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[str,str]) -> None:
        self.statements.append((sql, params))

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


@dataclass
class Connection:
    cursor_obj: Cursor

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> Cursor:
        return self.cursor_obj


@dataclass
class Rig:
    rows: list[tuple[object, ...]] = field(default_factory=list)
    statements: list[tuple[str, tuple[str,str]]] = field(default_factory=list)

    def open(self) -> Connection:
        return Connection(Cursor(self.rows, self.statements))


def row(role: str = "reviewer", *, granted: list[str] | None = None) -> tuple[object, ...]:
    return (
        UUID(CASE), UUID(ORG), 1, UUID(ACTOR),
        UUID(ACTOR), UUID(ORG), True,
        ["case:read", "evidence:read", "review:request"], role,
        ["case:read", "evidence:read", "review:request"] if granted is None else granted,
    )


def test_restricted_case_is_one_join_with_explicit_matter_grant():
    q = RESTRICTED_CASE_SQL.lower()
    assert "join caseproof._m1_matter_grants" in q
    assert "g.case_id=c.id" in q
    assert "g.user_id=m.user_id" in q
    assert "g.active=true" in q
    assert "g.permissions" in q
    rig = Rig([row()])
    result = RestrictedPostgresCaseRepository(rig.open).lookup_case_membership(ACTOR, CASE)
    assert result is not None
    assert CaseAction.PROPOSE_REVIEW in result[1].actions
    assert rig.statements == [(RESTRICTED_CASE_SQL, (ACTOR, CASE))]


def test_viewer_role_cannot_leak_review_permission():
    rig = Rig([row("viewer")])
    result = RestrictedPostgresCaseRepository(rig.open).lookup_case_membership(ACTOR, CASE)
    assert result is not None
    assert result[1].actions == frozenset({CaseAction.READ_CASE, CaseAction.READ_EVIDENCE})


def test_unganted_restricted_case_is_masked_no_tenant_oracle():
    rig = Rig()
    assert RestrictedPostgresCaseRepository(rig.open).lookup_case_membership(ACTOR, CASE) is None
    assert RestrictedPostgresCaseRepository(rig.open).lookup_case_membership(ACTOR, str(UUID(int=1))) is None


@pytest.mark.parametrize("broken", [
    [row(), row()],
    [(*row()[:-2], "admin", ["case:read"])],
    [(*row()[:-3], ["case:read", "role:owner"], "reviewer", ["case:read"])],
    [(*row()[:-1], ["case:read", "superuser:all"])],
])
def test_corrupted_or_overprivileged_rows_fail_closed(broken):
    rig = Rig(broken)
    with pytest.raises(AccessStoreUnavailable):
        RestrictedPostgresCaseRepository(rig.open).lookup_case_membership(ACTOR, CASE)



def test_membership_does_not_imply_case_level_review() -> None:
    rig = Rig([row(granted=["case:read", "evidence:read"])])
    pair = RestrictedPostgresCaseRepository(rig.open).lookup_case_membership(ACTOR, CASE)
    assert pair is not None
    assert CaseAction.READ_EVIDENCE in pair[1].actions
    assert CaseAction.PROPOSE_REVIEW not in pair[1].actions


def test_explicit_review_without_case_read_does_not_authorize_case() -> None:
    rig = Rig([row(granted=["review:request"])])
    pair = RestrictedPostgresCaseRepository(rig.open).lookup_case_membership(ACTOR, CASE)
    assert pair is not None
    assert CaseAction.READ_CASE not in pair[1].actions
