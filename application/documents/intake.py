"""Replayable normalization-to-extraction integration, with caller-authorized source inputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from application.documents.contracts import DocumentParser, ParsedDocument, restore
from application.extraction.contracts import (
    ClaimSlot,
    EntityScope,
    ExtractionConfig,
    ExtractionError,
    ExtractionProvider,
    ExtractionRequest,
    Scope,
    StepJournal,
    StepState,
    Vocabulary,
    canonical,
    decode,
    digest,
    text,
)
from application.extraction.pipeline import EvidenceIntelligence, ExtractionReport
from packages.evidence_kernel.domain.source_versions import SourceVersion


@dataclass(frozen=True)
class CapturedDocument:
    source_id: str
    source: SourceVersion

    def __post_init__(self) -> None:
        text(self.source_id, limit=128)
        if not isinstance(self.source, SourceVersion):
            raise ExtractionError("captured immutable source required")


@dataclass(frozen=True)
class EntityAssignment:
    """Independently supplied investigation scope, never an LLM confirmation."""

    entity_id: str
    kind: str
    source_id: str
    block_ids: tuple[str, ...] = ()  # Empty means all individually bounded blocks.
    confirmed: bool = False

    def __post_init__(self) -> None:
        for value in (self.entity_id, self.kind, self.source_id):
            text(value, limit=128)
        if (
            type(self.confirmed) is not bool
            or type(self.block_ids) is not tuple
            or len(set(self.block_ids)) != len(self.block_ids)
        ):
            raise ExtractionError("typed immutable entity assignment required")


@dataclass(frozen=True)
class IntakeResult:
    status: str
    documents: tuple[ParsedDocument, ...] = field(repr=False)
    failures: tuple[dict[str, str], ...]
    extraction: ExtractionReport | None = field(default=None, repr=False)
    approved: bool = field(default=False, init=False)


class DocumentIntelligence:
    def __init__(
        self, parser: DocumentParser, provider: ExtractionProvider, journal: StepJournal, policy: Vocabulary
    ) -> None:
        self.parser, self.provider, self.journal, self.policy = parser, provider, journal, policy

    def _normalize(self, scope: Scope, run_id: str, document: CapturedDocument) -> ParsedDocument:
        source = document.source
        fingerprint = digest(
            {
                "source_id": document.source_id,
                "document": source.document_id,
                "version": source.version_id,
                "sha": source.sha256_hex,
                "media": source.media_type,
                "ingested_at": source.ingested_at.isoformat(),
                "parser": self.parser.identity,
            }
        )
        step = "normalize:" + digest({"id": document.source_id})
        row = self.journal.reserve(scope, run_id, step, fingerprint)
        if row.state is StepState.PREPARED:
            try:
                artifact = self.parser.parse(source)
                parsed = restore(document.source_id, source, artifact, datetime.fromisoformat(row.created_at))
                payload = canonical(
                    {
                        "checkpoint_schema": "normalization-v1",
                        "state": "parsed",
                        "artifact": parsed.artifact(),
                    }
                )
            except ExtractionError:
                payload = canonical(
                    {"checkpoint_schema": "normalization-v1", "state": "failed", "reason": "parser_rejected"}
                )
            # Pure parsing may race. Only one identical artifact/failure may commit.
            try:
                row = self.journal.transition(
                    scope, run_id, step, StepState.PREPARED, StepState.COMPLETED, payload
                )
            except ExtractionError:
                row = self.journal.reserve(scope, run_id, step, fingerprint)
                if row.state is not StepState.COMPLETED or row.payload != payload:
                    raise
        if row.state is not StepState.COMPLETED or row.payload is None:
            raise ExtractionError("normalization_checkpoint_unavailable")
        saved = decode(row.payload)
        if saved.get("checkpoint_schema") != "normalization-v1":
            raise ExtractionError("unsupported normalization checkpoint")
        if saved.get("state") == "failed":
            raise ExtractionError("persisted_normalization_failure")
        if set(saved) != {"checkpoint_schema", "state", "artifact"} or saved["state"] != "parsed":
            raise ExtractionError("invalid normalization checkpoint")
        return restore(document.source_id, source, saved["artifact"], datetime.fromisoformat(row.created_at))

    def run(
        self,
        *,
        scope: Scope,
        run_id: str,
        documents: tuple[CapturedDocument, ...],
        assignments: tuple[EntityAssignment, ...],
        slots: tuple[ClaimSlot, ...],
        config: ExtractionConfig | None = None,
    ) -> IntakeResult:
        config = config or ExtractionConfig()
        text(run_id, limit=100)
        if type(documents) is not tuple or not 1 <= len(documents) <= 32:
            raise ExtractionError("bounded immutable source inventory required")
        ids = {d.source_id for d in documents}
        if len(ids) != len(documents) or len(
            {(d.source.document_id, d.source.version_id) for d in documents}
        ) != len(documents):
            raise ExtractionError("duplicate original evidence identity")
        if type(assignments) is not tuple or not assignments or len(assignments) > 128:
            raise ExtractionError("bounded immutable independent entity assignments required")
        if any(e.source_id not in ids for e in assignments) or {e.source_id for e in assignments} != ids:
            raise ExtractionError("entity source inventory mismatch")
        if type(slots) is not tuple or not slots or {s for slot in slots for s in slot.source_ids} != ids:
            raise ExtractionError("claim source inventory mismatch")
        if sum(len(d.source.content) for d in documents) > 20 * 1024 * 1024:
            raise ExtractionError("case byte budget exceeded")
        # Reserve the whole intake before any parse/call. No stale partial inputs may be reused.
        manifest: dict[str, Any] = {
            "parser": self.parser.identity,
            "scope": scope.namespace,
            "documents": [
                {
                    "id": d.source_id,
                    "document": d.source.document_id,
                    "version": d.source.version_id,
                    "sha": d.source.sha256_hex,
                    "media": d.source.media_type,
                    "ingested_at": d.source.ingested_at.isoformat(),
                }
                for d in documents
            ],
            "assignments": [asdict(a) for a in assignments],
            "slots": [asdict(s) for s in slots],
            "config": asdict(config),
            "provider": self.provider.identity,
            "model": self.provider.model,
            "vocabulary": self.policy.namespace,
            "validator": self.policy.version,
        }
        self.journal.reserve(scope, run_id, "intake", digest(manifest))
        parsed, failures = [], []
        for document in documents:
            try:
                result = self._normalize(scope, run_id, document)
                parsed.append(result)
                if not result.evidence.complete:
                    failures.append({"source_id": document.source_id, "reason": "normalization_incomplete"})
            except ExtractionError:
                failures.append({"source_id": document.source_id, "reason": "normalization_failed"})
        if failures:
            return IntakeResult("blocked", tuple(parsed), tuple(failures))
        boundaries = []
        for assignment in assignments:
            result = next(p for p in parsed if p.evidence.source_id == assignment.source_id)
            selected = set(assignment.block_ids) or {b.block_id for b in result.blocks}
            if selected - {b.block_id for b in result.blocks}:
                raise ExtractionError("entity block unavailable")
            for block in result.blocks:
                if block.block_id in selected:
                    boundaries.append(
                        EntityScope(
                            assignment.entity_id,
                            assignment.kind,
                            assignment.source_id,
                            block.start,
                            block.end,
                            assignment.confirmed,
                        )
                    )
        request = ExtractionRequest(
            scope, run_id + ":extract", tuple(p.evidence for p in parsed), tuple(boundaries), slots, config
        )
        extraction = EvidenceIntelligence(self.provider, self.journal, self.policy).run(request)
        return IntakeResult(
            "review_required" if extraction.extraction_complete else "blocked",
            tuple(parsed),
            extraction.failures,
            extraction,
        )
