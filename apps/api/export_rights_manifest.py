"""PR203: frozen, receipt-bound export permissions for exact source versions.

A rights attestation is EVIDENCE of the decision made at release time, not a
portable credential, policy grant or statement of current authorization.
The existing server HMAC signs the attestation inside the release manifest.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn

from application.data_rights import Action, Decision
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.data_rights_enforcement import SignedRightsGate

HEX64 = re.compile(r"^[0-9a-f]{64}$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SCHEMA = "caseproof-export-rights-v1"


def _error() -> NoReturn:
    raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)


def attest_export_rights(
    gate: SignedRightsGate, *, bearer: str, case_id: str,
    sources: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    """Evaluate each server-frozen source exactly once, fail closed, no secrets."""
    if not sources or len(sources) > 32:
        _error()
    evaluations = gate.require_bundle(
        bearer=bearer, case_id=case_id, sources=sources, action=Action.EXPORT,
    )
    if len(evaluations) != len(sources):
        _error()
    rows: list[dict[str, Any]] = []
    for source, evaluation in zip(sources, evaluations, strict=True):
        document, version, digest = (
            source.get("document_id"), source.get("version_id"), source.get("sha256"),
        )
        if (
            not isinstance(document, str) or UUID.fullmatch(document) is None
            or not isinstance(version, str) or UUID.fullmatch(version) is None
            or not isinstance(digest, str) or HEX64.fullmatch(digest) is None
            or evaluation.decision is not Decision.ALLOW
            or type(evaluation.policy_version) is not int
            or evaluation.policy_version < 1
        ):
            _error()
        rows.append({
            "document_id": document,
            "version_id": version,
            "original_sha256": digest,
            "decision": "allow",
            "policy_version": evaluation.policy_version,
        })
    attestation = {
        "schema": SCHEMA,
        "action": "export",
        "scope": "same_matter",
        "decision": "allow",
        "sources": rows,
    }
    validate_export_rights(attestation, sources)
    return attestation


def validate_export_rights(
    attestation: object, sources: Sequence[Mapping[str, object]],
) -> None:
    """Validate structure and frozen source correspondence on historical reads.

    Caller still MUST authenticate, check the existing server HMAC and artifact
    hashes. This never reauthorizes a historical artifact after policy changes.
    """
    if not isinstance(attestation, dict) or set(attestation) != {
        "schema", "action", "scope", "decision", "sources",
    } or (
        attestation["schema"] != SCHEMA
        or attestation["action"] != "export"
        or attestation["scope"] != "same_matter"
        or attestation["decision"] != "allow"
    ):
        _error()
    rows = attestation["sources"]
    if (
        not isinstance(rows, list) or not isinstance(sources, Sequence)
        or not 0 < len(rows) <= 32 or len(rows) != len(sources)
    ):
        _error()
    expected: dict[str, str] = {}
    for source in sources:
        if not isinstance(source, Mapping):
            _error()
        version, digest = source.get("version_id"), source.get("sha256")
        if not isinstance(version, str) or not isinstance(digest, str) or version in expected:
            _error()
        expected[version] = digest
    seen: set[str] = set()
    for entry in rows:
        if not isinstance(entry, dict) or set(entry) != {
            "document_id", "version_id", "original_sha256", "decision", "policy_version",
        }:
            _error()
        document, version, digest = (
            entry["document_id"], entry["version_id"], entry["original_sha256"],
        )
        if (
            not isinstance(document, str) or UUID.fullmatch(document) is None
            or not isinstance(version, str) or UUID.fullmatch(version) is None
            or not isinstance(digest, str) or HEX64.fullmatch(digest) is None
            or version not in expected or version in seen
            or expected[version] != digest
            or entry["decision"] != "allow"
            or type(entry["policy_version"]) is not int or entry["policy_version"] < 1
        ):
            _error()
        seen.add(version)
