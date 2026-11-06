"""Genuine GoTrue JWT rights acceptance for an owned synthetic F3-F6 run.

Only a registered M0.5-owned matter is eligible. No fixture rights are
backfilled into existing dossiers. Never print JWTs, emails, source IDs,
authorization references, document bytes or provider response bodies.
"""
from __future__ import annotations

import http.client
import json
from uuid import UUID, uuid5

from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import PROJECT_REF

HOST = f"{PROJECT_REF}.supabase.co"
MAX_BODY = 8192


def request(
    key: str, endpoint: str, data: dict[str, object], *,
    bearer: str | None = None,
) -> tuple[int, object]:
    if not key.startswith(("sb_publishable_", "sb_secret_", "eyJ")):
        raise RuntimeError("RIGHTS_UNSUPPORTED_TRANSPORT_KEY")
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    headers = {"apikey": key, "Content-Type": "application/json", "Cache-Control": "no-store"}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    elif key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    con = http.client.HTTPSConnection(HOST, timeout=15)
    try:
        con.request("POST", endpoint, raw, headers)
        res = con.getresponse()
        status, body = res.status, res.read(MAX_BODY + 1)
    except (OSError, TimeoutError, http.client.HTTPException):
        raise RuntimeError("RIGHTS_SIGNED_REQUEST_UNAVAILABLE") from None
    finally:
        con.close()
    if len(body) > MAX_BODY:
        raise RuntimeError("RIGHTS_RESPONSE_TOO_LARGE")
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeError):
        parsed = None
    return status, parsed


def signed_session(publishable: str, *, email: str, password: str):
    return SupabasePasswordSignin(PROJECT_REF, publishable).sign_in(
        PasswordCredentials(email=email, password=password),
    )


def approve_owned_bundle(
    *, admin_key: str, publishable: str, run: str, case: str,
    sources: list[dict[str, object]], owner_email: str, owner_password: str,
    ungranted_email: str, ungranted_password: str,
) -> None:
    """Approve exact owned test versions using the signed owner's rights RPC."""
    if not 1 <= len(sources) <= 4 or len({row.get("version_id") for row in sources}) != len(sources):
        raise RuntimeError("RIGHTS_SYNTHETIC_BUNDLE_SCOPE_INVALID")
    owner = signed_session(publishable, email=owner_email, password=owner_password)
    guest = signed_session(publishable, email=ungranted_email, password=ungranted_password)
    if owner.user_id == guest.user_id:
        raise RuntimeError("RIGHTS_TWO_GENUINE_AUTH_SUBJECTS_REQUIRED")
    status, result = request(
        admin_key, "/rest/v1/rpc/caseproof_rights_fixture_grant",
        {"p_run": str(UUID(run)), "p_case": str(UUID(case)),
         "p_owner": str(UUID(owner.user_id))},
    )
    if status != 200 or result is not True:
        raise RuntimeError("RIGHTS_SYNTHETIC_OWNER_GRANT_DENIED")

    for row in sources:
        document_id = str(UUID(str(row["document_id"])))
        version_id = str(UUID(str(row["version_id"])))
        deterministic_request = str(uuid5(UUID(run), "signed-rights:" + version_id))
        approved = {
            "origin": "CLIENT_UPLOAD",
            "classification": "CLIENT_CONFIDENTIAL",
            "authorization_reference": "synthetic-run-" + run,
            "process": True,
            "indexForSearch": True,
            "useAcrossMatters": False,
            "export": True,
        }
        status, result = request(
            publishable, "/rest/v1/rpc/caseproof_rights_manage",
            {"p_case": case, "p_document": document_id,
             "p_version": version_id, "p_expected_version": 0,
             "p_request": deterministic_request, "p_policy": approved},
            bearer=owner.access_token,
        )
        if status != 200 or not isinstance(result, dict) or result.get("policy_version") != 1:
            raise RuntimeError("RIGHTS_GENUINE_OWNER_POLICY_WRITE_DENIED")
        scope = {"p_case": case, "p_document": document_id, "p_version": version_id}
        allowed_status, readback = request(
            publishable, "/rest/v1/rpc/caseproof_rights_current",
            scope, bearer=owner.access_token,
        )
        if (
            allowed_status != 200 or not isinstance(readback, dict)
            or readback.get("policy_status") != "present"
            or readback.get("policy_version") != 1
            or readback.get("process") is not True
            or readback.get("export") is not True
            or readback.get("indexForSearch") is not True
            or readback.get("useAcrossMatters") is not False
        ):
            raise RuntimeError("RIGHTS_GENUINE_OWNER_APPROVAL_READBACK_FAILED")
        blocked_status, _ = request(
            publishable, "/rest/v1/rpc/caseproof_rights_current",
            scope, bearer=guest.access_token,
        )
        if blocked_status != 403:
            raise RuntimeError("RIGHTS_GENUINE_UNGRANTED_USER_NOT_HTTP_403")
    print("RIGHTS_GENUINE_JWT_APPROVED_BUNDLE_AND_UNGRANTED_403_PASSED", flush=True)


def assert_revoked_denied(
    *, publishable: str, case: str, document_id: str, version_id: str,
    owner_email: str, owner_password: str,
) -> None:
    owner = signed_session(publishable, email=owner_email, password=owner_password)
    status, _ = request(
        publishable, "/rest/v1/rpc/caseproof_rights_current",
        {"p_case": case, "p_document": document_id, "p_version": version_id},
        bearer=owner.access_token,
    )
    if status != 403:
        raise RuntimeError("RIGHTS_GENUINE_REVOKED_USER_NOT_HTTP_403")
    print("RIGHTS_GENUINE_JWT_REVOKED_403_PASSED", flush=True)
