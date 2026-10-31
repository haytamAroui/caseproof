"""DOCX-to-reference discovery with conservative coverage reporting.

This adapter only reports textual candidates; identity and pinpoint checks remain separate.
"""

from dataclasses import dataclass, field

from domains.disputes.reference_detection import ExhibitReference, detect_exhibit_references
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions


@dataclass(frozen=True)
class DocxReferenceDiscovery:
    references: tuple[ExhibitReference, ...]
    coverage_complete: bool
    unscanned_parts: tuple[str, ...]
    text_coverage_complete: bool
    region_manifest: dict[str, object] = field(default_factory=dict)


def discover_docx_references(payload: bytes) -> DocxReferenceDiscovery:
    extracted = extract_docx_text_regions(payload)
    references = tuple(
        ref
        for region in extracted.regions
        for ref in detect_exhibit_references(region.text, region=region.part)
    )
    return DocxReferenceDiscovery(
        references=references,
        coverage_complete=False,  # Recognition recall is not established by scanning text.
        unscanned_parts=extracted.unscanned_parts,
        text_coverage_complete=extracted.coverage_complete,
        region_manifest=extracted.manifest,
    )
