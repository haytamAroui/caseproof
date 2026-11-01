"""Protected development probe: signed registration of a draft, inventory, and two exhibits.

This deliberately fails if the existing RPC still enforces a single original.
It is NOT an acceptance receipt until the full upload/readback/revoke/restart
journey is wired and run in protected CI.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import sys
from uuid import UUID, uuid4

from apps.api.signed_supabase_originals import OriginalRef, PrivateStorageDenied, SignedOriginalsStorage
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import ISSUER, PROJECT_REF
from scripts.verify_dev_live_review_roundtrip import _request, _server_start, _server_stop
from scripts.verify_dev_live_txt_journey import LiveFixtureError, admin_rpc, success


def _pdf(objects: list[bytes]) -> bytes:
    """Construct a deterministic, valid single-page PDF with an xref table."""
    data = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(data)


def _text_pdf(text: str) -> bytes:
    stream = f"BT /F1 14 Tf 40 180 Td ({text}) Tj ET".encode()
    return _pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 240] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ])


def _scan_pdf() -> bytes:
    import zlib
    width, height = 240, 120
    # Image-only: black strokes on white pixels, no PDF text operators.
    pixels = bytes(
        0 if (22 < y < 90 and (x // 11 + y // 8) % 7 == 0) else 255
        for y in range(height) for x in range(width)
    )
    image = zlib.compress(pixels)
    stream = b"q 240 0 0 120 0 0 cm /Im1 Do Q"
    return _pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 240 120] "
        b"/Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        (f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
         f"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode "
         f"/Length {len(image)} >>\nstream\n").encode() + image + b"\nendstream",
    ])


def _sources() -> tuple[tuple[str, str, bytes], ...]:
    """Same four genuine synthetic formats as the Phase 3 dossier fixture."""
    from tests.fixtures.factory import generate_bundle

    return tuple((source.filename, source.media_type, source.content) for source in generate_bundle())



def _validate_registration(registered: object, case: str, metadata: list[dict]) -> list[dict]:
    """Do not upload against a response with altered scope, bytes or identifiers."""
    if not isinstance(registered, dict) or registered.get("case_id") != case:
        raise LiveFixtureError("signed bundle registration returned wrong matter")
    rows = registered.get("sources")
    if not isinstance(rows, list) or len(rows) != len(metadata):
        raise LiveFixtureError("signed bundle registration returned incomplete identities")
    documents, versions = set(), set()
    for row, expected in zip(rows, metadata, strict=True):
        if not isinstance(row, dict) or any(row.get(key) != value for key, value in expected.items()):
            raise LiveFixtureError("registered source metadata differs from request")
        try:
            document, version = UUID(row["document_id"]), UUID(row["version_id"])
        except (KeyError, ValueError, TypeError, AttributeError):
            raise LiveFixtureError("registered source identity invalid") from None
        if document in documents or version in versions:
            raise LiveFixtureError("registered source identity duplicated")
        documents.add(document)
        versions.add(version)
    return rows



def verify_registration(
    credentials: tuple[PasswordCredentials, PasswordCredentials, PasswordCredentials],
    *, admin_key: str, publishable: str,
) -> None:
    signin = SupabasePasswordSignin(PROJECT_REF, publishable)
    sessions = tuple(signin.sign_in(item) for item in credentials)
    verifier = SupabaseAuthUserVerifier(PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, publishable))
    identities = tuple(verifier.verify_bearer(session.access_token) for session in sessions)
    actors = tuple(identity.subject_id for identity in identities)
    if (len(set(actors)) != 3 or any(
        identity.subject_id != session.user_id or identity.issuer != ISSUER
        or identity.audience != "authenticated"
        for identity, session in zip(identities, sessions, strict=True)
    )):
        raise LiveFixtureError("three distinct signed users required")
    run_id = str(uuid4())
    proc = None
    refs = []
    cleanup_refs = []
    sources = _sources()
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
        metadata = [
            {
                "role": ("draft", "inventory", "exhibit", "exhibit")[index],
                "filename": filename,
                "media_type": media_type,
                "byte_length": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for index, (filename, media_type, payload) in enumerate(sources)
        ]
        con = http.client.HTTPSConnection(f"{PROJECT_REF}.supabase.co", timeout=15)
        try:
            con.request(
                "POST", "/rest/v1/rpc/caseproof_dev_register_bundle",
                json.dumps({"p_case": case, "p_request": str(uuid4()), "p_sources": metadata}).encode(),
                headers={
                    "apikey": publishable,
                    "Authorization": "Bearer " + owner,
                    "Content-Type": "application/json",
                },
            )
            response = con.getresponse()
            status, raw = response.status, response.read(16385)
        finally:
            con.close()
        if status != 200:
            raise LiveFixtureError("MULTISOURCE_BLOCKED: signed bundle registration rejected")
        registered = json.loads(raw)
        registered_rows = _validate_registration(registered, case, metadata)
        print("LIVE_MULTISOURCE_REGISTERED: draft, inventory and two exhibit versions")
        stored = SignedOriginalsStorage(publishable)
        outsiders = (sessions[1].access_token, sessions[2].access_token)
        for source, item in zip(sources, registered_rows, strict=True):
            filename, media_type, payload = source
            ref = OriginalRef(
                UUID(org), UUID(case), UUID(item["document_id"]),
                UUID(item["version_id"]), hashlib.sha256(payload).hexdigest(), media_type,
            )
            refs.append(ref)
            cleanup_refs.append(ref)
            endpoint = (
                f"/dev/live/matters/{case}/sources/"
                f"{ref.document_id}/{ref.version_id}/upload"
            )
            encoded = {"content_base64": base64.b64encode(payload).decode("ascii")}
            for outsider in outsiders:
                status, _ = _request(outsider, "POST", endpoint, encoded)
                if status not in (401, 403, 404):
                    raise LiveFixtureError("unauthorized original upload was not denied")
            uploaded = success(owner, "POST", endpoint, encoded)
            if uploaded.get("verified") is not True or uploaded.get("sha256") != ref.sha256_hex:
                raise LiveFixtureError("Storage SHA-256 upload verification missing")
            if stored.get_verified(ref, owner) != payload:
                raise LiveFixtureError("Storage SHA-256 readback bytes differ")
            for outsider in outsiders:
                try:
                    stored.get_verified(ref, outsider)
                except PrivateStorageDenied:
                    pass
                else:
                    raise LiveFixtureError("unauthorized original download accepted")
        print("LIVE_MULTISOURCE_STORAGE: four signed uploads, hash readbacks, outsider denials")
        # A new process must reconstruct the same signed source metadata and bytes.
        _server_stop(proc)
        proc = None
        refs.clear()  # Deliberately discard all pre-restart Storage references.
        proc = _server_start()
        fresh = signin.sign_in(credentials[0])
        if fresh.user_id != actors[0]:
            raise LiveFixtureError("fresh sign-in changed the matter owner")
        print("LIVE_MULTISOURCE_REOPEN: cold process restart and fresh signed session")
        # Rediscover from durable database records, not the pre-restart refs list.
        for outsider in outsiders:
            denied, _ = _request(outsider, "GET", f"/dev/live/matters/{case}/manifest")
            if denied not in (401, 403, 404):
                raise LiveFixtureError("outsider manifest access was not denied")
        manifest_status, manifest = _request(fresh.access_token, "GET", f"/dev/live/matters/{case}/manifest")
        if manifest_status != 200 or manifest.get("case_id") != case:
            raise LiveFixtureError("signed cold manifest rediscovery failed")
        actual = manifest.get("sources")
        if not isinstance(actual, list) or len(actual) != 4:
            raise LiveFixtureError("persisted bundle incomplete")
        expected = [dict(item, version_number=1) for item in registered_rows]
        if actual != expected:
            raise LiveFixtureError("persisted manifest differs from registration")
        rediscovered = []
        for item, (_, _, payload) in zip(actual, sources, strict=True):
            ref = OriginalRef(UUID(org), UUID(case), UUID(item["document_id"]),
                              UUID(item["version_id"]), item["sha256"], item["media_type"])
            rediscovered.append(ref)
            if stored.get_verified(ref, fresh.access_token) != payload:
                raise LiveFixtureError("persisted manifest source readback mismatch")
        refs.extend(rediscovered)  # Revocation checks use only manifest-derived references.
        print("LIVE_MULTISOURCE_MANIFEST_REOPEN: durable identities, roles and four hashes")
        print("LIVE_MULTISOURCE_MANIFEST_DENIED: foreign and ungranted identities")


        if admin_rpc(admin_key, "revoke", {
            "p_run": run_id, "p_owner": actors[0], "p_case": case,
        }) is not True:
            raise LiveFixtureError("bundle matter revoke failed")
        for ref in refs:
            try:
                stored.get_verified(ref, fresh.access_token)
            except PrivateStorageDenied:
                pass
            else:
                raise LiveFixtureError("revoked owner still reads a bundle member")
        denied, _ = _request(fresh.access_token, "GET", f"/dev/live/matters/{case}/manifest")
        if denied not in (401, 403, 404):
            raise LiveFixtureError("revoked manifest access was not denied")
        print("LIVE_MULTISOURCE_REVOKED: all four original paths and manifest denied")


    finally:
        if proc is not None:
            _server_stop(proc)
        from scripts.verify_m1_live_positive_original import _remove_original
        cleanup_errors = []
        for ref in cleanup_refs:
            try:
                _remove_original(admin_key, ref)
            except Exception as exc:
                cleanup_errors.append("storage:" + type(exc).__name__)
        try:
            admin_rpc(admin_key, "cleanup", {"p_run": run_id, "p_owner": actors[0]})
        except Exception as exc:
            cleanup_errors.append("fixture:" + type(exc).__name__)
        if cleanup_errors:
            print("LIVE_MULTISOURCE_TEARDOWN: " + ", ".join(cleanup_errors), file=sys.stderr)
            raise LiveFixtureError("scoped bundle cleanup failed")
        print("LIVE_MULTISOURCE_TEARDOWN: storage and fixture cleanup completed", flush=True)

def main() -> int:
    if (
        os.getenv("CASEPROOF_DEV_LIVE_MULTISOURCE") != "YES"
        or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
        or os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
    ):
        print("LIVE_MULTISOURCE_FAILED: protected main-branch dispatch required", file=sys.stderr)
        return 1
    from scripts.verify_dev_ephemeral_auth import GoTrueDevAdmin
    from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe

    publishable = os.getenv("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
    admin_key = os.getenv("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
    if not publishable.startswith("sb_publishable_") or not admin_key:
        print("LIVE_MULTISOURCE_FAILED: missing protected credentials", file=sys.stderr)
        return 1
    try:
        ephemeral_private_probe(
            admin=GoTrueDevAdmin(admin_key),
            probe=lambda credentials: verify_registration(
                credentials, admin_key=admin_key, publishable=publishable,
            ),
        )
        print("LIVE_MULTISOURCE_PROBE_PASSED: signed draft/inventory/PDF/scan storage/revocation/restart")
        return 0
    except Exception as exc:
        stage = "ephemeral_auth_cleanup" if isinstance(exc, RuntimeError) and str(exc) == "ephemeral dev identity cleanup failed" else "probe_or_fixture"
        print(f"LIVE_MULTISOURCE_FAILED: stage={stage} type={type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
