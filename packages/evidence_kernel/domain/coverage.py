"""KRN-106 — versioned issue/source coverage inventory and fail-closed evaluation.

Coverage is a declared investigation scope, NOT proof that the declaration
contains every real-world issue or source. Exclusion metadata is untrusted
and never authorizes an ordinary-complete outcome. These in-memory records
are NOT production authorization, durable storage, or approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import RLock

from packages.evidence_kernel.domain.fidelity import CitationResolution, ContentFidelity
from packages.evidence_kernel.domain.finding_links import (
    FindingEvidenceLinkRevision,
    FindingLinkNotFound,
    InMemoryFindingEvidenceLedger,
    LinkSufficiency,
    SemanticRelation,
)
from packages.evidence_kernel.domain.source_versions import SourceRecordNotFound


class CoverageError(ValueError):
    """Malformed or inconsistent declared investigation coverage."""


class CoverageConflict(CoverageError):
    """An immutable manifest version/scope cannot be reused or redefined."""


class CoverageNotFound(KeyError):
    """No manifest exists in the trusted tenant namespace."""


class SourceState(StrEnum):
    EXPECTED_UNKNOWN = "expected_unknown"
    MISSING = "missing"
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    EXCLUDED = "excluded"


class AttemptState(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IssueStatus(StrEnum):
    OPEN = "open"
    SUPPORTED = "supported"
    QUALIFIED = "qualified"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"


class CoverageReason(StrEnum):
    STALE_MANIFEST = "stale_manifest"
    POLICY_MISMATCH = "policy_mismatch"
    SOURCE_UNACCOUNTED = "source_unaccounted"
    SOURCE_NOT_REGISTERED = "source_not_registered"
    REPRESENTATION_NOT_REGISTERED = "representation_not_registered"
    ISSUE_UNSUPPORTED = "issue_unsupported"
    LINK_UNAVAILABLE_OR_STALE = "link_unavailable_or_stale"
    LINK_SOURCE_OUT_OF_SCOPE = "link_source_out_of_scope"
    LINK_FIDELITY_NOT_MATCHED = "link_fidelity_not_matched"
    SEMANTIC_UNRESOLVED = "semantic_unresolved"
    CONTRADICTION_PRESENT = "contradiction_present"
    HISTORICAL_CONTRADICTION = "historical_contradiction"
    LINK_SUFFICIENCY_UNASSESSED = "link_sufficiency_unassessed"
    EXCLUSION_NOT_AUTHORIZED = "exclusion_not_authorized"


def _required(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CoverageError(f"{name} required")


def _positive(value: object, name: str) -> None:
    if type(value) is not int or value < 1:
        raise CoverageError(f"{name} must be a positive integer")


def _unique(values: tuple[str, ...], name: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise CoverageError(f"{name} requires nonempty immutable tuple")
    for value in values:
        _required(value, name)
    if tuple(sorted(set(values))) != values:
        raise CoverageError(f"{name} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ProcessingAttempt:
    attempt_id: str
    state: AttemptState
    representation_ids: tuple[str, ...] = ()
    reason_code: str = ""

    def __post_init__(self) -> None:
        _required(self.attempt_id, "attempt_id")
        if not isinstance(self.state, AttemptState):
            raise CoverageError("typed processing attempt state required")
        if self.state is AttemptState.SUCCEEDED:
            _unique(self.representation_ids, "successful representation IDs")
        elif self.representation_ids:
            raise CoverageError("pending or failed attempt must not claim representations")
        if self.state is AttemptState.FAILED:
            _required(self.reason_code, "failure reason code")


@dataclass(frozen=True, slots=True)
class ExpectedSource:
    """Source inventory is a recorded claim, cross-checked at evaluation."""

    source_id: str
    document_id: str | None
    version_id: str | None
    state: SourceState
    attempts: tuple[ProcessingAttempt, ...] = ()

    def __post_init__(self) -> None:
        _required(self.source_id, "source_id")
        if not isinstance(self.state, SourceState):
            raise CoverageError("typed source inventory state required")
        if (self.document_id is None) != (self.version_id is None):
            raise CoverageError("document/version must be specified together")
        if self.document_id is None:
            if self.state is not SourceState.EXPECTED_UNKNOWN or self.attempts:
                raise CoverageError("unknown source identity must remain expected_unknown")
        else:
            _required(self.document_id, "document_id")
            _required(self.version_id, "version_id")
            if self.state is SourceState.EXPECTED_UNKNOWN:
                raise CoverageError("known source identity cannot be expected_unknown")
        if not isinstance(self.attempts, tuple):
            raise CoverageError("processing attempts must be immutable tuple")
        if len({x.attempt_id for x in self.attempts}) != len(self.attempts):
            raise CoverageError("duplicate processing attempt IDs")
        last = self.attempts[-1].state if self.attempts else None
        if self.state is SourceState.PROCESSED and last is not AttemptState.SUCCEEDED:
            raise CoverageError("processed requires latest successful attempt")
        if self.state is SourceState.FAILED and last is not AttemptState.FAILED:
            raise CoverageError("failed requires latest failed attempt")
        if self.state is SourceState.PENDING and self.attempts and last is not AttemptState.PENDING:
            raise CoverageError("pending source must have latest pending attempt")
        if self.state is SourceState.MISSING and self.attempts:
            raise CoverageError("missing source cannot claim processing attempts")


@dataclass(frozen=True, slots=True)
class LinkUse:
    """Explicit statement/link revisions relied upon by one issue."""

    link_id: str
    assessment_revision: int
    finding_id: str
    statement_revision: int

    def __post_init__(self) -> None:
        _required(self.link_id, "link_id")
        _positive(self.assessment_revision, "link assessment revision")
        _required(self.finding_id, "finding_id")
        _positive(self.statement_revision, "finding statement revision")


@dataclass(frozen=True, slots=True)
class RequiredIssue:
    issue_id: str
    acceptance_policy: str
    source_ids: tuple[str, ...]
    relied_on_links: tuple[LinkUse, ...] = ()

    def __post_init__(self) -> None:
        _required(self.issue_id, "issue_id")
        _required(self.acceptance_policy, "issue acceptance policy")
        _unique(self.source_ids, "required source IDs")
        if not isinstance(self.relied_on_links, tuple):
            raise CoverageError("relied-on links must be immutable tuple")
        keys = tuple(link.link_id for link in self.relied_on_links)
        if tuple(sorted(set(keys))) != keys:
            raise CoverageError("relied-on links must be sorted with unique IDs")


@dataclass(frozen=True, slots=True)
class ExclusionProposal:
    """Recorded exception CLAIM, not an authenticated approval or audit event."""

    source_id: str
    reason: str = field(repr=False)
    claimed_actor_ref: str
    claimed_permission_ref: str
    claimed_audit_event_ref: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.source_id, "source_id"),
            (self.reason, "reason"),
            (self.claimed_actor_ref, "actor reference"),
            (self.claimed_permission_ref, "permission reference"),
            (self.claimed_audit_event_ref, "audit event reference"),
        ):
            _required(value, name)


@dataclass(frozen=True, slots=True)
class CoverageManifest:
    case_id: str
    scope_version: int
    manifest_revision: int
    policy_version: str
    issues: tuple[RequiredIssue, ...]
    sources: tuple[ExpectedSource, ...]
    exclusions: tuple[ExclusionProposal, ...] = ()
    scope_change_reason: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        _required(self.case_id, "case_id")
        _positive(self.scope_version, "scope_version")
        _positive(self.manifest_revision, "manifest_revision")
        _required(self.policy_version, "policy_version")
        if not isinstance(self.issues, tuple) or not isinstance(self.sources, tuple):
            raise CoverageError("immutable required issue/source inventory required")
        _unique(tuple(item.issue_id for item in self.issues), "issue IDs")
        _unique(tuple(item.source_id for item in self.sources), "source IDs")
        _unique_or_empty(tuple(x.source_id for x in self.exclusions), "exclusion source IDs")
        known = {src.source_id for src in self.sources}
        assigned: set[str] = set()
        for issue in self.issues:
            if any(source_id not in known for source_id in issue.source_ids):
                raise CoverageError("issue references an unknown expected source")
            assigned.update(issue.source_ids)
        if assigned != known:
            raise CoverageError("every expected source must be associated with an issue")
        claimed_exclusions = {item.source_id for item in self.exclusions}
        if claimed_exclusions != {
            item.source_id for item in self.sources if item.state is SourceState.EXCLUDED
        }:
            raise CoverageError("excluded source and explicit proposal must correspond")
        if self.scope_version > 1:
            _required(self.scope_change_reason, "scope revision rationale")

    def scope_shape(self) -> tuple[object, ...]:
        """Immutable content that cannot shrink within one scope version."""
        return (
            tuple(
                (issue.issue_id, issue.acceptance_policy, issue.source_ids)
                for issue in self.issues
            ),
            tuple(
                (src.source_id, src.document_id, src.version_id)
                for src in self.sources
            ),
        )


def _unique_or_empty(values: tuple[str, ...], name: str) -> None:
    if not isinstance(values, tuple) or tuple(sorted(set(values))) != values:
        raise CoverageError(f"{name} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class CoveragePolicy:
    """Explicit version pin; effective policy/auth must be verified externally."""

    version: str

    def __post_init__(self) -> None:
        _required(self.version, "policy version")


@dataclass(frozen=True, slots=True)
class IssueCoverage:
    issue_id: str
    status: IssueStatus
    relied_on_link_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CoverageBlocker:
    reason: CoverageReason
    subject_id: str


@dataclass(frozen=True, slots=True)
class CoverageEvaluation:
    """Snapshot-level ordinary completeness only; never an approved conclusion."""

    case_id: str
    scope_version: int
    manifest_revision: int
    policy_version: str
    ordinary_complete: bool
    issues: tuple[IssueCoverage, ...]
    blockers: tuple[CoverageBlocker, ...]
    excluded_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.ordinary_complete, bool)
            or self.ordinary_complete != (not self.blockers)
        ):
            raise CoverageError("completion must match explicit blockers")


@dataclass
class InMemoryCoverageLedger:
    """Append-only tenant-keyed manifest store, NOT durable/audited authorization."""

    _history: dict[tuple[str, str], tuple[CoverageManifest, ...]] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def register(self, tenant_scope: str, manifest: CoverageManifest) -> CoverageManifest:
        _required(tenant_scope, "trusted tenant scope")
        with self._lock:
            key = (tenant_scope, manifest.case_id)
            old = self._history.get(key, ())
            if manifest.manifest_revision != len(old) + 1:
                raise CoverageConflict("manifest revision must advance exactly one")
            if old:
                previous = old[-1]
                if manifest.scope_version not in (
                    previous.scope_version, previous.scope_version + 1
                ):
                    raise CoverageConflict("scope version must be stable or advance exactly one")
                if (
                    manifest.scope_version == previous.scope_version
                    and manifest.scope_shape() != previous.scope_shape()
                ):
                    raise CoverageConflict("issue/source scope changed without scope revision")
            elif manifest.scope_version != 1:
                raise CoverageConflict("new case scope must begin at version one")
            self._history[key] = (*old, manifest)
        return manifest

    def current(self, tenant_scope: str, case_id: str) -> CoverageManifest:
        _required(tenant_scope, "trusted tenant scope")
        with self._lock:
            versions = self._history.get((tenant_scope, case_id))
            if versions is None:
                raise CoverageNotFound("coverage manifest unavailable")
            return versions[-1]

    def history(self, tenant_scope: str, case_id: str) -> tuple[CoverageManifest, ...]:
        _required(tenant_scope, "trusted tenant scope")
        with self._lock:
            versions = self._history.get((tenant_scope, case_id))
            if versions is None:
                raise CoverageNotFound("coverage manifest unavailable")
            return versions


@dataclass(frozen=True, slots=True)
class CoverageEvaluator:
    manifests: InMemoryCoverageLedger
    findings: InMemoryFindingEvidenceLedger

    def evaluate(
        self, tenant_scope: str, expected: CoverageManifest, policy: CoveragePolicy
    ) -> CoverageEvaluation:
        if not isinstance(expected, CoverageManifest) or not isinstance(policy, CoveragePolicy):
            raise CoverageError("typed manifest and policy required")
        current = self.manifests.current(tenant_scope, expected.case_id)
        if current != expected:
            return self._blocked(expected, CoverageReason.STALE_MANIFEST, expected.case_id)
        if current.policy_version != policy.version:
            return self._blocked(expected, CoverageReason.POLICY_MISMATCH, expected.case_id)

        blockers: set[tuple[CoverageReason, str]] = set()
        processed: set[str] = set()
        for src in current.sources:
            if src.state is not SourceState.PROCESSED:
                blockers.add((CoverageReason.SOURCE_UNACCOUNTED, src.source_id))
                if src.state is SourceState.EXCLUDED:
                    blockers.add((CoverageReason.EXCLUSION_NOT_AUTHORIZED, src.source_id))
                continue
            assert src.document_id is not None and src.version_id is not None
            try:
                self.findings.evaluator.resolver.sources.get_source(
                    tenant_scope, src.document_id, src.version_id
                )
            except SourceRecordNotFound:
                blockers.add((CoverageReason.SOURCE_NOT_REGISTERED, src.source_id))
                continue
            last = src.attempts[-1]
            for rep_id in last.representation_ids:
                try:
                    self.findings.evaluator.resolver.sources.get_representation_for_source(
                        tenant_scope, src.document_id, src.version_id, rep_id
                    )
                except SourceRecordNotFound:
                    blockers.add((CoverageReason.REPRESENTATION_NOT_REGISTERED, src.source_id))
                    break
            else:
                processed.add(src.source_id)

        statuses: list[IssueCoverage] = []
        pinned: dict[str, tuple[str, int, int]] = {}
        source_index = {src.source_id: src for src in current.sources}
        for issue in current.issues:
            issue_reasons: set[CoverageReason] = set()
            if any(source_id not in processed for source_id in issue.source_ids):
                issue_reasons.add(CoverageReason.SOURCE_UNACCOUNTED)
            relations: list[SemanticRelation] = []
            if not issue.relied_on_links:
                issue_reasons.add(CoverageReason.ISSUE_UNSUPPORTED)
            for relied in issue.relied_on_links:
                try:
                    history = self.findings.link_history(tenant_scope, relied.link_id)
                    item = history[-1]
                    statement = self.findings.latest_statement(tenant_scope, relied.finding_id)
                    if (
                        item.assessment_revision != relied.assessment_revision
                        or item.statement.finding_id != relied.finding_id
                        or item.statement.revision != relied.statement_revision
                        or statement.revision != relied.statement_revision
                        or statement != item.statement
                    ):
                        raise FindingLinkNotFound("stale statement/link")
                except FindingLinkNotFound:
                    issue_reasons.add(CoverageReason.LINK_UNAVAILABLE_OR_STALE)
                    continue
                pinned[relied.link_id] = (
                    relied.finding_id, relied.statement_revision, relied.assessment_revision
                )
                if not self._anchor_within_issue_sources(item, issue, source_index, processed):
                    issue_reasons.add(CoverageReason.LINK_SOURCE_OUT_OF_SCOPE)
                if (
                    item.fidelity.citation_resolution is not CitationResolution.RESOLVED
                    or item.fidelity.content_fidelity is not ContentFidelity.MATCHED
                ):
                    issue_reasons.add(CoverageReason.LINK_FIDELITY_NOT_MATCHED)
                if item.semantic.relation in (
                    SemanticRelation.INCONCLUSIVE, SemanticRelation.NOT_ASSESSED
                ):
                    issue_reasons.add(CoverageReason.SEMANTIC_UNRESOLVED)
                if item.semantic.relation is SemanticRelation.CONTRADICTS:
                    issue_reasons.add(CoverageReason.CONTRADICTION_PRESENT)
                if (
                    any(x.semantic.relation is SemanticRelation.CONTRADICTS for x in history)
                    and item.semantic.relation is not SemanticRelation.CONTRADICTS
                ):
                    issue_reasons.add(CoverageReason.HISTORICAL_CONTRADICTION)
                if item.semantic.sufficiency is not LinkSufficiency.SUFFICIENT:
                    issue_reasons.add(CoverageReason.LINK_SUFFICIENCY_UNASSESSED)
                relations.append(item.semantic.relation)
            if not relations:
                status = IssueStatus.OPEN
            elif SemanticRelation.CONTRADICTS in relations:
                status = IssueStatus.CONTRADICTED
            elif SemanticRelation.QUALIFIES in relations:
                status = IssueStatus.QUALIFIED
            elif issue_reasons:
                status = IssueStatus.UNRESOLVED
            elif all(x is SemanticRelation.SUPPORTS for x in relations):
                status = IssueStatus.SUPPORTED
            else:
                status = IssueStatus.UNRESOLVED
            if status is not IssueStatus.SUPPORTED:
                issue_reasons.add(CoverageReason.ISSUE_UNSUPPORTED)
            blockers.update((reason, issue.issue_id) for reason in issue_reasons)
            statuses.append(IssueCoverage(
                issue.issue_id, status, tuple(x.link_id for x in issue.relied_on_links)
            ))

        # Second optimistic read rejects linked assessments/coverage revised mid-evaluation.
        if self.manifests.current(tenant_scope, expected.case_id) != current:
            return self._blocked(expected, CoverageReason.STALE_MANIFEST, expected.case_id)
        for link_id, (finding_id, finding_rev, assessment_rev) in pinned.items():
            try:
                if (
                    self.findings.link_history(tenant_scope, link_id)[-1].assessment_revision
                    != assessment_rev
                    or self.findings.latest_statement(tenant_scope, finding_id).revision
                    != finding_rev
                ):
                    return self._blocked(expected, CoverageReason.LINK_UNAVAILABLE_OR_STALE, link_id)
            except FindingLinkNotFound:
                return self._blocked(expected, CoverageReason.LINK_UNAVAILABLE_OR_STALE, link_id)

        sorted_blockers = tuple(
            CoverageBlocker(reason, target)
            for reason, target in sorted(blockers, key=lambda pair: (pair[1], pair[0].value))
        )
        return CoverageEvaluation(
            case_id=current.case_id, scope_version=current.scope_version,
            manifest_revision=current.manifest_revision, policy_version=policy.version,
            ordinary_complete=not sorted_blockers,
            issues=tuple(statuses), blockers=sorted_blockers,
            excluded_source_ids=tuple(
                x.source_id for x in current.sources if x.state is SourceState.EXCLUDED
            ),
        )

    @staticmethod
    def _anchor_within_issue_sources(
        item: FindingEvidenceLinkRevision,
        issue: RequiredIssue,
        source_index: dict[str, ExpectedSource],
        processed: set[str],
    ) -> bool:
        return any(
            source_id in processed
            and source_index[source_id].document_id == item.anchor.document_id
            and source_index[source_id].version_id == item.anchor.version_id
            and item.anchor.representation_id in (
                source_index[source_id].attempts[-1].representation_ids
            )
            for source_id in issue.source_ids
        )

    @staticmethod
    def _blocked(
        manifest: CoverageManifest, reason: CoverageReason, subject: str
    ) -> CoverageEvaluation:
        return CoverageEvaluation(
            manifest.case_id, manifest.scope_version, manifest.manifest_revision,
            manifest.policy_version, False, (), (CoverageBlocker(reason, subject),),
            tuple(x.source_id for x in manifest.sources if x.state is SourceState.EXCLUDED),
        )
