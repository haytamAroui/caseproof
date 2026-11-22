"""Run the actual merged CaseProof engine over a bounded demo dossier and
render one self-contained French HTML report for visual inspection.

This is a DEMONSTRATION runner, not pilot acceptance:

- every figure comes from executing the already-merged engine modules at
  generation time (M2 unified brief check, review cycle with correction and
  recheck, task-4 corpus, task-5 suitability rules, task-3 lawyer decisions,
  task-6 DOCX coverage measurement) — no mock, no LLM call, no network;
- inputs stay labelled: real public sources keep their origin URL and
  provenance; the authored brief, facts, rules, exhibits and the simulated
  reviewer are marked synthetic/simulated, never lawyer-approved;
- the report banner states it is not legal validation, not the task-7 pilot
  gate, and that waiver consequences (task 2) remain undecided.

Dossier directory contract::

    dossier/
      meta.json        {"title", "brief", "audience_note"?}
      corpus/          corpus-manifest.toml + source files (task-4 format)
      rules/*.toml     demo-authored rules (task-5 format)
      facts.json       {"facts": [{"name","value","confirmed"}]}
      decisions.json   {"decided_at", "decisions": [...]}  (task-3 review)
      m2.json          brief/evidence/review journey (see _load_m2)
      brief.docx       authored Word document (measured + shown)

Usage:
    uv run --locked python -m scripts.demo_belgian_dossier \
        --dossier PATH --out report.html [--json-out run.json]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from application.litigation.brief_checks import (
    CitationCheckState,
    DraftReference,
    VersionedBrief,
)
from application.litigation.corpus import CorpusError, IngestionReport, load_corpus
from application.litigation.factual_values import (
    FactAssertion,
    FactKind,
    FactObservation,
    FactRole,
    FactState,
)
from application.litigation.lawyer_decisions import (
    Disposition,
    LawyerDecision,
    record_decision,
    validate_decision,
)
from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.review_cycle import (
    CorrectionProposal,
    ReviewPacket,
    decision_summary,
    preview_correction,
    ready_for_release,
    revise_review,
)
from application.litigation.rule_results import RuleResult, RuleStatus
from application.litigation.suitability_rules import ConfirmedFact, RuleFormatError, evaluate_rule, load_rule
from application.litigation.unified_review import (
    BriefRepresentation,
    ObservationReview,
    ReviewDisposition,
    SourceScope,
    run_unified_check,
)
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
from scripts.measure_docx_coverage import measure_file

DEMO_RUNNER_VERSION = "caseproof-demo-runner-v2"
SIMULATED_ACTOR = "demonstration-avocat-simule"
MAX_RULES = 16
MAX_FACTS = 64
MAX_DECISIONS = 32
MAX_TEXT = 400
MAX_BRIEF = 60_000
MAX_SOURCE = 120_000
MAX_SOURCES = 8
MAX_REFERENCES = 16
MAX_CLAIMS = 32


class DemoDossierError(ValueError):
    """Malformed or unsafe demo dossier input."""


def _bounded(value: Any, name: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not 0 < len(value) <= limit:
        raise DemoDossierError(f"{name} must be a string of 1..{limit} characters")
    return value


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise DemoDossierError(f"missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DemoDossierError(f"invalid JSON in {path.name}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class DossierMeta:
    title: str
    brief: str
    audience_note: str


def _load_meta(directory: Path) -> DossierMeta:
    data = _load_json(directory / "meta.json")
    if not isinstance(data, dict):
        raise DemoDossierError("meta.json must be an object")
    return DossierMeta(
        title=_bounded(data.get("title"), "meta.title"),
        brief=_bounded(data.get("brief"), "meta.brief", 128),
        audience_note=(lambda v: "" if v == "" else _bounded(v, "meta.audience_note", 600))(data.get("audience_note", "")),
    )


def _load_facts(directory: Path) -> dict[str, ConfirmedFact]:
    data = _load_json(directory / "facts.json")
    entries = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries or len(entries) > MAX_FACTS:
        raise DemoDossierError(f"facts.json needs 1..{MAX_FACTS} facts")
    facts: dict[str, ConfirmedFact] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DemoDossierError(f"fact #{index} must be an object")
        try:
            confirmed = entry.get("confirmed")
            fact_name = entry.get("name")
            fact_value = entry.get("value")
            if type(confirmed) is not bool:
                raise DemoDossierError(f"fact #{index}: confirmed must be a boolean")
            if not isinstance(fact_name, str) or not isinstance(fact_value, (str, int, float, bool)):
                raise DemoDossierError(f"fact #{index}: name must be a string, value a scalar")
            fact = ConfirmedFact(
                name=fact_name,
                value=fact_value,
                confirmed=confirmed,
            )
        except RuleFormatError as exc:
            raise DemoDossierError(f"fact #{index}: {exc}") from exc
        facts[fact.name] = fact
    return facts


def _load_decision_specs(directory: Path) -> tuple[str, list[dict[str, Any]]]:
    path = directory / "decisions.json"
    if not path.is_file():
        return "", []
    data = _load_json(path)
    entries = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(entries, list) or len(entries) > MAX_DECISIONS:
        raise DemoDossierError(f"decisions.json needs 0..{MAX_DECISIONS} decisions")
    decided_at = _bounded(data.get("decided_at"), "decisions.decided_at", 40)
    return decided_at, entries


def _load_rules(directory: Path) -> list[tuple[str, Any]]:
    rules_dir = directory / "rules"
    if not rules_dir.is_dir():
        raise DemoDossierError(f"missing rules directory: {rules_dir}")
    documents = sorted(rules_dir.glob("*.toml"))
    if not documents or len(documents) > MAX_RULES:
        raise DemoDossierError(f"rules/ needs 1..{MAX_RULES} TOML documents")
    loaded: list[tuple[str, Any]] = []
    for document in documents:
        try:
            loaded.append((document.name, load_rule(document.read_text(encoding="utf-8"))))
        except (RuleFormatError, UnicodeDecodeError) as exc:
            raise DemoDossierError(f"rule {document.name}: {exc}") from exc
    return loaded


def _locate(text: str, needle: str, name: str) -> tuple[int, int]:
    if text.count(needle) != 1:
        raise DemoDossierError(f"{name} must occur exactly once in the brief text")
    start = text.index(needle)
    return start, start + len(needle)


@dataclass(frozen=True, slots=True)
class M2Source:
    source_id: str
    document_id: str
    version_id: str
    text: str
    label: str
    synthetic: bool


@dataclass(frozen=True, slots=True)
class M2Dossier:
    case_id: str
    brief_version_id: str
    brief_text: str
    brief_label: str
    references: tuple[DraftReference, ...]
    claim_specs: tuple[dict[str, Any], ...]
    passages: tuple[dict[str, Any], ...]
    register: ExhibitRegister
    sources: tuple[M2Source, ...]
    review_decisions: tuple[dict[str, Any], ...]
    correction: dict[str, Any] | None


def _load_m2(directory: Path) -> M2Dossier:
    data = _load_json(directory / "m2.json")
    if not isinstance(data, dict):
        raise DemoDossierError("m2.json must be an object")
    case_id = _bounded(data.get("case_id"), "m2.case_id", 128)
    brief_version_id = _bounded(data.get("brief_version_id"), "m2.brief_version_id", 128)
    brief_label = (lambda v: "" if v == "" else _bounded(v, "m2.brief_label", 200))(data.get("brief_label", ""))
    brief_text = data.get("brief_text")
    if not isinstance(brief_text, str) or not brief_text.strip() or len(brief_text) > MAX_BRIEF:
        raise DemoDossierError(f"m2.brief_text must be 1..{MAX_BRIEF} characters")

    raw_refs = data.get("references")
    if not isinstance(raw_refs, list) or not 1 <= len(raw_refs) <= MAX_REFERENCES:
        raise DemoDossierError(f"m2.references needs 1..{MAX_REFERENCES} entries")
    references: list[DraftReference] = []
    for index, entry in enumerate(raw_refs):
        try:
            quote = entry.get("exact_quote")
            references.append(DraftReference(
                _bounded(entry.get("reference_id"), f"reference #{index} id", 128),
                _bounded(entry.get("exhibit_label"), f"reference #{index} label", 160),
                quote,
                entry.get("pdf_page"),
            ))
        except Exception as exc:
            raise DemoDossierError(f"reference #{index}: {exc}") from exc

    raw_claims = data.get("claims")
    if not isinstance(raw_claims, list) or len(raw_claims) > MAX_CLAIMS:
        raise DemoDossierError(f"m2.claims needs 0..{MAX_CLAIMS} entries")
    claim_specs: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_claims):
        if not isinstance(entry, dict):
            raise DemoDossierError(f"claim #{index} must be an object")
        kind = entry.get("kind")
        role = entry.get("role")
        language = entry.get("language", "fr")
        source_language = entry.get("source_language", "fr")
        if not (isinstance(kind, str) and isinstance(role, str)
                and isinstance(language, str) and isinstance(source_language, str)):
            raise DemoDossierError(f"claim #{index}: kind/role/languages must be strings")
        try:
            FactKind(kind)
            FactRole(role)
        except ValueError as exc:
            raise DemoDossierError(f"claim #{index}: unknown kind/role") from exc
        text = _bounded(entry.get("text"), f"claim #{index} text", 4000)
        _locate(brief_text, text, f"claim #{index} text")
        claim_specs.append({
            "claim_id": _bounded(entry.get("claim_id"), f"claim #{index} id", 160),
            "reference_id": _bounded(entry.get("reference_id"), f"claim #{index} reference_id", 160),
            "text": text,
            "kind": kind,
            "role": role,
            "language": language,
            "source_language": source_language,
        })

    raw_passages = data.get("passages", [])
    if not isinstance(raw_passages, list) or len(raw_passages) > 32:
        raise DemoDossierError("m2.passages needs 0..32 entries")
    passages: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_passages):
        if not isinstance(entry, dict):
            raise DemoDossierError(f"passage #{index} must be an object")
        text = _bounded(entry.get("text"), f"passage #{index} text", 4000)
        _locate(brief_text, text, f"passage #{index} text")
        passages.append({
            "passage_id": _bounded(entry.get("passage_id"), f"passage #{index} id", 160),
            "observation_id": _bounded(entry.get("observation_id"), f"passage #{index} observation_id", 200),
            "text": text,
        })

    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list) or not 1 <= len(raw_sources) <= MAX_SOURCES:
        raise DemoDossierError(f"m2.sources needs 1..{MAX_SOURCES} entries")
    sources: list[M2Source] = []
    for index, entry in enumerate(raw_sources):
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_SOURCE:
            raise DemoDossierError(f"source #{index} text must be 1..{MAX_SOURCE} characters")
        sources.append(M2Source(
            _bounded(entry.get("source_id"), f"source #{index} id", 128),
            _bounded(entry.get("document_id"), f"source #{index} document_id", 128),
            _bounded(entry.get("version_id"), f"source #{index} version_id", 128),
            text,
            _bounded(entry.get("label", ""), f"source #{index} label", 200),
            bool(entry.get("synthetic", True)),
        ))

    raw_exhibits = data.get("exhibits")
    if not isinstance(raw_exhibits, list) or not 1 <= len(raw_exhibits) <= 32:
        raise DemoDossierError("m2.exhibits needs 1..32 entries")
    source_keys = {(s.source_id, s.version_id) for s in sources}
    entries: list[ExhibitEntry] = []
    for index, entry in enumerate(raw_exhibits):
        try:
            pages = []
            for page in entry.get("pages", []):
                if (page.get("source_id"), page.get("version_id")) not in source_keys:
                    raise DemoDossierError(f"exhibit #{index} maps an unknown source")
                pages.append(ExhibitPage(page["source_id"], page["version_id"], page.get("pdf_page")))
            entries.append(ExhibitEntry(
                _bounded(entry.get("exhibit_id"), f"exhibit #{index} id", 128),
                _bounded(entry.get("display_label"), f"exhibit #{index} label", 160),
                tuple(pages),
                tuple(entry.get("aliases", [])),
                bool(entry.get("confirmed", False)),
            ))
        except DemoDossierError:
            raise
        except Exception as exc:
            raise DemoDossierError(f"exhibit #{index}: {exc}") from exc
    revision = data.get("register_revision")
    if type(revision) is not int or revision < 1:
        raise DemoDossierError("m2.register_revision must be a positive integer")
    register = ExhibitRegister(revision, tuple(entries))

    review = data.get("review") or {}
    review_decisions = review.get("decisions", [])
    if not isinstance(review_decisions, list) or len(review_decisions) > 64:
        raise DemoDossierError("m2.review.decisions needs 0..64 entries")
    correction = data.get("correction")
    if correction is not None and not isinstance(correction, dict):
        raise DemoDossierError("m2.correction must be an object")

    return M2Dossier(
        case_id, brief_version_id, brief_text, brief_label, tuple(references),
        tuple(claim_specs), tuple(passages), register, tuple(sources), tuple(review_decisions),
        correction,
    )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _references_with_quote_updates(
    m2: M2Dossier, quote_updates: dict[str, str]
) -> tuple[DraftReference, ...]:
    """Re-derive references after brief edits: a corrected citation passage
    becomes the reference's new exact quote (re-extracted from the new text)."""
    updated: list[DraftReference] = []
    for reference in m2.references:
        obs_id = f"citation:{reference.reference_id}"
        passage = next((p for p in m2.passages if p["observation_id"] == obs_id), None)
        if passage is not None and passage["passage_id"] in quote_updates:
            updated.append(DraftReference(
                reference.reference_id, reference.exhibit_label,
                quote_updates[passage["passage_id"]], reference.pdf_page,
            ))
        else:
            updated.append(reference)
    return tuple(updated)


