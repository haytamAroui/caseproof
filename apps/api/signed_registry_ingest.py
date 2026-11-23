"""Service-side derivation for trusted-registry ingestion of parsed originals.

The SQL TXT ingest decodes bytes itself; a DOCX cannot be parsed in SQL,
so the trusted path splits in two:

1. this module derives the registry payload from verified original bytes
   with the bounded fail-closed parser, applying the same publishability
   gate as the signed composer (contiguous block coverage, no warning
   beyond unverified layout page numbers);
2. public.caseproof_registry_ingest_parsed (service_role only) re-verifies
   everything SQL can verify — document version, media, custody path and
   digest against storage.objects, verified vault intent — computes the
   digests itself and freezes the immutable registry row.

No transport lives here on purpose: the service_role caller is wired by
the owner-approved ingestion runner, never by a signed-user path.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import re
from typing import Any
from uuid import UUID

from application.extraction.contracts import ExtractionError
from apps.api.signed_document_parse import parse_verified_original
from apps.api.signed_live_brief_composer import (
    _DOCX_MIME,
    _DOCX_PUBLISHABLE_WARNINGS,
)
from apps.api.signed_supabase_originals import (
    PrivateStorageDenied,
    PrivateStorageFailure,
    PrivateStorageOutcomeUnknown,
)

MAX_REPRESENTATION_BYTES = 1_048_576
MAX_ARGS_BYTES = 1_200_000
MAX_RESPONSE_BYTES = 65_536
PROJECT_REF = "ldwmocpxwskvhoojndrd"  # CaseProof dev. Never another project.
SECRET_KEY_ENV = "CASEPROOF_SUPABASE_SECRET_KEY"
_SECRET_KEY = re.compile(r"^sb_secret_[A-Za-z0-9_-]+$")
_RPC_NAME = re.compile(r"^caseproof_[a-z0-9_]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def derive_registry_ingest(
    *, document_id: str, version_id: str, data: bytes, media_type: str
) -> dict[str, str]:
    """Verified original bytes -> registry payload, fail-closed.

    Returns exactly the fields the service_role RPC takes beyond the
    identifiers: the parsed representation and the parser identity. Any
    coverage gap, unsupported media or over-limit result raises
    ExtractionError — a partial extraction is never ingested as trusted.
    """
    if media_type != _DOCX_MIME:
        raise ExtractionError("unsupported_parsed_ingest_media")
    text, manifest = parse_verified_original(
        document_id=document_id, version_id=version_id,
        data=data, media_type=media_type,
    )
    warnings = manifest.get("warnings")
    if (
        not isinstance(warnings, list)
        or set(warnings) - _DOCX_PUBLISHABLE_WARNINGS
        or not manifest.get("blocks")
    ):
        raise ExtractionError("parsed_coverage_gap")
    parser_id = manifest.get("parser_id")
    if type(parser_id) is not str or not 0 < len(parser_id) <= 256:
        raise ExtractionError("parser_identity_invalid")
    if not 0 < len(text.encode("utf-8")) <= MAX_REPRESENTATION_BYTES:
        raise ExtractionError("parsed_representation_limit")
    return {"representation": text, "parser_id": parser_id}


def secret_key_from_env(environ: dict[str, str]) -> str:
    """Service secret key from explicit configuration, never logged."""
    key = environ.get(SECRET_KEY_ENV, "")
    if not isinstance(key, str) or not _SECRET_KEY.fullmatch(key):
        raise ValueError(f"{SECRET_KEY_ENV} must be a Supabase secret key")
    return key


def _uuid(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"invalid {field_name}")
    try:
        parsed = UUID(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid {field_name}") from None
    if str(parsed) != value or parsed.int == 0:
        raise ValueError(f"invalid {field_name}")
    return value


def call_service_rpc(
    *,
    secret_key: str,
    name: str,
    args: dict[str, Any],
    timeout_seconds: float = 12.0,
    _conn_factory: object = None,
) -> Any:
    """Bounded service_role JSON-RPC POST, mirroring call_rpc's discipline.

    The secret key authenticates as apikey AND bearer (Supabase secret-key
    convention); it is never logged nor included in errors. Denials stay
    masked, network failures are UNKNOWN_OUTCOME (never silently retried
    into a duplicate write), and the RPC remains the write gate.
    """
    if not isinstance(secret_key, str) or not _SECRET_KEY.fullmatch(secret_key):
        raise ValueError("Use a Supabase secret key, never a publishable key")
    if not isinstance(name, str) or not _RPC_NAME.fullmatch(name):
        raise ValueError("Unsupported RPC name")
    if not isinstance(args, dict) or not all(type(k) is str for k in args):
        raise ValueError("RPC arguments must be a string-keyed object")
    if not 0.1 <= timeout_seconds <= 30.0:
        raise ValueError("Invalid RPC timeout")
    payload = json.dumps(args, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_ARGS_BYTES:
        raise ValueError("RPC arguments outside allowed bounds")

    factory = _conn_factory or (
        lambda: http.client.HTTPSConnection(
            PROJECT_REF + ".supabase.co", timeout=timeout_seconds,
        )
    )
    conn = factory()  # type: ignore[operator]
    headers = {
        "apikey": secret_key,
        "Authorization": "Bearer " + secret_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Cache-Control": "no-store",
    }
    try:
        conn.request("POST", "/rest/v1/rpc/" + name, body=payload, headers=headers)
        response = conn.getresponse()
        status = response.status
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, TimeoutError, http.client.HTTPException):
        raise PrivateStorageOutcomeUnknown("RPC network outcome unknown") from None
    finally:
        conn.close()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise PrivateStorageFailure("Oversized RPC response")
    if status in (401, 403, 404):
        raise PrivateStorageDenied("Private RPC unavailable")
    try:
        body = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PrivateStorageFailure("Unparseable RPC response") from None
    if status != 200:
        code = body.get("code") if isinstance(body, dict) else None
        if code in {"PGRST202", "42501", "PGRST301"}:
            # Missing from the schema cache or insufficient privilege:
            # never leak which one to the caller.
            raise PrivateStorageDenied("Private RPC unavailable")
        if code == "22023":
            raise ValueError("invalid parsed ingestion")
        if code == "23505":
            raise ValueError("immutable ingestion conflict")
        raise PrivateStorageFailure("RPC call failed")
    return body


def ingest_parsed_original(
    *,
    secret_key: str,
    case_id: str,
    document_id: str,
    version_id: str,
    request_id: str,
    data: bytes,
    media_type: str,
    timeout_seconds: float = 12.0,
    _conn_factory: object = None,
) -> dict[str, str]:
    """Derive the registry payload from verified bytes and ingest it.

    data MUST be the verified readback of the immutable Storage object for
    this exact version; the response is bound back to those bytes by
    comparing the registry's recorded original digest with the local
    digest of data, so a custody mismatch is a failure, never a success.
    """
    case_key = _uuid(case_id, "case_id")
    document_key = _uuid(document_id, "document_id")
    version_key = _uuid(version_id, "version_id")
    request_key = _uuid(request_id, "request_id")
    if type(data) is not bytes or not data:
        raise ValueError("verified original bytes required")
    derived = derive_registry_ingest(
        document_id=document_key, version_id=version_key,
        data=data, media_type=media_type,
    )
    result = call_service_rpc(
        secret_key=secret_key,
        name="caseproof_registry_ingest_parsed",
        args={
            "p_case": case_key,
            "p_document": document_key,
            "p_version": version_key,
            "p_request": request_key,
            "p_representation": derived["representation"],
            "p_parser_id": derived["parser_id"],
        },
        timeout_seconds=timeout_seconds,
        _conn_factory=_conn_factory,
    )
    if not isinstance(result, dict):
        raise PrivateStorageFailure("RPC result outside the ingestion contract")
    original_sha = result.get("original_sha")
    if (
        result.get("case_id") != case_key
        or result.get("document_id") != document_key
        or result.get("version_id") != version_key
        or type(original_sha) is not str
        or original_sha != hashlib.sha256(data).hexdigest()
        or type(result.get("representation_sha")) is not str
        or not _SHA256.fullmatch(result["representation_sha"])
        or result["representation_sha"]
        != hashlib.sha256(derived["representation"].encode("utf-8")).hexdigest()
        or type(result.get("snapshot_sha")) is not str
        or not _SHA256.fullmatch(result["snapshot_sha"])
    ):
        raise PrivateStorageFailure("RPC result outside the ingestion contract")
    return {
        "case_id": case_key,
        "document_id": document_key,
        "version_id": version_key,
        "original_sha": original_sha,
        "representation_sha": result["representation_sha"],
        "snapshot_sha": result["snapshot_sha"],
    }


__all__ = [
    "SECRET_KEY_ENV",
    "call_service_rpc",
    "derive_registry_ingest",
    "ingest_parsed_original",
    "secret_key_from_env",
]
