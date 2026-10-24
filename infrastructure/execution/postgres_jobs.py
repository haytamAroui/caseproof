"""Disposable owner-connection queue with DB-time leases and atomic events.

No tenant-facing credentials/roles or production worker service are installed.
"""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from application.extraction.contracts import ExtractionError, Scope, canonical
from application.runtime.jobs import JobResult, JobSpec, JobState, Lease, LeaseLost

_COLUMNS = "spec_json,state,attempt,revision,lease_token,worker_id,result_json,result_sha,reason"


class DisposableJobQueue:
    def __init__(self, connection_factory: Callable[[], Any]):
        self.connect = connection_factory

    @staticmethod
    def _duration(seconds: int) -> None:
        if type(seconds) is not int or not 3 <= seconds <= 300:
            raise ExtractionError("bounded lease duration required")

    @staticmethod
    def _keys(spec: JobSpec) -> tuple[UUID, UUID, UUID]:
        return spec.scope.org_id, spec.scope.case_id, spec.request_id

    @staticmethod
    def _authorize(conn: Any, scope: Scope, actor: UUID) -> tuple[int, str]:
        row = conn.execute(
            "select c.case_revision,c.effective_policy_version from caseproof.cases c "
            "join caseproof.organization_members m on m.org_id=c.org_id where c.org_id=%s and c.id=%s "
            "and m.user_id=%s and m.active and m.actions @> array['case:read','evidence:read','finding:write']::text[] "
            "for share of m,c",
            (scope.org_id, scope.case_id, actor),
        ).fetchone()
        if row is None:
            raise ExtractionError("job access denied")
        return int(row[0]), str(row[1])

    @staticmethod
    def _sources(conn: Any, spec: JobSpec) -> None:
        rows = conn.execute(
            "select v.id from jsonb_array_elements(%s::jsonb) s "
            "join caseproof.document_versions v on v.org_id=%s and v.id=(s->>'version_id')::uuid "
            "and v.document_id=(s->>'document_id')::uuid and v.original_sha256_hex=s->>'sha256' "
            "and v.media_type=s->>'media_type' join caseproof._s2_009b_vault_intents i "
            "on i.org_id=v.org_id and i.document_id=v.document_id and i.document_version_id=v.id "
            "and i.case_id=%s and i.intent_id=(s->>'intent_id')::uuid and i.sha256_hex=v.original_sha256_hex "
            "and i.state='verified' for share of v,i",
            (canonical([s.payload() for s in spec.sources]), spec.scope.org_id, spec.scope.case_id),
        ).fetchall()
        if len(rows) != len(spec.sources):
            raise ExtractionError("job source snapshot unavailable")

    def _current(self, conn: Any, spec: JobSpec) -> None:
        if self._authorize(conn, spec.scope, spec.actor_id) != (spec.case_revision, spec.policy_version):
            raise ExtractionError("job case or policy changed")
        self._sources(conn, spec)

    def _event(
        self,
        conn: Any,
        spec: JobSpec,
        revision: int,
        state: str,
        attempt: int,
        reason: str,
        worker: UUID | None,
    ) -> None:
        conn.execute(
            "insert into caseproof._worker_events(org_id,case_id,request_id,revision,state,attempt,reason,worker_id) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s)",
            (*self._keys(spec), revision, state, attempt, reason, worker),
        )

    def enqueue(self, spec: JobSpec) -> dict[str, Any]:
        with self.connect() as conn:
            self._current(conn, spec)
            inserted = conn.execute(
                "insert into caseproof._worker_jobs(org_id,case_id,request_id,actor_id,input_sha,spec_json) "
                "values(%s,%s,%s,%s,%s,%s) on conflict do nothing returning request_id",
                (*self._keys(spec), spec.actor_id, spec.fingerprint, canonical(spec.payload())),
            ).fetchone()
            row = conn.execute(
                "select input_sha from caseproof._worker_jobs where org_id=%s and case_id=%s and request_id=%s",
                self._keys(spec),
            ).fetchone()
            if row is None or row[0] != spec.fingerprint:
                raise ExtractionError("job request ID reused with different input")
            if inserted:
                self._event(conn, spec, 1, "queued", 0, "submitted", None)
            return self._read(conn, spec.scope, spec.request_id)

    @staticmethod
    def _hazard(conn: Any, spec: JobSpec) -> bool:
        return bool(
            conn.execute(
                "select exists(select 1 from caseproof._ei_steps where org_id=%s and case_id=%s "
                "and run_id in (%s,%s) and state in ('dispatched','outcome_unknown'))",
                (spec.scope.org_id, spec.scope.case_id, spec.run_id, spec.run_id + ":extract"),
            ).fetchone()[0]
        )

    def _terminal(self, conn: Any, row: Any, state: JobState, reason: str) -> None:
        spec = JobSpec.restore(row[0])
        conn.execute(
            "update caseproof._worker_jobs set state=%s,reason=%s,revision=revision+1,lease_token=null,worker_id=null,lease_until=null "
            "where org_id=%s and case_id=%s and request_id=%s",
            (state.value, reason, *self._keys(spec)),
        )
        self._event(conn, spec, row[3] + 1, state.value, row[2], reason, row[5])

    def claim(self, scope: Scope, worker_id: UUID, lease_seconds: int) -> Lease | None:
        self._duration(lease_seconds)
        if not isinstance(worker_id, UUID) or not worker_id.int:
            raise ExtractionError("trusted worker UUID required")
        with self.connect() as conn:
            # Scope is supplied by trusted internal scheduling, never an HTTP tenant header.
            conn.execute(
                "select id from caseproof.cases where org_id=%s and id=%s for share",
                (scope.org_id, scope.case_id),
            )
            row = conn.execute(
                "select " + _COLUMNS + " from caseproof._worker_jobs where org_id=%s and case_id=%s and "
                "((state in ('queued','retry_wait') and available_at<=clock_timestamp()) or "
                "(state='running' and lease_until<=clock_timestamp())) order by created_at,request_id limit 1 for update skip locked",
                (scope.org_id, scope.case_id),
            ).fetchone()
            if row is None:
                return None
            spec = JobSpec.restore(row[0])
            if self._hazard(conn, spec):
                self._terminal(conn, row, JobState.UNKNOWN, "dispatched_step_unresolved")
                return None
            try:
                self._current(conn, spec)
            except ExtractionError:
                self._terminal(conn, row, JobState.BLOCKED, "input_or_access_changed")
                return None
            if row[2] >= spec.max_attempts:
                self._terminal(conn, row, JobState.FAILED, "attempts_exhausted")
                return None
            token = uuid4()
            conn.execute(
                "update caseproof._worker_jobs set state='running',attempt=attempt+1,revision=revision+1,lease_token=%s,worker_id=%s,"
                "lease_until=clock_timestamp()+(%s * interval '1 second'),reason='claimed' where org_id=%s and case_id=%s and request_id=%s",
                (token, worker_id, lease_seconds, *self._keys(spec)),
            )
            self._event(conn, spec, row[3] + 1, "running", row[2] + 1, "claimed", worker_id)
            return Lease(spec, token, row[2] + 1, worker_id)

    def guard(self, conn: Any, lease: Lease) -> Any:
        self._current(conn, lease.spec)
        row = conn.execute(
            "select "
            + _COLUMNS
            + " from caseproof._worker_jobs where org_id=%s and case_id=%s and request_id=%s "
            "and state='running' and lease_token=%s and worker_id=%s and attempt=%s and lease_until>clock_timestamp() for update",
            (*self._keys(lease.spec), lease.token, lease.worker_id, lease.attempt),
        ).fetchone()
        if row is None or JobSpec.restore(row[0]).fingerprint != lease.spec.fingerprint:
            raise LeaseLost("lease expired, cancelled or replaced")
        return row

    def heartbeat(self, lease: Lease, lease_seconds: int) -> None:
        self._duration(lease_seconds)
        with self.connect() as conn:
            row = self.guard(conn, lease)
            conn.execute(
                "update caseproof._worker_jobs set lease_until=clock_timestamp()+(%s*interval '1 second'),revision=revision+1 "
                "where org_id=%s and case_id=%s and request_id=%s",
                (lease_seconds, *self._keys(lease.spec)),
            )
            self._event(conn, lease.spec, row[3] + 1, "running", lease.attempt, "heartbeat", lease.worker_id)

    def finish(self, lease: Lease, result: JobResult) -> dict[str, Any]:
        with self.connect() as conn:
            # A lost commit acknowledgement can recover this immutable outcome without re-executing.
            self._current(conn, lease.spec)
            old = conn.execute(
                "select "
                + _COLUMNS
                + " from caseproof._worker_jobs where org_id=%s and case_id=%s and request_id=%s for update",
                self._keys(lease.spec),
            ).fetchone()
            if (
                old is not None
                and old[1] == result.state.value
                and old[2] == lease.attempt
                and old[6] == result.payload_json
                and old[8] == result.reason
            ):
                return self._read(conn, lease.spec.scope, lease.spec.request_id)
            row = self.guard(conn, lease)
            target, reason = result.state, result.reason
            if self._hazard(conn, lease.spec):
                target, reason = JobState.UNKNOWN, "dispatched_step_unresolved"
            elif target is JobState.RETRY and lease.attempt >= lease.spec.max_attempts:
                target, reason = JobState.FAILED, "attempts_exhausted"
            payload = result.payload_json if target in {JobState.SUCCEEDED, JobState.BLOCKED} else None
            hashed = sha256(payload.encode()).hexdigest() if payload is not None else None
            conn.execute(
                "update caseproof._worker_jobs set state=%s,reason=%s,result_json=%s,result_sha=%s,revision=revision+1,"
                "lease_token=null,worker_id=null,lease_until=null,available_at=clock_timestamp()+(%s*interval '1 second') "
                "where org_id=%s and case_id=%s and request_id=%s",
                (target.value, reason, payload, hashed, min(60, 2**lease.attempt), *self._keys(lease.spec)),
            )
            self._event(conn, lease.spec, row[3] + 1, target.value, lease.attempt, reason, lease.worker_id)
            return self._read(conn, lease.spec.scope, lease.spec.request_id)

    @staticmethod
    def _read(conn: Any, scope: Scope, request_id: UUID) -> dict[str, Any]:
        row = conn.execute(
            "select input_sha,state,attempt,revision,reason,result_json,result_sha,lease_until from caseproof._worker_jobs "
            "where org_id=%s and case_id=%s and request_id=%s",
            (scope.org_id, scope.case_id, request_id),
        ).fetchone()
        if row is None:
            raise ExtractionError("job unavailable")
        if row[5] is not None and sha256(row[5].encode()).hexdigest() != row[6]:
            raise ExtractionError("job result integrity mismatch")
        return {
            "request_id": str(request_id),
            "input_hash": row[0],
            "state": row[1],
            "attempt": row[2],
            "revision": row[3],
            "reason": row[4],
            "result_json": row[5],
            "result_hash": row[6],
            "lease_until": row[7].isoformat() if row[7] else None,
            "approved": False,
        }

    def read(self, scope: Scope, request_id: UUID, actor_id: UUID) -> dict[str, Any]:
        with self.connect() as conn:
            self._authorize(conn, scope, actor_id)
            state = self._read(conn, scope, request_id)
            row = conn.execute(
                "select spec_json from caseproof._worker_jobs where org_id=%s and case_id=%s and request_id=%s",
                (scope.org_id, scope.case_id, request_id),
            ).fetchone()
            try:
                self._current(conn, JobSpec.restore(row[0]))
                state["input_current"] = True
            except ExtractionError:
                # Execution history stays visible; stale candidate content is not returned as current.
                state["input_current"] = False
                state["result_json"] = None
            return state

    def cancel(self, scope: Scope, request_id: UUID, actor_id: UUID) -> dict[str, Any]:
        with self.connect() as conn:
            self._authorize(conn, scope, actor_id)
            row = conn.execute(
                "select "
                + _COLUMNS
                + " from caseproof._worker_jobs where org_id=%s and case_id=%s and request_id=%s for update",
                (scope.org_id, scope.case_id, request_id),
            ).fetchone()
            if row is None or JobSpec.restore(row[0]).actor_id != actor_id:
                raise ExtractionError("only the submitting actor may cancel this job")
            if row[1] in {"queued", "running", "retry_wait"}:
                unknown = self._hazard(conn, JobSpec.restore(row[0]))
                self._terminal(
                    conn,
                    row,
                    JobState.UNKNOWN if unknown else JobState.CANCELLED,
                    "cancel_dispatch_unknown" if unknown else "cancelled_by_submitter",
                )
            return self._read(conn, scope, request_id)
