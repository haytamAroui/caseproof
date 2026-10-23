"""Adapter contracts for isolated S2-009b PostgreSQL VaultLedger.

Fake connections assert the exact parameterized command boundary; disposable
PostgreSQL CI separately exercises SQL rollback and concurrency.
"""

from uuid import UUID

import pytest

from apps.api.disposable_postgres_vault_ledger import (
    COMMAND_SQL, READ_SQL, DisposablePostgresVaultLedger,
    DisposableVaultActorContext,
)
from apps.api.evidence_vault_protocol import (
    UploadIntent, VaultConflict, VaultRecord, VaultScope, VaultState,
)

ORG = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CASE = UUID("aaaaaaaa-1111-4111-8111-111111111111")
INTENT = UUID("12345678-1234-4234-8234-1234567890ab")
ACTOR = UUID("aaaaaaaa-3333-4333-8333-333333333333")
VERSION = UUID("aaaaaaaa-4444-4444-8444-444444444444")
AUDIT = UUID("aaaaaaaa-5555-4555-8555-555555555555")


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, sql, params):
        self.sql, self.params = sql, params

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def cursor(self):
        return self._cursor


def fixture(rows):
    cursor = Cursor(rows)
    adapter = DisposablePostgresVaultLedger(
        lambda: Connection(cursor), DisposableVaultActorContext(ACTOR, VERSION),
    )
    scope = VaultScope(ORG, CASE)
    intent = UploadIntent(
        scope, INTENT, f"org/{ORG.hex}/case/{CASE.hex}/sources/" + "f" * 32,
        "a" * 64, 12, "text/plain",
    )
    return adapter, intent, cursor


def test_stage_is_parameterized_and_returns_pending() -> None:
    adapter, intent, cursor = fixture([(
        "pending", 1, 2, AUDIT, False,
        f"org/{ORG.hex}/case/{CASE.hex}/sources/" + "f" * 32,
    )])
    result = adapter.create_pending(intent)
    assert result.state is VaultState.PENDING and result.revision == 1
    assert result.availability_audit_id is None
    assert cursor.sql == COMMAND_SQL
    assert cursor.params[0] == str(ACTOR)
    assert cursor.params[4] == str(INTENT)
    assert cursor.params[6] == str(VERSION)
    assert cursor.params[7] == intent.object_key
    assert cursor.params[8] == intent.sha256_hex
    assert cursor.params[-1] is None
    assert "a" * 64 not in COMMAND_SQL


def test_exact_scoped_lookup_reconstructs_verified_receipt() -> None:
    adapter, intent, cursor = fixture([(
        ORG, CASE, INTENT, intent_key(), "a" * 64,
        12, "text/plain", "verified", 2, AUDIT,
    )])
    record = adapter.get_scoped(intent.scope, INTENT)
    assert record is not None and record.state is VaultState.VERIFIED
    assert record.availability_audit_id == AUDIT
    assert cursor.sql == READ_SQL
    assert cursor.params == (str(ORG), str(CASE), str(INTENT))


def intent_key():
    return f"org/{ORG.hex}/case/{CASE.hex}/sources/" + "f" * 32


def test_foreign_or_ambiguous_rows_fail_closed() -> None:
    adapter, intent, _ = fixture([])
    assert adapter.get_scoped(intent.scope, INTENT) is None
    adapter, intent, _ = fixture([(ORG, UUID(int=1), INTENT, intent_key(),
                                   "a" * 64, 12, "text/plain", "pending", 1, AUDIT)])
    with pytest.raises(VaultConflict):
        adapter.get_scoped(intent.scope, INTENT)


def test_verify_and_unavailability_use_expected_revision() -> None:
    adapter, intent, cursor = fixture([(
        "verified", 2, 3, AUDIT, False, intent_key(),
    )])
    pending = VaultRecord(intent, VaultState.PENDING, 1, None)
    verified = adapter.publish_verified(pending)
    assert verified.revision == 2 and verified.availability_audit_id == AUDIT
    assert cursor.params[3] == "verify" and cursor.params[11] == 1
    cursor.rows = [("unavailable", 3, 4, AUDIT, False, intent_key())]
    lost = adapter.mark_unavailable(verified, "digest_mismatch")
    assert lost.state is VaultState.UNAVAILABLE
    assert cursor.params[3] == "unavailable"
    assert cursor.params[11] == 2 and cursor.params[12] == "digest_mismatch"


def test_invalid_transitions_never_issue_sql() -> None:
    adapter, intent, cursor = fixture([])
    pending = VaultRecord(intent, VaultState.PENDING, 1, None)
    with pytest.raises(VaultConflict):
        adapter.mark_unavailable(pending, "missing")
    with pytest.raises(ValueError):
        adapter._command(intent, "approve")
    assert cursor.sql is None
