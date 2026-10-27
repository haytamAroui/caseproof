"""PIV-02/03 internal authenticated evidence-library read composition only.

No HTTP routes, grants, production storage, uploads or immutable DB writes.
Authorizes against EXISTING CaseAccessService, reads exact Vault bytes,
and rechecks current access, inventory and bytes before returning anything.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from application.documents.catalog import StoredDocument
from application.documents.intake import CapturedDocument
from application.extraction.contracts import ExtractionError
from application.litigation.library import EvidenceIndexer, EvidenceInventory, EvidencePreview
from apps.api.access_control import (
    AccessFailure,
    AccessRejected,
    AuthorizedCase,
    CaseAccessService,
    CaseAction,
)
from apps.api.evidence_vault_protocol import VaultCoordinator, VaultScope


class EvidenceCatalog(Protocol):
    def list_sources(self, authorized: AuthorizedCase) -> tuple[StoredDocument, ...]: ...


@dataclass(frozen=True)
class AuthenticatedEvidenceLibrary:
    access: CaseAccessService
    catalog: EvidenceCatalog
    vault_factory: Callable[[AuthorizedCase], VaultCoordinator]
    indexer: EvidenceIndexer

    def _authorize(self, bearer: str, case_id: str) -> AuthorizedCase:
        read = self.access.authorize(bearer, case_id, CaseAction.READ_CASE)
        evidence = self.access.authorize(bearer, case_id, CaseAction.READ_EVIDENCE)
        if (read.org_id, read.case_id, read.subject_id, read.case_revision) != (
            evidence.org_id, evidence.case_id, evidence.subject_id, evidence.case_revision
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return evidence

    def _capture(
        self, context: AuthorizedCase, vault: VaultCoordinator,
    ) -> tuple[tuple[StoredDocument, ...], tuple[CapturedDocument, ...]]:
        records = self.catalog.list_sources(context)
        if type(records) is not tuple or len(records) > 32:
            raise ExtractionError("bounded server-owned source inventory required")
        scope = VaultScope(UUID(context.org_id), UUID(context.case_id))
        documents = []
        seen = set()
        for record in records:
            if not isinstance(record, StoredDocument) or record.source_id in seen:
                raise ExtractionError("invalid trusted source catalog")
            seen.add(record.source_id)
            raw = vault.read(scope=scope, intent_id=record.intent_id)
            if raw != record.original.content:
                raise ExtractionError("verified immutable source mismatch")
            documents.append(CapturedDocument(record.source_id, record.original))
        return records, tuple(documents)

    def _stable(
        self,
        bearer: str,
        case_id: str,
        before: AuthorizedCase,
        records: tuple[StoredDocument, ...],
        documents: tuple[CapturedDocument, ...],
        vault: VaultCoordinator,
    ) -> None:
        after = self._authorize(bearer, case_id)
        if (after.org_id, after.case_id, after.subject_id, after.case_revision) != (
            before.org_id, before.case_id, before.subject_id, before.case_revision
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if self.catalog.list_sources(after) != records:
            raise ExtractionError("source inventory changed during processing")
        scope = VaultScope(UUID(after.org_id), UUID(after.case_id))
        for record, document in zip(records, documents, strict=True):
            if vault.read(scope=scope, intent_id=record.intent_id) != document.source.content:
                raise ExtractionError("source changed during processing")

    def inventory(self, *, bearer: str, case_id: str) -> EvidenceInventory:
        context = self._authorize(bearer, case_id)
        vault = self.vault_factory(context)
        records, documents = self._capture(context, vault)
        result = self.indexer.inventory(documents)
        self._stable(bearer, case_id, context, records, documents, vault)
        return result

    def preview(self, *, bearer: str, case_id: str, source_id: str) -> EvidencePreview:
        context = self._authorize(bearer, case_id)
        vault = self.vault_factory(context)
        records, documents = self._capture(context, vault)
        selected = [doc for doc in documents if doc.source_id == source_id]
        if len(selected) != 1:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        result = self.indexer.preview(selected[0])
        self._stable(bearer, case_id, context, records, documents, vault)
        return result
