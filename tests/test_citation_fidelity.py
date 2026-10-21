"""KRN-103 adversarial tests: citation location != fidelity != truth."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

import pytest

from packages.evidence_kernel.domain.anchors import (
    AnchorResolver,
    EvidenceAnchor,
    LayoutManifest,
    PdfLayout,
    PdfPage,
    PdfRegion,
    SheetRange,
    StructuredField,
    StructuredLayout,
    TextSpan,
    WorkbookLayout,
    WorkbookSheet,
)
from packages.evidence_kernel.domain.fidelity import (
    CitationResolution,
    ContentFidelity,
    ExactJsonScalar,
    ExactQuote,
    FidelityEvaluator,
    FindingRevision,
)
from packages.evidence_kernel.domain.source_versions import (
    DerivedRepresentation,
    InMemorySourceRegistry,
    SourceVersion,
)

STAMP = datetime(2026, 10, 21, 13, tzinfo=UTC)
SOURCE = b"invoice-copy"
TEXT = "Approved on Tuesday. Payment was NOT received."


def digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def setup(
    *,
    payload: bytes = TEXT.encode(),
    basis: str = "unicode_codepoint_zero_based_half_open",
    tenant: str = "tenant-a",
) -> tuple[FidelityEvaluator, EvidenceAnchor]:
    registry = InMemorySourceRegistry()
    source = SourceVersion("doc-1", "v1", digest(SOURCE), SOURCE, STAMP, "application/pdf")
    representation = DerivedRepresentation(
        representation_id="ocr-v1", document_id="doc-1", version_id="v1",
        source_sha256_hex=source.sha256_hex, sha256_hex=digest(payload),
        content=payload, media_type="text/plain", transform_name="parser",
        transform_version="1", transform_config_sha256=digest(b"config"),
        coordinate_convention=basis, created_at=STAMP,
    )
    registry.register_source(tenant, source)
    registry.register_representation(tenant, representation)
    evidence = EvidenceAnchor(
        "anchor-1", "doc-1", "v1", source.sha256_hex, representation.representation_id,
        representation.sha256_hex, TextSpan(0, 8),
    )
    return FidelityEvaluator(AnchorResolver(registry)), evidence


FINDING = FindingRevision("finding-1", "rev-1")


def test_matching_text_does_not_assert_semantic_support_or_sufficiency() -> None:
    evaluator, evidence = setup()
    # A truthful extract, connected to a deliberately false finding statement.
    # Nothing in KRN-103 may infer support from a matching quote.
    result = evaluator.evaluate("tenant-a", FINDING, evidence, ExactQuote("Approved"))
    assert result.citation_resolution is CitationResolution.RESOLVED
    assert result.content_fidelity is ContentFidelity.MATCHED
    assert result.semantic_relation == "not_assessed"
    assert result.sufficiency == "not_assessed"
    assert result.finding.statement_revision == "rev-1"
    assert not hasattr(result, "approved")
    assert not hasattr(result, "verified")


def test_wrong_quote_is_mismatched_even_when_location_resolves() -> None:
    evaluator, evidence = setup()
    result = evaluator.evaluate("tenant-a", FINDING, evidence, ExactQuote("Rejected"))
    assert result.citation_resolution is CitationResolution.RESOLVED
    assert result.content_fidelity is ContentFidelity.MISMATCHED
    assert result.reason_code == "text_differs"
    assert result.semantic_relation == "not_assessed"


@pytest.mark.parametrize("quote", ["approved", "Approved ", "Approved\n", "Approve", " Approv"])
def test_text_fidelity_is_exact_not_fuzzy_casefolded_or_substring(quote: str) -> None:
    evaluator, evidence = setup()
    actual = evaluator.evaluate("tenant-a", FINDING, evidence, ExactQuote(quote))
    assert actual.content_fidelity is ContentFidelity.MISMATCHED


def test_unicode_emoji_and_combining_marks_compare_exact_codepoints() -> None:
    evaluator, evidence = setup(payload="😀e\u0301".encode())
    result = evaluator.evaluate(
        "tenant-a", FINDING, replace(evidence, locator=TextSpan(0, 3)), ExactQuote("😀e\u0301")
    )
    assert result.content_fidelity is ContentFidelity.MATCHED
    normalized = evaluator.evaluate(
        "tenant-a", FINDING, replace(evidence, locator=TextSpan(0, 3)), ExactQuote("😀é")
    )
    assert normalized.content_fidelity is ContentFidelity.MISMATCHED


def test_wrong_offset_is_invalid_and_not_treated_as_missing_quote() -> None:
    evaluator, evidence = setup()
    result = evaluator.evaluate(
        "tenant-a", FINDING, replace(evidence, locator=TextSpan(0, 9999)), ExactQuote("Approved")
    )
    assert result.citation_resolution is CitationResolution.INVALID
    assert result.content_fidelity is ContentFidelity.INDETERMINATE


def test_missing_source_or_ocr_is_unresolved_without_tenant_leak() -> None:
    evaluator, evidence = setup()
    for bad in (
        replace(evidence, document_id="unknown"),
        replace(evidence, version_id="v2"),
        replace(evidence, representation_id="rep-not-present"),
    ):
        result = evaluator.evaluate("tenant-a", FINDING, bad, ExactQuote("Approved"))
        assert result.citation_resolution is CitationResolution.UNRESOLVED
        assert result.content_fidelity is ContentFidelity.INDETERMINATE
        assert result.reason_code == "identity_unavailable"
    other = evaluator.evaluate("tenant-b", FINDING, evidence, ExactQuote("Approved"))
    assert other.citation_resolution is CitationResolution.UNRESOLVED
    assert other.reason_code == "identity_unavailable"


def test_stale_source_and_representation_fingerprints_fail_before_fidelity() -> None:
    evaluator, evidence = setup()
    for bad in (
        replace(evidence, source_sha256_hex="0" * 64),
        replace(evidence, representation_sha256_hex="1" * 64),
    ):
        result = evaluator.evaluate("tenant-a", FINDING, bad, ExactQuote("Approved"))
        assert result.citation_resolution is CitationResolution.STALE
        assert result.content_fidelity is ContentFidelity.INDETERMINATE
        assert result.semantic_relation == "not_assessed"


def test_reocr_never_redirects_fidelity_to_a_new_representation() -> None:
    evaluator, evidence = setup()
    next_bytes = b"Rejected on Wednesday."
    previous = evaluator.resolver.sources.get_representation("tenant-a", "ocr-v1")
    second = replace(previous, representation_id="ocr-v2", content=next_bytes,
                     sha256_hex=digest(next_bytes))
    evaluator.resolver.sources.register_representation("tenant-a", second)
    old = evaluator.evaluate("tenant-a", FINDING, evidence, ExactQuote("Approved"))
    assert old.content_fidelity is ContentFidelity.MATCHED
    redirect = evaluator.evaluate(
        "tenant-a", FINDING, replace(evidence, representation_id="ocr-v2"), ExactQuote("Approved")
    )
    assert redirect.citation_resolution is CitationResolution.STALE
    assert redirect.content_fidelity is ContentFidelity.INDETERMINATE
    rebased = evaluator.evaluate(
        "tenant-a", FINDING,
        replace(evidence, representation_id="ocr-v2", representation_sha256_hex=digest(next_bytes)),
        ExactQuote("Approved"),
    )
    assert rebased.citation_resolution is CitationResolution.RESOLVED
    assert rebased.content_fidelity is ContentFidelity.MISMATCHED


def test_changed_finding_revision_does_not_inherit_semantic_approval() -> None:
    evaluator, evidence = setup()
    first = evaluator.evaluate("tenant-a", FINDING, evidence, ExactQuote("Approved"))
    second = evaluator.evaluate(
        "tenant-a", FindingRevision("finding-1", "rev-2"), evidence, ExactQuote("Approved")
    )
    assert first.finding != second.finding
    assert second.content_fidelity is ContentFidelity.MATCHED
    assert second.semantic_relation == "not_assessed"
    assert second.sufficiency == "not_assessed"


def test_fidelity_never_computes_a_match_from_pdf_geometry() -> None:
    evaluator, evidence = setup(payload=b"synthetic layout", basis="pdf_points_unrotated_bottom_left")
    page = PdfPage(0, Decimal(500), Decimal(700), 0)
    manifest = LayoutManifest("doc-1", "v1", "ocr-v1", evidence.representation_sha256_hex, PdfLayout((page,)))
    region = PdfRegion(0, Decimal(1), Decimal(2), Decimal(80), Decimal(90),
                       Decimal(500), Decimal(700), 0)
    a = replace(evidence, locator=region)
    unresolved = evaluator.evaluate("tenant-a", FINDING, a, ExactQuote("Approved"))
    assert unresolved.citation_resolution is CitationResolution.INVALID
    assert unresolved.content_fidelity is ContentFidelity.INDETERMINATE
    evaluator.resolver.register_layout("tenant-a", manifest)
    result = evaluator.evaluate("tenant-a", FINDING, a, ExactQuote("Approved"))
    assert result.citation_resolution is CitationResolution.RESOLVED
    assert result.content_fidelity is ContentFidelity.INDETERMINATE
    assert result.reason_code == "location_only"


def test_workbook_range_does_not_fabricate_cell_contents() -> None:
    evaluator, evidence = setup(payload=b"workbook normalized", basis="spreadsheet_a1_sheet_id")
    m = LayoutManifest(
        "doc-1", "v1", "ocr-v1", evidence.representation_sha256_hex,
        WorkbookLayout((WorkbookSheet("sheet-1", 30, 5),)),
    )
    evaluator.resolver.register_layout("tenant-a", m)
    result = evaluator.evaluate(
        "tenant-a", FINDING, replace(evidence, locator=SheetRange("sheet-1", "A1:B5")),
        ExactQuote("123.00"),
    )
    assert result.citation_resolution is CitationResolution.RESOLVED
    assert result.content_fidelity is ContentFidelity.INDETERMINATE


def json_setup(payload: bytes) -> tuple[FidelityEvaluator, EvidenceAnchor]:
    evaluator, a = setup(payload=payload, basis="json_path_v1")
    evaluator.resolver.register_layout(
        "tenant-a",
        LayoutManifest("doc-1", "v1", "ocr-v1", a.representation_sha256_hex,
                       StructuredLayout("schema-v1")),
    )
    return evaluator, replace(a, locator=StructuredField("schema-v1", ("value",)))


@pytest.mark.parametrize(
    ("actual", "expected", "status"),
    [
        (b'{"value":123}', 123, ContentFidelity.MATCHED),
        (b'{"value":123}', 124, ContentFidelity.MISMATCHED),
        (b'{"value":123}', True, ContentFidelity.MISMATCHED),
        (b'{"value":true}', True, ContentFidelity.MATCHED),
        (b'{"value":true}', 1, ContentFidelity.MISMATCHED),
        (b'{"value":false}', False, ContentFidelity.MATCHED),
        (b'{"value":null}', None, ContentFidelity.MATCHED),
        (b'{"value":null}', "", ContentFidelity.MISMATCHED),
        (b'{"value":"123"}', 123, ContentFidelity.MISMATCHED),
        (b'{"value":"123"}', "123", ContentFidelity.MATCHED),
    ],
)
def test_structured_scalars_compare_value_and_type_exactly(
    actual: bytes, expected: str | int | bool | None, status: ContentFidelity
) -> None:
    evaluator, a = json_setup(actual)
    result = evaluator.evaluate("tenant-a", FINDING, a, ExactJsonScalar(expected))
    assert result.citation_resolution is CitationResolution.RESOLVED
    assert result.content_fidelity is status
    assert result.semantic_relation == "not_assessed"


@pytest.mark.parametrize("payload", [b'{"value":3.14159}', b'{"value":[1]}', b'{"value":{"k":"v"}}'])
def test_unsupported_numeric_or_compound_json_does_not_gain_fidelity(
    payload: bytes,
) -> None:
    evaluator, evidence = json_setup(payload)
    result = evaluator.evaluate("tenant-a", FINDING, evidence, ExactJsonScalar(3))
    assert result.citation_resolution is CitationResolution.RESOLVED
    assert result.content_fidelity is ContentFidelity.INDETERMINATE
    assert result.reason_code == "unsupported_json_value"


def test_invalid_json_citation_is_not_a_fidelity_mismatch() -> None:
    evaluator, evidence = json_setup(b'{"value":NaN}')
    result = evaluator.evaluate("tenant-a", FINDING, evidence, ExactJsonScalar(1))
    assert result.citation_resolution is CitationResolution.INVALID
    assert result.content_fidelity is ContentFidelity.INDETERMINATE


def test_mismatched_expectation_and_locator_type_is_indeterminate() -> None:
    evaluator, evidence = setup()
    result = evaluator.evaluate("tenant-a", FINDING, evidence, ExactJsonScalar("Approved"))
    assert result.citation_resolution is CitationResolution.RESOLVED
    assert result.content_fidelity is ContentFidelity.INDETERMINATE
    assert result.reason_code == "expectation_locator_type_mismatch"
    evaluator, evidence = json_setup(b'{"value":"Approved"}')
    result = evaluator.evaluate("tenant-a", FINDING, evidence, ExactQuote("Approved"))
    assert result.content_fidelity is ContentFidelity.INDETERMINATE


@pytest.mark.parametrize("bad", [0.1, 1.0, [], {}, (1, 2), Decimal("3.5")])
def test_unsupported_expectations_rejected_at_boundary(bad: object) -> None:
    with pytest.raises(ValueError, match="expected value"):
        ExactJsonScalar(bad)  # type: ignore[arg-type]


def test_bad_quote_or_finding_identity_rejected_at_boundary() -> None:
    for quote in ("", 123, None):
        with pytest.raises(ValueError):
            ExactQuote(quote)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        FindingRevision("", "rev")
    with pytest.raises(ValueError):
        FindingRevision("id", "")


def test_untrusted_scope_fails_closed_instead_of_returning_positive_result() -> None:
    evaluator, evidence = setup()
    for tenant in ("", "  "):
        with pytest.raises(ValueError, match="tenant"):
            evaluator.evaluate(tenant, FINDING, evidence, ExactQuote("Approved"))


def test_result_does_not_print_private_expected_or_source_values() -> None:
    evaluator, evidence = setup(payload=b"unique-confidential-quote")
    result = evaluator.evaluate(
        "tenant-a", FINDING, replace(evidence, locator=TextSpan(0, 25)),
        ExactQuote("unique-confidential-quote"),
    )
    assert result.content_fidelity is ContentFidelity.MATCHED
    assert "unique-confidential-quote" not in repr(result)
    with pytest.raises(FrozenInstanceError):
        result.reason_code = "forged"  # type: ignore[misc]


def test_legacy_reference_api_is_unchanged() -> None:
    from packages.evidence_kernel.domain.evidence import SourceReference
    from packages.evidence_kernel.domain.workflow import DocumentVersion

    assert SourceReference("doc", digest(SOURCE), "text").document_id == "doc"
    assert DocumentVersion("doc", "v1", digest(b"x"), "x").version_id == "v1"
