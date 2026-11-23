"""M2 backend unified check — exact snapshots, typed observations, no AI.

Pure application orchestration only. A caller MUST independently authorize the
case and load version-pinned briefs, exhibit register, verified source
representations from trusted adapters. No HTTP/DB/LLM access, no legal verdict.
"""
from __future__ import annotations

import hashlib
import json
import re
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
from application.litigation.event_review import EventObservation, review_events
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
class LegalObservation:
    """One cited article checked against the matter's CHOSEN corpus.

    status is one of PASS/FAIL/UNDETERMINED/UNVERIFIED (the shared contract).
    It states corpus presence and quotation integrity only: never legal
    adequacy, applicability, correct interpretation or claim support.
    """

    reference_id: str
    raw_text: str
    start: int
    end: int
    act_code: str | None
    article: str | None
    language: str | None
    status: str
    reason: str
    corpus_key: str | None = None
    corpus_version: str | None = None
    corpus_text_sha256: str | None = None
    corpus_source_uri: str | None = None
    quote: str | None = None


@dataclass(frozen=True, slots=True)
class SuitabilityObservation:
    """One typed rule evaluated on facts declared as confirmed.

    The rule is the lawyer's, applied only to an article the brief cites that
    is present in the chosen corpus. status is PASS/FAIL/UNDETERMINED/UNVERIFIED
    (shared contract). It reports the lawyer's own condition; it is never a
    machine legal conclusion. ``missing`` names every input that blocked a verdict.
    """

    rule_id: str
    rule_version: str
    reference: str
    scope: str
    status: str
    reason: str
    article_key: str
    cited_by: tuple[str, ...]
    missing: tuple[str, ...]
    facts: tuple[tuple[str, str, bool, str], ...]  # name, value, confirmed, provenance
    input_hashes: tuple[tuple[str, str], ...]
    subresults: tuple[tuple[str, str], ...]


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
    legal_observations: tuple[LegalObservation, ...] = ()
    suitability_observations: tuple[SuitabilityObservation, ...] = ()
    event_observations: tuple[EventObservation, ...] = ()
    passage_flags: tuple[dict[str, Any], ...] = ()
    corpus_pack_sha256: str | None = None
    # Separate kinds: a literal/value mismatch is not a legal conclusion.


def _payload(run: VerificationRun, reviews: tuple[ObservationReview, ...] = ()) -> dict[str, Any]:
    legal: dict[str, Any] = (
        {"legal_references": [asdict(x) for x in run.legal_observations]}
        if run.legal_observations else {}
    )
    if run.corpus_pack_sha256 is not None:
        legal["corpus_pack_sha256"] = run.corpus_pack_sha256
    if run.suitability_observations:
        legal = {**legal, "suitability": [asdict(x) for x in run.suitability_observations]}
    if run.event_observations:
        legal = {**legal, "event_candidates": [asdict(x) for x in run.event_observations]}
    if run.passage_flags:
        legal = {**legal, "human_passage_flags": list(run.passage_flags)}
    return {
        **legal,
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
    legal_observations: tuple[LegalObservation, ...] = (),
    suitability_observations: tuple[SuitabilityObservation, ...] = (),
    passage_flags: tuple[dict[str, Any], ...] = (),
    corpus_pack_sha256: str | None = None,
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
    event_rows = review_events(representation.text, brief.references, citations.observations, previews)
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
    if corpus_pack_sha256 is not None:
        if re.fullmatch(r"[0-9a-f]{64}", corpus_pack_sha256) is None:
            raise VerificationError("invalid corpus pack identity")
        identity["corpus_pack_sha256"] = corpus_pack_sha256
    if passage_flags:
        if len(passage_flags) > 512:
            raise VerificationError("too many human passage flags")
        identity["human_passage_flags"] = passage_flags
    if event_rows:
        identity["events"] = [asdict(x) for x in event_rows]
    if legal_observations:
        # Present only when a corpus was chosen: a run without one keeps its
        # historical snapshot hash. The corpus identity (key, version, text
        # hash) is inside each observation, so a changed corpus changes the hash.
        identity["legal"] = [asdict(x) for x in legal_observations]
    if suitability_observations:
        identity["suitability"] = [asdict(x) for x in suitability_observations]
    return VerificationRun(
        brief.case_id, brief.version_id, brief.sha256_hex, representation.text_sha256,
        register.revision, ENGINE, source_scope.declared_source_versions,
        source_scope.excluded_source_versions, processed, incomplete,
        citations.observations, tuple(facts), _hash(identity),
        tuple(legal_observations), tuple(suitability_observations), event_rows, passage_flags,
        corpus_pack_sha256,
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
    valid_ids |= {f"flag:{x['id']}" for x in run.passage_flags}
    valid_ids |= {f"event:{x.observation_id}" for x in run.event_observations}
    valid_ids |= {f"legal:{x.reference_id}" for x in run.legal_observations}
    valid_ids |= {f"suitability:{x.rule_id}" for x in run.suitability_observations}
    if (len({x.observation_id for x in reviews}) != len(reviews)
            or any(not isinstance(x, ObservationReview) or x.observation_id not in valid_ids
                   for x in reviews)):
        raise VerificationError("review must target existing observation exactly once")
    return json.dumps(
        _payload(run, reviews), ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
