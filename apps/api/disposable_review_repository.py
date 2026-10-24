"""Atomic disposable review recommendations. Synthetic actor, not production Auth."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from application.extraction.contracts import ExtractionError, Scope, canonical, decode, digest
from application.review.contracts import (
    ZERO_HASH,
    ReviewCommand,
    ReviewConflict,
    ReviewSnapshot,
    event_digest,
    validate_command,
)


class DisposableReviewRepository:
    persistence = "disposable_postgres"

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connect = connection_factory

    @staticmethod
    def _authorize(conn: Any, scope: Scope, actor: UUID) -> tuple[int, str]:
        row = conn.execute(
            "select c.case_revision,c.effective_policy_version from caseproof.cases c "
            "join caseproof.organization_members m on m.org_id=c.org_id "
            "where c.org_id=%s and c.id=%s and m.user_id=%s and m.active "
            "and m.actions @> array['case:read','evidence:read','coverage:read','review:request']::text[] "
            "for share of m for update of c",
            (scope.org_id, scope.case_id, actor),
        ).fetchone()
        if row is None:
            raise ExtractionError("review access denied")
        return int(row[0]), str(row[1])

    @staticmethod
    def _guard(conn: Any, snapshot: ReviewSnapshot, case: tuple[int, str]) -> None:
        data = snapshot.data
        if (data["case_revision"], data["policy_version"]) != case:
            raise ReviewConflict("case_or_policy_changed")
        sources = data["sources"]
        if not sources or len(sources) > 32:
            raise ExtractionError("bounded original source manifest required")
        for source in sources:
            for name in ("document_id", "version_id", "intent_id"):
                try:
                    UUID(source[name])
                except (ValueError, TypeError):
                    raise ExtractionError("disposable physical source binding required") from None
        count = conn.execute(
            "select count(*) from jsonb_array_elements(%s::jsonb) s "
            "join caseproof.document_versions v on v.id=(s->>'version_id')::uuid "
            "and v.document_id=(s->>'document_id')::uuid and v.org_id=%s "
            "and v.original_sha256_hex=s->>'sha256' and v.media_type=s->>'media_type' "
            "join caseproof._s2_009b_vault_intents i on i.org_id=v.org_id "
            "and i.document_version_id=v.id and i.document_id=v.document_id "
            "and i.case_id=%s and i.intent_id=(s->>'intent_id')::uuid "
            "and i.sha256_hex=v.original_sha256_hex and i.state='verified'",
            (canonical(sources), snapshot.scope.org_id, snapshot.scope.case_id),
        ).fetchone()[0]
        if count != len(sources):
            raise ReviewConflict("source_snapshot_unavailable")

    def publish(self, snapshot: ReviewSnapshot, actor: UUID) -> None:
        with self._connect() as conn:
            case = self._authorize(conn, snapshot.scope, actor)
            self._guard(conn, snapshot, case)
            keys = (snapshot.scope.org_id, snapshot.scope.case_id, snapshot.snapshot_hash)
            conn.execute(
                "insert into caseproof._review_snapshots(org_id,case_id,snapshot_sha,payload,created_by) "
                "values(%s,%s,%s,%s,%s) on conflict do nothing",
                (*keys, snapshot.payload_json, actor),
            )
            row = conn.execute(
                "select payload from caseproof._review_snapshots where org_id=%s and case_id=%s "
                "and snapshot_sha=%s",
                keys,
            ).fetchone()
            if row[0] != snapshot.payload_json:
                raise ReviewConflict("immutable_snapshot_conflict")
            conn.execute(
                "insert into caseproof._review_heads(org_id,case_id,snapshot_sha,audit_sha) values(%s,%s,%s,%s) "
                "on conflict(org_id,case_id) do update set snapshot_sha=excluded.snapshot_sha",
                (*keys, ZERO_HASH),
            )

    @staticmethod
    def _read(conn: Any, scope: Scope) -> tuple[ReviewSnapshot, int, str]:
        row = conn.execute(
            "select s.snapshot_sha,s.payload,h.revision,h.audit_sha "
            "from caseproof._review_heads h join caseproof._review_snapshots s "
            "on s.org_id=h.org_id and s.case_id=h.case_id and s.snapshot_sha=h.snapshot_sha "
            "where h.org_id=%s and h.case_id=%s for update of h",
            (scope.org_id, scope.case_id),
        ).fetchone()
        if row is None:
            raise ExtractionError("review case unavailable")
        return ReviewSnapshot(scope, row[0], row[1]), int(row[2]), row[3]

    def state(self, scope: Scope, actor: UUID) -> dict[str, Any]:
        with self._connect() as conn:
            case = self._authorize(conn, scope, actor)
            snapshot, revision, audit_hash = self._read(conn, scope)
            self._guard(conn, snapshot, case)
            rows = conn.execute(
                "select event_json from caseproof._review_events "
                "where org_id=%s and case_id=%s order by revision limit 1001",
                (scope.org_id, scope.case_id),
            ).fetchall()
            if len(rows) > 1000:
                raise ExtractionError("review history exceeds export limit")
        return {
            "snapshot_hash": snapshot.snapshot_hash,
            "snapshot": snapshot.data,
            "revision": revision,
            "audit_head": audit_hash,
            "events": [decode(row[0]) for row in rows],
            "approved": False,
            "persistence": self.persistence,
        }

    def _append_event(self, conn: Any, scope: Scope, actor: UUID, event: dict[str, Any]) -> None:
        command = event["command"]
        conn.execute(
            "insert into caseproof._review_events(org_id,case_id,revision,snapshot_sha,actor_id,request_id,event_json,audit_sha) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                scope.org_id,
                scope.case_id,
                event["revision"],
                command["snapshot_hash"],
                actor,
                UUID(command["request_id"]),
                canonical(event),
                event["audit_hash"],
            ),
        )

    def record(self, scope: Scope, actor: UUID, command: ReviewCommand) -> dict[str, Any]:
        fingerprint = digest({"actor": str(actor), "scope": scope.namespace, "command": command.payload()})
        keys = (scope.org_id, scope.case_id, command.request_id)
        with self._connect() as conn:
            case = self._authorize(conn, scope, actor)
            snapshot, revision, previous_hash = self._read(conn, scope)
            self._guard(conn, snapshot, case)
            old = conn.execute(
                "select input_sha,receipt_json from caseproof._review_receipts "
                "where org_id=%s and case_id=%s and request_id=%s",
                keys,
            ).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise ReviewConflict("request_id_reused_with_different_input")
                return {**decode(old[1]), "replayed": True}
            validate_command(snapshot, command)
            if command.expected_revision != revision:
                raise ReviewConflict("review_revision_changed")
            if revision >= 1000:
                raise ExtractionError("review history limit")
            event = {
                "schema": "review-event-v1",
                "scope": scope.namespace,
                "revision": revision + 1,
                "actor_id": str(actor),
                "command": command.payload(),
                "recorded_at": datetime.now(UTC).isoformat(),
                "previous_hash": previous_hash,
                "authority": "recommendation_only",
            }
            event["audit_hash"] = event_digest(event)
            receipt = {
                "request_id": str(command.request_id),
                "snapshot_hash": command.snapshot_hash,
                "revision": revision + 1,
                "audit_hash": event["audit_hash"],
                "approved": False,
                "replayed": False,
            }
            self._append_event(conn, scope, actor, event)
            conn.execute(
                "update caseproof._review_heads set revision=%s,audit_sha=%s where org_id=%s and case_id=%s",
                (revision + 1, event["audit_hash"], scope.org_id, scope.case_id),
            )
            conn.execute(
                "insert into caseproof._review_receipts(org_id,case_id,request_id,input_sha,revision,receipt_json) "
                "values(%s,%s,%s,%s,%s,%s)",
                (*keys, fingerprint, revision + 1, canonical(receipt)),
            )
        return receipt
