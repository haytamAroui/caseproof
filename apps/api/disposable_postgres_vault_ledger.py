"""Disposable PostgreSQL VaultLedger adapter for the S2-009b SQL proposal.

NOT a production/Supabase adapter. The proposal function takes a synthetic
actor, not a signed identity; use only an isolated disposable PostgreSQL DB.
The caller must provision the S2-009b schema and bind an independently
selected source-version UUID. All mutations are parameterized and executed
by the database's atomic audit/idempotency function.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, Self
from uuid import UUID

from apps.api.evidence_vault_protocol import (
    UploadIntent,
    VaultConflict,
    VaultLedger,
    VaultRecord,
    VaultScope,
    VaultState,
)

COMMAND_SQL = """
select resulting_state, resulting_intent_revision, resulting_case_revision,
       recorded_audit, idempotent_replay, persisted_object_key
from caseproof._s2_009b_disposable_command(
 p_actor => %s::uuid, p_case => %s::uuid, p_intent => %s::uuid,
 p_operation => %s, p_request_key => %s, p_correlation => %s::uuid,
 p_document_version => %s::uuid, p_object_key => %s,
 p_sha => %s, p_byte_length => %s, p_media => %s,
 p_expected_intent_revision => %s, p_reason => %s, p_fault => null
)
"""

READ_SQL = """
select org_id, case_id, intent_id, object_key, sha256_hex, byte_length,
       media_type, state, intent_revision, last_audit_id
from caseproof._s2_009b_vault_intents
where org_id = %s::uuid and case_id = %s::uuid and intent_id = %s::uuid
limit 2
"""


class Cursor(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...]) -> object: ...
    def fetchall(self) -> Sequence[Sequence[object]]: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...


@dataclass(frozen=True, slots=True)
class DisposableVaultActorContext:
    actor_id: UUID
    document_version_id: UUID

    def __post_init__(self) -> None:
        if any(not isinstance(x, UUID) or x.int == 0 for x in (
            self.actor_id, self.document_version_id
        )):
            raise ValueError("non-nil synthetic fixture identifiers required")


@dataclass(frozen=True, slots=True)
class DisposablePostgresVaultLedger(VaultLedger):
    connection_factory: Callable[[], Connection]
    context: DisposableVaultActorContext

    def _command(self, intent: UploadIntent, operation: str,
                 *, expected: int | None = None,
                 reason: str | None = None) -> VaultRecord:
        if operation not in {"stage", "verify", "unavailable"}:
            raise ValueError("unknown disposable vault operation")
        if operation == "stage":
            key = str(intent.intent_id)
        else:
            key = f"{operation}-{intent.intent_id}-{expected}"
        params: tuple[object, ...] = (
            str(self.context.actor_id), str(intent.scope.case_id),
            str(intent.intent_id), operation, key, str(intent.intent_id),
            str(self.context.document_version_id) if operation == "stage" else None,
            intent.object_key if operation == "stage" else None,
            intent.sha256_hex if operation in {"stage", "verify"} else None,
            intent.byte_length if operation in {"stage", "verify"} else None,
            intent.media_type if operation == "stage" else None,
            expected, reason,
        )
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(COMMAND_SQL, params)
                rows = cursor.fetchall()
        if len(rows) != 1 or len(rows[0]) != 6:
            raise VaultConflict("unexpected disposable command receipt")
        state, revision, _, audit_id, _, stored_key = rows[0]
        target = {"stage": VaultState.PENDING, "verify": VaultState.VERIFIED,
                  "unavailable": VaultState.UNAVAILABLE}[operation]
        if state != target.value or stored_key != intent.object_key:
            raise VaultConflict("disposable receipt does not match frozen intent")
        if type(revision) is not int or revision < 1:
            raise VaultConflict("invalid disposable receipt revision")
        return VaultRecord(
            intent, target, revision,
            UUID(str(audit_id)) if operation != "stage" else None,
        )

    def create_pending(self, intent: UploadIntent) -> VaultRecord:
        return self._command(intent, "stage")

    def get_scoped(self, scope: VaultScope, intent_id: UUID) -> VaultRecord | None:
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(READ_SQL, (
                    str(scope.org_id), str(scope.case_id), str(intent_id),
                ))
                rows = cursor.fetchall()
        if not rows:
            return None
        if len(rows) != 1 or len(rows[0]) != 10:
            raise VaultConflict("ambiguous or invalid disposable source")
        org, case, identity, key, digest, size, media, state, revision, audit = rows[0]
        if (str(org) != str(scope.org_id) or str(case) != str(scope.case_id)
                or str(identity) != str(intent_id)):
            raise VaultConflict("disposable source scope mismatch")
        if (not isinstance(key, str) or not isinstance(digest, str)
                or type(size) is not int or not isinstance(media, str)
                or not isinstance(state, str) or type(revision) is not int):
            raise VaultConflict("invalid disposable source column types")
        intent = UploadIntent(scope, intent_id, key, digest, size, media)
        status = VaultState(state)
        return VaultRecord(
            intent, status, revision,
            UUID(str(audit)) if status != VaultState.PENDING else None,
        )

    def publish_verified(self, expected: VaultRecord) -> VaultRecord:
        if expected.state != VaultState.PENDING:
            raise VaultConflict("only pending evidence can be verified")
        return self._command(expected.intent, "verify", expected=expected.revision)

    def mark_unavailable(self, expected: VaultRecord, reason_code: str) -> VaultRecord:
        if expected.state != VaultState.VERIFIED:
            raise VaultConflict("only verified evidence can be invalidated")
        if reason_code not in {"missing", "digest_mismatch"}:
            raise ValueError("unsupported availability reason")
        return self._command(
            expected.intent, "unavailable", expected=expected.revision,
            reason=reason_code,
        )
