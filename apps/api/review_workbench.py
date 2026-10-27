"""Server-side review facade. Auth/source loading are injected, no production route."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from application.documents.contracts import ParsedDocument
from application.dossiers.pack import build_pack
from application.extraction.analysis import confirmed_boundaries_from_audit
from application.extraction.contracts import ExtractionError, ExtractionRequest, Scope
from application.review.contracts import ReviewCommand, ReviewRepository, ReviewSnapshot
from apps.api.access_control import AuthorizedCase, CaseAccessService, CaseAction


@dataclass(frozen=True)
class ReviewMaterial:
    snapshot: ReviewSnapshot
    documents: tuple[ParsedDocument, ...]


@dataclass(frozen=True)
class AuthenticatedReviewWorkbench:
    access: CaseAccessService
    load_current: Callable[[AuthorizedCase], ReviewMaterial]
    repository: ReviewRepository

    def _current(self, bearer: str, case_id: str) -> tuple[AuthorizedCase, ReviewMaterial]:
        contexts = [
            self.access.authorize(bearer, case_id, action)
            for action in (
                CaseAction.READ_CASE,
                CaseAction.READ_EVIDENCE,
                CaseAction.READ_COVERAGE,
                CaseAction.PROPOSE_REVIEW,
            )
        ]
        context = contexts[-1]
        if len({(c.case_id, c.org_id, c.subject_id, c.case_revision) for c in contexts}) != 1:
            raise ExtractionError("authorization snapshot changed")
        material = self.load_current(context)
        if (
            material.snapshot.scope != Scope(UUID(context.org_id), UUID(context.case_id))
            or material.snapshot.data["case_revision"] != context.case_revision
        ):
            raise ExtractionError("source snapshot changed")
        return context, material

    def view(self, *, bearer: str, case_id: str) -> dict[str, Any]:
        context, material = self._current(bearer, case_id)
        actor = UUID(context.subject_id)
        self.repository.publish(material.snapshot, actor)
        state = self.repository.state(material.snapshot.scope, actor)
        state["source_text"] = {p.evidence.source_id: p.evidence.content for p in material.documents}
        return state

    def record(self, *, bearer: str, case_id: str, command: ReviewCommand) -> dict[str, Any]:
        context, material = self._current(bearer, case_id)
        actor = UUID(context.subject_id)
        self.repository.publish(material.snapshot, actor)
        return self.repository.record(material.snapshot.scope, actor, command)

    def reviewed_scope(
        self, *, bearer: str, case_id: str, request: ExtractionRequest
    ) -> ExtractionRequest:
        """New-run entity scope derived exclusively from audited, authenticated review."""

        context, material = self._current(bearer, case_id)
        scope = Scope(UUID(context.org_id), UUID(context.case_id))
        if request.scope != scope:
            raise ExtractionError("requested extraction case differs from authenticated case")
        actor = UUID(context.subject_id)
        self.repository.publish(material.snapshot, actor)
        state = self.repository.state(scope, actor)
        evidence = material.snapshot.data["extraction"]["discoveries"]
        reviewed_hashes = {
            e["audit_hash"]
            for e in state["events"]
            if e.get("actor_id") and e.get("command", {}).get("kind") in {"confirm_boundary", "reject_boundary"}
        }
        return confirmed_boundaries_from_audit(
            request,
            tuple(evidence),
            state,
            authorize=lambda _scope, ref: _scope == scope and ref in reviewed_hashes,
        )

    def export(self, *, bearer: str, case_id: str) -> tuple[bytes, str]:
        context, material = self._current(bearer, case_id)
        actor = UUID(context.subject_id)
        self.repository.publish(material.snapshot, actor)
        state = self.repository.state(material.snapshot.scope, actor)
        # Source loader performs fresh availability/byte checks; no cached boolean authorizes export.
        after_context, after = self._current(bearer, case_id)
        if after.snapshot != material.snapshot or after_context.case_revision != context.case_revision:
            raise ExtractionError("source snapshot changed during export")
        return build_pack(material.snapshot, material.documents, state)
