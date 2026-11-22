"""Adapt detected exhibit references to signed-path DraftReference inputs.

The M2 checker (application.litigation.brief_checks) consumes authorized,
frozen DraftReference inputs; it does not read raw brief text. This adapter
is the bounded bridge from the existing domains-layer exhibit-reference
detector (domains.disputes.reference_detection, already used at intake) to
those inputs, for the existing signed workbench composition.

Honesty rules:
- A bare page number in a citation is NOT a physical PDF page. It is
  grounded only when the confirmed exhibit mapping yields exactly one
  page across all three page spaces (physical/printed/bundle); the
  matched page's physical PDF page is then supplied. Otherwise the
  reference is emitted without a page and the pinpoint is recorded as
  an explicit abstention, never silently resolved.
"""
from __future__ import annotations

from dataclasses import dataclass

from application.litigation.brief_checks import DraftReference
from domains.disputes.exhibits import ExhibitRegister
from domains.disputes.reference_detection import (
    ExhibitReference,
    detect_exhibit_references,
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


def _label(reference: ExhibitReference) -> str:
    word = reference.label
    if word.endswith("s") and word[:-1] in ("pièce", "stuk"):
        word = word[:-1]
    return f"{word} {reference.number}"


def adapt_references(
    detected: tuple[ExhibitReference, ...],
    register: ExhibitRegister,
) -> AdaptedDraftReferences:
    """Convert detected exhibit references to DraftReference entries."""
    if not isinstance(register, ExhibitRegister):
        raise DraftReferenceAdapterError("typed exhibit register required")

    references: list[DraftReference] = []
    abstentions: list[PageAbstention] = []

    for position, detected_ref in enumerate(detected, 1):
        reference_id = f"ref-{position:02d}"
        label = _label(detected_ref)
        pdf_page = None
        if detected_ref.page_hint is not None:
            resolution = register.resolve(label)
            if resolution.exhibit_id is None or not resolution.identity_confirmed:
                abstentions.append(
                    PageAbstention(
                        reference_id, label, detected_ref.page_hint, "exhibit_unconfirmed"
                    )
                )
            else:
                entry = next(
                    e for e in register.entries if e.exhibit_id == resolution.exhibit_id
                )
                matches = {
                    page.pdf_page
                    for page in entry.pages
                    if detected_ref.page_hint
                    in (page.pdf_page, page.printed_page, page.bundle_page)
                }
                matches.discard(None)
                if len(matches) == 1:
                    # Unique confirmed interpretation across all page spaces.
                    pdf_page = matches.pop()
                else:
                    abstentions.append(
                        PageAbstention(
                            reference_id,
                            label,
                            detected_ref.page_hint,
                            "page_unmapped" if not matches else "page_space_ambiguous",
                        )
                    )
        references.append(DraftReference(reference_id, label, None, pdf_page))

    if len(references) > MAX_ADAPTED_REFERENCES:
        raise DraftReferenceAdapterError("adapted references exceed bounded contract")
    return AdaptedDraftReferences(tuple(references), tuple(abstentions))


def adapt_text(
    text: str, register: ExhibitRegister, *, region: str = "brief"
) -> AdaptedDraftReferences:
    """Detect exhibit references in raw brief text, then adapt them."""
    return adapt_references(detect_exhibit_references(text, region=region), register)
