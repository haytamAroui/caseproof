"""S2-004 internal-only non-approval observation fingerprint contract.

This module is NOT an authenticated HTTP command or production write
adapter. A UUID typed as an actor is NOT proof of identity: only a future
verified server composition boundary may supply the authenticated subject.
No case state, evidence status, human approval or external action is allowed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OPERATION = "s2_004_internal_observation"
_FINGERPRINT_SCHEMA = "caseproof.s2-004.internal-observation-input.v1"


def _positive(value: int, label: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")


def _uuid(value: UUID, label: str) -> None:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a non-nil UUID")


@dataclass(frozen=True, slots=True)
class InternalObservation:
    """Strict semantic input; no caller-specified authority or lifecycle state."""

    case_id: UUID
    expected_case_revision: int
    expected_scope_version: int
    expected_manifest_revision: int
    expected_policy_version: str
    idempotency_key: str
    observation_sha256: str

    def __post_init__(self) -> None:
        _uuid(self.case_id, "case_id")
        for label in ("expected_case_revision", "expected_scope_version",
                      "expected_manifest_revision"):
            _positive(getattr(self, label), label)
        if (not isinstance(self.expected_policy_version, str)
                or not self.expected_policy_version.strip()
                or len(self.expected_policy_version) > 128):
            raise ValueError("bounded effective policy version required")
        if (not isinstance(self.idempotency_key, str)
                or not 1 <= len(self.idempotency_key) <= 128
                or self.idempotency_key.strip() != self.idempotency_key):
            raise ValueError("bounded, nonblank idempotency key required")
        if not isinstance(self.observation_sha256, str) or not _SHA256.fullmatch(
            self.observation_sha256
        ):
            raise ValueError("observation_sha256 must be lowercase SHA-256")


def semantic_input_sha256(subject_id: UUID, observation: InternalObservation) -> str:
    """Hash exact semantic inputs, without request/correlation ID or raw content.

    The subject MUST originate from a verified server-held context; this
    function does not authenticate and is not exposed through an HTTP route.
    Correlation identifiers change on retries; the semantic hash must not.
    """
    _uuid(subject_id, "subject_id")
    if not isinstance(observation, InternalObservation):
        raise TypeError("strict InternalObservation required")
    payload = {
        "schema": _FINGERPRINT_SCHEMA,
        "operation": _OPERATION,
        "actor_subject_id": str(subject_id),
        "case_id": str(observation.case_id),
        "expected_case_revision": observation.expected_case_revision,
        "expected_scope_version": observation.expected_scope_version,
        "expected_manifest_revision": observation.expected_manifest_revision,
        "expected_policy_version": observation.expected_policy_version,
        "idempotency_key": observation.idempotency_key,
        "observation_sha256": observation.observation_sha256,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
