"""M2 headless integrated regression: exact evidence, NL/FR/EN values and review.

No real signed Supabase sessions, customer data, hosted persistence or legal review.
"""
import json
from dataclasses import replace
from hashlib import sha256

import pytest

from application.litigation.brief_checks import (
    CitationCheckState,
    DraftReference,
    VersionedBrief,
)
from application.litigation.factual_values import (
    FactAssertion,
    FactError,
    FactKind,
    FactRole,
    FactState,
    _money_value,
)
from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.review_cycle import (
    CorrectionProposal,
    ReviewPacket,
    preview_correction,
    ready_for_release,
    revert_correction,
    revise_review,
)
from application.litigation.unified_review import (
    BriefRepresentation,
    ObservationReview,
    ReviewDisposition,
    SourceScope,
    VerificationError,
    run_unified_check,
    verification_record,
)
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister


def rig(
    brief_text: str = "Le paiement de €14500 a été effectué le 12 mai 2026.",
    source_text: str = "Le paiement de €12500 a été effectué le 22 mai 2026.",
    *, language: str = "fr", source_language: str = "fr",
    quote: str | None = None, page: int | None = 1,
    state: str = "ready", label: str = "Pièce 1",
):
    entry = ExhibitEntry("ex-1", "Pièce 1", (ExhibitPage("src-1", "v1", 1),),
                         ("Stuk 1",), confirmed=True)
    register = ExhibitRegister(4, (entry,))
    reference = DraftReference("ref-1", label, quote, page)
    brief = VersionedBrief("case-1", "brief-v1", sha256(b"original brief").hexdigest(), (reference,))
    claims = tuple(
        FactAssertion("fact-"+kind.value, "ref-1", brief_text, 0, len(brief_text),
                      kind, FactRole.PAYMENT, language, source_language)
        for kind in (FactKind.MONEY, FactKind.DATE)
    )
    b = BriefRepresentation(brief, brief_text, sha256(brief_text.encode()).hexdigest(),
                            "bounded-synthetic-v1", claims)
    row = EvidenceRow(
        "src-1", "doc-1", "v1", sha256(source_text.encode()).hexdigest(),
        "application/pdf", state, "bounded-parser-v1", "repr-1",
        (), ("needs_ocr",) if state != "ready" else (),
    )
    p = EvidencePreview(row, source_text, ((0, len(source_text), "pdf-page-1", 0),))
    scope = SourceScope((("src-1", "v1"),))
    return b, register, (p,), scope


def check(*args, **kwargs):
    b, register, previews, scope = rig(*args, **kwargs)
    return run_unified_check(
        representation=b, register=register, previews=previews,
        source_scope=scope, authorized_case_id="case-1",
        authorized_register_revision=4,
    )


def test_quote_free_french_brief_finds_two_anchored_candidates():
    run = check()
    assert len(run.citation_observations) == 1
    assert run.citation_observations[0].state is CitationCheckState.NO_QUOTATION
    assert {x.kind for x in run.factual_observations} == {FactKind.DATE, FactKind.MONEY}
    assert all(x.state is FactState.DIFFERENCE for x in run.factual_observations)
    assert all(x.source_id == "src-1" and x.source_version_id == "v1" for x in run.factual_observations)
    assert all(x.source_sha256 and x.source_locator == "pdf-page-1" and x.source_pdf_page == 1
               for x in run.factual_observations)
    assert all(x.source_start is not None and x.source_end is not None for x in run.factual_observations)
    assert run.incomplete == ()
    assert len(run.snapshot_hash) == 64


def test_clean_quote_free_dossier_produces_zero_candidate_differences():
    s = "Le paiement de €12500 a été effectué le 22 mai 2026."
    run = check(s, s)
    assert all(x.state is FactState.MATCH for x in run.factual_observations)
    assert all(x.state is CitationCheckState.NO_QUOTATION for x in run.citation_observations)
    data = json.loads(verification_record(run))
    assert data["scope_complete"] is True
    assert data["professional_certificate"] is False
    assert data["filing_status"] == "not_assessed"
    assert data["legal_conclusion"] == "not_assessed"


