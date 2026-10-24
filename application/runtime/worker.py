"""One bounded job, heartbeat and safe outcome handling. No provider selection."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event, Thread
from typing import Any
from uuid import UUID

from application.extraction.contracts import ExtractionError, OutcomeUnknown, Scope
from application.runtime.jobs import JobQueue, JobResult, JobState, Lease, LeaseLost, RetryLater


class ExtractionWorker:
    def __init__(self, queue: JobQueue, execute: Callable[[Lease], JobResult], *, lease_seconds: int = 180):
        if type(lease_seconds) is not int or not 3 <= lease_seconds <= 300:
            raise ExtractionError("bounded lease duration required")
        self.queue, self.execute, self.lease_seconds = queue, execute, lease_seconds

    def run_once(self, scope: Scope, worker_id: UUID) -> dict[str, Any] | None:
        lease = self.queue.claim(scope, worker_id, self.lease_seconds)
        if lease is None:
            return None
        stop, lost = Event(), Event()

        def renew() -> None:
            while not stop.wait(self.lease_seconds / 3):
                try:
                    self.queue.heartbeat(lease, self.lease_seconds)
                except Exception:
                    # No raw exception is logged. Journal fences also recheck before every call/write.
                    lost.set()
                    return

        thread = Thread(target=renew, name="extraction-lease", daemon=True)
        thread.start()
        try:
            try:
                result = self.execute(lease)
            except LeaseLost:
                raise
            except OutcomeUnknown:
                result = JobResult(JobState.UNKNOWN, "provider_outcome_unknown")
            except RetryLater:
                result = JobResult(JobState.RETRY, "preflight_retry")
            except ExtractionError:
                result = JobResult(JobState.BLOCKED, "job_rejected")
            except Exception:
                # The operation may have committed. Stable job ID + durable checkpoints govern recovery.
                result = JobResult(JobState.UNKNOWN, "execution_unknown")
            if lost.is_set():
                raise LeaseLost("heartbeat outcome uncertain; reconcile durable job")
            return self.queue.finish(lease, result)
        finally:
            stop.set()
            thread.join(timeout=5)
