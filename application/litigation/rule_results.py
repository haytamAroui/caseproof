"""Common per-rule verification result contract: PASS/FAIL/UNDETERMINED/UNVERIFIED.

This module only PROJECTS the existing granular check states into the shared
four-status contract. It never re-runs, replaces or weakens a check, never
infers semantic support, legal correctness or document authenticity, and never
turns a machine observation into a human decision. The original check outputs
remain authoritative and are preserved verbatim as sub-results.

- PASS: the rule ran with sufficient evidence and its condition holds.
- FAIL: the rule ran with sufficient evidence and its condition is violated.
  A FAIL is about the named narrow rule only (e.g. exact quotation absent from
  the checked representation), never a legal conclusion.
- UNDETERMINED: the machine cannot decide: evidence insufficient or ambiguous,
  the check not applicable or not run, or a human review still pending.
- UNVERIFIED is RESERVED: it names exactly one situation, a legal article absent
  from the corpus chosen for the case. No current rule family returns it; it
  becomes active when legal-source rules are wired (later roadmap task). A
  missing source, unconfirmed inventory, unmapped page, failed extraction or
  unreadable text is UNDETERMINED with its granular reason preserved, never
  UNVERIFIED. UNVERIFIED never means the reference does not exist.

See docs/standards/rule-result-contract-v1.md for the written mapping of every
existing rule family. Human dispositions (confirm/qualify/reject/waive) live in
the signed review path and are NOT modeled here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from application.litigation.brief_checks import CitationCheckState, CitationObservation
from application.litigation.dossier_contracts import CONTRACT
from application.litigation.factual_values import FactObservation, FactState
from application.litigation.paraphrase_guard import GUARD_VERSION
from application.litigation.unified_review import ENGINE, LegalObservation, VerificationRun
from domains.disputes.dossier_verification import ALGORITHM

CONTRACT_VERSION = "caseproof-rule-result-contract-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class RuleContractError(ValueError):
    """Unrecognized or malformed input for the common result projection."""


class RuleStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNDETERMINED = "UNDETERMINED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class RulePrecondition:
    name: str
    met: bool
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not 0 < len(self.name) <= 128:
            raise RuleContractError("bounded precondition name required")
        if type(self.met) is not bool or type(self.detail) is not str or len(self.detail) > 400:
            raise RuleContractError("typed precondition outcome and bounded detail required")


@dataclass(frozen=True, slots=True)
class RuleResult:
    """One rule, one status, with reference, scope, preconditions and hashes."""

    rule_id: str
    rule_version: str
    status: RuleStatus
    reference: str
    scope: str
    preconditions: tuple[RulePrecondition, ...]
    input_hashes: tuple[tuple[str, str], ...]
    reason: str
    subresults: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not 0 < len(self.rule_id) <= 128:
            raise RuleContractError("bounded rule identity required")
        if not isinstance(self.rule_version, str) or not 0 < len(self.rule_version) <= 128:
            raise RuleContractError("explicit rule version required")
        if not isinstance(self.status, RuleStatus):
            raise RuleContractError("typed four-status result required")
        if not isinstance(self.reference, str) or not 0 < len(self.reference) <= 256:
            raise RuleContractError("the assessed reference must be named")
        if not isinstance(self.scope, str) or not 0 < len(self.scope) <= 400:
            raise RuleContractError("bounded scope statement required")
        if not isinstance(self.preconditions, tuple) or len(self.preconditions) > 32:
            raise RuleContractError("bounded typed preconditions required")
        if not all(isinstance(p, RulePrecondition) for p in self.preconditions):
            raise RuleContractError("typed preconditions required")
        if not isinstance(self.reason, str) or not 0 < len(self.reason) <= 400:
            raise RuleContractError("every result names its reason")
        for label, digest in self.input_hashes:
            if not isinstance(label, str) or not 0 < len(label) <= 64:
                raise RuleContractError("bounded input hash label required")
            if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
                raise RuleContractError("input hashes must be well-formed sha256 digests")
        if len(self.input_hashes) != len({label for label, _ in self.input_hashes}):
            raise RuleContractError("unique input hash labels required")
        for key, value in self.subresults:
            if not isinstance(key, str) or not isinstance(value, str) or not key or len(value) > 400:
                raise RuleContractError("granular sub-results must be preserved as bounded strings")
        if not self.subresults:
            raise RuleContractError("the original granular states must be preserved")


def _hashes(*pairs: tuple[str, str | None]) -> tuple[tuple[str, str], ...]:
    """Keep the digests the caller actually has; fail closed on a malformed one.

    A missing digest (None) is simply omitted. A digest that is present but is
    not a well-formed sha256 raises instead of being silently dropped: the
    contract names input hashes as integrity evidence, so a corrupt digest must
    surface, never vanish.
    """
    digests: list[tuple[str, str]] = []
    for label, digest in pairs:
        if digest is None:
            continue
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise RuleContractError(f"malformed sha256 digest for input: {label}")
        digests.append((label, digest))
    return tuple(digests)


def _require(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuleContractError(f"projection input missing {name}")
    return value


_CITATION_STATUS: dict[CitationCheckState, RuleStatus] = {
    CitationCheckState.EXACT_MATCH: RuleStatus.PASS,
    CitationCheckState.QUOTE_NOT_FOUND: RuleStatus.FAIL,
    CitationCheckState.MULTIPLE_MATCHES: RuleStatus.UNDETERMINED,
    CitationCheckState.NO_QUOTATION: RuleStatus.UNDETERMINED,
    CitationCheckState.OCR_UNRELIABLE: RuleStatus.UNDETERMINED,
    CitationCheckState.REPRESENTATION_CONFLICT: RuleStatus.UNDETERMINED,
    CitationCheckState.REFERENCE_UNRESOLVED: RuleStatus.UNDETERMINED,
    CitationCheckState.REFERENCE_AMBIGUOUS: RuleStatus.UNDETERMINED,
    CitationCheckState.PAGE_UNMAPPED: RuleStatus.UNDETERMINED,
    CitationCheckState.SOURCE_UNAVAILABLE: RuleStatus.UNDETERMINED,
    CitationCheckState.INCOMPLETE_EXTRACTION: RuleStatus.UNDETERMINED,
}

_FACT_STATUS: dict[FactState, RuleStatus] = {
    FactState.MATCH: RuleStatus.PASS,
    FactState.DIFFERENCE: RuleStatus.FAIL,
    FactState.NEEDS_CONTEXT: RuleStatus.UNDETERMINED,
    FactState.NOT_ASSESSED: RuleStatus.UNDETERMINED,
}


def citation_result(
    observation: CitationObservation,
    *,
    brief_sha256: str | None = None,
    representation_sha256: str | None = None,
) -> RuleResult:
    """Project a citation literal check; the granular state stays the sub-result."""
    if not isinstance(observation, CitationObservation):
        raise RuleContractError("typed citation observation required")
    state = observation.state
    if state not in _CITATION_STATUS:
        raise RuleContractError(f"unmapped citation state: {state!r}")
    identity_ok = state not in {
        CitationCheckState.REFERENCE_UNRESOLVED,
        CitationCheckState.REFERENCE_AMBIGUOUS,
    }
    page_ok = state is not CitationCheckState.PAGE_UNMAPPED
    source_ok = state is not CitationCheckState.SOURCE_UNAVAILABLE
    extraction_ok = state is not CitationCheckState.INCOMPLETE_EXTRACTION
    preconditions = (
        RulePrecondition("exhibit_identity_resolved", identity_ok, state.value),
        RulePrecondition("requested_page_mapped", page_ok, state.value),
        RulePrecondition("source_available", source_ok, state.value),
        RulePrecondition("source_extraction_complete", extraction_ok, state.value),
        RulePrecondition("explicit_quotation_present", state is not CitationCheckState.NO_QUOTATION, state.value),
    )
    return RuleResult(
        rule_id="citation.literal",
        rule_version=ENGINE,
        status=_CITATION_STATUS[state],
        reference=observation.reference_id,
        scope=observation.scope_note,
        preconditions=preconditions,
        input_hashes=_hashes(
            ("brief_original_sha256", brief_sha256),
            ("brief_representation_sha256", representation_sha256),
            ("source_original_sha256", observation.source_sha256),
        ),
        reason=state.value,
        subresults=(("citation_state", state.value),),
    )


def fact_result(
    observation: FactObservation,
    *,
    brief_sha256: str | None = None,
    representation_sha256: str | None = None,
) -> RuleResult:
    """Project a typed factual comparison; a candidate difference is FAIL of the
    narrow same-role value rule, never a confirmed contradiction."""
    if not isinstance(observation, FactObservation):
        raise RuleContractError("typed fact observation required")
    state = observation.state
    if state not in _FACT_STATUS:
        raise RuleContractError(f"unmapped fact state: {state!r}")
    preconditions = (
        RulePrecondition("source_representation_ready", state is not FactState.NOT_ASSESSED, state.value),
        RulePrecondition("unique_role_aligned_value", state is not FactState.NEEDS_CONTEXT, state.value),
    )
    return RuleResult(
        rule_id="fact.value",
        rule_version=ENGINE,
        status=_FACT_STATUS[state],
        reference=observation.claim_id,
        scope=(
            f"typed {observation.kind.value}/{observation.role.value} comparison inside one "
            "verified source-mapped span of the cited exhibit; roles are explicit draft metadata"
        ),
        preconditions=preconditions,
        input_hashes=_hashes(
            ("brief_original_sha256", brief_sha256),
            ("brief_representation_sha256", representation_sha256),
            ("source_original_sha256", observation.source_sha256),
        ),
        reason=observation.explanation,
        subresults=(
            ("fact_state", state.value),
            ("fact_kind", observation.kind.value),
            ("fact_role", observation.role.value),
        ),
    )


_IDENTITY_STATUS: dict[str, RuleStatus] = {
    "resolved": RuleStatus.PASS,
    "not_in_inventory": RuleStatus.FAIL,
    "ambiguous": RuleStatus.UNDETERMINED,
    "source_missing": RuleStatus.UNDETERMINED,
    "not_assessed": RuleStatus.UNDETERMINED,
}

_PAGE_MAPPING_STATUS: dict[str, RuleStatus] = {
    "mapped": RuleStatus.PASS,
    "conflicting": RuleStatus.UNDETERMINED,
    "unmapped": RuleStatus.UNDETERMINED,
}

_LITERAL_STATUS: dict[str, RuleStatus] = {
    "exact_match": RuleStatus.PASS,
    "quote_not_found": RuleStatus.FAIL,
    "multiple_matches": RuleStatus.UNDETERMINED,
    "translation_review_required": RuleStatus.UNDETERMINED,
    "not_applicable": RuleStatus.UNDETERMINED,
    "not_assessed": RuleStatus.UNDETERMINED,
}

# Visual fidelity is never a machine PASS or FAIL: agreement is uncalibrated and
# a not-run or unreliable assessment is pending human confirmation. Every known
# visual state is therefore UNDETERMINED; UNVERIFIED is reserved (absent corpus
# article) and never applies to visual fidelity.
_VISUAL_STATES = {"ocr_unreliable", "representation_conflict", "not_assessed"}


def _mapped(mapping: dict[str, RuleStatus], value: str, family: str) -> RuleStatus:
    if value not in mapping:
        raise RuleContractError(f"unmapped {family} state: {value!r}")
    return mapping[value]


def _finding_fields(finding: dict[str, Any]) -> tuple[str, str | None]:
    if not isinstance(finding, dict):
        raise RuleContractError("dossier finding projection requires the finding record")
    reference = _require(finding.get("reference_id"), "reference_id")
    digest = finding.get("source_sha256")
    return reference, digest if isinstance(digest, str) else None


def finding_identity_result(finding: dict[str, Any]) -> RuleResult:
    reference, digest = _finding_fields(finding)
    state = _require(finding.get("identity"), "identity")
    reason = finding.get("identity_reason")
    status = _mapped(_IDENTITY_STATUS, state, "exhibit identity")
    return RuleResult(
        rule_id="exhibit.identity",
        rule_version=ALGORITHM,
        status=status,
        reference=reference,
        scope=(
            "exact exhibit identity of this reference against the confirmed complete "
            "inventory and its authorized source; no fuzzy matching"
        ),
        preconditions=(
            RulePrecondition(
                "inventory_confirmed_complete",
                state != "not_assessed",
                reason if isinstance(reason, str) else state,
            ),
            RulePrecondition("authorized_source_present", state != "source_missing", state),
        ),
        input_hashes=_hashes(("source_original_sha256", digest)),
        reason=reason if isinstance(reason, str) and reason else state,
        subresults=(("identity", state),),
    )


def finding_page_mapping_result(finding: dict[str, Any]) -> RuleResult:
    reference, digest = _finding_fields(finding)
    state = _require(finding.get("page_mapping"), "page_mapping")
    reason = finding.get("page_mapping_reason")
    status = _mapped(_PAGE_MAPPING_STATUS, state, "page mapping")
    return RuleResult(
        rule_id="exhibit.page_mapping",
        rule_version=ALGORITHM,
        status=status,
        reference=reference,
        scope=(
            "the requested pinpoint page of this reference mapped to one physical PDF page "
            "of the pinned source version"
        ),
        preconditions=(
            RulePrecondition("exhibit_identity_resolved", finding.get("identity") == "resolved",
                             str(finding.get("identity"))),
            RulePrecondition("unique_mapping_record", state != "conflicting", state),
        ),
        input_hashes=_hashes(("source_original_sha256", digest)),
        reason=reason if isinstance(reason, str) and reason else state,
        subresults=(
            ("page_mapping", state),
            ("pdf_page", str(finding.get("pdf_page"))),
        ),
    )


def finding_literal_result(finding: dict[str, Any]) -> RuleResult:
    reference, digest = _finding_fields(finding)
    literal = finding.get("literal_assessment")
    if not isinstance(literal, dict):
        raise RuleContractError("dossier finding projection requires literal_assessment")
    state = _require(literal.get("state"), "literal_assessment.state")
    reason = _require(literal.get("reason"), "literal_assessment.reason")
    status = _mapped(_LITERAL_STATUS, state, "literal fidelity")
    return RuleResult(
        rule_id="fidelity.literal",
        rule_version=CONTRACT,
        status=status,
        reference=reference,
        scope=(
            "the exact quotation of this reference present inside the checked page "
            "representation only; lexical fidelity, never semantic support"
        ),
        preconditions=(
            RulePrecondition("explicit_quotation_present", state != "not_applicable", state),
            RulePrecondition("source_text_available", state != "not_assessed", state),
        ),
        input_hashes=_hashes(("source_original_sha256", digest)),
        reason=reason,
        subresults=(
            ("literal_assessment", state),
            ("fidelity", str(finding.get("fidelity"))),
        ),
    )


def finding_visual_result(finding: dict[str, Any]) -> RuleResult:
    reference, digest = _finding_fields(finding)
    visual = finding.get("visual_assessment")
    if not isinstance(visual, dict):
        raise RuleContractError("dossier finding projection requires visual_assessment")
    state = _require(visual.get("state"), "visual_assessment.state")
    reason = _require(visual.get("reason"), "visual_assessment.reason")
    if state not in _VISUAL_STATES:
        raise RuleContractError(f"unmapped visual fidelity state: {state!r}")
    status = RuleStatus.UNDETERMINED
    return RuleResult(
        rule_id="fidelity.visual",
        rule_version=CONTRACT,
        status=status,
        reference=reference,
        scope=(
            "regional visual fidelity of the cited page; agreement is uncalibrated and "
            "always requires human confirmation of the original pixels"
        ),
        preconditions=(
            RulePrecondition("visual_assessment_performed", bool(visual.get("performed")), reason),
            RulePrecondition("calibrated_agreement", False, "calibration_not_available"),
        ),
        input_hashes=_hashes(("source_original_sha256", digest)),
        reason=reason,
        subresults=(("visual_assessment", state),),
    )


def finding_support_result(finding: dict[str, Any]) -> RuleResult:
    reference, digest = _finding_fields(finding)
    support = _require(finding.get("support"), "support")
    if support != "not_assessed":
        raise RuleContractError(f"machine support must stay not_assessed, got: {support!r}")
    return RuleResult(
        rule_id="support.human",
        rule_version=CONTRACT,
        status=RuleStatus.UNDETERMINED,
        reference=reference,
        scope=(
            "semantic support of the draft assertion by the cited source: human decision "
            "only, never a machine outcome; pending until the lawyer disposes of it"
        ),
        preconditions=(
            RulePrecondition("lawyer_disposition_recorded", False, "human_only"),
        ),
        input_hashes=_hashes(("source_original_sha256", digest)),
        reason="human_only_pending_lawyer_disposition",
        subresults=(("support", support),),
    )


def finding_results(finding: dict[str, Any]) -> tuple[RuleResult, ...]:
    """All per-dimension rule results of one dossier finding."""
    return (
        finding_identity_result(finding),
        finding_page_mapping_result(finding),
        finding_literal_result(finding),
        finding_visual_result(finding),
        finding_support_result(finding),
    )


def guard_result(advisory: dict[str, Any], *, reference: str) -> RuleResult:
    """Project a paraphrase-guard advisory. The guard is advisory only: it can
    require manual review but never returns PASS or FAIL."""
    if not isinstance(advisory, dict):
        raise RuleContractError("typed paraphrase guard advisory required")
    state = _require(advisory.get("state"), "guard state")
    if state not in {"needs_manual_review", "not_assessed"}:
        raise RuleContractError(f"unmapped guard state: {state!r}")
    reason_codes = advisory.get("reason_codes")
    reason = (
        ",".join(code for code in reason_codes if isinstance(code, str))
        if isinstance(reason_codes, list) and reason_codes
        else state
    )
    return RuleResult(
        rule_id="paraphrase.guarded_terms",
        rule_version=GUARD_VERSION,
        status=RuleStatus.UNDETERMINED,
        reference=reference,
        scope=(
            "lexical guarded-term warnings near the cited passage; review priorities, "
            "never contradictions or semantic support; not run counts as pending"
        ),
        preconditions=(
            RulePrecondition("unique_verbatim_anchor",
                             advisory.get("anchor_basis") != "unavailable",
                             str(advisory.get("anchor_basis"))),
        ),
        input_hashes=_hashes(("source_original_sha256", advisory.get("source_sha256"))),
        reason=reason or state,
        subresults=(
            ("guard_state", state),
            ("warning_count", str(len(advisory.get("warnings", ())))),
        ),
    )


def coverage_issue_result(
    issue_status: str,
    *,
    subject: str,
    manifest_version: str,
    reason: str,
) -> RuleResult:
    """Project one kernel coverage issue evaluation. The declared scope is a
    recorded claim, never proof of real-world completeness."""
    mapping = {
        "supported": RuleStatus.PASS,
        "contradicted": RuleStatus.FAIL,
        "qualified": RuleStatus.UNDETERMINED,
        "unresolved": RuleStatus.UNDETERMINED,
        "open": RuleStatus.UNDETERMINED,  # not yet evaluated: pending, never UNVERIFIED here
    }
    status = _mapped(mapping, issue_status, "coverage issue")
    return RuleResult(
        rule_id="coverage.issue",
        rule_version=manifest_version,
        status=status,
        reference=subject,
        scope="declared investigation coverage of this issue; the declaration is not audited here",
        preconditions=(
            RulePrecondition("issue_evaluated", issue_status != "open", issue_status),
        ),
        input_hashes=(),
        reason=reason,
        subresults=(("issue_status", issue_status),),
    )


def legal_result(
    observation: LegalObservation,
    *,
    brief_sha256: str | None = None,
    representation_sha256: str | None = None,
) -> RuleResult:
    """Project a legal-reference check. UNVERIFIED keeps its single meaning."""
    status = RuleStatus(observation.status)
    corpus_ok = observation.status != RuleStatus.UNVERIFIED.value
    return RuleResult(
        rule_id="legal.reference_in_corpus",
        rule_version="caseproof-legal-reference-check-v1",
        status=status,
        reference=observation.reference_id,
        scope=("Article presence in the matter's chosen corpus and literal "
               "quotation integrity only; not applicability, adequacy or support."),
        preconditions=(
            RulePrecondition("article_present_in_chosen_corpus", corpus_ok, observation.reason),
            RulePrecondition("explicit_quotation_present", observation.quote is not None,
                             observation.reason),
        ),
        input_hashes=_hashes(
            ("brief_original_sha256", brief_sha256),
            ("brief_representation_sha256", representation_sha256),
            ("corpus_text_sha256", observation.corpus_text_sha256),
        ),
        reason=observation.reason,
        subresults=(("legal_reference_state", observation.reason),),
    )


def run_rule_results(run: VerificationRun) -> tuple[RuleResult, ...]:
    """Project every citation and factual observation of a frozen unified run.

    The run's own payload, snapshot hash and report stay byte-identical; this is
    an additional view over the same machine findings, not a new check.
    """
    if not isinstance(run, VerificationRun):
        raise RuleContractError("typed frozen verification run required")
    return tuple(
        [citation_result(x, brief_sha256=run.brief_sha256,
                         representation_sha256=run.representation_sha256)
         for x in run.citation_observations]
        + [fact_result(x, brief_sha256=run.brief_sha256,
                       representation_sha256=run.representation_sha256)
           for x in run.factual_observations]
        + [legal_result(x, brief_sha256=run.brief_sha256,
                        representation_sha256=run.representation_sha256)
           for x in run.legal_observations]
    )


def to_dict(result: RuleResult) -> dict[str, Any]:
    """Deterministic JSON-serializable view of one rule result."""
    if not isinstance(result, RuleResult):
        raise RuleContractError("typed rule result required")
    return {
        "contract": CONTRACT_VERSION,
        "rule_id": result.rule_id,
        "rule_version": result.rule_version,
        "status": result.status.value,
        "reference": result.reference,
        "scope": result.scope,
        "preconditions": [
            {"name": p.name, "met": p.met, "detail": p.detail} for p in result.preconditions
        ],
        "input_hashes": {label: digest for label, digest in result.input_hashes},
        "reason": result.reason,
        "subresults": dict(result.subresults),
    }


def to_json(result: RuleResult) -> str:
    return json.dumps(to_dict(result), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
