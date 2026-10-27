"""Protected real Supabase dev M1 positive original acceptance.

Uses exactly the existing two GitHub Auth environment secrets, no database DSN.
Only an admin-scoped dev fixture RPC seeds the minimum rows; ALL evidence
operations use three independent real signed-user JWTs through PostgREST and
Storage RLS. Cleanup removes the object via Storage API, then exact fixture
rows, then all GoTrue users. NOT live M2 check/review/recheck acceptance.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

from apps.api.signed_supabase_originals import (
    OriginalRef,
    PrivateStorageDenied,
    SignedOriginalsStorage,
)
from apps.api.signed_supabase_source_library import SignedSourceLibrary
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import ISSUER, PROJECT_REF, GoTrueDevAdmin
from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe

HOST = f"{PROJECT_REF}.supabase.co"
FIXTURE = b"CASEPROOF CI 2026: synthetic proof of 125 EUR on 23 October. Not client evidence.\n"
DIGEST = hashlib.sha256(FIXTURE).hexdigest()
MAX_RESPONSE = 16384


class LiveFixtureError(RuntimeError):
    """Never print provider payloads, JWTs, IDs or emails."""


def _admin_http(
    *, key: str, method: str, path: str, data: dict[str, Any] | None,
) -> tuple[int, Any]:
    # Pinned exact RPCs. Never expose generic SQL or unbounded object actions.
    allowed = {
        "/rest/v1/rpc/caseproof_dev_fixture_begin",
        "/rest/v1/rpc/caseproof_dev_fixture_revoke",
        "/rest/v1/rpc/caseproof_dev_fixture_cleanup",
        "/storage/v1/object/caseproof-originals-dev",
    }
    if path not in allowed or method not in {"POST", "DELETE"}:
        raise LiveFixtureError("unapproved dev admin operation")
    if not (key.startswith("sb_secret_") or key.startswith("eyJ")):
        raise LiveFixtureError("requires existing protected Auth admin secret")
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Legacy admin service-role JWTs remain bearer tokens. New sb_secret_
    # API keys are supplied only as apikey; not as a JWT.
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    conn = http.client.HTTPSConnection(HOST, timeout=12)
    try:
        conn.request(
            method, path,
            body=json.dumps(data, separators=(",", ":")).encode() if data is not None else None,
            headers=headers,
        )
        response = conn.getresponse()
        code = response.status
        raw = response.read(MAX_RESPONSE + 1)
    except (OSError, TimeoutError, http.client.HTTPException):
        raise LiveFixtureError("dev admin API outcome unknown") from None
    finally:
        conn.close()
    if len(raw) > MAX_RESPONSE:
        raise LiveFixtureError("oversized dev admin response")
    try:
        result = json.loads(raw.decode()) if raw else None
    except (UnicodeError, ValueError):
        raise LiveFixtureError("invalid dev admin response") from None
    return code, result


def _rpc(key: str, function: str, values: dict[str, Any]) -> Any:
    if function not in {"begin", "revoke", "cleanup"}:
        raise LiveFixtureError("unapproved fixture RPC")
    status, body = _admin_http(
        key=key, method="POST", path="/rest/v1/rpc/caseproof_dev_fixture_" + function,
        data=values,
    )
    if status != 200:
        raise LiveFixtureError("protected fixture RPC failed")
    return body


def _remove_original(key: str, ref: OriginalRef) -> None:
    status, _ = _admin_http(
        key=key, method="DELETE",
        path="/storage/v1/object/caseproof-originals-dev",
        data={"prefixes": [ref.path]},
    )
    if status not in (200, 204):
        raise LiveFixtureError("admin Storage cleanup failed")


def _denied(op: Any) -> None:
    try:
        op()
    except PrivateStorageDenied:
        return
    raise AssertionError("ungranted or revoked actor could read an existing original")


def verify_positive(
    credentials: tuple[PasswordCredentials, ...],
    *,
    admin_key: str, publishable: str,
) -> None:
    if len(credentials) != 3:
        raise AssertionError("requires three independent GoTrue identities")
    signin = SupabasePasswordSignin(PROJECT_REF, publishable)
    verifier = SupabaseAuthUserVerifier(
        PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, publishable),
    )
    sessions = tuple(signin.sign_in(c) for c in credentials)
    identities = tuple(verifier.verify_bearer(s.access_token) for s in sessions)
    actors = tuple(i.subject_id for i in identities)
    if len(set(actors)) != 3 or any(
        x.user_id != v.subject_id or v.issuer != ISSUER or v.audience != "authenticated"
        for x, v in zip(sessions, identities, strict=True)
    ):
        raise AssertionError("real signed-user mapping failed")
    print("LIVE 1/6: three confirmed remote signed users")

    run_id = str(uuid4())
    fixture_created = False
    begin_attempted = False
    ref: OriginalRef | None = None
    cleanup_error: Exception | None = None
    storage = SignedOriginalsStorage(publishable)
    library = SignedSourceLibrary(storage)
    try:
        # Even if the HTTPS response is lost after DB COMMIT, a scoped
        # cleanup must still be attempted using our generated run ID.
        begin_attempted = True
        d = _rpc(admin_key, "begin", {
            "p_run_id": run_id,
            "p_owner": actors[0],
            "p_guest": actors[1],
            "p_foreign": actors[2],
            "p_sha": DIGEST,
            "p_size": len(FIXTURE),
        })
        fixture_created = True
        if not isinstance(d, dict) or d.get("sha256_hex") != DIGEST:
            raise LiveFixtureError("fixture issuer returned wrong identity")
        org, case, doc, version = (
            str(UUID(d[k])) for k in ("org_id","case_id","document_id","version_id")
        )
        ref = OriginalRef(UUID(org), UUID(case), UUID(doc), UUID(version),
                          DIGEST, "text/plain")
        args = {"case_id": case, "document_id": doc, "version_id": version}
        resolved, n = library.source(bearer=sessions[0].access_token, **args)
        if resolved != ref or n != len(FIXTURE):
            raise AssertionError("actual signed view returned incorrect version")
        print("LIVE 2/6: real private case, exact grant and version resolved via signed PostgREST")

        library.put_once(bearer=sessions[0].access_token, data=FIXTURE, **args)
        readback = library.read(bearer=sessions[0].access_token, **args)
        if readback != FIXTURE or hashlib.sha256(readback).hexdigest() != DIGEST:
            raise AssertionError("original bytes/digest do not match")
        print("LIVE 3/6: real Storage upload and SHA-256-verified readback")

        for outsider in sessions[1:]:
            _denied(lambda u=outsider: storage.get_verified(ref, u.access_token))
            _denied(lambda u=outsider: library.read(bearer=u.access_token, **args))
        print("LIVE 4/6: same-org ungranted and foreign-org users denied EXISTING original")

        if _rpc(admin_key,"revoke",{"p_run_id":run_id,"p_owner":actors[0]}) is not True:
            raise AssertionError("grant revocation did not succeed")
        _denied(lambda: storage.get_verified(ref, sessions[0].access_token))
        _denied(lambda: library.read(bearer=sessions[0].access_token, **args))
        print("LIVE 5/6: grant revoked, even owner loses access to EXISTING original")
    finally:
        if begin_attempted:
            try:
                if ref is not None:
                    _remove_original(admin_key, ref)
                cleaned = _rpc(admin_key, "cleanup",
                               {"p_run_id": run_id, "p_owner": actors[0]})
                if fixture_created and cleaned is not True:
                    raise LiveFixtureError("expected exact fixture not removed")
                if cleaned not in (True, False):
                    raise LiveFixtureError("invalid cleanup receipt")
            except Exception as e:
                cleanup_error = e
        if cleanup_error is not None:
            raise LiveFixtureError("fixture cleanup failed; inspect dev and retry controlled cleanup") from None
    print("LIVE 6/6: admin Storage delete and SQL fixture cleanup completed")


def main() -> int:
    try:
        if (
            os.getenv("CASEPROOF_DEV_LIVE_POSITIVE") != "YES"
            or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
            or os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.getenv("GITHUB_REF") != "refs/heads/main"
        ):
            raise LiveFixtureError("protected main-only manual run required")
        admin_key = os.environ.get("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
        publishable = os.environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
        admin = GoTrueDevAdmin(admin_key)
        if not publishable.startswith("sb_publishable_"):
            raise LiveFixtureError("dev publishable key required")
        ephemeral_private_probe(
            admin=admin,
            probe=lambda credentials: verify_positive(
                credentials, admin_key=admin_key, publishable=publishable,
            ),
        )
        print("LIVE_M1_POSITIVE_AUTH_RLS_STORAGE_CLEANUP_PASSED")
        print("LIVE_M2_CHECK_REVIEW_CORRECTION_NOT_RUN_IN_THIS_WORKFLOW")
        return 0
    except Exception as exc:
        print(f"LIVE_M1_POSITIVE_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
