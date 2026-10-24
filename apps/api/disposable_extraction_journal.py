"""Disposable owner-connection proof only, never production Auth/DB binding."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from application.extraction.contracts import ExtractionError, Scope, StepRecord, StepState, text
from application.extraction.journal import check_transition


class DisposablePostgresJournal:
    def __init__(self, connection_factory: Callable[[], Any], *, actor_id: UUID) -> None:
        if not isinstance(actor_id, UUID) or not actor_id.int:
            raise ExtractionError("synthetic actor required")
        self._connect, self._actor = connection_factory, actor_id

    def _authorize(self, conn: Any, scope: Scope) -> None:
        row = conn.execute(
            "select m.user_id from caseproof.organization_members m "
            "join caseproof.cases c on c.org_id=m.org_id "
            "where m.org_id=%s and m.user_id=%s and c.id=%s and m.active "
            "and m.actions @> array['case:read','finding:write']::text[] for share of m,c",
            (scope.org_id, self._actor, scope.case_id),
        ).fetchone()
        if row is None:
            raise ExtractionError("disposable actor not authorized for scope")

    @staticmethod
    def _keys(scope: Scope, run_id: str, step: str) -> tuple[UUID, UUID, str, str]:
        text(run_id, limit=128)
        text(step, limit=256)
        return scope.org_id, scope.case_id, run_id, step

    def _event(
        self,
        conn: Any,
        keys: tuple[UUID, UUID, str, str],
        revision: int,
        state: StepState,
        payload: str | None,
    ) -> None:
        conn.execute(
            "insert into caseproof._ei_events "
            "(org_id,case_id,run_id,step_id,revision,state,payload_sha,actor_id) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *keys,
                revision,
                state.value,
                sha256(payload.encode()).hexdigest() if payload is not None else None,
                self._actor,
            ),
        )

    def reserve(self, scope: Scope, run_id: str, step: str, fingerprint: str) -> StepRecord:
        keys = self._keys(scope, run_id, step)
        with self._connect() as conn:
            self._authorize(conn, scope)
            inserted = conn.execute(
                "insert into caseproof._ei_steps(org_id,case_id,run_id,step_id,actor_id,input_sha,state) "
                "values(%s,%s,%s,%s,%s,%s,'prepared') on conflict do nothing returning revision",
                (*keys, self._actor, fingerprint),
            ).fetchone()
            row = conn.execute(
                "select state,input_sha,created_at,payload from caseproof._ei_steps "
                "where org_id=%s and case_id=%s and run_id=%s and step_id=%s",
                keys,
            ).fetchone()
            if not row or row[1] != fingerprint:
                raise ExtractionError("immutable checkpoint input changed")
            if inserted:
                self._event(conn, keys, 1, StepState.PREPARED, None)
        return self._record(row)

    def transition(
        self,
        scope: Scope,
        run_id: str,
        step: str,
        previous: StepState,
        target: StepState,
        payload: str | None = None,
    ) -> StepRecord:
        check_transition(previous, target, payload)
        keys = self._keys(scope, run_id, step)
        with self._connect() as conn:
            self._authorize(conn, scope)
            row = conn.execute(
                "update caseproof._ei_steps set state=%s,payload=coalesce(%s,payload),revision=revision+1 "
                "where org_id=%s and case_id=%s and run_id=%s and step_id=%s and state=%s "
                "returning state,input_sha,created_at,payload,revision",
                (target.value, payload, *keys, previous.value),
            ).fetchone()
            if not row:
                raise ExtractionError("checkpoint CAS conflict")
            self._event(conn, keys, row[4], target, row[3])
        return self._record(row)

    @staticmethod
    def _record(row: Any) -> StepRecord:
        if not isinstance(row[2], datetime):
            raise ExtractionError("invalid persisted timestamp")
        return StepRecord(StepState(row[0]), str(row[1]), row[2].isoformat(), row[3])
