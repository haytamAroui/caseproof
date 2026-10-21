"""KRN-103: independent citation resolution and exact content-fidelity checks.

Fidelity to a captured representation is NOT evidence of authenticity, factual
truth, semantic support, completeness, sufficiency, or human approval.

This pure-Python in-memory reference delegates tenant scope to a trusted caller.
For PDF regions and spreadsheet ranges KRN-102 resolves only geometry/layout:
no content fidelity can be determined without a separate trusted extraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from packages.evidence_kernel.domain.anchors import (
    AnchorResolutionError,
    AnchorResolver,
    EvidenceAnchor,
    StructuredField,
    TextSpan,
)
from packages.evidence_kernel.domain.source_versions import SourceRecordNotFound

METHOD_VERSION = "krn103-exact-v1"


class CitationResolution(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    STALE = "stale"
    INVALID = "invalid"


class ContentFidelity(StrEnum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class FindingRevision:
    """A reference to an exact finding statement; not an assertion of truth."""

    finding_id: str
    statement_revision: str

    def __post_init__(self) -> None:
        for item in (self.finding_id, self.statement_revision):
            if not isinstance(item, str) or not item.strip():
                raise ValueError("finding ID and statement revision must be nonempty")


@dataclass(frozen=True, slots=True)
class ExactQuote:
    """Byte-preserving text comparison after the anchor's declared decoding."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("expected quotation must be nonempty text")


JsonScalar = str | int | bool | None


@dataclass(frozen=True, slots=True)
class ExactJsonScalar:
    """Supported exact JSON scalar, excluding lossy floating-point comparison."""

    value: JsonScalar

    def __post_init__(self) -> None:
        if type(self.value) not in (str, int, bool, type(None)):
            raise ValueError("expected value must be a string, integer, boolean or null")


Expectation = ExactQuote | ExactJsonScalar


@dataclass(frozen=True, slots=True)
class FidelityAssessment:
    """Deterministic assessment for one anchor against one finding revision.

    Do not promote findings using this result alone. Semantic support and
    sufficiency are intentionally always NOT_ASSESSED here.
    """

    finding: FindingRevision
    anchor: EvidenceAnchor
    citation_resolution: CitationResolution
    content_fidelity: ContentFidelity
    reason_code: str
    semantic_relation: Literal["not_assessed"] = "not_assessed"
    sufficiency: Literal["not_assessed"] = "not_assessed"
    method_version: Literal["krn103-exact-v1"] = "krn103-exact-v1"


@dataclass(frozen=True, slots=True)
class FidelityEvaluator:
    resolver: AnchorResolver

    def _result(
        self,
        finding: FindingRevision,
        anchor: EvidenceAnchor,
        citation_resolution: CitationResolution,
        content_fidelity: ContentFidelity,
        reason_code: str,
    ) -> FidelityAssessment:
        return FidelityAssessment(
            finding=finding,
            anchor=anchor,
            citation_resolution=citation_resolution,
            content_fidelity=content_fidelity,
            reason_code=reason_code,
        )

    def evaluate(
        self,
        tenant_scope: str,
        finding: FindingRevision,
        anchor: EvidenceAnchor,
        expected: Expectation,
    ) -> FidelityAssessment:
        """Evaluate a locator separately from its exact quote/value fidelity.

        Missing identities, including cross-tenant attempts, are uniformly
        unresolved. A known identity with wrong immutable hash is stale.
        Invalid locator geometry, basis, or manifest is invalid.
        All non-resolved assessments have indeterminate fidelity.
        """
        if not isinstance(expected, (ExactQuote, ExactJsonScalar)):
            raise ValueError("expected quotation or typed JSON scalar required")
        if not isinstance(tenant_scope, str) or not tenant_scope.strip():
            raise ValueError("trusted tenant scope required")
        try:
            source = self.resolver.sources.get_source(
                tenant_scope, anchor.document_id, anchor.version_id
            )
            representation = self.resolver.sources.get_representation_for_source(
                tenant_scope, anchor.document_id, anchor.version_id, anchor.representation_id
            )
        except SourceRecordNotFound:
            return self._result(
                finding, anchor, CitationResolution.UNRESOLVED,
                ContentFidelity.INDETERMINATE, "identity_unavailable",
            )

        if (
            source.sha256_hex != anchor.source_sha256_hex
            or representation.sha256_hex != anchor.representation_sha256_hex
            or representation.source_sha256_hex != anchor.source_sha256_hex
        ):
            return self._result(
                finding, anchor, CitationResolution.STALE,
                ContentFidelity.INDETERMINATE, "fingerprint_mismatch",
            )

        try:
            location = self.resolver.resolve(tenant_scope, anchor)
        except SourceRecordNotFound:
            return self._result(
                finding, anchor, CitationResolution.UNRESOLVED,
                ContentFidelity.INDETERMINATE, "identity_unavailable",
            )
        except AnchorResolutionError:
            return self._result(
                finding, anchor, CitationResolution.INVALID,
                ContentFidelity.INDETERMINATE, "locator_not_resolved",
            )

        locator = anchor.locator
        if isinstance(locator, TextSpan) and isinstance(expected, ExactQuote):
            exact = location.value == expected.text
            return self._result(
                finding, anchor, CitationResolution.RESOLVED,
                ContentFidelity.MATCHED if exact else ContentFidelity.MISMATCHED,
                "exact_text_match" if exact else "text_differs",
            )

        if isinstance(locator, StructuredField) and isinstance(expected, ExactJsonScalar):
            actual = location.value
            if type(actual) not in (str, int, bool, type(None)):
                return self._result(
                    finding, anchor, CitationResolution.RESOLVED,
                    ContentFidelity.INDETERMINATE, "unsupported_json_value",
                )
            exact = type(actual) is type(expected.value) and actual == expected.value
            return self._result(
                finding, anchor, CitationResolution.RESOLVED,
                ContentFidelity.MATCHED if exact else ContentFidelity.MISMATCHED,
                "exact_scalar_match" if exact else "scalar_differs",
            )

        return self._result(
            finding, anchor, CitationResolution.RESOLVED,
            ContentFidelity.INDETERMINATE,
            "location_only" if not isinstance(locator, (TextSpan, StructuredField))
            else "expectation_locator_type_mismatch",
        )
