"""Strict, deterministic source-version rights evaluation.

This module does not authorize access. In PR 1 its result is observational
only and must be called after the existing signed authorization succeeds.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    UNKNOWN = "unknown"


class Action(StrEnum):
    PROCESS = "process"
    INDEX_FOR_SEARCH = "indexForSearch"
    USE_ACROSS_MATTERS = "useAcrossMatters"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class RightsPolicy:
    version: int
    authorization_reference: str | None
    permissions: Mapping[str, bool]
    classification: str = "CLIENT_UPLOAD"


@dataclass(frozen=True, slots=True)
class Evaluation:
    decision: Decision
    reason: str
    policy_version: int | None


def evaluate_detail(
    policy: RightsPolicy | None, action: str, *, same_matter: bool
) -> Evaluation:
    if action not in {item.value for item in Action}:
        return Evaluation(Decision.DENY, "unsupported_action", policy.version if policy else None)
    if policy is None:
        return Evaluation(Decision.UNKNOWN, "policy_missing", None)
    if type(policy.version) is not int or policy.version < 1:
        return Evaluation(Decision.DENY, "invalid_policy_version", None)
    if policy.classification not in {"CLIENT_UPLOAD", "CLIENT_CONFIDENTIAL"}:
        return Evaluation(Decision.DENY, "invalid_classification", policy.version)
    if not same_matter and action in {"export", "useAcrossMatters"}:
        return Evaluation(Decision.DENY, "cross_matter_prohibited", policy.version)
    if action == "process" and (
        not isinstance(policy.authorization_reference, str)
        or not policy.authorization_reference.strip()
    ):
        return Evaluation(Decision.DENY, "authorization_reference_missing", policy.version)
    permission = policy.permissions.get(action)
    if type(permission) is not bool:
        return Evaluation(Decision.DENY, "permission_missing_or_invalid", policy.version)
    return Evaluation(
        Decision.ALLOW if permission else Decision.DENY,
        "explicit_policy",
        policy.version,
    )


def evaluate(policy: RightsPolicy | None, action: str, *, same_matter: bool) -> Decision:
    return evaluate_detail(policy, action, same_matter=same_matter).decision
