"""Versioned dossier coverage and fidelity presentation; no semantic authority."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

CONTRACT = "caseproof-verification-contracts-v1"
QUOTE = re.compile(r'^\s*[,;:]?\s*(?:(?:PDF|printed|gedrukte|imprimée|bundle|bundel|liasse)\s+)?(?:pp?|pages?)\.?\s*\d+\s*[,;:.]?\s*(?:(?:traduction|vertaling|translation)\s*[:\-]?\s*)?["“«]([^"”»]{1,1000})["”»]', re.I)
TRANSLATED = re.compile(r'\b(?:traduction|vertaling|translation)\b', re.I)


def quotation_context(tail: str, *, draft_language: str | None, source_language: str | None) -> dict[str, Any]:
    match = QUOTE.match(tail)
    marked = bool(match and TRANSLATED.search(tail[:match.start(1)]))
    return {"quoted_text": match[1] if match else None, "draft_language": draft_language,
            "source_language": source_language,
            "language_basis": "reviewer_declared_not_independently_verified",
            "translation_review_required": bool(marked or (match and draft_language and source_language
                                                           and draft_language != source_language))}


def assess_fidelity(finding: dict[str, Any], page: dict[str, Any] | None) -> None:
    """Literal fidelity and visual uncertainty stay independent of human support."""
    quote = finding["quoted_text"]
    translated = finding["translation_review_required"]
    visual = finding["visual_assessment"]
    layer = page.get("layer_text", "") if page else ""
    finding["source_text_context"] = layer[:4000]
    finding["source_text_context_partial"] = len(layer) > 4000
    if finding.get("fidelity") == "ocr_unreliable" and (page is None or page.get("error")):
        visual["state"] = "ocr_unreliable"
        visual["reason"] = "source_scan_ocr_unavailable"

    if not quote:
        literal, reason = "not_applicable", "no_explicit_quotation"
    elif translated:
        literal, reason = "translation_review_required", "translated_prose_requires_human_review"
    elif not layer or page is None or page.get("error"):
        literal, reason = "not_assessed", "source_text_unavailable_or_partial"
    else:
        first = layer.find(quote)
        multiple = first >= 0 and layer.find(quote, first + 1) >= 0
        literal = "multiple_matches" if multiple else "exact_match" if first >= 0 else "quote_not_found"
        reason = "literal_in_checked_page_representation_only"
    finding["literal_assessment"] = {"state": literal, "reason": reason,
                                    "semantic_support": "not_assessed"}
    if visual["state"] in {"ocr_unreliable", "representation_conflict"}:
        finding["fidelity"] = visual["state"]
    elif translated:
        finding["fidelity"] = "translation_review_required"
    elif literal == "exact_match" and visual.get("reason") != "uncalibrated_agreement":
        finding["fidelity"] = "not_assessed"
    elif literal != "not_applicable":
        finding["fidelity"] = literal


def add_report_contract(report: dict[str, Any], region_manifest: dict[str, object],
                        language_context: dict[str, Any]) -> None:
    report["verification_contract"] = {"version": CONTRACT,
        "snapshot_scope": "supplied_bundle_not_filing_proof", "language_context": language_context,
        "processing_boundary": "self_hosted_isolated_worker_customer_environment_not_approved",
        "semantic_support": "human_only", "visual_agreement": "not_calibrated"}
    report["coverage"]["docx_regions"] = region_manifest
    report["coverage"]["references_detected"] = len(report["findings"])
    report["coverage"]["references_checked"] = report["coverage"]["checked"]
    report["coverage"]["references_not_assessed"] = report["coverage"]["unresolved"]
    ledger = []
    for source in report["sources"]:
        if source.get("role") != "exhibit":
            continue
        for number in range(1, source.get("page_count", 0) + 1):
            page = report["visual_pages"].get(source["version_id"] + ":" + str(number))
            ledger.append({"version_id": source["version_id"], "original_sha256": source["sha256"],
                "pdf_page": number, "method": "OCR_LOCAL_WORKER" if page and not page.get("error")
                else "FAILED" if page else "NOT_PROCESSED",
                "reason": page.get("error") if page else "outside_assessed_reference_scope",
                "text_layer_present": number not in source.get("image_only_pages", []),
                "engine_versions": {k: page[k] for k in ("engine", "normalization_version", "pypdf_version", "poppler_version", "tesseract_version", "ocr_build", "runtime_image") if k in page} if page else {}})
    report["coverage"]["source_pages"] = ledger
    unknown = [s['version_id'] for s in report['sources'] if s.get('role') == 'exhibit'
               and (s.get('parse_error') or not s.get('page_count'))]
    report["coverage"]["source_page_counts_unknown"] = unknown
    report["coverage"]["source_pages_known_total"] = len(ledger)
    report["coverage"]["source_pages_total"] = None if unknown else len(ledger)
    report["coverage"]["source_pages_ocr_processed"] = sum(p["method"] == "OCR_LOCAL_WORKER" for p in ledger)
    report["coverage"]["source_pages_failed_or_skipped"] = sum(p["method"] != "OCR_LOCAL_WORKER" for p in ledger)
    report["coverage"]["dimension_counts"] = {
        "identity": dict(Counter(f['identity'] for f in report['findings'])),
        "page_mapping": dict(Counter(f['page_mapping'] for f in report['findings'])),
        "literal": dict(Counter(f['literal_assessment']['state'] for f in report['findings'])),
        "visual": dict(Counter(f['visual_assessment']['state'] for f in report['findings'])),
        "human_support": dict(Counter(f['support'] for f in report['findings'])),
    }
    report["abstentions"] = [{"reference_id": f["reference_id"],
        "identity_reason": f.get("identity_reason"), "page_reason": f.get("page_mapping_reason"),
        "literal_reason": f["literal_assessment"]["reason"],
        "visual_reason": f["visual_assessment"]["reason"],
        "translation_review_required": f["translation_review_required"]}
        for f in report["findings"] if f["technical_check"] != "checked"
        or f["literal_assessment"]["state"] in {"not_assessed", "translation_review_required"}
        or f["visual_assessment"]["state"] == "not_assessed"]
