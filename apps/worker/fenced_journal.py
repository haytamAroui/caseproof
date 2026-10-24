"""The queue fence and extraction checkpoint write share the SAME transaction."""

from typing import Any

from application.extraction.contracts import ExtractionError, Scope
from application.runtime.jobs import Lease
from apps.api.disposable_extraction_journal import DisposablePostgresJournal
from infrastructure.execution.postgres_jobs import DisposableJobQueue


class FencedExtractionJournal(DisposablePostgresJournal):
    def __init__(self, queue: DisposableJobQueue, lease: Lease):
        super().__init__(queue.connect, actor_id=lease.spec.actor_id)
        self.queue, self.lease = queue, lease

    def _authorize(self, conn: Any, scope: Scope) -> None:
        if scope != self.lease.spec.scope:
            raise ExtractionError("worker journal scope mismatch")
        self.queue.guard(conn, self.lease)
        super()._authorize(conn, scope)

    def _keys(self, scope: Scope, run_id: str, step: str) -> tuple[Any, Any, str, str]:  # type: ignore[override]
        if run_id not in {self.lease.spec.run_id, self.lease.spec.run_id + ":extract"}:
            raise ExtractionError("worker checkpoint run mismatch")
        return super()._keys(scope, run_id, step)
