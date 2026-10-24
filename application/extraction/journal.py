"""Reference checkpoint state machine; production authorization belongs to composition."""

from dataclasses import replace
from datetime import UTC, datetime
from threading import RLock

from application.extraction.contracts import ExtractionError, Scope, StepRecord, StepState

ALLOWED = {
    StepState.PREPARED: {StepState.DISPATCHED, StepState.COMPLETED},
    StepState.DISPATCHED: {StepState.RECEIVED, StepState.UNKNOWN, StepState.FAILED},
    StepState.RECEIVED: {StepState.COMPLETED, StepState.FAILED},
}


def check_transition(previous: StepState, target: StepState, payload: str | None) -> None:
    if target not in ALLOWED.get(previous, set()):
        raise ExtractionError("invalid checkpoint transition")
    if target in {StepState.RECEIVED, StepState.COMPLETED} and payload is None:
        raise ExtractionError("durable artifact required")
    if payload is not None and len(payload.encode("utf-8")) > 4 * 1024 * 1024:
        raise ExtractionError("checkpoint artifact limit exceeded")


class MemoryJournal:
    """Tests only: thread-safe CAS, no durability or authenticated access claim."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str], StepRecord] = {}
        self._lock = RLock()

    def reserve(self, scope: Scope, run_id: str, step: str, fingerprint: str) -> StepRecord:
        key = (scope.namespace, run_id, step)
        with self._lock:
            record = self._rows.setdefault(
                key, StepRecord(StepState.PREPARED, fingerprint, datetime.now(UTC).isoformat())
            )
            if record.input_digest != fingerprint:
                raise ExtractionError("immutable checkpoint input changed")
            return record

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
        key = (scope.namespace, run_id, step)
        with self._lock:
            record = self._rows[key]
            if record.state != previous:
                raise ExtractionError("checkpoint CAS conflict")
            record = replace(record, state=target, payload=payload if payload is not None else record.payload)
            self._rows[key] = record
            return record
