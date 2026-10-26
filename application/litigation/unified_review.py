"""M2 backend unified check — exact snapshots, typed observations, no AI.

Pure application orchestration only. A caller MUST independently authorize the
case and load version-pinned briefs, exhibit register, verified source
representations from trusted adapters. No HTTP/DB/LLM access, no legal verdict.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from application.litigation.brief_checks import (
    CitationCheckState,
    CitationObservation,
    DraftCheckError,
    VersionedBrief,
    check_brief_references,
)
from application.litigation.factual_values import (
    FactAssertion,
    FactObservation,
    compare_fact,
)
from application.litigation.library import EvidencePreview
from domains.disputes.exhibits import ExhibitRegister, MappingState

ENGINE = "caseproof-disputes-unified-factual-v1"
REPORT_SCHEMA = "caseproof-litigation-verification-run-v1"


class VerificationError(ValueError):
    """Invalid source-backed checking contract; fail closed."""


@dataclass(frozen=True, slots=True)
class BriefRepresentation:
    """Normalized text, NOT substitute for independently verified original."""
    brief: VersionedBrief
    text: str
    text_sha256: str
    parser_id: str
    claims: tuple[FactAssertion, ...]

    def __post_init__(self) -> None:
        if (type(self.text) is not str or len(self.text) > 120_000
                or self.text_sha256 != hashlib.sha256(self.text.encode()).hexdigest()
                or not self.parser_id or len(self.parser_id) > 256
                or type(self.claims) is not tuple or len(self.claims) > 128
                or not all(isinstance(x, FactAssertion) for x in self.claims)):
            raise VerificationError("invalid immutable brief representation")
        refs = {x.reference_id for x in self.brief.references}
        ids = [x.claim_id for x in self.claims]
        if len(set(ids)) != len(ids) or any(x.reference_id not in refs for x in self.claims):
            raise VerificationError("claims must bind to unique existing brief references")
        if any(
            x.text_end > len(self.text) or self.text[x.text_start:x.text_end] != x.text
            for x in self.claims
        ):
            raise VerificationError("factual assertion not anchored in brief text")


@dataclass(frozen=True, slots=True)
class SourceScope:
    """Explicit denominator; never inferred from only the supplied ready files."""
    declared_source_versions: tuple[tuple[str, str], ...]
    excluded_source_versions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if (not self.declared_source_versions or len(self.declared_source_versions) > 32
                or len(set(self.declared_source_versions)) != len(self.declared_source_versions)
                or len(set(self.excluded_source_versions)) != len(self.excluded_source_versions)
                or any(pair not in self.declared_source_versions for pair in self.excluded_source_versions)
                or any(len(pair) != 2 or not all(type(x) is str and x for x in pair)
                       for pair in self.declared_source_versions + self.excluded_source_versions)):
            raise VerificationError("invalid versioned source scope")


class ReviewDisposition(StrEnum):
    CONFIRMED = "confirmed_candidate"
    DISMISSED = "dismissed"
    NEEDS_INFORMATION = "needs_information"


@dataclass(frozen=True, slots=True)
class ObservationReview:
    """Reviewer statement, NOT semantic truth or production approval."""
    observation_id: str
    actor_id: str
    disposition: ReviewDisposition
    rationale: str

    def __post_init__(self) -> None:
        if (not self.observation_id or not self.actor_id or not isinstance(self.disposition, ReviewDisposition)
                or type(self.rationale) is not str or not 0 < len(self.rationale.strip()) <= 2000):
            raise VerificationError("typed human review record required")


@dataclass(frozen=True, slots=True)
class VerificationRun:
    case_id: str
    brief_version_id: str
    brief_sha256: str
    representation_sha256: str
    exhibit_revision: int
    rule_version: str
    declared: tuple[tuple[str, str], ...]
    excluded: tuple[tuple[str, str], ...]
    processed: tuple[tuple[str, str], ...]
    incomplete: tuple[tuple[str, str], ...]
    citation_observations: tuple[CitationObservation, ...]
    factual_observations: tuple[FactObservation, ...]
    snapshot_hash: str
    # Separate kinds: a literal/value mismatch is not a legal conclusion.


def _payload(run: VerificationRun, reviews: tuple[ObservationReview, ...] = ()) -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA,
        "engine": ENGINE,
        "case_id": run.case_id,
        "brief_version_id": run.brief_version_id,
        "brief_original_sha256": run.brief_sha256,
        "brief_representation_sha256": run.representation_sha256,
        "exhibit_revision": run.exhibit_revision,
        "sources": {
            "declared": run.declared, "excluded": run.excluded,
            "processed": run.processed, "incomplete": run.incomplete,
        },
        "citations": [asdict(x) for x in run.citation_observations],
        "factual_candidates": [asdict(x) for x in run.factual_observations],
        "reviewer_dispositions": [asdict(x) for x in reviews],
        "snapshot_hash": run.snapshot_hash,
        "scope_complete": len(run.incomplete) == 0 and not run.excluded
                          and len(run.declared) == len(run.processed),
        "legal_conclusion": "not_assessed",
        "filing_status": "not_assessed",
        "professional_certificate": False,
    }


def _hash(data: object) -> str:
    return hashlib.sha256(json.dumps(
        data, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode()).hexdigest()


def run_unified_check(
    *, representation: BriefRepresentation,
    register: ExhibitRegister,
    previews: tuple[EvidencePreview, ...],
    source_scope: SourceScope,
    authorized_case_id: str,
    authorized_register_revision: int,
) -> VerificationRun:
    """No implicit trust from request parameters; authorized_* are server-owned."""
    if not isinstance(representation, BriefRepresentation) or not isinstance(source_scope, SourceScope):
        raise VerificationError("typed trusted snapshots required")
    brief = representation.brief
    if brief.case_id != authorized_case_id or register.revision != authorized_register_revision:
        raise VerificationError("case or exhibit snapshot changed")
    expected = set(source_scope.declared_source_versions)
    excluded = set(source_scope.excluded_source_versions)
    present: set[tuple[str, str]] = set()
    for preview in previews:
        if not isinstance(preview, EvidencePreview):
            raise VerificationError("verified typed source preview required")
        key = (preview.row.source_id, preview.row.version_id)
        if key not in expected or key in excluded or key in present:
            raise VerificationError("source beyond declared authorized scope or duplicated")
        present.add(key)
    try:
        citations = check_brief_references(
            brief=brief, register=register, previews=previews,
            authorized_case_id=authorized_case_id,
            authorized_register_revision=authorized_register_revision,
        )
    except DraftCheckError as exc:
        raise VerificationError("citation source snapshot invalid") from exc
    by_ref = {x.reference_id: x for x in citations.observations}
    brief_refs = {x.reference_id: x for x in brief.references}
    by_source = {(x.row.source_id, x.row.version_id): x for x in previews}
    facts: list[FactObservation] = []
    usable = {CitationCheckState.EXACT_MATCH, CitationCheckState.NO_QUOTATION,
              CitationCheckState.QUOTE_NOT_FOUND}
    for assertion in representation.claims:
        citation = by_ref[assertion.reference_id]
        reference = brief_refs[assertion.reference_id]
        page = register.resolve(reference.exhibit_label, pdf_page=reference.pdf_page)
        verified_preview: EvidencePreview | None = None
        physical_page: int | None = None
        if citation.state in usable and page.state is MappingState.CONFIRMED and page.page:
            verified_preview = by_source.get((page.page.source_id, page.page.version_id))
            physical_page = reference.pdf_page if reference.pdf_page is not None else page.page.pdf_page
        # Unknown/partial citation is always UNKNOWN for a dependent factual claim.
        facts.append(compare_fact(
            assertion, verified_brief_text=representation.text,
            preview=verified_preview, pdf_page=physical_page,
        ))
    processed = tuple(sorted(
        (x.row.source_id, x.row.version_id) for x in previews
        if x.row.status == "ready" and not x.row.warnings and x.row.representation_id
    ))
    incomplete = tuple(sorted(expected - set(processed)))
    identity = {
        "schema": REPORT_SCHEMA,
        "case": brief.case_id,
        "brief": (brief.version_id, brief.sha256_hex, representation.text_sha256,
                  representation.parser_id),
        "exhibit_revision": register.revision,
        "claim_parsing": tuple(
            (a.claim_id, a.reference_id, a.text_start, a.text_end,
             a.kind, a.role, a.language, a.source_language)
            for a in representation.claims
        ),
        "exhibit_identifiers": tuple(
            (e.exhibit_id, e.display_label, e.aliases, e.confirmed, e.manual_inclusion, tuple(
                (p.source_id, p.version_id, p.pdf_page, p.printed_page, p.bundle_page)
                for p in e.pages
            )) for e in register.entries
        ),
        "sources": tuple(sorted(
            (x.row.source_id, x.row.version_id, x.row.original_sha256,
             x.row.representation_id, x.row.parser_id, x.row.status,
             x.row.warnings, x.spans)
            for x in previews
        )),
        "declared": source_scope.declared_source_versions,
        "excluded": source_scope.excluded_source_versions,
        "citations": [asdict(x) for x in citations.observations],
        "factual": [asdict(x) for x in facts],
        "rule_version": ENGINE,
    }
    return VerificationRun(
        brief.case_id, brief.version_id, brief.sha256_hex, representation.text_sha256,
        register.revision, ENGINE, source_scope.declared_source_versions,
        source_scope.excluded_source_versions, processed, incomplete,
        citations.observations, tuple(facts), _hash(identity),
    )


def verification_record(
    run: VerificationRun,
    *,
    reviews: tuple[ObservationReview, ...] = (),
) -> bytes:
    """Deterministic neutral report; NOT a certified or submitted legal artifact."""
    if not isinstance(run, VerificationRun) or len(reviews) > 256:
        raise VerificationError("bounded verification report required")
    valid_ids = {f"citation:{x.reference_id}" for x in run.citation_observations}
    valid_ids |= {f"fact:{x.claim_id}" for x in run.factual_observations}
    if (len({x.observation_id for x in reviews}) != len(reviews)
            or any(not isinstance(x, ObservationReview) or x.observation_id not in valid_ids
                   for x in reviews)):
        raise VerificationError("review must target existing observation exactly once")
    return json.dumps(
        _payload(run, reviews), ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
