"""Thread-safe reference only. Memory is not durable/audited production storage."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import UUID

from application.extraction.contracts import ExtractionError, Scope, digest
from application.review.contracts import (
    ZERO_HASH,
    ReviewCommand,
    ReviewConflict,
    ReviewSnapshot,
    event_digest,
    validate_command,
)


class MemoryReviewRepository:
    persistence = "session_memory"

    def __init__(self) -> None:
        self._heads: dict[str, ReviewSnapshot] = {}
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._receipts: dict[tuple[str, UUID], tuple[str, dict[str, Any]]] = {}
        self._lock = RLock()

    def publish(self, snapshot: ReviewSnapshot, actor: UUID) -> None:
        with self._lock:
            current = self._heads.get(snapshot.scope.namespace)
            if current and current.data["case_revision"] > snapshot.data["case_revision"]:
                raise ReviewConflict("stale_case_revision")
            self._heads[snapshot.scope.namespace] = snapshot
            self._events.setdefault(snapshot.scope.namespace, [])

    def state(self, scope: Scope, actor: UUID) -> dict[str, Any]:
        with self._lock:
            if scope.namespace not in self._heads:
                raise ExtractionError("review case unavailable")
            events = self._events[scope.namespace]
            return {
                "snapshot_hash": self._heads[scope.namespace].snapshot_hash,
                "snapshot": self._heads[scope.namespace].data,
                "revision": len(events),
                "events": [dict(e) for e in events],
                "audit_head": events[-1]["audit_hash"] if events else ZERO_HASH,
                "approved": False,
                "persistence": self.persistence,
            }

    def record(self, scope: Scope, actor: UUID, command: ReviewCommand) -> dict[str, Any]:
        with self._lock:
            state = self.state(scope, actor)
            fingerprint = digest(
                {"actor": str(actor), "scope": scope.namespace, "command": command.payload()}
            )
            key = (scope.namespace, command.request_id)
            previous = self._receipts.get(key)
            if previous:
                if previous[0] != fingerprint:
                    raise ReviewConflict("request_id_reused_with_different_input")
                return {**previous[1], "replayed": True}
            validate_command(self._heads[scope.namespace], command)
            if command.expected_revision != state["revision"]:
                raise ReviewConflict("review_revision_changed")
            if state["revision"] >= 1000:
                raise ExtractionError("review history limit")
            event = {
                "schema": "review-event-v1",
                "scope": scope.namespace,
                "revision": state["revision"] + 1,
                "actor_id": str(actor),
                "command": command.payload(),
                "recorded_at": datetime.now(UTC).isoformat(),
                "previous_hash": state["audit_head"],
                "authority": "recommendation_only",
            }
            event["audit_hash"] = event_digest(event)
            receipt = {
                "request_id": str(command.request_id),
                "snapshot_hash": command.snapshot_hash,
                "revision": event["revision"],
                "audit_hash": event["audit_hash"],
                "approved": False,
                "replayed": False,
            }
            self._events[scope.namespace].append(event)
            self._receipts[key] = (fingerprint, receipt)
            return receipt
