"""Adapt parsed citation markers to signed-path DraftReference inputs.

The M2 checker (application.litigation.brief_checks) consumes authorized,
frozen DraftReference inputs; it does not read raw brief text. This adapter
is the bounded bridge from lexical extraction (citation_markers) to those
inputs, for the existing signed workbench composition.

Scope and honesty rules:
- Only exhibit-inventory markers ("pièce N" / "stuk N") become
  DraftReference entries; legal-article markers are reported as out of
  scope for this checker, never silently dropped or mislabeled.
- A bare page number in a citation is NOT a physical PDF page. It is
  grounded only when the confirmed exhibit mapping yields exactly one
  page in exactly one page space (physical/printed/bundle); the matched
  page's physical PDF page is then supplied. Otherwise the reference is
  emitted without a page and the pinpoint is recorded as an abstention.
"""
from __future__ import annotations

from dataclasses import dataclass

from application.litigation.brief_checks import DraftReference
from domains.disputes.exhibits import ExhibitRegister
from infrastructure.parsers.citation_markers import (
    CitationExtraction,
    extract_citations,
)

MAX_ADAPTED_REFERENCES = 128


class DraftReferenceAdapterError(ValueError):
    """Out-of-bounds adapter input."""


@dataclass(frozen=True, slots=True)
class PageAbstention:
    reference_id: str
    exhibit_label: str
    page_hint: int
    reason: str  # "page_space_ambiguous" | "page_unmapped" | "exhibit_unconfirmed"


@dataclass(frozen=True, slots=True)
class AdaptedDraftReferences:
    references: tuple[DraftReference, ...]
    page_abstentions: tuple[PageAbstention, ...]
    out_of_scope_markers: tuple[str, ...]  # marker_ids of legal-article markers


def adapt_extraction(
    extraction: CitationExtraction,
    register: ExhibitRegister,
) -> AdaptedDraftReferences:
    """Convert exhibit markers to DraftReference entries with grounded pages."""
    if not isinstance(register, ExhibitRegister):
        raise DraftReferenceAdapterError("typed exhibit register required")

    references: list[DraftReference] = []
    abstentions: list[PageAbstention] = []
    out_of_scope: list[str] = []

    for marker in extraction.markers:
        if marker.form != "exhibit_reference":
            out_of_scope.append(marker.marker_id)
            continue
        label = marker.target
        pdf_page = None
        if marker.page_hint is not None:
            resolution = register.resolve(label)
            if resolution.exhibit_id is None or not resolution.identity_confirmed:
                abstentions.append(
                    PageAbstention(
                        marker.marker_id, label, marker.page_hint, "exhibit_unconfirmed"
                    )
                )
            else:
                entry = next(e for e in register.entries if e.exhibit_id == resolution.exhibit_id)
                matches = {
                    page.pdf_page
                    for page in entry.pages
                    if marker.page_hint
                    in (page.pdf_page, page.printed_page, page.bundle_page)
                }
                matches.discard(None)
                if len(matches) == 1:
                    # Unique confirmed interpretation across all page spaces.
                    pdf_page = matches.pop()
                else:
                    abstentions.append(
                        PageAbstention(
                            marker.marker_id,
                            label,
                            marker.page_hint,
                            "page_unmapped" if not matches else "page_space_ambiguous",
                        )
                    )
        references.append(
            DraftReference(marker.marker_id, label, marker.quote, pdf_page)
        )

    if len(references) > MAX_ADAPTED_REFERENCES:
        raise DraftReferenceAdapterError("adapted references exceed bounded contract")
    return AdaptedDraftReferences(tuple(references), tuple(abstentions), tuple(out_of_scope))


def adapt_text(text: str, register: ExhibitRegister) -> AdaptedDraftReferences:
    """Extract markers from raw brief text, then adapt them."""
    return adapt_extraction(extract_citations(text), register)
