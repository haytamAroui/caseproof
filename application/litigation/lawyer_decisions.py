"""Lawyer decisions over rule results (roadmap task 3).

The four lawyer dispositions — confirm, qualify, reject, waive — recorded
with motive and scope over a rule result produced under the common contract
(task 1), with explicit invalidation rules on recompute.

Hard rules:

- The original machine finding is preserved verbatim on every decision and
  is NEVER rewritten: a FAIL stays a FAIL, whatever the disposition.
- A decision binds the EXACT machine result it answers: rule identity, rule
  version, reference, input hashes AND a fingerprint of the full canonical
  result (status, reason, scope, preconditions, sub-results). When a
  recompute changes any of those, or the result disappears, the decision is
  INVALIDATED and surfaces as such; a new machine finding never silently
  inherits a decision.
- A waiver (dérogation) answers an exception, i.e. any non-PASS result
  (FAIL, UNDETERMINED or UNVERIFIED): the user's concept gives the lawyer
  the decision on every exception, and a PASS has nothing to except. What an
  accepted waiver PERMITS (export, labeled "ready with exceptions" state) is
  the user's pending product decision (roadmap task 2) and is NOT decided
  here; this module records decisions, it grants nothing.
- These are traceable decision records, not legal approvals, not filing
  acts. Persistence with signed actor authorization is an integration gate,
  as with the M2 review cycle.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import uuid4

from application.litigation.rule_results import RuleResult, RuleStatus, to_json

DECISION_FORMAT_VERSION = "caseproof-lawyer-decision-v1"
_ISO8601 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})")
_UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")


class LawyerDecisionError(ValueError):
    """Malformed or unlawful lawyer decision."""


class Disposition(StrEnum):
    CONFIRMED = "confirmed"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    WAIVED = "waived"


class DecisionValidity(StrEnum):
    VALID = "valid"
    INVALIDATED = "invalidated"


def _bounded(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not 0 < len(value.strip()) <= limit:
        raise LawyerDecisionError(f"bounded non-empty string required for {name}")
    return value.strip()


@dataclass(frozen=True, slots=True)
class LawyerDecision:
    """One lawyer disposition bound to one exact machine result."""

    decision_id: str
    rule_id: str
    rule_version: str
    reference: str
    machine_status: str
    machine_reason: str
    input_hashes: tuple[tuple[str, str], ...]
    result_fingerprint: str
    actor_id: str
    disposition: Disposition
    rationale: str
    scope: str
    decided_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.decision_id, str) or _UUID4.fullmatch(self.decision_id) is None:
            raise LawyerDecisionError("decision identity is a version-4 UUID")
        _bounded(self.rule_id, "rule_id", 128)
        _bounded(self.rule_version, "rule_version", 128)
        _bounded(self.reference, "reference", 256)
        if self.machine_status not in {status.value for status in RuleStatus}:
            raise LawyerDecisionError("the preserved machine status is a contract status")
        _bounded(self.machine_reason, "machine_reason", 400)
        _bounded(self.actor_id, "actor_id", 128)
        if not isinstance(self.disposition, Disposition):
            raise LawyerDecisionError("typed disposition required")
        _bounded(self.rationale, "rationale", 2000)
        _bounded(self.scope, "scope", 400)
        if not isinstance(self.decided_at, str) or _ISO8601.fullmatch(self.decided_at) is None:
            raise LawyerDecisionError("decided_at is an ISO-8601 timestamp with timezone")
        for label, digest in self.input_hashes:
            _bounded(label, "input hash label", 64)
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise LawyerDecisionError("preserved input hashes are well-formed sha256")
        if not isinstance(self.result_fingerprint, str) or not re.fullmatch(
                r"[0-9a-f]{64}", self.result_fingerprint):
            raise LawyerDecisionError("the preserved result fingerprint is a sha256")
        if self.disposition is Disposition.WAIVED and self.machine_status == RuleStatus.PASS.value:
            raise LawyerDecisionError(
                "a waiver answers a non-PASS exception; the lawyer decides every exception,"
                " and what a waiver permits is a separate product decision")

    @property
    def content_hash(self) -> str:
        """Traceability hash over the full decision content."""
        canonical = json.dumps(
            {
                "format": DECISION_FORMAT_VERSION,
                "decision_id": self.decision_id,
                "rule_id": self.rule_id,
                "rule_version": self.rule_version,
                "reference": self.reference,
                "machine_status": self.machine_status,
                "machine_reason": self.machine_reason,
                "input_hashes": list(self.input_hashes),
                "result_fingerprint": self.result_fingerprint,
                "actor_id": self.actor_id,
                "disposition": self.disposition.value,
                "rationale": self.rationale,
                "scope": self.scope,
                "decided_at": self.decided_at,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_decision(
    result: RuleResult,
    *,
    actor_id: str,
    disposition: Disposition,
    rationale: str,
    scope: str,
    decided_at: str,
) -> LawyerDecision:
    """Record a disposition over an actual machine result, preserving it verbatim."""
    if not isinstance(result, RuleResult):
        raise LawyerDecisionError("a decision answers an actual RuleResult")
    return LawyerDecision(
        decision_id=str(uuid4()),
        rule_id=result.rule_id,
        rule_version=result.rule_version,
        reference=result.reference,
        machine_status=result.status.value,
        machine_reason=result.reason,
        input_hashes=result.input_hashes,
        result_fingerprint=hashlib.sha256(to_json(result).encode("utf-8")).hexdigest(),
        actor_id=actor_id,
        disposition=disposition,
        rationale=rationale,
        scope=scope,
        decided_at=decided_at,
    )


def validate_decision(decision: LawyerDecision, current: RuleResult | None) -> tuple[DecisionValidity, str]:
    """Re-check a decision against the current machine result after recompute.

    Specific causes are reported first (version, inputs, status); any other
    content drift (reason, scope, preconditions, sub-results) is caught by
    the full-result fingerprint as result_content_changed.
    """
    if not isinstance(decision, LawyerDecision):
        raise LawyerDecisionError("a typed LawyerDecision is required")
    if current is None:
        return DecisionValidity.INVALIDATED, "result_no_longer_produced"
    if not isinstance(current, RuleResult):
        raise LawyerDecisionError("the current state is an actual RuleResult")
    if current.rule_id != decision.rule_id or current.reference != decision.reference:
        raise LawyerDecisionError("a decision is validated against its own rule and reference")
    if current.rule_version != decision.rule_version:
        return DecisionValidity.INVALIDATED, "rule_version_changed"
    if current.input_hashes != decision.input_hashes:
        return DecisionValidity.INVALIDATED, "inputs_changed"
    if current.status.value != decision.machine_status:
        return DecisionValidity.INVALIDATED, "machine_status_changed"
    fingerprint = hashlib.sha256(to_json(current).encode("utf-8")).hexdigest()
    if fingerprint != decision.result_fingerprint:
        # Same rule, version, inputs and status, but the finding's reason,
        # scope, preconditions or sub-results moved: a NEW machine finding
        # must never silently inherit a decision.
        return DecisionValidity.INVALIDATED, "result_content_changed"
    return DecisionValidity.VALID, "current_result_unchanged"


@dataclass(frozen=True, slots=True)
class ResultDecisionView:
    """One machine result plus its current decision state; status is NEVER altered."""

    result: RuleResult
    decision: LawyerDecision | None
    validity: DecisionValidity | None
    validity_detail: str

    @property
    def machine_status(self) -> str:
        """The machine finding, always the original contract status."""
        return self.result.status.value


def decision_views(
    results: tuple[RuleResult, ...] | list[RuleResult],
    decisions: tuple[LawyerDecision, ...] | list[LawyerDecision],
) -> tuple[ResultDecisionView, ...]:
    """Pair current results with their decisions, re-validated on this recompute."""
    views: list[ResultDecisionView] = []
    for result in results:
        matching = [d for d in decisions if d.rule_id == result.rule_id and d.reference == result.reference]
        if not matching:
            views.append(ResultDecisionView(result=result, decision=None, validity=None,
                                            validity_detail="no_decision_recorded"))
            continue
        latest = max(matching, key=lambda d: d.decided_at)
        validity, detail = validate_decision(latest, result)
        views.append(ResultDecisionView(result=result, decision=latest, validity=validity,
                                        validity_detail=detail))
    return tuple(views)
