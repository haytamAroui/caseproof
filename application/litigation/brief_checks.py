"""PIV-07/09 — bounded deterministic draft-reference checking, no model or court decision.

Consumes server-authorized, frozen source previews + confirmed exhibit mapping.
This pure use case validates only whether an exact quoted string is present
within a single indexed source block. It cannot establish semantics, factual
truth, procedural validity or the correctness of a legal conclusion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from application.litigation.library import EvidencePreview
from application.litigation.representation_fidelity import (
    RepresentationComparison,
    RepresentationState,
)
from domains.disputes.exhibits import ExhibitRegister, MappingState


class DraftCheckError(ValueError):
    """Untrusted or out-of-snapshot draft-check input."""


class CitationCheckState(StrEnum):
    REPRESENTATION_CONFLICT = "representation_conflict"
    OCR_UNRELIABLE = "ocr_unreliable"
    EXACT_MATCH = "exact_match"
    NO_QUOTATION = "reference_checked_no_quotation"
    QUOTE_NOT_FOUND = "quote_not_found"
    REFERENCE_UNRESOLVED = "reference_unresolved"
    REFERENCE_AMBIGUOUS = "reference_ambiguous"
    PAGE_UNMAPPED = "page_unmapped"
    SOURCE_UNAVAILABLE = "source_unavailable"
    INCOMPLETE_EXTRACTION = "incomplete_extraction"
    MULTIPLE_MATCHES = "multiple_matches"


@dataclass(frozen=True, slots=True)
class DraftReference:
    reference_id: str
    exhibit_label: str
    exact_quote: str | None
    pdf_page: int | None = None

    def __post_init__(self) -> None:
        for value in (self.reference_id, self.exhibit_label):
            if type(value) is not str or not value.strip():
                raise DraftCheckError("nonempty bounded draft reference required")
        if (
            len(self.reference_id) > 128 or len(self.exhibit_label) > 160
            or (self.exact_quote is not None and (
                type(self.exact_quote) is not str or not self.exact_quote.strip()
                or len(self.exact_quote) > 4000
            ))
        ):
            raise DraftCheckError("reference text exceeds bounds")
        if self.pdf_page is not None and (
            type(self.pdf_page) is not int or not 1 <= self.pdf_page <= 100_000
        ):
            raise DraftCheckError("invalid physical PDF page")


@dataclass(frozen=True, slots=True)
class VersionedBrief:
    case_id: str
    version_id: str
    sha256_hex: str
    references: tuple[DraftReference, ...]

    def __post_init__(self) -> None:
        if (
            not self.case_id or not self.version_id
            or len(self.sha256_hex) != 64
            or any(c not in "0123456789abcdef" for c in self.sha256_hex)
            or type(self.references) is not tuple
            or len(self.references) > 128
        ):
            raise DraftCheckError("immutable versioned brief contract required")
        if not all(isinstance(ref, DraftReference) for ref in self.references):
            raise DraftCheckError("typed references required")
        ids = [ref.reference_id for ref in self.references]
        if len(ids) != len(set(ids)):
            raise DraftCheckError("duplicate draft reference IDs")


@dataclass(frozen=True, slots=True)
class CitationObservation:
    reference_id: str
    state: CitationCheckState
    exhibit_id: str | None
    source_id: str | None
    source_version_id: str | None
    source_sha256: str | None
    representation_id: str | None
    text_start: int | None
    text_end: int | None
    scope_note: str
    representation_comparisons: tuple[RepresentationComparison, ...] = ()
    visual_fidelity: str = "not_assessed"
    # EXACT_MATCH is lexical fidelity within one parsed span, NOT
    # semantic support, document authenticity or legal approval.

    # Stored derived fields survive asdict() in API, manifests and run hashes.
    visual_comparison_supplied: bool = field(init=False)
    visual_coverage: str = field(init=False)
    visual_assessment: str = field(init=False)
    fidelity_rules_version: str = field(init=False, default="representation-gate-v2")

    def __post_init__(self) -> None:
        comparisons = self.representation_comparisons
        object.__setattr__(self, "visual_comparison_supplied", bool(comparisons))
        object.__setattr__(self, "visual_coverage", (
            "whole_page" if any(c.covers_whole_page and c.text_start is None for c in comparisons)
            else "regional" if comparisons and all(c.text_start is not None for c in comparisons)
            else "unknown" if comparisons else "not_supplied"
        ))
        states = {c.state for c in comparisons}
        assessment = (
            RepresentationState.REPRESENTATION_CONFLICT
            if RepresentationState.REPRESENTATION_CONFLICT in states
            else RepresentationState.OCR_UNRELIABLE
            if RepresentationState.OCR_UNRELIABLE in states
            else RepresentationState.NOT_ASSESSED
        )
        object.__setattr__(self, "visual_assessment", assessment.value)


@dataclass(frozen=True, slots=True)
class DraftCheckReport:
    case_id: str
    brief_version_id: str
    brief_sha256: str
    exhibit_revision: int
    observations: tuple[CitationObservation, ...]
    unresolved_count: int
    mismatch_count: int
    exact_count: int
    evidence_scope_complete: bool
    engine_version: str = "caseproof-literal-citation-v2"

    @property
    def exact_without_visual_comparison_count(self) -> int:
        """Exact matches that no source-bound visual comparison covered."""
        return sum(
            o.state is CitationCheckState.EXACT_MATCH and not o.visual_comparison_supplied
            for o in self.observations
        )


def _note(reference: DraftReference, state: CitationCheckState,
          *, exhibit_id: str | None = None,
          preview: EvidencePreview | None = None,
          span: tuple[int, int] | None = None,
          comparisons: tuple[RepresentationComparison, ...] | None = None) -> CitationObservation:
    row = preview.row if preview is not None else None
    return CitationObservation(
        reference.reference_id, state, exhibit_id,
        row.source_id if row else None,
        row.version_id if row else None,
        row.original_sha256 if row else None,
        row.representation_id if row else None,
        span[0] if span else None, span[1] if span else None,
        state.value,
        comparisons if comparisons is not None else (),
        state.value if state in {CitationCheckState.REPRESENTATION_CONFLICT,
                                 CitationCheckState.OCR_UNRELIABLE} else "not_assessed",
    )


def check_brief_references(
    *, brief: VersionedBrief, register: ExhibitRegister,
    previews: tuple[EvidencePreview, ...],
    authorized_case_id: str,
    authorized_register_revision: int,
) -> DraftCheckReport:
    """Server must have authenticated/authorized exact case before calling.

    Previews are scoped to the authorized case by the caller; this pure
    function only enforces version alignment and rejects ambiguous inventory.
    Never deserialize authorized_case_id directly from HTTP.
    """
    if (
        type(authorized_case_id) is not str or not authorized_case_id
        or brief.case_id != authorized_case_id
        or type(authorized_register_revision) is not int
        or register.revision != authorized_register_revision
        or type(previews) is not tuple or len(previews) > 32
    ):
        raise DraftCheckError("out-of-snapshot brief or exhibit scope")
    indexed: dict[tuple[str, str], EvidencePreview] = {}
    for preview in previews:
        if not isinstance(preview, EvidencePreview):
            raise DraftCheckError("typed independently verified previews required")
        row = preview.row
        key = (row.source_id, row.version_id)
        if key in indexed or len(row.original_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in row.original_sha256
        ):
            raise DraftCheckError("duplicate/invalid source identity")
        indexed[key] = preview

    observations: list[CitationObservation] = []
    for reference in brief.references:
        resolved = register.resolve(reference.exhibit_label, pdf_page=reference.pdf_page)
        if resolved.state is MappingState.UNRESOLVED:
            observations.append(_note(reference, CitationCheckState.REFERENCE_UNRESOLVED))
            continue
        if resolved.state in {MappingState.AMBIGUOUS, MappingState.SUGGESTED}:
            observations.append(_note(reference, CitationCheckState.REFERENCE_AMBIGUOUS))
            continue
        if resolved.state is MappingState.PAGE_UNMAPPED or resolved.page is None:
            observations.append(_note(reference, CitationCheckState.PAGE_UNMAPPED, exhibit_id=resolved.exhibit_id))
            continue
        page = resolved.page
        matched_preview = indexed.get((page.source_id, page.version_id))
        if matched_preview is None:
            observations.append(_note(reference, CitationCheckState.SOURCE_UNAVAILABLE,
                                      exhibit_id=resolved.exhibit_id))
            continue
        row = matched_preview.row
        if row.status != "ready" or row.warnings or not row.representation_id or not matched_preview.spans:
            observations.append(_note(reference, CitationCheckState.INCOMPLETE_EXTRACTION,
                                      exhibit_id=resolved.exhibit_id, preview=matched_preview))
            continue
        # Derived representation text must have source-linked bounds.
        if any(
            type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(matched_preview.text)
            for start, end, _, _ in matched_preview.spans
        ):
            raise DraftCheckError("invalid representation span boundaries")
        # A confirmed mapping to physical page N does not permit matching
        # a quote on a different page when the draft omits a page number.
        expected_pdf_page = reference.pdf_page if reference.pdf_page is not None else page.pdf_page
        matches: list[tuple[int, int]] = []
        from_position = 0
        while reference.exact_quote is not None:
            begin = matched_preview.text.find(reference.exact_quote, from_position)
            if begin < 0:
                break
            end = begin + len(reference.exact_quote)
            if any(
                start <= begin and end <= finish
                and (expected_pdf_page is None or
                     (page_index is not None and page_index + 1 == expected_pdf_page))
                for start, finish, _, page_index in matched_preview.spans
            ):
                matches.append((begin, end))
            from_position = begin + 1
        if len(matches) > 1:
            state = CitationCheckState.MULTIPLE_MATCHES
        elif len(matches) == 1:
            state = CitationCheckState.EXACT_MATCH
        else:
            state = (CitationCheckState.NO_QUOTATION if reference.exact_quote is None
                     else CitationCheckState.QUOTE_NOT_FOUND)
        applied_list: list[RepresentationComparison] = []
        for comparison in matched_preview.representation_comparisons:
            if comparison.pdf_page != expected_pdf_page:
                continue
            bounded = comparison.text_start is not None and comparison.text_end is not None
            if (comparison.original_sha256 != row.original_sha256
                    or comparison.representation_id != row.representation_id):
                if not bounded:
                    raise DraftCheckError("stale representation comparison")
                state = CitationCheckState.INCOMPLETE_EXTRACTION
                applied_list = []
                break
            if comparison.text_start is not None and comparison.text_end is not None and (comparison.text_end > len(matched_preview.text)
                    or matched_preview.text[comparison.text_start:comparison.text_end] != comparison.extracted_text):
                raise DraftCheckError("comparison not bound to represented text")
            # Unlocated comparisons remain conservative page gates. Validated
            # source offsets alone may prove a region disjoint from this quote.
            if comparison.text_start is not None and comparison.text_end is not None and len(matches) == 1:
                begin, end = matches[0]
                if not (comparison.text_start < end and begin < comparison.text_end):
                    continue
            if bounded and reference.exact_quote is None:
                continue  # No quote to anchor; only unlocated page gates apply.
            applied_list.append(comparison)
        applied = tuple(applied_list)
        if state is not CitationCheckState.INCOMPLETE_EXTRACTION:
            blocked = {item.state for item in applied}
            if RepresentationState.REPRESENTATION_CONFLICT in blocked:
                state = CitationCheckState.REPRESENTATION_CONFLICT
            elif RepresentationState.OCR_UNRELIABLE in blocked:
                state = CitationCheckState.OCR_UNRELIABLE
        observations.append(_note(
            reference, state, exhibit_id=resolved.exhibit_id, preview=matched_preview,
            span=matches[0] if len(matches) == 1 else None, comparisons=applied,
        ))
    all_obs = tuple(observations)
    unknown = {
        CitationCheckState.REFERENCE_UNRESOLVED, CitationCheckState.REFERENCE_AMBIGUOUS,
        CitationCheckState.PAGE_UNMAPPED, CitationCheckState.SOURCE_UNAVAILABLE,
        CitationCheckState.INCOMPLETE_EXTRACTION, CitationCheckState.MULTIPLE_MATCHES,
        CitationCheckState.REPRESENTATION_CONFLICT, CitationCheckState.OCR_UNRELIABLE,
    }
    return DraftCheckReport(
        brief.case_id, brief.version_id, brief.sha256_hex, register.revision, all_obs,
        sum(o.state in unknown for o in all_obs),
        sum(o.state is CitationCheckState.QUOTE_NOT_FOUND for o in all_obs),
        sum(o.state is CitationCheckState.EXACT_MATCH for o in all_obs),
        bool(previews) and all(p.row.status == "ready" and not p.row.warnings for p in previews),
    )
