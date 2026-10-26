"""Internal worker byte loader. Authorization is rechecked in the queue transaction.

This disposable adapter is composed with a scope-bound catalog/Vault, never a
stored bearer token or user-provided path. Real service delegation remains gated.
"""

from collections.abc import Callable
from dataclasses import dataclass

from application.documents.catalog import StoredDocument
from application.documents.intake import CapturedDocument
from application.extraction.contracts import ExtractionError
from application.runtime.jobs import JobSpec
from apps.api.evidence_vault_protocol import VaultCoordinator, VaultScope
from infrastructure.execution.postgres_jobs import DisposableJobQueue


@dataclass(frozen=True)
class VaultJobDocuments:
    queue: DisposableJobQueue
    catalog: Callable[[JobSpec], tuple[StoredDocument, ...]]
    vault: Callable[[JobSpec], VaultCoordinator]

    def __call__(self, spec: JobSpec) -> tuple[CapturedDocument, ...]:
        with self.queue.connect() as conn:
            self.queue._current(conn, spec)
        records = self.catalog(spec)
        if len(records) != len(spec.sources):
            raise ExtractionError("worker source inventory changed")
        vault = self.vault(spec)
        scope = VaultScope(spec.scope.org_id, spec.scope.case_id)
        captured = []
        for record, ref in zip(records, spec.sources, strict=True):
            if record.intent_id != ref.intent_id or record.source_id != ref.source_id:
                raise ExtractionError("worker intent binding changed")
            raw = vault.read(scope=scope, intent_id=record.intent_id)
            if raw != record.original.content:
                raise ExtractionError("worker Vault bytes changed")
            captured.append(CapturedDocument(record.source_id, record.original))
        return tuple(captured)