def _build_representation(
    m2: M2Dossier, text: str, version_id: str,
    claim_overrides: dict[str, str] | None = None,
) -> BriefRepresentation:
    brief = VersionedBrief(m2.case_id, version_id, _sha(f"original:{version_id}"), m2.references)
    claims: list[FactAssertion] = []
    for spec in m2.claim_specs:
        claim_text = (claim_overrides or {}).get(spec["claim_id"], spec["text"])
        start, end = _locate(text, claim_text, f"claim {spec['claim_id']}")
        claims.append(FactAssertion(
            spec["claim_id"], spec["reference_id"], claim_text, start, end,
            FactKind(spec["kind"]), FactRole(spec["role"]),
            spec["language"], spec["source_language"],
        ))
    return BriefRepresentation(brief, text, _sha(text), "caseproof-demo-runner-v2", tuple(claims))


def _previews(m2: M2Dossier) -> tuple[EvidencePreview, ...]:
    previews: list[EvidencePreview] = []
    for source in m2.sources:
        row = EvidenceRow(
            source.source_id, source.document_id, source.version_id, _sha(source.text),
            "application/pdf", "ready", "caseproof-demo-source-v1", f"repr-{source.source_id}",
            (), (),
        )
        previews.append(EvidencePreview(row, source.text, ((0, len(source.text), "pdf-page-1", 0),)))
    return tuple(previews)


