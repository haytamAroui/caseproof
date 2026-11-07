"""PR202: genuine JWT, explicitly approved source, revoked 403 and teardown.

This is deliberately independent from the branch-protected F3-F6 browser
acceptance: it does not modify their security guard. The scope is one
synthetic original and the signed live review/correction RPCs. It must
never claim F5/F6 browser or Word compatibility markers.
"""
from __future__ import annotations

import hashlib
import os
import sys
from uuid import UUID, uuid4

from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.m05_registry import call, forget, record
from scripts.rights_signed_live import request
from scripts.teardown_test_run import teardown
from scripts.verify_dev_ephemeral_auth import PROJECT_REF, GoTrueDevAdmin
from scripts.verify_dev_live_review_roundtrip import _request, _server_start, _server_stop
from scripts.verify_dev_live_txt_journey import admin_rpc
from tests.fixtures.run_lifecycle import credentials, new_run_id

ORIGINAL = b"CaseProof strictly synthetic invoice: balance 125 EUR.\n"
DIGEST = hashlib.sha256(ORIGINAL).hexdigest()


def demand(status: int, expected: int, stage: str) -> None:
    if status != expected:
        raise RuntimeError("RIGHTS_" + stage + "_EXPECTED_HTTP_" + str(expected))


def main() -> int:
    if (
        os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
        or os.getenv("CASEPROOF_RIGHTS_SIGNED_LIVE") != "YES"
        or os.getenv("ENFORCE_DOCUMENT_RIGHTS") != "true"
    ):
        raise RuntimeError("RIGHTS_TEST_REQUIRES_EXPLICIT_DEV_ENFORCEMENT")
    admin_key = os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
    publishable = os.environ["CASEPROOF_DEV_PUBLISHABLE_KEY"]
    if not publishable.startswith("sb_publishable_"):
        raise RuntimeError("RIGHTS_PUBLISHABLE_KEY_REQUIRED")
    run = new_run_id()
    record(admin_key, run, "run", run)
    generated = credentials(run)
    actors: dict[str, str] = {}
    case: str | None = None
    proc = None
    failure: Exception | None = None
    try:
        admin = GoTrueDevAdmin(admin_key)
        for role, (email, password) in generated.items():
            record(admin_key, run, "auth_user", role + ":" + email, "RESERVED")
            actor = admin.create_confirmed(email=email, password=password)
            actors[role] = actor
            record(admin_key, run, "auth_user", role + ":" + actor, "CREATED")
            forget(admin_key, run, "auth_user", role + ":" + email)
        setup = admin_rpc(admin_key, "setup", {
            "p_run": run,
            "p_owner": actors["owner"],
            "p_guest": actors["ungranted"],
            "p_foreign": actors["foreign"],
        })
        org = str(UUID(setup["org_id"]))
        signin = SupabasePasswordSignin(PROJECT_REF, publishable)
        owner = signin.sign_in(PasswordCredentials(*generated["owner"]))
        guest = signin.sign_in(PasswordCredentials(*generated["ungranted"]))
        if owner.user_id != actors["owner"] or guest.user_id != actors["ungranted"]:
            raise RuntimeError("RIGHTS_GENUINE_AUTH_SUBJECT_MISMATCH")
        proc = _server_start()
        status, body = _request(owner.access_token, "POST", "/dev/live/matters", {
            "org_id": org,
            "name": "Synthetic rights acceptance",
            "request_id": str(uuid4()),
        })
        demand(status, 200, "SIGNED_CREATE")
        case = str(UUID(body["case_id"]))
        record(admin_key, run, "matter", case, "CREATED")
        status, source = _request(
            owner.access_token, "POST", f"/dev/live/matters/{case}/sources",
            {"request_id": str(uuid4()), "filename": "synthetic_invoice.txt",
             "sha256": DIGEST, "byte_length": len(ORIGINAL), "media_type": "text/plain"},
        )
        demand(status, 200, "SIGNED_REGISTER")
        doc, version = (str(UUID(source[key])) for key in ("document_id", "version_id"))
        record(admin_key, run, "storage_file",
               "/".join((org, case, doc, version, DIGEST)))
        status, grant = request(
            admin_key, "/rest/v1/rpc/caseproof_rights_fixture_grant",
            {"p_run": run, "p_case": case, "p_owner": owner.user_id},
        )
        if status != 200 or grant is not True:
            raise RuntimeError("RIGHTS_OWNED_TEST_GRANT_MISSING")
        explicit_rights = {
            "origin": "CLIENT_UPLOAD",
            "classification": "CLIENT_CONFIDENTIAL",
            "authorization_reference": "synthetic-run-" + run,
            "process": True, "indexForSearch": True,
            "useAcrossMatters": False, "export": True,
        }
        rights_rpc = "/rest/v1/rpc/caseproof_rights_manage"
        status, approved = request(
            publishable, rights_rpc,
            {"p_case": case, "p_document": doc, "p_version": version,
             "p_expected_version": 0, "p_request": str(uuid4()),
             "p_policy": explicit_rights}, bearer=owner.access_token,
        )
        demand(status, 200, "SIGNED_RIGHTS_APPROVAL")
        if not isinstance(approved, dict) or approved.get("policy_version") != 1:
            raise RuntimeError("RIGHTS_SIGNED_APPROVED_REVISION_MISSING")
        status, _ = request(
            publishable, "/rest/v1/rpc/caseproof_rights_current",
            {"p_case": case, "p_document": doc, "p_version": version},
            bearer=guest.access_token,
        )
        demand(status, 403, "UNGRANTED_RIGHTS_READ")
        print("RIGHTS_GENUINE_JWT_APPROVED_POLICY_UNGRANTED_403_PASSED", flush=True)

        import base64
        path = f"/dev/live/matters/{case}/sources/{doc}/{version}"
        status, upload = _request(
            owner.access_token, "POST", path + "/upload",
            {"content_base64": base64.b64encode(ORIGINAL).decode("ascii")},
        )
        demand(status, 200, "SIGNED_UPLOAD")
        if upload.get("sha256") != DIGEST or upload.get("verified") is not True:
            raise RuntimeError("RIGHTS_ORIGINAL_READBACK_NOT_VERIFIED")
        status, ingested = _request(
            owner.access_token, "POST",
            path + "/ingest?request_id=" + str(uuid4()),
        )
        demand(status, 200, "APPROVED_PROCESS")
        if ingested.get("original_sha") != DIGEST:
            raise RuntimeError("RIGHTS_PROCESSED_ORIGINAL_CHANGED")
        if admin_rpc(admin_key, "org_write", {
            "p_run": run, "p_owner": actors["owner"],
            "p_case": case, "p_enabled": True,
        }) is not True:
            raise RuntimeError("RIGHTS_SYNTHETIC_DRAFT_WRITE_GRANT_DENIED")
        text = "The synthetic balance is 125 EUR and requires human review."
        status, authored = _request(
            owner.access_token, "POST",
            f"/dev/live/matters/{case}/briefs",
            {"source_version_id": version, "text": text,
             "quote": "125 EUR", "request_id": str(uuid4())},
        )
        demand(status, 200, "AUTHORED_BRIEF")
        brief = str(UUID(authored["brief_version_id"]))
        base = f"/dev/live/matters/{case}/briefs/{brief}"
        status, checked = _request(owner.access_token, "POST", base + "/check")
        demand(status, 200, "APPROVED_SIGNED_CHECK")
        if checked.get("outcome") != "candidate_quote_supported":
            raise RuntimeError("RIGHTS_SIGNED_CHECK_EVIDENCE_MISMATCH")
        status, _ = _request(guest.access_token, "POST", base + "/check")
        if status not in (403, 404):
            raise RuntimeError("RIGHTS_UNGRANTED_CHECK_NOT_DENIED")
        print("RIGHTS_GENUINE_JWT_APPROVED_INGEST_CHECK_PASSED", flush=True)

        # New append-only denial must supersede the earlier explicit ALLOW.
        restricted = {**explicit_rights, "process": False, "export": False,
                      "indexForSearch": False}
        status, denied_policy = request(
            publishable, rights_rpc,
            {"p_case": case, "p_document": doc, "p_version": version,
             "p_expected_version": 1, "p_request": str(uuid4()),
             "p_policy": restricted}, bearer=owner.access_token,
        )
        demand(status, 200, "SIGNED_REVOCATION_WRITE")
        if not isinstance(denied_policy, dict) or denied_policy.get("policy_version") != 2:
            raise RuntimeError("RIGHTS_LATEST_DENIAL_NOT_PERSISTED")
        status, _ = request(
            publishable, "/rest/v1/rpc/caseproof_dev_live_review",
            {"p_case": case, "p_version": brief, "p_action": "check"},
            bearer=owner.access_token,
        )
        demand(status, 403, "DIRECT_RPC_CHECK_AFTER_DENIAL")
        status, _ = request(
            publishable, "/rest/v1/rpc/caseproof_dev_correct_brief",
            {"p_case": case, "p_version": brief, "p_snapshot": checked["snapshot_hash"],
             "p_expected_review": 1, "p_before": "125 EUR", "p_after": "126 EUR",
             "p_action": "preview"},
            bearer=owner.access_token,
        )
        demand(status, 403, "DIRECT_RPC_CORRECTION_AFTER_DENIAL")
        print("RIGHTS_DIRECT_RPC_DENIAL_AFTER_REVOCATION_403_PASSED", flush=True)

        if admin_rpc(admin_key, "revoke", {
            "p_run": run, "p_owner": actors["owner"], "p_case": case,
        }) is not True:
            raise RuntimeError("RIGHTS_SYNTHETIC_MEMBERSHIP_REVOKE_FAILED")
        status, _ = request(
            publishable, "/rest/v1/rpc/caseproof_rights_current",
            {"p_case": case, "p_document": doc, "p_version": version},
            bearer=owner.access_token,
        )
        demand(status, 403, "REVOKED_USER_RIGHTS")
        print("RIGHTS_GENUINE_JWT_REVOKED_MEMBERSHIP_403_PASSED", flush=True)
    except Exception as exc:
        failure = exc
    finally:
        _server_stop(proc)
        try:
            teardown(run, admin_key)
        except Exception:
            print("RIGHTS_TEARDOWN_FAILED", file=sys.stderr)
            return 1
    if call(admin_key, "verify", run) is not True:
        raise RuntimeError("RIGHTS_RESIDUAL_FIXTURE_ENTRIES")
    print("ZERO_RESIDUAL_VERIFIED", flush=True)
    if failure is not None:
        print("RIGHTS_SIGNED_E2E_FAILED:" + type(failure).__name__, file=sys.stderr)
        return 1
    print("RIGHTS_GENUINE_SIGNED_ALLOW_DENY_CLEANUP_PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
