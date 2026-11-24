"""Adapt detected exhibit references to signed-path DraftReference inputs.

The M2 checker (application.litigation.brief_checks) consumes authorized,
frozen DraftReference inputs; it does not read raw brief text. This adapter
bridges the existing domains-layer exhibit-reference detector (already used
at intake) to those inputs, reusing the dossier journey's CANONICAL page
suffix syntax and abstention policy (PAGE_AFTER_REFERENCE): an unlabeled
page is never assigned a space; only an explicit, uniquely confirmed
physical/printed/bundle mapping grounds a physical PDF page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from application.litigation.brief_checks import DraftReference
from domains.disputes.dossier_verification import PAGE_AFTER_REFERENCE
from domains.disputes.exhibits import ExhibitRegister
from domains.disputes.reference_detection import detect_exhibit_references

MAX_ADAPTED_REFERENCES = 128
_SEQUENCE_RE = re.compile(r"^\s*(?:[-–—−]|[,;]\s*\d|(?:and|en|et|to|tot|à)\s+\d)", re.IGNORECASE)


class DraftReferenceAdapterError(ValueError):
    """Out-of-bounds adapter input."""


@dataclass(frozen=True, slots=True)
class PageAbstention:
    reference_id: str
    exhibit_label: str
    page_label: str
    reason: str  # "page_space_unspecified" | "page_space_ambiguous" | "page_unmapped"
    # | "page_sequence_unsupported" | "exhibit_unconfirmed"


@dataclass(frozen=True, slots=True)
class AdaptedDraftReferences:
    references: tuple[DraftReference, ...]
    page_abstentions: tuple[PageAbstention, ...]


def _label(word: str, number: str) -> str:
    base = word[:-1] if word.endswith("s") and word[:-1] in ("pièce", "stuk") else word
    return f"{base} {number}"


def _space(raw: str) -> str:
    folded = raw.casefold()
    if folded == "pdf":
        return "pdf"
    if folded in {"printed", "gedrukte", "imprimée"}:
        return "printed"
    return "bundle"


def adapt_text(
    text: str, register: ExhibitRegister, *, region: str = "brief"
) -> AdaptedDraftReferences:
    """Detect exhibit references in raw brief text, then adapt them.

    Page semantics identical to the dossier journey: the page suffix is
    parsed from the text following each reference; without an explicit
    space label the page never maps, even when a mapping looks unique.
    """
    if not isinstance(register, ExhibitRegister):
        raise DraftReferenceAdapterError("typed exhibit register required")

    references: list[DraftReference] = []
    abstentions: list[PageAbstention] = []

    for position, detected in enumerate(
        detect_exhibit_references(text, region=region), 1
    ):
        reference_id = f"ref-{position:02d}"
        label = _label(detected.label, detected.number)
        pdf_page = None

        suffix = PAGE_AFTER_REFERENCE.match(text[detected.end :])
        if suffix is not None:
            raw_space, page_label = suffix[1], suffix[2]
            tail = text[detected.end + suffix.end() :]
            if _SEQUENCE_RE.match(tail):
                abstentions.append(
                    PageAbstention(reference_id, label, page_label, "page_sequence_unsupported")
                )
            else:
                resolution = register.resolve(label)
                if resolution.exhibit_id is None or not resolution.identity_confirmed:
                    abstentions.append(
                        PageAbstention(reference_id, label, page_label, "exhibit_unconfirmed")
                    )
                elif raw_space is None:
                    abstentions.append(
                        PageAbstention(reference_id, label, page_label, "page_space_unspecified")
                    )
                elif not page_label.isascii() or not page_label.isdigit():
                    abstentions.append(
                        PageAbstention(reference_id, label, page_label, "page_unmapped")
                    )
                else:
                    entry = next(
                        e for e in register.entries if e.exhibit_id == resolution.exhibit_id
                    )
                    space = _space(raw_space)
                    number = int(page_label)
                    matches = {
                        page.pdf_page
                        for page in entry.pages
                        if (page.pdf_page if space == "pdf" else
                            page.printed_page if space == "printed" else
                            page.bundle_page) == number
                        and page.pdf_page is not None
                    }
                    if len(matches) == 1:
                        pdf_page = matches.pop()
                    else:
                        abstentions.append(
                            PageAbstention(
                                reference_id,
                                label,
                                page_label,
                                "page_unmapped" if not matches else "page_space_ambiguous",
                            )
                        )
        references.append(DraftReference(reference_id, label, None, pdf_page))

    if len(references) > MAX_ADAPTED_REFERENCES:
        raise DraftReferenceAdapterError("adapted references exceed bounded contract")
    return AdaptedDraftReferences(tuple(references), tuple(abstentions))