def _run_check(m2: M2Dossier, representation: BriefRepresentation) -> Any:
    scope = SourceScope(tuple((s.source_id, s.version_id) for s in m2.sources))
    return run_unified_check(
        representation=representation,
        register=m2.register,
        previews=_previews(m2),
        source_scope=scope,
        authorized_case_id=m2.case_id,
        authorized_register_revision=m2.register.revision,
    )


@dataclass(frozen=True, slots=True)
class M2Journey:
    run1: Any
    packet: ReviewPacket
    correction_preview: Any
    corrected_claim_id: str | None
    corrected_text: str
    run2: Any | None
    release_ready: bool
    summary: dict[str, int]


def _run_m2_journey(m2: M2Dossier) -> M2Journey:
    representation = _build_representation(m2, m2.brief_text, m2.brief_version_id)
    run1 = _run_check(m2, representation)

    packet = ReviewPacket(run1.snapshot_hash, 0, ())
    valid_ids = {f"citation:{x.reference_id}" for x in run1.citation_observations}
    valid_ids |= {f"fact:{x.claim_id}" for x in run1.factual_observations}
    for index, spec in enumerate(m2.review_decisions):
        if spec.get("observation_id") not in valid_ids:
            raise DemoDossierError(f"review decision #{index} answers an unknown observation")
        disposition_value = spec.get("disposition")
        if not isinstance(disposition_value, str):
            raise DemoDossierError(f"review decision #{index}: disposition must be a string")
        try:
            disposition = ReviewDisposition(disposition_value)
        except ValueError as exc:
            raise DemoDossierError(f"review decision #{index}: unknown disposition") from exc
        packet = revise_review(
            run=run1, packet=packet, expected_revision=packet.revision,
            decision=ObservationReview(
                spec["observation_id"], SIMULATED_ACTOR, disposition,
                _bounded(spec.get("rationale"), f"review decision #{index} rationale", 2000),
            ),
        )

    correction_preview = None
    corrected_claim_id: str | None = None
    corrected_text = m2.brief_text
    run2 = None
    if m2.correction is not None:
        passage_id = _bounded(m2.correction.get("passage_id"), "correction.passage_id", 160)
        passage_spec: dict[str, Any] | None = None
        for passage in m2.passages:
            if passage["passage_id"] == passage_id:
                passage_spec = passage
        if passage_spec is None:
            raise DemoDossierError("correction refers to an unknown passage_id")
        claim_id = passage_id
        after = _bounded(m2.correction.get("after"), "correction.after", 4000)
        start, end = _locate(m2.brief_text, passage_spec["text"], "correction.before")
        proposal = CorrectionProposal(
            observation_id=passage_spec["observation_id"],
            actor_id=SIMULATED_ACTOR,
            expected_run_hash=run1.snapshot_hash,
            expected_brief_version=m2.brief_version_id,
            expected_text_sha256=representation.text_sha256,
            start=start,
            end=end,
            before=passage_spec["text"],
            after=after,
            rationale=_bounded(m2.correction.get("rationale"), "correction.rationale", 2000),
        )
        correction_preview = preview_correction(run=run1, text=m2.brief_text, proposal=proposal)
        corrected_claim_id = claim_id
        corrected_text = correction_preview.proposed_text
        representation2 = BriefRepresentation(
            VersionedBrief(m2.case_id, m2.brief_version_id + "-corrige",
                           _sha("original:" + m2.brief_version_id + "-corrige"),
                           _references_with_quote_updates(m2, {passage_spec["passage_id"]: after})),
            corrected_text, _sha(corrected_text), "caseproof-demo-runner-v2", (),
        )
        run2 = _run_check(m2, representation2)

    return M2Journey(
        run1=run1,
        packet=packet,
        correction_preview=correction_preview,
        corrected_claim_id=corrected_claim_id,
        corrected_text=corrected_text,
        run2=run2,
        release_ready=ready_for_release(run1, packet),
        summary=decision_summary(packet),
    )


