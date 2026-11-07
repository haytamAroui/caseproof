"""Read-only reviewer-to-source provenance projection.

This is an integrity *correspondence* view joining an authorized frozen
dossier snapshot to an independently loaded review ledger. It is NOT a
new durable review receipt or cryptographic co-signature. Missing context
never earns a positive binding status.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

SOURCE_BINDING_SCHEMA = "caseproof-review-source-binding-view-v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


def _quote_digest(finding: dict[str, Any]) -> str | None:
    quote = finding.get("quoted_text")
    context = finding.get("source_text_context")
    assessment = finding.get("literal_assessment")
    if (
        not isinstance(quote, str)
        or not quote
        or not isinstance(context, str)
        or len(context) > 12_000
        or not isinstance(assessment, dict)
        or assessment.get("state") != "exact_match"
        or finding.get("source_text_context_partial") is not False
        or finding.get("fidelity") in {"ocr_unreliable", "representation_conflict"}
    ):
        return None
    first = context.find(quote)
    if first < 0 or context.find(quote, first + 1) >= 0:
        return None
    # Derived page text hash, not the original PDF pixel/crop hash.
    return hashlib.sha256(quote.encode("utf-8")).hexdigest()


def project_review_source_bindings(
    report: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fail closed on wrong snapshot/reference, abstain on unsupported provenance."""
    snapshot = report.get("snapshot_hash")
    if not _valid_sha(snapshot):
        raise ValueError("signed snapshot hash required")
    findings = report.get("findings")
    sources = report.get("sources")
    if not isinstance(findings, list) or not isinstance(sources, list):
        raise ValueError("frozen report missing source/findings")
    if len(findings) > 10_000 or len(rows) > 10_000:
        raise ValueError("source binding bounded count exceeded")
    by_id: dict[str, dict[str, Any]] = {}
    versions: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("version_id"), str):
            raise ValueError("malformed source inventory")
        sid = source["version_id"]
        if sid in versions:
            raise ValueError("duplicate source version")
        versions[sid] = source
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("reference_id"), str):
            raise ValueError("malformed frozen finding")
        ref = finding["reference_id"]
        if ref in by_id:
            raise ValueError("duplicate frozen reference")
        by_id[ref] = finding

    projections: list[dict[str, Any]] = []
    seen_requests: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("malformed review record")
        ref = row.get("reference_id")
        request = row.get("request_id")
        if not isinstance(ref, str) or ref not in by_id:
            raise ValueError("orphan review reference")
        if not isinstance(request, str) or not request or request in seen_requests:
            raise ValueError("missing/duplicate durable review request id")
        seen_requests.add(request)
        if row.get("snapshot_hash") not in (None, snapshot):
            raise ValueError("review from different snapshot")
        finding = by_id[ref]
        version = finding.get("version_id")
        digest = finding.get("source_sha256")
        physical_page = finding.get("pdf_page")
        source = versions.get(version) if isinstance(version, str) else None
        source_is_pinned = (
            source is not None
            and _valid_sha(digest)
            and source.get("sha256") == digest
            and type(physical_page) is int
            and physical_page >= 1
            and type(source.get("page_count")) is int
            and physical_page <= source["page_count"]
        )
        visual = finding.get("visual_assessment")
        regions = visual.get("regions") if isinstance(visual, dict) else None
        expected = (
            [r.get("region_id") if isinstance(r, dict) else None for r in regions]
            if isinstance(regions, list) and len(regions) <= 96
            else None
        )
        reviewed = row.get("reviewed_region_ids")
        region_correspondence = (
            isinstance(expected, list)
            and bool(expected)
            and all(_valid_sha(r) for r in expected)
            and len(expected) == len(set(expected))
            and isinstance(reviewed, list)
            and len(reviewed) == len(expected)
            and all(_valid_sha(r) for r in reviewed)
            and set(reviewed) == set(expected)
        )
        rationale = row.get("rationale")
        projections.append(
            {
                "schema": SOURCE_BINDING_SCHEMA,
                "snapshot_hash": snapshot,
                "review_request_id": request,
                "reference_id": ref,
                "reviewer_id": row.get("reviewer_id"),
                "decision": row.get("decision"),
                "review_timestamp": row.get("timestamp"),
                "source_version_id": version if source_is_pinned else None,
                "original_pdf_sha256": digest if source_is_pinned else None,
                "physical_pdf_page": physical_page if source_is_pinned else None,
                "reviewed_region_ids": reviewed if region_correspondence else [],
                "rationale_sha256": (
                    hashlib.sha256(rationale.encode("utf-8")).hexdigest()
                    if isinstance(rationale, str) and rationale
                    else None
                ),
                "derived_quote_sha256": (
                    _quote_digest(finding) if source_is_pinned and region_correspondence else None
                ),
                "binding_state": (
                    "SOURCE_VERSION_AND_REVIEW_REGIONS_CORRESPOND"
                    if source_is_pinned and region_correspondence
                    else "NOT_SOURCE_BOUND"
                ),
                "signed_as_one_record": False,
                "original_pdf_pixels_verified_by_this_projection": False,
                "semantic_support_verified_by_this_projection": False,
                "notice": (
                    "Read-only correspondence of frozen source and existing review ledger, "
                    "not an independent signed receipt, crop validation, or legal verdict."
                ),
            }
        )
    return projections
