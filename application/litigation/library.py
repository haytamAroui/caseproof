"""PIV-04/05 deterministic, bounded, model-free evidence inventory/provenance.

This indexes already preserved source versions supplied from an authorized
Vault composition. It neither uploads customer bytes nor authenticates actors.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from application.documents.contracts import DocumentParser, ParsedDocument, restore
from application.documents.intake import CapturedDocument
from application.extraction.contracts import ExtractionError
from application.litigation.representation_fidelity import RepresentationComparison


@dataclass(frozen=True, slots=True)
class PageState:
    pdf_page: int | None
    state: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    source_id: str
    document_id: str
    version_id: str
    original_sha256: str
    media_type: str
    status: str
    parser_id: str | None
    representation_id: str | None
    pages: tuple[PageState, ...]
    warnings: tuple[str, ...]
    # Inventory intentionally excludes source text and original bytes.


@dataclass(frozen=True, slots=True)
class EvidencePreview:
    row: EvidenceRow
    text: str
    spans: tuple[tuple[int, int, str, int | None], ...]
    representation_comparisons: tuple[RepresentationComparison, ...] = ()
    # Text is an unapproved representation, not evidence of source authenticity.


@dataclass(frozen=True, slots=True)
class EvidenceInventory:
    rows: tuple[EvidenceRow, ...]
    complete: bool
    failed_count: int
    partial_count: int


def page_inventory(parsed: ParsedDocument) -> tuple[PageState, ...]:
    if parsed.evidence.source.media_type != "application/pdf":
        # DOCX page numbering cannot be reconstructed from extracted text.
        state = "page_unmapped" if parsed.evidence.source.media_type == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ) else "not_paginated"
        return (PageState(None, state, parsed.warnings),)
    indexed = {block.page_index for block in parsed.blocks if block.kind == "pdf_page"}
    page_warnings: dict[int, set[str]] = {}
    for warning in parsed.warnings:
        # Explicit page token emitted by the bounded parser worker.
        if ":page:" in warning:
            reason, suffix = warning.rsplit(":page:", 1)
            if suffix.isdecimal() and 0 <= int(suffix) < 64:
                page_warnings.setdefault(int(suffix), set()).add(reason)
    numbers = {number for number in indexed if number is not None} | set(page_warnings)
    if not numbers:
        return (PageState(None, "unresolved_page_inventory", parsed.warnings),)
    result = []
    for number in range(max(numbers) + 1):
        page_notes = tuple(sorted(page_warnings.get(number, set())))
        if number not in indexed:
            result.append(PageState(number + 1, "needs_ocr_or_review", page_notes))
        elif page_notes:
            result.append(PageState(number + 1, "partial", page_notes))
        else:
            result.append(PageState(number + 1, "indexed_text", ()))
    return tuple(result)


class EvidenceIndexer:
    """Internal processing: parsed source text is never an authorization token."""

    def __init__(self, parser: DocumentParser, *, clock: Callable[[], datetime] | None = None) -> None:
        self.parser = parser
        self.clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _captured(doc: CapturedDocument) -> None:
        if not isinstance(doc, CapturedDocument):
            raise ExtractionError("trusted captured source required")

    def _parse(self, doc: CapturedDocument) -> ParsedDocument:
        self._captured(doc)
        return restore(doc.source_id, doc.source, self.parser.parse(doc.source), self.clock())

    @staticmethod
    def _row(doc: CapturedDocument, parsed: ParsedDocument | None) -> EvidenceRow:
        source = doc.source
        if parsed is None:
            return EvidenceRow(
                doc.source_id, source.document_id, source.version_id,
                source.sha256_hex, source.media_type,
                "failed", None, None, (), ("document_parse_rejected",),
            )
        pages = page_inventory(parsed)
        status = "ready" if parsed.evidence.complete and all(
            p.state in {"indexed_text", "not_paginated"} for p in pages
        ) else "partial"
        return EvidenceRow(
            doc.source_id, source.document_id, source.version_id, source.sha256_hex,
            source.media_type, status, parsed.parser_id,
            parsed.evidence.representation.representation_id, pages, parsed.warnings,
        )

    def inventory(self, documents: tuple[CapturedDocument, ...]) -> EvidenceInventory:
        if type(documents) is not tuple or len(documents) > 32:
            raise ExtractionError("bounded source inventory required")
        if len({doc.source_id for doc in documents}) != len(documents):
            raise ExtractionError("duplicate source identity")
        rows = []
        for doc in documents:
            self._captured(doc)
            try:
                parsed = self._parse(doc)
            except (ExtractionError, ValueError, OSError, RuntimeError):
                parsed = None
            rows.append(self._row(doc, parsed))
        rows_t = tuple(rows)
        return EvidenceInventory(
            rows_t, bool(rows_t) and all(row.status == "ready" for row in rows_t),
            sum(row.status == "failed" for row in rows_t),
            sum(row.status == "partial" for row in rows_t),
        )

    def preview(self, document: CapturedDocument) -> EvidencePreview:
        parsed = self._parse(document)
        return EvidencePreview(
            self._row(document, parsed),
            parsed.evidence.content,
            tuple((block.start, block.end, block.locator, block.page_index) for block in parsed.blocks),
        )