@pytest.mark.parametrize(("lang", "brief", "source"), [
    ("nl", "De betaling van €14500 gebeurde op 12 mei 2026.",
     "De betaling van €12500 gebeurde op 22 mei 2026."),
    ("en", "The payment of €14500 was made on 12 May 2026.",
     "The payment of €12500 was made on 22 May 2026."),
    ("fr", "Le paiement de €14500 a été effectué le 12 mai 2026.",
     "Le paiement de €12500 a été effectué le 22 mai 2026."),
])
def test_nl_fr_en_payment_amount_and_dates_have_same_role_anchors(lang, brief, source):
    run = check(brief, source, language=lang, source_language=lang)
    assert all(x.state is FactState.DIFFERENCE for x in run.factual_observations)


def test_mixed_language_source_can_be_explicit_and_safe():
    b = "De betaling van €14500 gebeurde op 12 mei 2026."
    s = "Le paiement de €12500 a été effectué le 22 mai 2026."
    run = check(b, s, language="nl", source_language="fr")
    assert all(x.state is FactState.DIFFERENCE for x in run.factual_observations)


@pytest.mark.parametrize(("brief", "source"), [
    ("Le paiement de €14500 a été effectué le 12 mai 2026.",
     "Date d'échéance : €12500 le 22 mai 2026."),
    ("Le paiement de €14500 a été effectué le 12 mai 2026.",
     "Le paiement de €12500 et €1500 a été effectué le 22 mai 2026."),
    ("Le paiement de €14500 a été effectué le 12 mai 2026.",
     "Le paiement de €12500 net a été effectué le 22 mai 2026."),
    ("Le paiement de €14500 a été effectué le 12 mai 2026.",
     "Le paiement de €12500 peut-être effectué le 22 mai 2026."),
    ("Le paiement de €14500 a été effectué le 12 mai 2026.",
     "La facture de €12500 date du 22 mai 2026."),
])
def test_unrelated_roles_multiple_values_vat_and_uncertainty_abstain(brief, source):
    run = check(brief, source)
    assert not any(x.state is FactState.DIFFERENCE for x in run.factual_observations)


def test_unmatched_or_unconfirmed_exhibit_never_runs_a_factual_comparison():
    b, reg, previews, scope = rig()
    missing = replace(b, brief=replace(
        b.brief, references=(replace(b.brief.references[0], exhibit_label="Stuk 99"),),
    ))
    run = run_unified_check(representation=missing, register=reg, previews=previews,
                            source_scope=scope, authorized_case_id="case-1",
                            authorized_register_revision=4)
    assert run.citation_observations[0].state is CitationCheckState.REFERENCE_UNRESOLVED
    assert all(x.state is FactState.NOT_ASSESSED for x in run.factual_observations)


def test_partial_pdf_cannot_claim_contradiction():
    b, reg, previews, scope = rig(state="partial")
    run = run_unified_check(representation=b, register=reg, previews=previews,
                            source_scope=scope, authorized_case_id="case-1",
                            authorized_register_revision=4)
    assert all(x.state is FactState.NOT_ASSESSED for x in run.factual_observations)
    assert run.incomplete == (("src-1", "v1"),)


def test_missing_source_is_unknown_and_scope_not_complete():
    b, reg, _, scope = rig()
    run = run_unified_check(representation=b, register=reg, previews=(),
                            source_scope=scope, authorized_case_id="case-1",
                            authorized_register_revision=4)
    assert all(x.state is FactState.NOT_ASSESSED for x in run.factual_observations)
    assert not json.loads(verification_record(run))["scope_complete"]


def test_matter_and_register_snapshot_mismatch_fail_closed():
    b, reg, previews, scope = rig()
    for case, revision in (("other", 4), ("case-1", 3)):
        with pytest.raises(VerificationError):
            run_unified_check(representation=b, register=reg, previews=previews,
                              source_scope=scope, authorized_case_id=case,
                              authorized_register_revision=revision)


def test_duplicate_or_extra_source_fails_closed():
    b, reg, previews, scope = rig()
    with pytest.raises(VerificationError):
        run_unified_check(representation=b, register=reg, previews=previews+previews,
                          source_scope=scope, authorized_case_id="case-1",
                          authorized_register_revision=4)
    with pytest.raises(VerificationError):
        run_unified_check(representation=b, register=reg, previews=previews,
                          source_scope=SourceScope((("other", "v1"),)),
                          authorized_case_id="case-1", authorized_register_revision=4)


def test_stale_or_fabricated_claim_span_fails_closed():
    b, reg, previews, scope = rig()
    invalid_claim = replace(b.claims[0], text_start=1, text_end=len(b.text)+1)
    with pytest.raises(VerificationError):
        replace(b, claims=(invalid_claim,))
    with pytest.raises(FactError):
        replace(b.claims[0], kind="made_up")