def _evaluate(directory: Path) -> dict[str, Any]:
    meta = _load_meta(directory)
    corpus_report = load_corpus(directory / "corpus")
    coverage = measure_file(directory / meta.brief)
    facts = _load_facts(directory)
    rules = _load_rules(directory)
    results = [evaluate_rule(rule, facts, corpus_report.article_keys) for _name, rule in rules]
    decided_at, specs = _load_decision_specs(directory)
    decisions: list[LawyerDecision] = []
    by_rule = {result.rule_id: result for result in results}
    for index, spec in enumerate(specs):
        if not isinstance(spec, dict):
            raise DemoDossierError(f"decision #{index} must be an object")
        rule_id = spec.get("rule_id")
        result = by_rule.get(rule_id) if isinstance(rule_id, str) else None
        if result is None:
            raise DemoDossierError(f"decision #{index} answers an unknown rule_id")
        disposition_value = spec.get("disposition")
        if not isinstance(disposition_value, str):
            raise DemoDossierError(f"decision #{index}: disposition must be a string")
        try:
            disposition = Disposition(disposition_value)
        except ValueError as exc:
            raise DemoDossierError(f"decision #{index}: unknown disposition") from exc
        try:
            decisions.append(
                record_decision(
                    result,
                    actor_id=SIMULATED_ACTOR,
                    disposition=disposition,
                    rationale=_bounded(spec.get("rationale"), "rationale", 600),
                    scope=_bounded(spec.get("scope"), "scope"),
                    decided_at=decided_at,
                )
            )
        except Exception as exc:
            raise DemoDossierError(f"decision #{index}: {exc}") from exc
    validity = {decision.decision_id: validate_decision(decision, by_rule[decision.rule_id]) for decision in decisions}
    m2 = _load_m2(directory)
    journey = _run_m2_journey(m2)
    return {
        "meta": meta,
        "corpus": corpus_report,
        "coverage": coverage,
        "facts": facts,
        "results": results,
        "decisions": decisions,
        "validity": validity,
        "m2": m2,
        "journey": journey,
    }


