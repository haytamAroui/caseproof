"""S2-005 SQL adapter's negative contract: no tenant existence oracle or writes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Self
from uuid import UUID

import pytest

from apps.api.access_control import (
    AccessFailure,
    AccessRejected,
    AccessStoreUnavailable,
    CaseAccessService,
    CaseAction,
    VerifiedSubject,
)
from apps.api.postgres_case_repository import (
    JOINED_CASE_MEMBERSHIP_SQL,
    PostgresCaseAccessRepository,
)

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CASE_A = "aaaaaaaa-1111-4111-8111-111111111111"
CASE_B = "bbbbbbbb-2222-4222-8222-222222222222"
NOW = datetime(2026, 10, 22, tzinfo=UTC)


def match_row(*, member: str = USER_A, org: str = ORG_A,
              case: str = CASE_A, actions: object = None) -> tuple[object, ...]:
    rights = ["case:read", "evidence:read"] if actions is None else actions
    return (UUID(case), UUID(org), 4, UUID(USER_B), UUID(member),
            UUID(org), True, rights)


@dataclass
class FakeCursor:
    rows: list[tuple[object, ...]]
    statements: list[tuple[str, tuple[str, str]]]
    broken: bool = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def execute(self, statement: str, parameters: tuple[str, str]) -> None:
        self.statements.append((statement, parameters))
        if self.broken:
            raise RuntimeError("sensitive db exception, never leak")

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


@dataclass
class FakeConnection:
    cursor_instance: FakeCursor
    closed: bool = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.closed = True

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


@dataclass
class DBRig:
    records: list[tuple[object, ...]]
    broken: bool = False
    statements: list[tuple[str, tuple[str, str]]] = field(default_factory=list)
    connections: list[FakeConnection] = field(default_factory=list)

    def open(self) -> FakeConnection:
        c = FakeConnection(FakeCursor(self.records, self.statements, self.broken))
        self.connections.append(c)
        return c


def test_single_parameterized_case_membership_join_is_immutable() -> None:
    sql = JOINED_CASE_MEMBERSHIP_SQL.lower()
    assert "from caseproof.cases as c" in sql
    assert "inner join caseproof.organization_members as m" in sql
    assert "m.org_id = c.org_id" in sql
    assert "m.user_id = %s" in sql
    assert "m.active = true" in sql
    assert "where c.id = %s" in sql
    assert "limit 2" in sql
    assert "set role" not in sql
    assert "create " not in sql
    assert "update " not in sql
    assert "delete " not in sql
    assert sql.count("%s") == 2


def test_authorized_current_membership_converts_typed_row() -> None:
    rig = DBRig([match_row()])
    repo = PostgresCaseAccessRepository(rig.open)
    pair = repo.lookup_case_membership(USER_A, CASE_A)
    assert pair is not None
    case, member = pair
    assert case.owner_org_id == ORG_A
    assert case.created_by_subject == USER_B
    assert case.revision == 4
    assert member.active
    assert member.subject_id == USER_A
    assert member.actions == frozenset({CaseAction.READ_CASE, CaseAction.READ_EVIDENCE})
    assert rig.statements == [(JOINED_CASE_MEMBERSHIP_SQL, (USER_A, CASE_A))]
    assert rig.connections[0].closed


def test_unknown_or_foreign_case_is_same_none_result_with_no_second_lookup() -> None:
    rig = DBRig([])
    repo = PostgresCaseAccessRepository(rig.open)
    for case in (CASE_A, CASE_B):
        assert repo.lookup_case_membership(USER_A, case) is None
    assert len(rig.statements) == 2
    assert all(record[0] == JOINED_CASE_MEMBERSHIP_SQL for record in rig.statements)
    assert all(c.closed for c in rig.connections)


@pytest.mark.parametrize("case_id,subject", [
    ("", USER_A),
    ("obviously-not-uuid", USER_A),
    (CASE_A, "not-a-subject"),
    (CASE_A, ""),
    ("1; DROP TABLE caseproof.cases;", USER_A),
])
def test_untrusted_resource_ids_are_never_interpolated_or_queried(
    case_id: str, subject: str
) -> None:
    rig = DBRig([])
    assert PostgresCaseAccessRepository(rig.open).lookup_case_membership(
        subject, case_id
    ) is None
    assert not rig.connections


@pytest.mark.parametrize("rows", [
    [match_row(), match_row()],
    [match_row(member=USER_B)],
    [(UUID(CASE_A), UUID(ORG_A), 4, UUID(USER_B), UUID(USER_A),
      UUID(ORG_B), True, ["case:read"])],
    [match_row(case=CASE_B)],
    [match_row(actions=["case:read", "permission:superuser"])],
    [match_row(actions={"case:read"})],
    [(UUID(CASE_A), UUID(ORG_A), True, UUID(USER_B), UUID(USER_A),
      UUID(ORG_A), True, ["case:read"])],
    [(UUID(CASE_A), UUID(ORG_A))],
])
def test_corrupt_privileged_row_fails_closed(rows: list[tuple[object, ...]]) -> None:
    rig = DBRig(rows)
    with pytest.raises(AccessStoreUnavailable) as e:
        PostgresCaseAccessRepository(rig.open).lookup_case_membership(USER_A, CASE_A)
    assert str(e.value) == "Case membership read unavailable"
    assert rig.connections[0].closed


@pytest.mark.parametrize("actions", [
    ["case:read", "case:read"],
    ["case:read", "evidence:read", "case:read", "evidence:read"],
])
def test_schema_valid_duplicate_membership_grants_are_normalized(
    actions: list[str],
) -> None:
    rig = DBRig([match_row(actions=actions)])
    pair = PostgresCaseAccessRepository(rig.open).lookup_case_membership(USER_A, CASE_A)
    assert pair is not None
    _, membership = pair
    assert membership.actions == frozenset(CaseAction(value) for value in actions)
    assert rig.connections[0].closed


def test_internal_sql_errors_fail_503_without_foreign_case_existence_or_db_details() -> None:
    rig = DBRig([], broken=True)
    repo = PostgresCaseAccessRepository(rig.open)
    for case_id in (CASE_A, CASE_B):
        with pytest.raises(AccessStoreUnavailable) as e:
            repo.lookup_case_membership(USER_A, case_id)
        assert "sensitive" not in str(e.value)
        assert "db" not in str(e.value).lower()
    assert all(c.closed for c in rig.connections)


@dataclass
class FakeVerifiedBearer:
    def verify_bearer(self, token: str) -> VerifiedSubject:
        if token != "verified-token":
            raise ValueError("use fixture token only")
        return VerifiedSubject(
            USER_A, "https://auth.example.test", "authenticated",
            NOW - timedelta(minutes=1), NOW + timedelta(minutes=20), False,
        )


def test_authorization_service_uses_same_joined_adapter_and_enforces_rights() -> None:
    rig = DBRig([match_row()])
    service = CaseAccessService(
        FakeVerifiedBearer(), PostgresCaseAccessRepository(rig.open),
        "https://auth.example.test", "authenticated", lambda: NOW,
    )
    authorized = service.authorize("verified-token", CASE_A, CaseAction.READ_CASE)
    assert authorized.org_id == ORG_A
    assert authorized.subject_id == USER_A
    with pytest.raises(AccessRejected) as e:
        service.authorize("verified-token", CASE_A, CaseAction.REQUEST_APPROVAL)
    assert e.value.code is AccessFailure.PERMISSION_DENIED


def test_authorization_service_fails_closed_on_database_error_without_case_leak() -> None:
    rig = DBRig([], broken=True)
    service = CaseAccessService(
        FakeVerifiedBearer(), PostgresCaseAccessRepository(rig.open),
        "https://auth.example.test", "authenticated", lambda: NOW,
    )
    for case in (CASE_A, CASE_B):
        with pytest.raises(AccessRejected) as e:
            service.authorize("verified-token", case, CaseAction.READ_CASE)
        assert (e.value.http_status, e.value.code) == (
            503, AccessFailure.SERVICE_UNAVAILABLE
        )
