"""Internal composition of bearer authorization, scoped Vault reads and extraction.

No HTTP route, live DB identity binding or approval is installed. Recheck access
before/after work; this read/proposal operation is not an atomic human decision.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from application.documents.intake import (
    CapturedDocument,
    DocumentIntelligence,
    EntityAssignment,
    IntakeResult,
)
from application.extraction.contracts import ClaimSlot, ExtractionConfig, ExtractionError, Scope
from apps.api.access_control import AuthorizedCase, CaseAccessService, CaseAction
from apps.api.evidence_vault_protocol import VaultCoordinator, VaultScope
from packages.evidence_kernel.domain.source_versions import SourceVersion


@dataclass(frozen=True)
class StoredDocument:
    source_id: str
    original: SourceVersion
    intent_id: UUID


class CaseDocuments(Protocol):
    def list_sources(self, authorized: AuthorizedCase) -> tuple[StoredDocument, ...]: ...


@dataclass(frozen=True)
class AuthenticatedDocumentIntelligence:
    access: CaseAccessService
    catalog: CaseDocuments
    vault_factory: Callable[[AuthorizedCase], VaultCoordinator]
    service_factory: Callable[[AuthorizedCase], DocumentIntelligence]

    def _authorize(self, bearer: str, case_id: str) -> AuthorizedCase:
        contexts = [
            self.access.authorize(bearer, case_id, action)
            for action in (CaseAction.READ_CASE, CaseAction.READ_EVIDENCE, CaseAction.PROPOSE_FINDING)
        ]
        if len({(c.org_id, c.case_id, c.subject_id, c.case_revision) for c in contexts}) != 1:
            raise ExtractionError("authorization snapshot changed")
        return contexts[-1]

    def run(
        self,
        *,
        bearer: str,
        case_id: str,
        run_id: str,
        assignments: tuple[EntityAssignment, ...],
        slots: tuple[ClaimSlot, ...],
        config: ExtractionConfig | None = None,
    ) -> IntakeResult:
        context = self._authorize(bearer, case_id)
        vault = self.vault_factory(context)
        sources = self.catalog.list_sources(context)
        if type(sources) is not tuple or not 1 <= len(sources) <= 32:
            raise ExtractionError("bounded server source catalog required")
        scope = Scope(UUID(context.org_id), UUID(context.case_id))
        vault_scope = VaultScope(scope.org_id, scope.case_id)
        captured = []
        for record in sources:
            raw = vault.read(scope=vault_scope, intent_id=record.intent_id)
            if raw != record.original.content:
                raise ExtractionError("catalog does not match preserved original bytes")
            captured.append(CapturedDocument(record.source_id, record.original))
        result = self.service_factory(context).run(
            scope=scope,
            run_id=run_id,
            documents=tuple(captured),
            assignments=assignments,
            slots=slots,
            config=config,
        )
        # Never return a stale successful projection if source availability/access changed.
        after = self._authorize(bearer, case_id)
        if (after.org_id, after.subject_id, after.case_revision) != (
            context.org_id,
            context.subject_id,
            context.case_revision,
        ):
            raise ExtractionError("case changed during extraction; re-review required")
        if self.catalog.list_sources(after) != sources:
            raise ExtractionError("source inventory changed during extraction")
        for record in sources:
            if vault.read(scope=vault_scope, intent_id=record.intent_id) != record.original.content:
                raise ExtractionError("source changed during extraction")
        return result
