"""Executable offline NL synthetic M1 source normalization → unified M2 check.

No real signed Auth, customer data, LLM, storage migration, court output or UI.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from application.documents.intake import CapturedDocument
from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.factual_values import FactAssertion, FactKind, FactRole, FactState
from application.litigation.library import EvidenceIndexer
from application.litigation.review_cycle import CorrectionProposal, preview_correction, revert_correction
from application.litigation.unified_review import (
    BriefRepresentation,
    ObservationReview,
    ReviewDisposition,
    SourceScope,
    run_unified_check,
    verification_record,
)
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion


def main() -> None:
    text = "De betaling van €12500 gebeurde op 22 mei 2026."
    assertion = "De betaling van €14500 gebeurde op 12 mei 2026."
    original = text.encode()
    source = SourceVersion(
        "doc-nl-1", "source-v1", sha256(original).hexdigest(), original,
        datetime(2026, 10, 26, tzinfo=UTC), "text/plain",
    )
    preview = EvidenceIndexer(LimitedDocumentParser()).preview(
        CapturedDocument("s1", source),
    )
    register = ExhibitRegister(1, (
        ExhibitEntry("ex-1", "Stuk 1", (ExhibitPage("s1", "source-v1", printed_page=1),),
                     ("Pièce 1",), confirmed=True),
    ))
    brief = VersionedBrief(
        "matter-synthetic", "brief-v1", sha256(assertion.encode()).hexdigest(),
        (DraftReference("ref-1", "Pièce 1", None),),
    )

    def represented(value: str, version: str) -> BriefRepresentation:
        return BriefRepresentation(
            VersionedBrief(brief.case_id, version, sha256(value.encode()).hexdigest(),
                           brief.references),
            value, sha256(value.encode()).hexdigest(), "synthetic-text-parser-v1",
            (
                FactAssertion("amount", "ref-1", value, 0, len(value),
                              FactKind.MONEY, FactRole.PAYMENT, "nl", "nl"),
                FactAssertion("date", "ref-1", value, 0, len(value),
                              FactKind.DATE, FactRole.PAYMENT, "nl", "nl"),
            ),
        )

    kwargs = {
        "register": register, "previews": (preview,),
        "source_scope": SourceScope((("s1", "source-v1"),)),
        "authorized_case_id": "matter-synthetic", "authorized_register_revision": 1,
    }
    first = run_unified_check(representation=represented(assertion, "brief-v1"), **kwargs)
    assert sum(x.state is FactState.DIFFERENCE for x in first.factual_observations) == 2
    review = ObservationReview(
        "fact:amount", "synthetic-reviewer", ReviewDisposition.NEEDS_INFORMATION,
        "Validate the confirmed exhibit.",
    )
    report = json.loads(verification_record(first, reviews=(review,)))
    assert not report["professional_certificate"] and report["scope_complete"]
    start = assertion.index("€14500")
    proposal = CorrectionProposal(
        "fact:amount", "synthetic-reviewer", first.snapshot_hash,
        "brief-v1", sha256(assertion.encode()).hexdigest(),
        start, start + len("€14500"), "€14500", "€12500",
        "Propose corrected amount only after source review.",
    )
    updated = preview_correction(run=first, text=assertion, proposal=proposal)
    assert revert_correction(preview=updated, current_text=updated.proposed_text,
                             proposal=proposal) == assertion
    second = run_unified_check(representation=represented(updated.proposed_text, "brief-v2"), **kwargs)
    assert second.snapshot_hash != first.snapshot_hash
    assert sum(x.state is FactState.DIFFERENCE for x in second.factual_observations) == 1
    result = {
        "schema": "caseproof-m2-headless-fixture-v1",
        "mode": "offline_synthetic_only",
        "language": "nl",
        "source_sha256": source.sha256_hex,
        "first_check_snapshot": first.snapshot_hash,
        "rechecked_snapshot": second.snapshot_hash,
        "original_candidate_differences": 2,
        "after_amount_correction_candidates": 1,
        "scope_complete": report["scope_complete"],
        "caseproof_verified_legal_truth": False,
        "customer_release_authorized": False,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
