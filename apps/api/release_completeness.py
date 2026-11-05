"""Pure, fail-closed completeness policy for one frozen reviewed release.

Review completeness means each detected reference has a saved disposition.
It never measures OCR, inventory, semantic support or filing readiness.
"""
from __future__ import annotations

from typing import Any

from apps.api.access_control import AccessFailure, AccessRejected

DECISIONS = {
    "CONFIRMED_SUPPORTED", "CONFIRMED_QUALIFIED", "CONFIRMED_CONTRADICTED",
}
MAX_LINKS = 128


def release_policy(report: dict[str, Any]) -> dict[str, Any]:
    """Count unique finding identities, never ledger rows or machine states."""
    findings = report.get("findings")
    decisions = report.get("human_decisions")
    if not isinstance(findings, list) or not isinstance(decisions, list):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    references: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        reference = finding.get("reference_id")
        if not isinstance(reference, str) or not reference or len(reference) > 256:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        references.append(reference)
    if len(set(references)) != len(references):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)

    present = set(references)
    reviewed: set[str] = set()
    requests: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        reference, request = decision.get("reference_id"), decision.get("request_id")
        if (
            not isinstance(reference, str) or reference not in present
            or not isinstance(request, str) or not request
            or decision.get("decision") not in DECISIONS
            or not isinstance(decision.get("reviewer_id"), str)
            or not decision["reviewer_id"]
            or not isinstance(decision.get("rationale"), str)
            or not decision["rationale"]
            or not isinstance(decision.get("timestamp"), str)
            or not decision["timestamp"]
        ):
            # Orphaned/invalid reviews must not certify a reference by accident.
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        prior = requests.get(request)
        if prior is not None and prior != decision:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        requests[request] = decision
        reviewed.add(reference)

    pending = [ref for ref in references if ref not in reviewed]
    completed = [ref for ref in references if ref in reviewed]
    total = len(references)
    n_reviewed = len(completed)
    scope = "blocked" if n_reviewed == 0 else "complete" if not pending else "partial"
    reasons = (
        ["NO_FINDINGS"] if total == 0
        else ["NO_APPLICABLE_REVIEWS"] if n_reviewed == 0
        else ["UNREVIEWED_FINDINGS"] if pending else []
    )
    return {
        "version": 1,
        "scope": scope,
        "can_release": scope != "blocked",
        "total_findings": total,
        "required_findings": total,
        "reviewed_findings": n_reviewed,
        "unreviewed_findings": len(pending),
        "review_complete": scope == "complete",
        "reviewed_reference_ids": completed[:MAX_LINKS],
        "unreviewed_reference_ids": pending[:MAX_LINKS],
        "references_truncated": len(completed) > MAX_LINKS or len(pending) > MAX_LINKS,
        "reason_codes": reasons,
    }
