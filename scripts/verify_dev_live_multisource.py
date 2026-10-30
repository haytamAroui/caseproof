"""Protected development probe: signed registration of one inventory and three exhibits.

This deliberately fails if the existing RPC still enforces a single original.
It is NOT an acceptance receipt until the full upload/readback/revoke/restart
journey is wired and run in protected CI.
"""
from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import PROJECT_REF
from scripts.verify_dev_live_txt_journey import LiveFixtureError, admin_rpc, success
from scripts.verify_dev_live_review_roundtrip import _request, _server_start, _server_stop


SOURCES = (
    ("inventory.txt", "text/plain", b"Inventory: Stuk 1; Stuk 2; Stuk 3\n"),
    ("stuk-1.pdf", "application/pdf", b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"),
    ("stuk-2.pdf", "application/pdf", b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"),
    ("stuk-3-scan.pdf", "application/pdf", b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"),
)


def verify_registration(
    credentials: tuple[PasswordCredentials, PasswordCredentials, PasswordCredentials],
    *, admin_key: str, publishable: str,
) -> None:
    signin = SupabasePasswordSignin(PROJECT_REF, publishable)
    sessions = tuple(signin.sign_in(item) for item in credentials)
    actors = tuple(session.user_id for session in sessions)
    if len(set(actors)) != 3:
        raise LiveFixtureError("three distinct signed users required")
    run_id = str(uuid4())
    proc = None
    try:
        setup = admin_rpc(admin_key, "setup", {
            "p_run": run_id, "p_owner": actors[0],
            "p_guest": actors[1], "p_foreign": actors[2],
        })
        org = str(UUID(setup["org_id"]))
        proc = _server_start()
        owner = sessions[0].access_token
        created = success(owner, "POST", "/dev/live/matters", {
            "org_id": org, "name": "Synthetic multi-source matter", "request_id": str(uuid4()),
        })
        case = str(UUID(created["case_id"]))
        for filename, media_type, payload in SOURCES:
            request = {
                "request_id": str(uuid4()), "filename": filename,
                "media_type": media_type, "byte_length": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            status, result = _request(owner, "POST", f"/dev/live/matters/{case}/sources", request)
            if status != 200:
                raise LiveFixtureError("MULTISOURCE_BLOCKED: signed registration rejected a bundle member")
            if not all(result.get(key) for key in ("document_id", "version_id")):
                raise LiveFixtureError("signed registration returned incomplete identity")
        print("LIVE_MULTISOURCE_REGISTERED: inventory and three exhibit versions")
    finally:
        if proc is not None:
            _server_stop(proc)
        admin_rpc(admin_key, "cleanup", {"p_run": run_id})
