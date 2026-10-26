"""Deterministic M1 in-process transaction fixture, NOT durable production storage.

Testing only. No real sign-in. Demonstrates expected CAS, revision and
idempotency behavior for an independently authorized future PostgreSQL port.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from threading import RLock
from uuid import UUID, uuid4

from application.litigation.exhibit_confirmation import (
    ConfirmedExhibits,
    ExhibitCommit,
    ExhibitConfirmationError,
    ExhibitPrincipal,
    KnownSourceVersion,
)
from domains.disputes.exhibits import ExhibitRegister


@dataclass
class FixtureExhibitStore:
    sources: dict[tuple[UUID, UUID], tuple[KnownSourceVersion, ...]] = field(default_factory=dict)
    allowed_reviewers: set[tuple[UUID, UUID, UUID]] = field(default_factory=set)
    _current: dict[tuple[UUID, UUID], ConfirmedExhibits] = field(default_factory=dict)
    _requests: dict[tuple[UUID, UUID, UUID], tuple[bytes, ConfirmedExhibits]] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def _check(self, principal: ExhibitPrincipal) -> None:
        if (principal.org_id, principal.case_id, principal.subject_id) not in self.allowed_reviewers:
            raise ExhibitConfirmationError("unauthorized or revoked matter reviewer")

    def permitted_versions(self, principal: ExhibitPrincipal) -> tuple[KnownSourceVersion, ...]:
        with self._lock:
            self._check(principal)
            return self.sources.get((principal.org_id, principal.case_id), ())

    def commit(
        self, principal: ExhibitPrincipal, command: ExhibitCommit, payload: bytes,
    ) -> ConfirmedExhibits:
        with self._lock:
            self._check(principal)
            known = {(x.source_id, x.version_id) for x in self.sources.get(
                (principal.org_id, principal.case_id), ()
            )}
            for entry in command.entries:
                if not entry.confirmed or any((p.source_id, p.version_id) not in known for p in entry.pages):
                    raise ExhibitConfirmationError("source/confirmation changed before commit")
            key = (principal.org_id, principal.case_id)
            request = (*key, command.request_id)
            previous = self._requests.get(request)
            if previous is not None:
                if previous[0] != payload:
                    raise ExhibitConfirmationError("request ID replay with different payload")
                return previous[1]
            state = self._current.get(key)
            revision = 0 if state is None else state.register.revision
            if revision != command.expected_revision:
                raise ExhibitConfirmationError("stale register revision")
            result = ConfirmedExhibits(
                ExhibitRegister(revision + 1, command.entries),
                hashlib.sha256(payload).hexdigest(), uuid4(), principal.subject_id,
                command.request_id,
            )
            self._current[key] = result
            self._requests[request] = (payload, result)
            return result

    def current(self, principal: ExhibitPrincipal) -> ConfirmedExhibits | None:
        with self._lock:
            self._check(principal)
            return self._current.get((principal.org_id, principal.case_id))
