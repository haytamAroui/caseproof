"""Pinned PostgREST JSON-RPC transport for signed-user live adapters.

Every call is a bounded POST to /rest/v1/rpc/<name> on the pinned project
host with the publishable key and the signed user's bearer. No redirects are
followed, responses are size-bounded, network failures are UNKNOWN_OUTCOME
(never silently retried into a duplicate write), and authorization failures
map to masked denial. This module performs no authorization decision itself:
the RPC (security definer, server side) remains the write gate.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import re
from typing import Any

from apps.api.signed_supabase_originals import (
    PrivateStorageDenied,
    PrivateStorageFailure,
    PrivateStorageOutcomeUnknown,
)

PROJECT_REF = "ldwmocpxwskvhoojndrd"  # CaseProof dev. Never another project.
API_KEY = re.compile(r"^sb_publishable_[A-Za-z0-9_-]+$")
RPC_NAME = re.compile(r"^caseproof_[a-z0-9_]+$")
MAX_ARGS_BYTES = 16_384
MAX_RESPONSE_BYTES = 262_144

__all__ = ["call_rpc"]


def call_rpc(
    *,
    publishable_key: str,
    bearer: str,
    name: str,
    args: dict[str, Any],
    timeout_seconds: float = 12.0,
    _conn_factory: object = None,
) -> Any:
    """Call one caseproof RPC and return its parsed JSON result.

    Raises PrivateStorageDenied for masked or unauthorized access (HTTP
    401/403/404, or a PostgREST/PostgreSQL denial payload), ValueError for
    invalid caller input, PrivateStorageOutcomeUnknown when the network
    outcome is uncertain and PrivateStorageFailure for an unusable response.
    """
    if not isinstance(publishable_key, str) or not API_KEY.fullmatch(publishable_key):
        raise ValueError("Use a Supabase publishable key, never a service key")
    if (
        not isinstance(bearer, str) or not bearer or len(bearer) > 8192
        or any(ch in bearer for ch in "\r\n")
    ):
        raise ValueError("Invalid signed-user bearer")
    if not isinstance(name, str) or not RPC_NAME.fullmatch(name):
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
        "apikey": publishable_key,
        "Authorization": "Bearer " + bearer,
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
            # Function missing from the schema cache or insufficient
            # privilege: never leak which one to the caller.
            raise PrivateStorageDenied("Private RPC unavailable")
        raise PrivateStorageFailure("RPC call failed")
    return body


def response_digest(value: Any) -> str:
    """Stable digest of one RPC JSON response, for contract-test pinning."""
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
