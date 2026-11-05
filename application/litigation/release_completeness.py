"""T30/T31: deterministic review eligibility, distinct from document coverage.

This module does not infer legal support, filing permission or source accuracy.
All review counts are based on unique, source-snapshot-bound finding identities.
"""

from __future__ import annotations

from typing import Any


class ReleaseIntegrityError(ValueError):
    """An inconsistent frozen review ledger cannot be classified safely."""


POLICY_VERSION = "caseproof-release-completeness-v1"
DECISIONS = frozenset(
    {
        "CONFIRMED_SUPPORTED",
        "CONFIRMED_QUALIFIED",
        "CONFIRMED_CONTRADICTED",
    }
)


def release_completeness(report: dict[str, Any]) -> dict[str, Any]:
    """Return the same conservative calculation for preview and release commit.

    Duplicate, orphaned or malformed human receipts are an integrity failure,
    never an invitation to count review rows as completed findings.
    """
    findings = report.get("findings")
    decisions = report.get("human_decisions")
    coverage = report.get("coverage")
    if not isinstance(findings, list) or not isinstance(decisions, list) or not isinstance(coverage, dict):
        raise ReleaseIntegrityError("invalid frozen review ledger")
    references: list[str] = []
    for finding in findings:
        if (
            not isinstance(finding, dict)
            or not isinstance(finding.get("reference_id"), str)
            or not finding["reference_id"]
        ):
            raise ReleaseIntegrityError("invalid frozen review ledger")
        references.append(finding["reference_id"])
    if len(set(references)) != len(references):
        raise ReleaseIntegrityError("invalid frozen review ledger")
    valid = set(references)
    reviewed: set[str] = set()
    requests: set[str] = set()
    for receipt in decisions:
        if not isinstance(receipt, dict) or any(
            not isinstance(receipt.get(key), str) or not receipt[key].strip()
            for key in ("reference_id", "request_id", "decision", "reviewer_id", "rationale", "timestamp")
        ):
            raise ReleaseIntegrityError("invalid frozen review ledger")
        ref = receipt["reference_id"]
        request = receipt["request_id"]
        if receipt["decision"] not in DECISIONS or ref not in valid or ref in reviewed or request in requests:
            raise ReleaseIntegrityError("invalid frozen review ledger")
        reviewed.add(ref)
        requests.add(request)
    total = len(references)
    pending = [ref for ref in references if ref not in reviewed]
    complete = total > 0 and not pending
    can_partial = bool(reviewed) and not complete
    codes: list[str] = []
    if total == 0:
        codes.append("NO_DETECTED_FINDINGS")
    if not reviewed:
        codes.append("NO_SAVED_REVIEWS")
    if pending:
        codes.append("UNREVIEWED_FINDINGS")
    if coverage.get("text_coverage_complete") is not True:
        codes.append("TEXT_COVERAGE_INCOMPLETE_OR_UNKNOWN")
    if coverage.get("reference_recall_measured") is not True:
        codes.append("REFERENCE_RECALL_UNMEASURED")
    # These warnings do not upgrade or downgrade a lawyer's *review* scope.
    # Complete review means every *detected* finding was reviewed, not all
    # legal claims in the dossier were discovered or checked.
    return {
        "policy_version": POLICY_VERSION,
        "total_findings": total,
        "required_reviews": total,
        "reviewed_findings": len(reviewed),
        "unreviewed_findings": len(pending),
        "unreviewed_reference_ids": pending,
        "review_complete": complete,
        "can_release_complete": complete,
        "can_release_partial": can_partial,
        "text_coverage_complete": coverage.get("text_coverage_complete") is True,
        "reference_recall_measured": coverage.get("reference_recall_measured") is True,
        "reason_codes": codes,
    }


def select_release_scope(
    policy: dict[str, Any],
    release_type: str,
    partial_acknowledged: bool,
) -> dict[str, Any]:
    """An explicit partial request is mandatory; preview never authorizes a POST."""
    if release_type == "complete_review":
        if partial_acknowledged or not policy["can_release_complete"]:
            raise ValueError("COMPLETE_REVIEW_REQUIRED")
    elif release_type == "partial_review":
        if not partial_acknowledged or not policy["can_release_partial"]:
            raise ValueError("PARTIAL_REVIEW_ACKNOWLEDGEMENT_REQUIRED")
    else:
        raise ValueError("UNSUPPORTED_RELEASE_TYPE")
    return {
        **policy,
        "release_type": release_type,
        "partial_acknowledged": partial_acknowledged,
    }