_STATUS_LABELS = {
    RuleStatus.PASS: ("Conforme", "pass"),
    RuleStatus.FAIL: ("Non conforme", "fail"),
    RuleStatus.UNDETERMINED: ("Indéterminé", "undetermined"),
    RuleStatus.UNVERIFIED: ("Non vérifié", "unverified"),
}
_DISPOSITION_LABELS = {
    Disposition.CONFIRMED: "Confirmé",
    Disposition.QUALIFIED: "Qualifié",
    Disposition.REJECTED: "Rejeté",
    Disposition.WAIVED: "Dérogation",
}
_FACT_STATE_LABELS = {
    FactState.MATCH: ("Correspond", "pass"),
    FactState.DIFFERENCE: ("Écart détecté", "fail"),
    FactState.NEEDS_CONTEXT: ("Contexte requis", "undetermined"),
    FactState.NOT_ASSESSED: ("Non évalué", "unverified"),
}
_CITATION_LABELS = {
    CitationCheckState.EXACT_MATCH: ("Citation exacte", "pass"),
    CitationCheckState.QUOTE_NOT_FOUND: ("Citation introuvable", "fail"),
    CitationCheckState.NO_QUOTATION: ("Référence vérifiée, sans citation", "undetermined"),
    CitationCheckState.REPRESENTATION_CONFLICT: ("Conflit de représentation", "unverified"),
    CitationCheckState.OCR_UNRELIABLE: ("OCR non fiable", "unverified"),
    CitationCheckState.REFERENCE_UNRESOLVED: ("Référence hors registre des pièces", "unverified"),
    CitationCheckState.REFERENCE_AMBIGUOUS: ("Référence ambiguë", "unverified"),
    CitationCheckState.PAGE_UNMAPPED: ("Page non mappée", "unverified"),
    CitationCheckState.SOURCE_UNAVAILABLE: ("Source indisponible", "unverified"),
    CitationCheckState.INCOMPLETE_EXTRACTION: ("Extraction incomplète", "unverified"),
    CitationCheckState.MULTIPLE_MATCHES: ("Correspondances multiples", "unverified"),
}
_REVIEW_LABELS = {
    ReviewDisposition.CONFIRMED: "Écart confirmé",
    ReviewDisposition.DISMISSED: "Écart écarté",
    ReviewDisposition.NEEDS_INFORMATION: "Information requise",
}


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _chip(label: str, css: str) -> str:
    return f'<span class="chip {css}">{_esc(label)}</span>'


def _status_chip(status: RuleStatus) -> str:
    label, css = _STATUS_LABELS[status]
    return _chip(label, css)


def _fact_obs_card(obs: FactObservation, corrected: bool) -> str:
    label, css = _FACT_STATE_LABELS[obs.state]
    rows = []
    if obs.brief_token is not None or obs.source_token is not None:
        rows.append(
            f"<p><strong>Conclusions :</strong> <code>{_esc(obs.brief_token)}</code> · "
            f"<strong>Source :</strong> <code>{_esc(obs.source_token)}</code></p>"
        )
    if obs.source_locator:
        rows.append(f"<p><strong>Ancre source :</strong> {_esc(obs.source_locator)}"
                    + (f" page {obs.source_pdf_page}" if obs.source_pdf_page else "") + "</p>")
    return (
        '<div class="card">'
        f"<h3>{_chip(label, css)} fait <code>{_esc(obs.claim_id)}</code>"
        f"{' — après correction' if corrected else ''}</h3>"
        f"<p><strong>Type :</strong> {_esc(obs.kind.value)} ({_esc(obs.role.value)}) · "
        f"<strong>Explication :</strong> {_esc(obs.explanation)}</p>"
        f"{''.join(rows)}"
        "</div>"
    )


def _citation_card(obs: Any, corrected: bool) -> str:
    label, css = _CITATION_LABELS[obs.state]
    return (
        '<div class="card">'
        f"<h3>{_chip(label, css)} référence <code>{_esc(obs.reference_id)}</code>"
        f"{' — après correction' if corrected else ''}</h3>"
        f"<p>{_esc(obs.scope_note)}</p>"
        + (f"<p><strong>Source :</strong> {_esc(obs.source_id)} · sha256 "
           f"<code>{_esc((obs.source_sha256 or '')[:12])}…</code></p>" if obs.source_id else "")
        + "</div>"
    )


