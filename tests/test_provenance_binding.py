"""KRN-107 — evidence provenance bridge: reconciliation, retry, tamper, scope."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256

import pytest

from packages.evidence_kernel.domain.anchors import AnchorResolver, EvidenceAnchor, TextSpan
from packages.evidence_kernel.domain.coverage import (
    AttemptState,
    CoverageEvaluator,
    CoverageManifest,
    CoveragePolicy,
    ExpectedSource,
    InMemoryCoverageLedger,
    LinkUse,
    ProcessingAttempt,
    RequiredIssue,
    SourceState,
)
from packages.evidence_kernel.domain.fidelity import ExactQuote, FidelityEvaluator
from packages.evidence_kernel.domain.finding_links import (
    AssessorKind,
    FindingStatement,
    InMemoryFindingEvidenceLedger,
    LinkSufficiency,
    SemanticAssessmentProposal,
    SemanticRelation,
)
from packages.evidence_kernel.domain.provenance import (
    InMemoryProvenanceLedger,
    ProvenanceConflict,
    ProvenanceIntegrityError,
)
from packages.evidence_kernel.domain.provenance_binding import (
    BindingConflict,
    BindingError,
    BindingNotFound,
    BindingStale,
    InMemoryProvenanceBridge,
    ObservationAction,
)
from packages.evidence_kernel.domain.source_versions import (
    DerivedRepresentation,
    InMemorySourceRegistry,
    SourceVersion,
)

STAMP = datetime(2026, 10, 21, 20, tzinfo=UTC)
ORIGINAL = b"original confidential scanned file"
QUOTE = b"Payment was NOT received. Approved by Alice."


def sha(content: bytes) -> str:
    return sha256(content).hexdigest()


def proposed(
    relation: SemanticRelation = SemanticRelation.SUPPORTS,
    sufficiency: LinkSufficiency = LinkSufficiency.SUFFICIENT,
) -> SemanticAssessmentProposal:
    return SemanticAssessmentProposal(
        relation, sufficiency, AssessorKind.MODEL, "model-proposal-1",
        "model-method-v1", "Confidential reasoning not for logging", STAMP,
    )


def setup(
    *,
    source_state: SourceState = SourceState.PROCESSED,
    relation: SemanticRelation = SemanticRelation.SUPPORTS,
    quote: str = "Payment",
) -> tuple[InMemoryProvenanceBridge, CoverageManifest, FindingStatement, EvidenceAnchor]:
    sources = InMemorySourceRegistry()
    source = SourceVersion("doc", "v1", sha(ORIGINAL), ORIGINAL, STAMP, "application/pdf")
    representation = DerivedRepresentation(
        "ocr1", "doc", "v1", source.sha256_hex, sha(QUOTE), QUOTE,
        "text/plain", "OCR", "ocr-v1", sha(b"ocr config"),
        "unicode_codepoint_zero_based_half_open", STAMP,
    )
    sources.register_source("tenant-a", source)
    sources.register_representation("tenant-a", representation)
    findings = InMemoryFindingEvidenceLedger(FidelityEvaluator(AnchorResolver(sources)))
    finding = FindingStatement("finding", 1, "Payment has already arrived.")
    findings.register_statement("tenant-a", finding)
    anchor = EvidenceAnchor(
        "anchor", "doc", "v1", source.sha256_hex,
        "ocr1", representation.sha256_hex, TextSpan(0, 7),
    )
    findings.append_assessment(
        "tenant-a", "link", 1, finding, anchor, ExactQuote(quote),
        proposed(relation),
    )
    attempts = (
        (ProcessingAttempt("attempt-1", AttemptState.SUCCEEDED, ("ocr1",)),)
        if source_state is SourceState.PROCESSED else ()
    )
    manifest = CoverageManifest(
        "case", 1, 1, "coverage-policy-v1",
        (RequiredIssue("issue", "acceptance-v1", ("source",),
                       (LinkUse("link", 1, "finding", 1),), ("finding",)),),
        (ExpectedSource("source", "doc", "v1", source_state, attempts),),
    )
    records = InMemoryCoverageLedger()
    records.register("tenant-a", manifest)
    return (
        InMemoryProvenanceBridge(CoverageEvaluator(records, findings), InMemoryProvenanceLedger()),
        manifest, finding, anchor,
    )


def record(
    bridge: InMemoryProvenanceBridge,
    *,
    packet: object | None = None,
    key: str = "idempotency-1",
    event: str = "event-1",
    actor: str = "claimed-reviewer",
    action: ObservationAction = ObservationAction.SNAPSHOT,
    note: str = "",
    tenant: str = "tenant-a",
):
    current = packet if packet is not None else bridge.capture(
        "tenant-a", "case", CoveragePolicy("coverage-policy-v1")
    )
    return bridge.record(
        tenant, current, event_id=event, idempotency_key=key,
        actor_reference_claim=actor, action=action, note=note, occurred_at=STAMP,
    )


def test_coverage_and_assessor_lineage_are_frozen_without_raw_evidence() -> None:
    bridge, manifest, finding, anchor = setup()
    packet = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    assert packet.case_id == manifest.case_id
    assert packet.manifest_revision == 1
    assert packet.ordinary_complete is True
    assert packet.blockers == ()
    assert packet.sources[0].source_sha256_hex == anchor.source_sha256_hex
    assert packet.sources[0].representation_digests == (
        ("ocr1", anchor.representation_sha256_hex),
    )
    link = packet.issues[0].links[0]
    assert link.available
    assert link.statement_sha256_hex == finding.statement_sha256_hex
    assert link.assessment_revision == 1
    assert link.representation_id == "ocr1"
    assert link.citation_resolution == "resolved"
    assert link.content_fidelity == "matched"
    assert link.semantic_relation == "supports"
    assert link.assessor_kind_claim == "model"  # never reviewer authority
    assert link.assessor_reference_claim == "model-proposal-1"
    assert link.assessment_timestamp == STAMP.isoformat()
    assert len(packet.fingerprint) == 64
    assert "Payment was NOT received" not in repr(packet)
    assert "Confidential reasoning" not in repr(packet)


def test_faithful_quote_can_contradict_false_claim_without_being_approved() -> None:
    bridge, _, _, _ = setup(relation=SemanticRelation.CONTRADICTS)
    packet = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    assert packet.ordinary_complete is False
    assert ("contradiction_present", "issue") in packet.blockers
    assert packet.issues[0].links[0].semantic_relation == "contradicts"
    assert not hasattr(packet, "approved")


def test_missing_source_cannot_be_recorded_as_complete() -> None:
    bridge, _, _, _ = setup(source_state=SourceState.MISSING)
    snapshot = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    assert not snapshot.ordinary_complete
    assert ("source_unaccounted", "source") in snapshot.blockers
    assert snapshot.sources[0].state == "missing"
    assert snapshot.sources[0].representation_digests == ()
    receipt = record(bridge, packet=snapshot)
    assert bridge.verify_record("tenant-a", receipt.idempotency_key)


def test_mismatched_quote_keeps_fidelity_failure_in_snapshot() -> None:
    bridge, _, _, _ = setup(quote="Paid now")
    snapshot = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    assert not snapshot.ordinary_complete
    assert snapshot.issues[0].links[0].content_fidelity == "mismatched"
    assert ("link_fidelity_not_matched", "issue") in snapshot.blockers


def test_hash_chain_observation_and_receipt_verify_without_promoting() -> None:
    bridge, _, _, _ = setup()
    packet = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    receipt = record(bridge, packet=packet)
    assert receipt.packet == packet
    assert receipt.sequence == 1
    assert receipt.actor_reference_claim == "claimed-reviewer"
    assert len(receipt.input_fingerprint) == 64
    assert bridge.verify_record("tenant-a", "idempotency-1")
    events = bridge.events.history("tenant-a")
    assert len(events) == 1
    assert events[0].actor_id == "unverified:claimed-reviewer"
    assert events[0].subject_id == "case"
    assert "Payment" not in events[0].payload_json
    assert "Confidential" not in events[0].payload_json
    assert not hasattr(bridge, "approve")
    assert not hasattr(bridge, "promote")
    assert not hasattr(receipt, "approval_authority")


def test_note_proposal_stores_only_domain_separated_note_hash() -> None:
    bridge, _, _, _ = setup()
    note = "Private reviewer says further evidence may be missing"
    receipt = record(
        bridge, action=ObservationAction.REVIEW_NOTE_PROPOSED, note=note,
    )
    assert receipt.action is ObservationAction.REVIEW_NOTE_PROPOSED
    assert receipt.note_sha256_hex == sha(b"krn107-note-v1\x00" + note.encode())
    assert note not in repr(receipt)
    assert note not in bridge.events.history("tenant-a")[0].payload_json
    assert bridge.verify_record("tenant-a", receipt.idempotency_key)


def test_review_disagreement_is_a_proposal_not_a_conclusion() -> None:
    bridge, _, _, _ = setup(relation=SemanticRelation.CONTRADICTS)
    r = record(
        bridge, action=ObservationAction.REVIEW_DISAGREEMENT_PROPOSED,
        note="I disagree with the current categorization",
    )
    assert r.packet.ordinary_complete is False
    assert r.action.value == "review_disagreement_proposed"
    assert not hasattr(r, "verified_by_human")


def test_identical_idempotency_retry_returns_same_event_even_after_revision() -> None:
    bridge, _, _, anchor = setup()
    old = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    first = record(bridge, packet=old)
    stmt = bridge.coverage.findings.get_statement("tenant-a", "finding", 1)
    bridge.coverage.findings.append_assessment(
        "tenant-a", "link", 2, stmt, anchor, ExactQuote("Payment"),
        proposed(SemanticRelation.CONTRADICTS),
    )
    retry = record(bridge, packet=old, event="ignored-on-replay")
    assert retry is first
    assert len(bridge.events.history("tenant-a")) == 1
    assert bridge.verify_record("tenant-a", "idempotency-1")


@pytest.mark.parametrize(
    "diff", [
        {"actor": "other-claimed-actor"},
        {"action": ObservationAction.REVIEW_NOTE_PROPOSED, "note": "review note"},
        {"action": ObservationAction.REVIEW_DISAGREEMENT_PROPOSED, "note": "different note"},
    ],
)
def test_idempotency_collision_with_different_inputs_is_rejected(
    diff: dict[str, object],
) -> None:
    bridge, _, _, _ = setup()
    record(bridge)
    with pytest.raises(BindingConflict):
        record(bridge, **diff)  # type: ignore[arg-type]
    assert len(bridge.events.history("tenant-a")) == 1


def test_distinct_observations_form_valid_linked_history() -> None:
    bridge, _, _, _ = setup()
    a = record(bridge)
    b = record(bridge, key="key-2", event="event-2")
    assert a.sequence == 1
    assert b.sequence == 2
    assert a.event_hash != b.event_hash
    assert bridge.events.history("tenant-a")[1].previous_hash == a.event_hash
    assert bridge.verify_record("tenant-a", "key-2")


def test_duplicate_event_id_under_different_keys_is_atomic_failure() -> None:
    bridge, _, _, _ = setup()
    record(bridge)
    with pytest.raises(ProvenanceConflict):
        record(bridge, key="key-2")
    with pytest.raises(BindingNotFound):
        bridge.verify_record("tenant-a", "key-2")
    assert len(bridge.events.history("tenant-a")) == 1


def test_latest_assessment_invalidates_unrecorded_stale_packet() -> None:
    bridge, _, finding, anchor = setup()
    stale = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    bridge.coverage.findings.append_assessment(
        "tenant-a", "link", 2, finding, anchor, ExactQuote("Payment"),
        proposed(SemanticRelation.CONTRADICTS),
    )
    with pytest.raises(BindingStale):
        record(bridge, packet=stale)
    assert bridge.events.history("tenant-a") == ()


def test_new_manifest_version_invalidates_old_packet() -> None:
    bridge, manifest, _, _ = setup()
    stale = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    bridge.coverage.manifests.register(
        "tenant-a", replace(manifest, manifest_revision=2),
    )
    with pytest.raises(BindingStale):
        record(bridge, packet=stale)


def test_new_finding_statement_version_invalidates_old_packet() -> None:
    bridge, _, _, _ = setup()
    stale = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    bridge.coverage.findings.register_statement(
        "tenant-a", FindingStatement("finding", 2, "Changed case finding."),
    )
    with pytest.raises(BindingStale):
        record(bridge, packet=stale)


def test_reocr_version_does_not_silently_redirect_existing_fingerprints() -> None:
    bridge, _, _, _ = setup()
    snap = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    old_rep = bridge.coverage.findings.evaluator.resolver.sources.get_representation(
        "tenant-a", "ocr1"
    )
    next_rep = replace(
        old_rep, representation_id="ocr2", content=b"Different OCR result",
        sha256_hex=sha(b"Different OCR result"),
    )
    bridge.coverage.findings.evaluator.resolver.sources.register_representation(
        "tenant-a", next_rep
    )
    current = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    assert current.fingerprint == snap.fingerprint
    assert current.sources[0].representation_digests == (("ocr1", old_rep.sha256_hex),)


def test_revoked_source_access_blocks_stale_observation() -> None:
    bridge, _, _, _ = setup()
    stale = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    # Reference fixture simulates deletion/access revocation; not production controls.
    bridge.coverage.findings.evaluator.resolver.sources._representations.pop(
        ("tenant-a", "ocr1")
    )
    with pytest.raises(BindingStale):
        record(bridge, packet=stale)
    refreshed = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    assert refreshed.ordinary_complete is False


def test_wrong_tenant_cannot_read_other_tenant_observation_or_case() -> None:
    bridge, _, _, _ = setup()
    receipt = record(bridge)
    with pytest.raises(BindingNotFound):
        bridge.verify_record("tenant-b", receipt.idempotency_key)
    with pytest.raises(KeyError):
        bridge.capture("tenant-b", "case", CoveragePolicy("coverage-policy-v1"))
    with pytest.raises(KeyError):
        record(bridge, tenant="tenant-b", packet=receipt.packet, key="another")
    assert bridge.events.history("tenant-b") == ()


def test_tampered_provenance_chain_is_detected() -> None:
    bridge, _, _, _ = setup()
    receipt = record(bridge)
    before = bridge.events.history("tenant-a")
    bridge.events._events["tenant-a"] = (
        replace(before[0], payload_json='{"forged":"truth"}'),
    )
    assert not bridge.verify_record("tenant-a", receipt.idempotency_key)
    with pytest.raises(ProvenanceIntegrityError):
        record(bridge, key="key-2", event="event-2")


def test_chain_truncation_detected_with_locally_retained_receipt() -> None:
    bridge, _, _, _ = setup()
    record(bridge)
    bridge.events._events["tenant-a"] = ()
    assert bridge.events.verify("tenant-a") is True
    assert bridge.verify_record("tenant-a", "idempotency-1") is False
    with pytest.raises(ProvenanceIntegrityError):
        record(bridge)


def test_corrupted_locally_retained_receipt_does_not_verify() -> None:
    bridge, _, _, _ = setup()
    record(bridge)
    old = bridge._receipts[("tenant-a", "idempotency-1")]
    bridge._receipts[("tenant-a", "idempotency-1")] = replace(
        old, event_hash="0" * 64
    )
    assert bridge.verify_record("tenant-a", "idempotency-1") is False


def test_policy_mismatch_never_captures_a_success_packet() -> None:
    bridge, _, _, _ = setup()
    with pytest.raises(BindingStale):
        bridge.capture("tenant-a", "case", CoveragePolicy("not-effective-policy"))


@pytest.mark.parametrize(
    "invalid", [
        {"event_id": ""},
        {"idempotency_key": ""},
        {"actor_reference_claim": ""},
        {"action": "approved"},
        {"occurred_at": datetime(2026, 10, 21)},
        {"occurred_at": STAMP.astimezone(timezone(timedelta(hours=1)))},
    ],
)
def test_invalid_observation_fields_fail_closed(invalid: dict[str, object]) -> None:
    bridge, _, _, _ = setup()
    packet = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    valid: dict[str, object] = {
        "event_id": "evt", "idempotency_key": "key", "actor_reference_claim": "actor",
        "action": ObservationAction.SNAPSHOT, "occurred_at": STAMP,
    }
    with pytest.raises((BindingError, TypeError)):
        bridge.record("tenant-a", packet, **(valid | invalid))  # type: ignore[arg-type]
    assert bridge.events.history("tenant-a") == ()


def test_review_note_required_and_snapshot_cannot_smuggle_review_text() -> None:
    bridge, _, _, _ = setup()
    packet = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    with pytest.raises(BindingError):
        record(bridge, packet=packet, action=ObservationAction.REVIEW_NOTE_PROPOSED)
    with pytest.raises(BindingError):
        record(bridge, packet=packet, note="approved!")
    assert bridge.events.history("tenant-a") == ()


def test_forged_snapshot_never_records_a_matching_observation() -> None:
    bridge, _, _, _ = setup()
    packet = bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))
    with pytest.raises(BindingStale):
        record(bridge, packet=replace(packet, ordinary_complete=False))
    with pytest.raises(BindingStale):
        record(bridge, packet=replace(packet, policy_version="forged"))
    assert bridge.events.history("tenant-a") == ()


def test_capture_fails_on_concurrent_link_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge, _, statement, anchor = setup()
    original = InMemoryProvenanceBridge._link_trace
    injected = False

    def mutate(self: InMemoryProvenanceBridge, tenant: str, ref: object):
        nonlocal injected
        value = original(self, tenant, ref)
        if not injected:
            injected = True
            self.coverage.findings.append_assessment(
                "tenant-a", "link", 2, statement, anchor, ExactQuote("Payment"),
                proposed(SemanticRelation.CONTRADICTS),
            )
        return value

    monkeypatch.setattr(InMemoryProvenanceBridge, "_link_trace", mutate)
    with pytest.raises(BindingStale):
        bridge.capture("tenant-a", "case", CoveragePolicy("coverage-policy-v1"))


def test_legacy_provenance_and_evidence_interfaces_unchanged() -> None:
    from packages.evidence_kernel.domain.evidence import SourceReference

    bridge, _, _, _ = setup()
    assert bridge.events.verify("tenant-a")
    assert SourceReference("d", sha(ORIGINAL), "quote").document_id == "d"
