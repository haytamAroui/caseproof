"""KRN-107: traceable, read-only coverage/evidence provenance observations.

Binds KRN-101/104/106 identities to the existing v1 in-memory hash chain.
Observations describe captured state; they NEVER commit state, authenticate
actors, approve findings, or supply the atomic audit required in production.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from threading import RLock

from packages.evidence_kernel.domain.coverage import (
    CoverageEvaluator,
    CoverageManifest,
    CoveragePolicy,
    ExpectedSource,
)
from packages.evidence_kernel.domain.finding_links import FindingLinkNotFound
from packages.evidence_kernel.domain.provenance import (
    InMemoryProvenanceLedger,
    ProvenanceIntegrityError,
)
from packages.evidence_kernel.domain.source_versions import SourceRecordNotFound

SCHEMA = "krn107-provenance-snapshot-v1"
EVENT_KIND = "reference.provenance_observed"


class BindingError(ValueError):
    """Invalid reference observation input or unsupported metadata."""


class BindingStale(BindingError):
    """The captured packet no longer describes the observed current revisions."""


class BindingConflict(BindingError):
    """An idempotency key was reused for a different observation."""


class BindingNotFound(KeyError):
    """Receipt is not accessible in this tenant namespace."""


class ObservationAction(StrEnum):
    SNAPSHOT = "snapshot"
    REVIEW_NOTE_PROPOSED = "review_note_proposed"
    REVIEW_DISAGREEMENT_PROPOSED = "review_disagreement_proposed"


def _required(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise BindingError(f"{name} must be nonempty")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceLineage:
    source_id: str
    state: str
    document_id: str | None
    version_id: str | None
    source_sha256_hex: str | None
    # All last successful, currently readable representations, with their hashes.
    representation_digests: tuple[tuple[str, str], ...]
    latest_attempt_id: str | None


@dataclass(frozen=True, slots=True)
class LinkLineage:
    link_id: str
    finding_id: str
    statement_revision: int
    assessment_revision: int
    available: bool
    statement_sha256_hex: str = ""
    anchor_id: str = ""
    document_id: str = ""
    source_version_id: str = ""
    source_sha256_hex: str = ""
    representation_id: str = ""
    representation_sha256_hex: str = ""
    expected_content_sha256_hex: str = ""
    citation_resolution: str = ""
    content_fidelity: str = ""
    semantic_relation: str = ""
    link_sufficiency: str = ""
    assessor_kind_claim: str = ""
    assessor_reference_claim: str = ""
    assessor_method_version: str = ""
    assessment_timestamp: str = ""


@dataclass(frozen=True, slots=True)
class IssueLineage:
    issue_id: str
    status: str
    required_source_ids: tuple[str, ...]
    required_finding_ids: tuple[str, ...]
    links: tuple[LinkLineage, ...]


@dataclass(frozen=True, slots=True)
class CaseProvenanceSnapshot:
    """Only identifiers/statuses/digests; no raw source, quote, statement or rationale."""

    case_id: str
    scope_version: int
    manifest_revision: int
    policy_version: str
    ordinary_complete: bool
    blockers: tuple[tuple[str, str], ...]
    sources: tuple[SourceLineage, ...]
    issues: tuple[IssueLineage, ...]
    schema_version: str = SCHEMA

    @property
    def fingerprint(self) -> str:
        return _fingerprint(asdict(self))


@dataclass(frozen=True, slots=True)
class ProvenanceReceipt:
    """In-memory correlation with a hash-chain event, not durable audit."""

    event_id: str
    tenant_scope: str
    idempotency_key: str
    event_hash: str
    sequence: int
    input_fingerprint: str
    packet: CaseProvenanceSnapshot
    action: ObservationAction
    note_sha256_hex: str
    actor_reference_claim: str
    recorded_at: str


@dataclass
class InMemoryProvenanceBridge:
    """Read and label KRN-106/104 observations; NEVER mutate their ledgers.

    A service boundary must authenticate tenant and actor. The underlying
    provenance ledger is only tamper-evident while independently retained:
    privileged mutation, chain truncation and store loss are not prevented.
    """

    coverage: CoverageEvaluator
    events: InMemoryProvenanceLedger
    _receipts: dict[tuple[str, str], ProvenanceReceipt] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def _source_trace(self, tenant: str, source: ExpectedSource) -> SourceLineage:
        source_hash: str | None = None
        rep_hashes: list[tuple[str, str]] = []
        if source.document_id is not None and source.version_id is not None:
            try:
                original = self.coverage.findings.evaluator.resolver.sources.get_source(
                    tenant, source.document_id, source.version_id
                )
                source_hash = original.sha256_hex
                if source.attempts:
                    for rep_id in source.attempts[-1].representation_ids:
                        try:
                            rep = self.coverage.findings.evaluator.resolver.sources.get_representation_for_source(
                                tenant, source.document_id, source.version_id, rep_id
                            )
                        except SourceRecordNotFound:
                            continue
                        rep_hashes.append((rep_id, rep.sha256_hex))
            except SourceRecordNotFound:
                pass
        return SourceLineage(
            source.source_id, source.state.value, source.document_id, source.version_id,
            source_hash, tuple(rep_hashes),
            source.attempts[-1].attempt_id if source.attempts else None,
        )

    def _link_trace(self, tenant: str, ref: object) -> LinkLineage:
        # Only called with immutable KRN-106 LinkUse.
        from packages.evidence_kernel.domain.coverage import LinkUse

        if not isinstance(ref, LinkUse):
            raise BindingError("typed evidence-link selector required")
        unavailable = LinkLineage(
            ref.link_id, ref.finding_id, ref.statement_revision, ref.assessment_revision, False
        )
        try:
            history = self.coverage.findings.link_history(tenant, ref.link_id)
            record = history[-1]
            current = self.coverage.findings.latest_statement(tenant, ref.finding_id)
        except FindingLinkNotFound:
            return unavailable
        if (
            record.assessment_revision != ref.assessment_revision
            or record.statement.finding_id != ref.finding_id
            or record.statement.revision != ref.statement_revision
            or current != record.statement
        ):
            return unavailable
        anchor = record.anchor
        sem = record.semantic
        return LinkLineage(
            ref.link_id, ref.finding_id, ref.statement_revision, ref.assessment_revision, True,
            record.statement.statement_sha256_hex, anchor.anchor_id, anchor.document_id,
            anchor.version_id, anchor.source_sha256_hex, anchor.representation_id,
            anchor.representation_sha256_hex, record.expected_content_sha256_hex,
            record.fidelity.citation_resolution.value,
            record.fidelity.content_fidelity.value,
            sem.relation.value, sem.sufficiency.value, sem.assessor_kind.value,
            sem.assessor_reference, sem.assessment_method_version, sem.assessed_at.isoformat(),
        )

    def capture(
        self, tenant_scope: str, case_id: str, policy: CoveragePolicy
    ) -> CaseProvenanceSnapshot:
        _required(tenant_scope, "trusted tenant scope")
        _required(case_id, "case_id")
        if not isinstance(policy, CoveragePolicy):
            raise BindingError("typed coverage policy required")
        manifest: CoverageManifest = self.coverage.manifests.current(tenant_scope, case_id)
        evaluation = self.coverage.evaluate(tenant_scope, manifest, policy)
        # A stale/mismatched evaluator result is not a valid snapshot basis.
        if (
            evaluation.manifest_revision != manifest.manifest_revision
            or evaluation.policy_version != policy.version
        ):
            raise BindingStale("manifest or policy changed during capture")
        issue_status = {item.issue_id: item.status.value for item in evaluation.issues}
        sources = tuple(self._source_trace(tenant_scope, src) for src in manifest.sources)
        issues = tuple(
            IssueLineage(
                issue.issue_id,
                issue_status.get(issue.issue_id, "unresolved"),
                issue.source_ids, issue.finding_ids,
                tuple(self._link_trace(tenant_scope, ref) for ref in issue.relied_on_links),
            )
            for issue in manifest.issues
        )
        result = CaseProvenanceSnapshot(
            manifest.case_id, manifest.scope_version, manifest.manifest_revision,
            manifest.policy_version, evaluation.ordinary_complete,
            tuple((block.reason.value, block.subject_id) for block in evaluation.blockers),
            sources, issues,
        )
        # Read/read reconciliation; this is not an atomic write or durability guarantee.
        if self.coverage.manifests.current(tenant_scope, case_id) != manifest:
            raise BindingStale("manifest revised during capture")
        if self.coverage.evaluate(tenant_scope, manifest, policy) != evaluation:
            raise BindingStale("coverage or assessment revisions changed during capture")
        if tuple(self._link_trace(tenant_scope, ref) for issue in manifest.issues
                 for ref in issue.relied_on_links) != tuple(
            trace for issue in issues for trace in issue.links
        ):
            raise BindingStale("link attribution revised during capture")
        if tuple(self._source_trace(tenant_scope, s) for s in manifest.sources) != sources:
            raise BindingStale("source lineage revised during capture")
        return result

    def record(
        self,
        tenant_scope: str,
        expected: CaseProvenanceSnapshot,
        *,
        event_id: str,
        idempotency_key: str,
        actor_reference_claim: str,
        action: ObservationAction,
        occurred_at: datetime,
        note: str = "",
    ) -> ProvenanceReceipt:
        """Append one *observation* to the v1 hash chain, never a review approval.

        Same idempotency key + identical content returns the original record
        even after subsequent case revisions. A divergent replay conflicts.
        """
        _required(tenant_scope, "trusted tenant scope")
        _required(event_id, "event_id")
        _required(idempotency_key, "idempotency_key")
        _required(actor_reference_claim, "actor reference claim")
        if not isinstance(expected, CaseProvenanceSnapshot) or expected.schema_version != SCHEMA:
            raise BindingError("supported immutable provenance snapshot required")
        if not isinstance(action, ObservationAction):
            raise BindingError("typed observation action required")
        if not isinstance(occurred_at, datetime) or occurred_at.tzinfo is None or (
            occurred_at.utcoffset() != timedelta(0)
        ):
            raise BindingError("event timestamp must be timezone-aware UTC")
        if not isinstance(note, str):
            raise BindingError("note must be text")
        if action is ObservationAction.SNAPSHOT and note:
            raise BindingError("snapshot observation cannot carry a review note")
        if action is not ObservationAction.SNAPSHOT and not note.strip():
            raise BindingError("review proposal requires a nonempty note")

        # Domain-separated digest; never copy raw review text into events/receipt.
        note_hash = sha256(b"krn107-note-v1\x00" + note.encode("utf-8")).hexdigest()
        input_hash = _fingerprint({
            "schema": SCHEMA, "packet": expected.fingerprint, "action": action.value,
            "actor_ref_claim": actor_reference_claim, "note_sha256": note_hash,
        })
        key = (tenant_scope, idempotency_key)
        with self._lock:
            prior = self._receipts.get(key)
            if prior is not None:
                if prior.input_fingerprint != input_hash:
                    raise BindingConflict("idempotency key reused for different observation")
                if not self.verify_record(tenant_scope, idempotency_key):
                    raise ProvenanceIntegrityError("previous observation no longer verifies")
                return prior

            current = self.capture(tenant_scope, expected.case_id, CoveragePolicy(expected.policy_version))
            if current != expected:
                raise BindingStale("expected evidence and coverage packet is stale")
            payload = {
                "schema": SCHEMA,
                "case_id": expected.case_id,
                "scope_version": expected.scope_version,
                "manifest_revision": expected.manifest_revision,
                "policy_version": expected.policy_version,
                "packet_sha256": expected.fingerprint,
                "input_sha256": input_hash,
                "action": action.value,
                "note_sha256": note_hash,
            }
            event = self.events.append(
                tenant_scope, event_id, EVENT_KIND, expected.case_id,
                "unverified:" + actor_reference_claim, payload, occurred_at=occurred_at,
            )
            result = ProvenanceReceipt(
                event_id, tenant_scope, idempotency_key, event.event_hash, event.sequence,
                input_hash, expected, action, note_hash, actor_reference_claim,
                event.occurred_at,
            )
            self._receipts[key] = result
            return result

    def verify_record(self, tenant_scope: str, idempotency_key: str) -> bool:
        """Verify the locally retained receipt against the untruncated event chain.

        A fully erased in-memory ledger and receipt store cannot be detected.
        """
        _required(tenant_scope, "trusted tenant scope")
        _required(idempotency_key, "idempotency_key")
        receipt = self._receipts.get((tenant_scope, idempotency_key))
        if receipt is None:
            raise BindingNotFound("observation receipt unavailable")
        if not self.events.verify(tenant_scope):
            return False
        matches = tuple(
            event for event in self.events.history(tenant_scope)
            if event.event_id == receipt.event_id
        )
        if len(matches) != 1:
            return False
        event = matches[0]
        if (
            event.event_hash != receipt.event_hash or event.sequence != receipt.sequence
            or event.subject_id != receipt.packet.case_id or event.kind != EVENT_KIND
            or event.actor_id != "unverified:" + receipt.actor_reference_claim
            or event.occurred_at != receipt.recorded_at
        ):
            return False
        try:
            payload = json.loads(event.payload_json)
        except (ValueError, TypeError):
            return False
        return bool(payload == {
            "schema": SCHEMA, "case_id": receipt.packet.case_id,
            "scope_version": receipt.packet.scope_version,
            "manifest_revision": receipt.packet.manifest_revision,
            "policy_version": receipt.packet.policy_version,
            "packet_sha256": receipt.packet.fingerprint,
            "input_sha256": receipt.input_fingerprint,
            "action": receipt.action.value, "note_sha256": receipt.note_sha256_hex,
        })
