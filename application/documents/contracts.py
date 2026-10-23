"""Immutable normalized text and deterministic mappings back to captured sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any, Protocol

from application.extraction.contracts import ExtractionError, ExtractionSource, digest, text
from packages.evidence_kernel.domain.anchors import TEXT_BASIS
from packages.evidence_kernel.domain.source_versions import DerivedRepresentation, SourceVersion

PARSER_SCHEMA = "caseproof-normalization-v1"
MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 120_000
MAX_BLOCKS = 2048


@dataclass(frozen=True)
class SourceBlock:
    block_id: str
    start: int
    end: int
    kind: str
    locator: str
    page_index: int | None = None

    def __post_init__(self) -> None:
        text(self.block_id, limit=128)
        text(self.locator, limit=4096)
        if self.kind not in {"text", "pdf_page", "xml_field", "email_header", "email_body"}:
            raise ExtractionError("unsupported block kind")
        if type(self.start) is not int or type(self.end) is not int or not 0 <= self.start < self.end:
            raise ExtractionError("invalid block text range")
        if self.kind == "pdf_page":
            if type(self.page_index) is not int or not 0 <= self.page_index < 64:
                raise ExtractionError("physical PDF page identity required")
        elif self.page_index is not None:
            raise ExtractionError("unexpected page identity")


@dataclass(frozen=True)
class ParsedDocument:
    evidence: ExtractionSource
    blocks: tuple[SourceBlock, ...]
    parser_id: str
    warnings: tuple[str, ...]
    fields: tuple[tuple[str, str], ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if type(self.blocks) is not tuple or len(self.blocks) > MAX_BLOCKS:
            raise ExtractionError("bounded immutable blocks required")
        if len({b.block_id for b in self.blocks}) != len(self.blocks):
            raise ExtractionError("duplicate block ID")
        last = 0
        for index, b in enumerate(self.blocks):
            if b.start < last or b.end > len(self.evidence.content):
                raise ExtractionError("overlapping/out-of-range block")
            gap = self.evidence.content[last : b.start]
            if gap != ("" if index == 0 else "\n\n"):
                raise ExtractionError("unmapped representation content")
            last = b.end
        if last != len(self.evidence.content):
            raise ExtractionError("unmapped representation suffix")
        if self.evidence.complete and (not self.blocks or self.warnings):
            raise ExtractionError("complete normalization cannot hide warnings or empty output")
        if type(self.warnings) is not tuple or any(type(w) is not str for w in self.warnings):
            raise ExtractionError("typed parser warnings required")
        if type(self.fields) is not tuple or len({p for p, _ in self.fields}) != len(self.fields):
            raise ExtractionError("immutable unique XML field paths required")

    def locations(self, start: int, end: int) -> tuple[SourceBlock, ...]:
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(self.evidence.content)
        ):
            raise ExtractionError("citation outside exact representation")
        blocks = tuple(b for b in self.blocks if b.start < end and start < b.end)
        # Only unmapped separators may lie between mapped spans, never a fabricated page/region.
        if not blocks or start < blocks[0].start or end > blocks[-1].end:
            raise ExtractionError("citation has unmapped boundaries")
        return blocks

    def artifact(self) -> dict[str, Any]:
        return {
            "schema": PARSER_SCHEMA,
            "text": self.evidence.content,
            "blocks": [asdict(b) for b in self.blocks],
            "parser_id": self.parser_id,
            "warnings": list(self.warnings),
            "fields": [list(f) for f in self.fields],
            "complete": self.evidence.complete,
        }


def restore(source_id: str, source: SourceVersion, artifact: dict[str, Any], at: datetime) -> ParsedDocument:
    required = {"schema", "text", "blocks", "parser_id", "warnings", "fields", "complete"}
    if set(artifact) != required or artifact["schema"] != PARSER_SCHEMA:
        raise ExtractionError("unknown normalization artifact")
    content = artifact["text"]
    if type(content) is not str or len(content) > MAX_TEXT_CHARS or type(artifact["complete"]) is not bool:
        raise ExtractionError("bounded typed normalization required")
    if not all(type(artifact[k]) is list for k in ("blocks", "warnings", "fields")):
        raise ExtractionError("typed normalization inventories required")
    if (
        len(artifact["blocks"]) > MAX_BLOCKS
        or len(artifact["warnings"]) > MAX_BLOCKS
        or len(artifact["fields"]) > MAX_BLOCKS
    ):
        raise ExtractionError("normalization inventory limit")
    parser_id = text(artifact["parser_id"], limit=256)
    config = digest(
        {"schema": PARSER_SCHEMA, "max_chars": MAX_TEXT_CHARS, "normalization": "parser_specific"}
    )
    raw = content.encode()
    manifest_hash = digest(artifact)
    rep = DerivedRepresentation(
        "rep:"
        + digest(
            {
                "document": source.document_id,
                "version": source.version_id,
                "source": source.sha256_hex,
                "parser": parser_id,
                "manifest": manifest_hash,
            }
        ),
        source.document_id,
        source.version_id,
        source.sha256_hex,
        sha256(raw).hexdigest(),
        raw,
        "text/plain",
        "caseproof_normalization",
        parser_id,
        config,
        TEXT_BASIS,
        at,
    )
    try:
        blocks = tuple(SourceBlock(**block) for block in artifact["blocks"])
        fields = tuple((text(p, limit=4096), v) for p, v in artifact["fields"])
        if any(type(v) is not str or len(v) > MAX_TEXT_CHARS for _, v in fields):
            raise ExtractionError("bounded XML scalar required")
        return ParsedDocument(
            ExtractionSource(source_id, source, rep, artifact["complete"]),
            blocks,
            parser_id,
            tuple(artifact["warnings"]),
            fields,
        )
    except (TypeError, ValueError) as exc:
        raise ExtractionError("invalid normalization mapping") from exc


class DocumentParser(Protocol):
    identity: str

    def parse(self, source: SourceVersion) -> dict[str, Any]: ...
