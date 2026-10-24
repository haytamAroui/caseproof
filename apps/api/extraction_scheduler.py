"""Internal bearer-to-job composition. No mounted HTTP route or approval action."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from application.documents.intake import EntityAssignment
from application.extraction.contracts import ClaimSlot, ExtractionConfig, ExtractionError, Scope, canonical
from application.runtime.jobs import JobQueue, JobSpec, SourceRef
from apps.api.access_control import AuthorizedCase, CaseAccessService, CaseAction
from apps.api.authenticated_document_intelligence import CaseDocuments


@dataclass(frozen=True)
class AuthenticatedExtractionScheduler:
    access: CaseAccessService
    catalog: CaseDocuments
    queue: JobQueue
    policy_version: Callable[[AuthorizedCase], str]
    engine_versions: Callable[[], dict[str, str]]

    def _context(self, bearer: str, case_id: str) -> AuthorizedCase:
        contexts = [
            self.access.authorize(bearer, case_id, action)
            for action in (CaseAction.READ_CASE, CaseAction.READ_EVIDENCE, CaseAction.PROPOSE_FINDING)
        ]
        if len({(c.org_id, c.case_id, c.subject_id, c.case_revision) for c in contexts}) != 1:
            raise ExtractionError("job authorization snapshot changed")
        return contexts[-1]

    def submit(
        self,
        *,
        bearer: str,
        case_id: str,
        request_id: UUID,
        assignments: tuple[EntityAssignment, ...],
        slots: tuple[ClaimSlot, ...],
        config: ExtractionConfig | None = None,
    ) -> dict[str, Any]:
        c = self._context(bearer, case_id)
        records = self.catalog.list_sources(c)
        refs = tuple(
            SourceRef(
                r.source_id,
                UUID(r.original.document_id),
                UUID(r.original.version_id),
                r.intent_id,
                r.original.sha256_hex,
                r.original.media_type,
            )
            for r in records
        )
        plan = canonical(
            {
                "assignments": [asdict(a) for a in assignments],
                "slots": [asdict(s) for s in slots],
                "config": asdict(config or ExtractionConfig()),
                "engine": self.engine_versions(),
            }
        )
        spec = JobSpec(
            Scope(UUID(c.org_id), UUID(c.case_id)),
            request_id,
            UUID(c.subject_id),
            c.case_revision,
            self.policy_version(c),
            refs,
            plan,
        )
        # Queue transaction independently checks membership/revision/policy and actual Vault metadata.
        return self.queue.enqueue(spec)

    def status(self, *, bearer: str, case_id: str, request_id: UUID) -> dict[str, Any]:
        c = self._context(bearer, case_id)
        return self.queue.read(Scope(UUID(c.org_id), UUID(c.case_id)), request_id, UUID(c.subject_id))

    def cancel(self, *, bearer: str, case_id: str, request_id: UUID) -> dict[str, Any]:
        c = self._context(bearer, case_id)
        return self.queue.cancel(Scope(UUID(c.org_id), UUID(c.case_id)), request_id, UUID(c.subject_id))