def test_report_hash_reproducibility_and_disposition_binding():
    run = check()
    assert run.snapshot_hash == check().snapshot_hash
    review = ObservationReview("fact:fact-money", "reviewer-1",
                               ReviewDisposition.NEEDS_INFORMATION, "Verify payment.")
    raw = verification_record(run, reviews=(review,))
    assert b"reviewer-1" in raw
    with pytest.raises(VerificationError):
        verification_record(run, reviews=(review, review))
    with pytest.raises(VerificationError):
        verification_record(run, reviews=(replace(review, observation_id="fact:ghost"),))


def test_review_is_expected_revision_cas_and_not_legal_approval():
    run = check()
    packet = ReviewPacket(run.snapshot_hash, 0)
    decision = ObservationReview("fact:fact-money", "reviewer-1",
                                 ReviewDisposition.CONFIRMED, "Checked original.")
    next_packet = revise_review(run=run, packet=packet, expected_revision=0, decision=decision)
    assert next_packet.revision == 1
    assert not ready_for_release(run, next_packet)
    with pytest.raises(VerificationError):
        revise_review(run=run, packet=next_packet, expected_revision=0, decision=decision)
    with pytest.raises(VerificationError):
        ready_for_release(replace(run, snapshot_hash="0"*64), next_packet)


def test_correction_preview_reversible_without_mutating_evidence():
    b, reg, previews, scope = rig()
    run = run_unified_check(representation=b, register=reg, previews=previews,
                            source_scope=scope, authorized_case_id="case-1",
                            authorized_register_revision=4)
    old = "€14500"
    start = b.text.index(old)
    proposal = CorrectionProposal(
        "fact:fact-money", "reviewer-1", run.snapshot_hash,
        b.brief.version_id, b.text_sha256, start, start+len(old),
        old, "€12500", "Align with cited payment record.",
    )
    candidate = preview_correction(run=run, text=b.text, proposal=proposal)
    assert candidate.proposed_text != b.text
    assert "€12500" in candidate.proposed_text
    assert revert_correction(preview=candidate,
                             current_text=candidate.proposed_text,
                             proposal=proposal) == b.text
    with pytest.raises(VerificationError):
        preview_correction(run=run, text=b.text+"changed", proposal=proposal)
    with pytest.raises(VerificationError):
        revert_correction(preview=candidate, current_text=b.text, proposal=proposal)
    # Rechecking is a NEW brief version; no previous run or source is rewritten.
    new = replace(
        b, brief=replace(b.brief, version_id="brief-v2"),
        text=candidate.proposed_text, text_sha256=candidate.proposed_text_sha256,
        claims=tuple(replace(x, text=candidate.proposed_text,
                             text_end=len(candidate.proposed_text)) for x in b.claims),
    )
    rerun = run_unified_check(representation=new, register=reg, previews=previews,
                              source_scope=scope, authorized_case_id="case-1",
                              authorized_register_revision=4)
    assert rerun.snapshot_hash != run.snapshot_hash
    assert rerun.factual_observations[0].state is FactState.MATCH
    assert rerun.factual_observations[1].state is FactState.DIFFERENCE


@pytest.mark.parametrize(("token", "lang", "expected"), [
    ("€14.500", "nl", "14500"),
    ("EUR 14,500", "en", "14500"),
    ("€14,500", "fr", None),
    ("€14.500", "en", None),
    ("€14 500", "fr", "14500"),
    ("€14.500,00", "nl", "14500.00"),
])
def test_amount_locale_explicit_not_guessed(token, lang, expected):
    value = _money_value(token, lang)
    assert (str(value) if value is not None else None) == expected


def test_run_snapshot_changes_with_exhibit_alias_or_source_locator():
    b, register, previews, scope = rig()
    params = dict(representation=b, previews=previews, source_scope=scope,
                  authorized_case_id="case-1", authorized_register_revision=4)
    baseline = run_unified_check(register=register, **params)
    renamed = replace(register, entries=(replace(
        register.entries[0], aliases=("Stuk 1", "Bijlage A"),
    ),))
    assert baseline.snapshot_hash != run_unified_check(register=renamed, **params).snapshot_hash
    moved = replace(previews[0], spans=((0, len(previews[0].text), "changed-page-locator", 0),))
    assert baseline.snapshot_hash != run_unified_check(
        representation=b, register=register, previews=(moved,),
        source_scope=scope, authorized_case_id="case-1", authorized_register_revision=4,
    ).snapshot_hash