def render_html(run: dict[str, Any], *, generated_at: str) -> str:
    meta: DossierMeta = run["meta"]
    corpus: IngestionReport = run["corpus"]
    coverage = run["coverage"]
    facts: dict[str, ConfirmedFact] = run["facts"]
    results: list[RuleResult] = run["results"]
    decisions: list[LawyerDecision] = run["decisions"]
    validity = run["validity"]
    m2: M2Dossier = run["m2"]
    journey: M2Journey = run["journey"]
    by_rule = {decision.rule_id: decision for decision in decisions}

    counts: dict[RuleStatus, int] = {status: 0 for status in RuleStatus}
    for result in results:
        counts[result.status] += 1

    article_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(record.act)} art. {_esc(record.article)}</td>"
        f"<td>{_esc(record.language)}</td>"
        f"<td>{_esc(record.version)}</td>"
        f'<td><a href="{_esc(record.source_uri)}">{_esc(record.source_uri)}</a></td>'
        f"<td><code>{_esc(record.original_sha256[:12])}…</code></td>"
        "</tr>"
        for record in corpus.records
    ) or '<tr><td colspan="5">Aucun article ingéré.</td></tr>'

    fact_rows = "\n".join(
        f"<tr><td><code>{_esc(fact.name)}</code></td><td>{_esc(fact.value)}</td>"
        f'<td>{"confirmé" if fact.confirmed else "non confirmé"}</td></tr>'
        for fact in facts.values()
    )

    result_cards: list[str] = []
    for result in results:
        decision = by_rule.get(result.rule_id)
        decision_html = ""
        if decision is not None:
            validity_state, detail = validity[decision.decision_id]
            decision_html = (
                '<div class="decision">'
                "<p><strong>Décision (relecture simulée) :</strong> "
                f"{_esc(_DISPOSITION_LABELS[decision.disposition])} — {_esc(decision.rationale)}</p>"
                f"<p><strong>Portée :</strong> {_esc(decision.scope)}</p>"
                f"<p><strong>Validité après recalcul :</strong> {_esc(validity_state.value)} ({_esc(detail)})</p>"
                "</div>"
            )
        precond = ""
        if result.preconditions:
            items = "".join(
                "<li>" + _esc(p.name) + " (" + ("satisfaite" if p.met else "non satisfaite") + ") : "
                + _esc(p.detail) + "</li>"
                for p in result.preconditions
            )
            precond = f"<p><strong>Préconditions :</strong></p><ul>{items}</ul>"
        subs = ""
        if result.subresults:
            items = "".join(f"<li><code>{_esc(k)}</code> : {_esc(v)}</li>" for k, v in result.subresults)
            subs = f"<p><strong>Sous-résultats :</strong></p><ul>{items}</ul>"
        result_cards.append(
            '<div class="card">'
            f"<h3>{_status_chip(result.status)} {_esc(result.rule_id)} <small>v{_esc(result.rule_version)}</small></h3>"
            f"<p><strong>Référence :</strong> {_esc(result.reference)}</p>"
            f"<p><strong>Portée de la règle :</strong> {_esc(result.scope)}</p>"
            f"<p><strong>Motif :</strong> {_esc(result.reason)}</p>"
            f"{precond}{subs}{decision_html}"
            "</div>"
        )

    _REGION_KIND_LABELS = {
        "MAIN_BODY": "corps du document",
        "COMMENT_EXCLUDED": "commentaire",
        "HIDDEN_TEXT_EXCLUDED": "texte masqué",
        "STRUCTURED_CONTENT": "contenu structuré",
        "UNKNOWN_WORD_PART": "partie Word inconnue",
    }
    omitted = [
        "<li>"
        + _esc(_REGION_KIND_LABELS.get(entry["kind"], entry["kind"]))
        + f" — {_esc(entry['part'])} : <strong>{_esc(entry['status'])}</strong> ({_esc(entry['reason'])})</li>"
        for entry in coverage["regions"]
        if entry["status"] != "READ"
    ]
    omitted_html = (
        "<p><strong>Le lecteur Word du produit ne lit PAS ce document tel quel :</strong></p>"
        f"<ul>{''.join(omitted)}</ul>"
        "<p>Le corps est refusé tant que les révisions ne sont pas figées (comportement de « fail-closed »). "
        "Le texte vérifié dans cette démonstration est donc une extraction de démonstration "
        "(simulée, sans les annotations de test), pas la sortie du lecteur produit.</p>"
        if omitted else "<p>Aucune région omise.</p>"
    )

    source_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(source.label or source.source_id)}</td>"
        f"<td>{_esc(source.version_id)}</td>"
        f"<td>{'synthétique (créé pour la démo)' if source.synthetic else 'source publique réelle'}</td>"
        f"<td><code>{_esc(_sha(source.text)[:12])}…</code></td>"
        "</tr>"
        for source in m2.sources
    )

    run1 = journey.run1
    review_rows = []
    for review_decision in journey.packet.decisions:
        review_rows.append(
            "<tr>"
            f"<td><code>{_esc(review_decision.observation_id)}</code></td>"
            f"<td>{_esc(_REVIEW_LABELS[review_decision.disposition])}</td>"
            f"<td>{_esc(review_decision.rationale)}</td>"
            "</tr>"
        )
    review_html = (
        "<table><tr><th>Observation</th><th>Disposition (relecture simulée)</th><th>Motif</th></tr>"
        + "\n".join(review_rows) + "</table>"
        if review_rows else "<p>Aucune disposition enregistrée.</p>"
    )

    correction_html = "<p>Aucune correction dans cette démonstration.</p>"
    if journey.correction_preview is not None and journey.run2 is not None:
        claim_id = journey.corrected_claim_id
        spec = next((c for c in m2.passages if c["passage_id"] == claim_id), None)
        before = spec["text"] if spec else ""
        after = m2.correction.get("after", "") if m2.correction else ""
        run2_facts = "".join(_fact_obs_card(o, True) for o in journey.run2.factual_observations)
        run2_citations = "".join(_citation_card(o, True) for o in journey.run2.citation_observations)
        correction_html = (
            "<p>Le relecteur (simulé) corrige la conclusion. Le moteur recalcule réellement "
            "l'ensemble du dossier sur la nouvelle version.</p>"
            '<div class="card diff">'
            f"<p><strong>Avant :</strong> <code>{_esc(before)}</code></p>"
            f"<p><strong>Après :</strong> <code>{_esc(after)}</code></p>"
            f"<p><strong>Nouvelle version :</strong> {_esc(m2.brief_version_id)}-corrige · "
            f"nouvelle empreinte <code>{_esc(journey.run2.representation_sha256[:12])}…</code> "
            f"(ancienne <code>{_esc(journey.run1.representation_sha256[:12])}…</code>)</p>"
            "</div>"
            "<p><strong>Revérification après correction (nouvelle exécution réelle) :</strong></p>"
            f"{run2_citations}{run2_facts}"
        )

    run1_citations = "".join(_citation_card(o, False) for o in run1.citation_observations)
    run1_facts = "".join(_fact_obs_card(o, False) for o in run1.factual_observations)
    summary = journey.summary

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>CaseProof — Démonstration : {_esc(meta.title)}</title>
<style>
  body {{ font-family: -apple-system, 'Segoe UI', sans-serif; margin: 0; color: #1a1a2e; background: #f4f4f8; }}
  .page {{ max-width: 880px; margin: 0 auto; padding: 24px 20px 64px; }}
  .banner {{ background: #fff3cd; border: 1px solid #e0a800; border-radius: 8px; padding: 14px 18px; margin: 16px 0 24px; }}
  .banner strong {{ color: #8a5a00; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 4px; }}
  h2 {{ font-size: 1.15rem; margin: 32px 0 12px; border-bottom: 2px solid #d5d5e0; padding-bottom: 6px; }}
  h3 {{ font-size: 1rem; margin: 0 0 8px; }}
  h3 small {{ color: #777; font-weight: normal; }}
  .meta {{ color: #555; font-size: .9rem; }}
  .card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 14px 18px; margin: 12px 0; }}
  .card.diff {{ background: #fdf6ec; }}
  .decision {{ background: #eef4ff; border-left: 3px solid #4477cc; padding: 8px 12px; margin-top: 10px; border-radius: 0 6px 6px 0; }}
  .chip {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .8rem; font-weight: 600; color: #fff; }}
  .chip.pass {{ background: #2e7d32; }} .chip.fail {{ background: #c62828; }}
  .chip.undetermined {{ background: #ef6c00; }} .chip.unverified {{ background: #616161; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; font-size: .88rem; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #ececf4; }}
  code {{ background: #eee; padding: 1px 5px; border-radius: 4px; font-size: .85em; }}
  a {{ color: #2a5db0; word-break: break-all; }}
  .stats span {{ margin-right: 16px; }}
  .footnote {{ color: #555; font-size: .85rem; margin-top: 40px; border-top: 1px solid #ccc; padding-top: 12px; }}
</style>
</head>
<body>
<div class="page">
  <h1>CaseProof — Démonstration</h1>
  <p class="meta">{_esc(meta.title)} · généré le {_esc(generated_at)} · moteur {_esc(DEMO_RUNNER_VERSION)}</p>
  <div class="banner">
    <strong>Démonstration, pas une validation juridique.</strong>
    Chaque résultat de cette page est produit par une exécution réelle du moteur CaseProof
    au moment de la génération ; ce n'est pas un enregistrement rejoué.
    Le dossier, les faits et la relecture sont des exemples créés pour la démonstration :
    aucun avocat n'a validé ces règles, ces faits ou ces décisions. Ce résultat ne constitue
    ni un conseil juridique, ni le pilote (tâche 7), ni une couverture du droit belge.
    {_esc(meta.audience_note)}
  </div>

  <h2>1. Le document analysé</h2>
  <div class="card">
    <p><strong>Fichier :</strong> {_esc(meta.brief)} — <em>{_esc(m2.brief_label or 'document de démonstration (synthétique)')}</em></p>
    <p><strong>Couverture du lecteur Word</strong> (mesure réelle, tâche 6 ; sha256 <code>{_esc(coverage["sha256"][:12])}…</code>) :</p>
    {omitted_html}
  </div>

  <h2>2. Le corpus de référence (sources publiques réelles)</h2>
  <p class="meta">{len(corpus.records)} article(s) ingéré(s), {len(corpus.failures)} échec(s) d'ingestion,
     {len(corpus.ambiguous_versions)} version(s) ambiguë(s). Originals préservés, empreinte vérifiée.</p>
  <table>
    <tr><th>Texte</th><th>Langue</th><th>Version déclarée</th><th>Source</th><th>Empreinte</th></tr>
    {article_rows}
  </table>

  <h2>3. Les pièces du dossier</h2>
  <p class="meta">Registre de pièces révision {m2.register.revision} — dans le produit, chaque pièce est confirmée par l'utilisateur.</p>
  <table>
    <tr><th>Pièce</th><th>Version</th><th>Origine</th><th>Empreinte</th></tr>
    {source_rows}
  </table>

  <h2>4. Vérification des conclusions contre les pièces</h2>
  <p class="meta">Exécution réelle du moteur de vérification unifiée : citations exactes et valeurs factuelles
     comparées uniquement dans le passage source cité. Instantané <code>{_esc(run1.snapshot_hash[:12])}…</code></p>
  {run1_citations}
  {run1_facts}

  <h2>5. La relecture (simulée)</h2>
  {review_html}
  <p class="meta">Décisions : {summary.get('confirmed_candidate', 0)} confirmée(s),
     {summary.get('dismissed', 0)} écartée(s), {summary.get('needs_information', 0)} en attente d'information.</p>

  <h2>6. Correction et revérification</h2>
  {correction_html}

  <h2>7. Les règles de fond (moteur déterministe)</h2>
  <p class="meta">Faits saisis pour la démonstration (extraction simulée) :</p>
  <table>
    <tr><th>Fait</th><th>Valeur</th><th>État</th></tr>
    {fact_rows}
  </table>
  <p class="stats meta">
    <span>{_status_chip(RuleStatus.PASS)} {counts[RuleStatus.PASS]}</span>
    <span>{_status_chip(RuleStatus.FAIL)} {counts[RuleStatus.FAIL]}</span>
    <span>{_status_chip(RuleStatus.UNDETERMINED)} {counts[RuleStatus.UNDETERMINED]}</span>
    <span>{_status_chip(RuleStatus.UNVERIFIED)} {counts[RuleStatus.UNVERIFIED]}</span>
  </p>
  {''.join(result_cards)}

  <h2>8. Ce qui reste à valider</h2>
  <ul>
    <li>Les règles, faits, pièces et décisions de cette démonstration ne sont pas approuvés par un avocat.</li>
    <li>La conséquence d'une dérogation (export / état « prêt avec exceptions ») est une décision produit ouverte (tâche 2).</li>
    <li>La transmission reste verrouillée à ce stade du produit (autorité M4) : <code>ready_for_release = {str(journey.release_ready)}</code>.</li>
    <li>Le pilote réel (tâche 7) attend un avocat partenaire, de vrais documents et sa décision.</li>
    <li>Aucune donnée n'est persistée ni envoyée ; ce rapport est un artefact local généré à la demande.</li>
  </ul>

  <p class="footnote">CaseProof — vérification déterministe de conclusions contre des sources choisies.
     Les sources listées en sections 2 et 3 sont les seules références utilisées par le moteur.</p>
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dossier", required=True, type=Path, help="demo dossier directory")
    parser.add_argument("--out", required=True, type=Path, help="HTML report output path")
    parser.add_argument("--json-out", type=Path, default=None, help="optional JSON run summary")
    args = parser.parse_args(argv)

    try:
        run = _evaluate(args.dossier)
    except (DemoDossierError, CorpusError) as exc:
        print(f"demo dossier rejected: {exc}", file=sys.stderr)
        return 2

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    report = render_html(run, generated_at=generated_at)
    args.out.write_text(report, encoding="utf-8")

    journey: M2Journey = run["journey"]
    results: list[RuleResult] = run["results"]
    summary = {
        "runner": DEMO_RUNNER_VERSION,
        "generated_at": generated_at,
        "report_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
        "articles": len(run["corpus"].records),
        "ingestion_failures": len(run["corpus"].failures),
        "rule_statuses": {status.value: sum(1 for r in results if r.status is status) for status in RuleStatus},
        "rule_decisions": len(run["decisions"]),
        "m2_run1": {
            "citations": [o.state.value for o in journey.run1.citation_observations],
            "facts": [o.state.value for o in journey.run1.factual_observations],
            "snapshot": journey.run1.snapshot_hash[:12],
        },
        "m2_recheck": (
            None if journey.run2 is None else {
                "facts": [o.state.value for o in journey.run2.factual_observations],
                "snapshot": journey.run2.snapshot_hash[:12],
            }
        ),
        "release_ready": journey.release_ready,
    }
    if args.json_out is not None:
        args.json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
