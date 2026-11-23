"""Validate explicit trusted-ingestion lineage, never impersonate a vault intent."""
from __future__ import annotations

import re
from uuid import UUID

_SHA = re.compile(r"^[0-9a-f]{64}$")


def valid_storage_binding(
    binding: object, *, org: str, case: str, document: str, version: str,
    original_sha: object, representation_sha: object | None = None,
    byte_length: object | None = None, media_type: object | None = None,
) -> bool:
    if not isinstance(binding, dict):
        return False
    try:
        audit = binding.get("audit_id")
        if not isinstance(audit, str) or str(UUID(audit)) != audit or UUID(audit).int == 0:
            return False
    except ValueError:
        return False
    snapshot = binding.get("snapshot_sha256")
    rep = binding.get("representation_sha256")
    length = binding.get("byte_length")
    return bool(
        binding.get("kind") == "trusted_storage_source_v1"
        and binding.get("bucket") == "caseproof-originals-dev"
        and isinstance(original_sha, str) and _SHA.fullmatch(original_sha)
        and binding.get("original_sha256") == original_sha
        and binding.get("object_key") == f"{org}/{case}/{document}/{version}/{original_sha}"
        and isinstance(snapshot, str) and _SHA.fullmatch(snapshot)
        and isinstance(rep, str) and _SHA.fullmatch(rep)
        and (representation_sha is None or rep == representation_sha)
        and type(length) is int and 1 <= length <= 5_242_880
        and (byte_length is None or length == byte_length)
        and binding.get("media_type") in {
            "text/plain", "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        and (media_type is None or binding.get("media_type") == media_type)
    )
