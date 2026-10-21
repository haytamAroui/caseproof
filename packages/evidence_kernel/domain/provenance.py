"""Sector-neutral, deterministic, append-only provenance events.

Reference in-memory implementation only. No durable audit guarantee.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from threading import RLock
from typing import Any


class ProvenanceConflict(ValueError):
    """Duplicate identifier or invalid append."""


class ProvenanceIntegrityError(ValueError):
    """A recorded event has been modified or reordered."""


def _canonical(value: Mapping[str, Any]) -> str:
    return dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True, slots=True)
class ProvenanceEvent:
    tenant_id: str
    sequence: int
    event_id: str
    kind: str
    subject_id: str
    actor_id: str
    occurred_at: str
    payload_json: str
    previous_hash: str
    event_hash: str

    def canonical_body(self) -> str:
        return _canonical({
            "tenant_id": self.tenant_id, "sequence": self.sequence,
            "event_id": self.event_id, "kind": self.kind,
            "subject_id": self.subject_id, "actor_id": self.actor_id,
            "occurred_at": self.occurred_at, "payload_json": self.payload_json,
            "previous_hash": self.previous_hash,
        })

    def validate_hash(self) -> bool:
        return sha256(self.canonical_body().encode("utf-8")).hexdigest() == self.event_hash


@dataclass
class InMemoryProvenanceLedger:
    """Per-tenant hash chain. In-memory chains are tamper-evident, not tamper-proof."""

    _events: dict[str, tuple[ProvenanceEvent, ...]] = field(default_factory=dict)
    _ids: set[tuple[str, str]] = field(default_factory=set)
    _lock: RLock = field(default_factory=RLock)

    def append(
        self, tenant_id: str, event_id: str, kind: str, subject_id: str,
        actor_id: str, payload: Mapping[str, Any], *,
        occurred_at: datetime | None = None,
    ) -> ProvenanceEvent:
        if not all(isinstance(v, str) and v.strip() for v in (
            tenant_id, event_id, kind, subject_id, actor_id,
        )):
            raise ValueError("nonempty tenant, event, kind, subject and actor IDs required")
        timestamp = occurred_at or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone aware")
        payload_json = _canonical(payload)
        with self._lock:
            if (tenant_id, event_id) in self._ids:
                raise ProvenanceConflict("duplicate event ID")
            prior = self._events.get(tenant_id, ())
            if prior and not self._verify_events(tenant_id, prior):
                raise ProvenanceIntegrityError("existing chain corrupted")
            event = ProvenanceEvent(
                tenant_id=tenant_id, sequence=len(prior) + 1,
                event_id=event_id, kind=kind, subject_id=subject_id,
                actor_id=actor_id, occurred_at=timestamp.isoformat(),
                payload_json=payload_json,
                previous_hash=prior[-1].event_hash if prior else "0" * 64,
                event_hash="",
            )
            from dataclasses import replace
            event = replace(event, event_hash=sha256(event.canonical_body().encode("utf-8")).hexdigest())
            self._events[tenant_id] = (*prior, event)
            self._ids.add((tenant_id, event_id))
            return event

    @staticmethod
    def _verify_events(tenant_id: str, events: tuple[ProvenanceEvent, ...]) -> bool:
        previous = "0" * 64
        for index, event in enumerate(events, start=1):
            if (event.tenant_id != tenant_id or event.sequence != index
                    or event.previous_hash != previous or not event.validate_hash()):
                return False
            previous = event.event_hash
        return True

    def verify(self, tenant_id: str) -> bool:
        if not tenant_id.strip():
            raise ValueError("tenant ID required")
        with self._lock:
            return self._verify_events(tenant_id, self._events.get(tenant_id, ()))

    def history(self, tenant_id: str, subject_id: str | None = None) -> tuple[ProvenanceEvent, ...]:
        if not tenant_id.strip():
            raise ValueError("tenant ID required")
        with self._lock:
            events = self._events.get(tenant_id, ())
            if not self._verify_events(tenant_id, events):
                raise ProvenanceIntegrityError("chain corrupted")
            return tuple(e for e in events if subject_id is None or e.subject_id == subject_id)
