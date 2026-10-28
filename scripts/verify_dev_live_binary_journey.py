"""Protected main-only LIVE signed PDF and DOCX acceptance with real Storage bytes.

One synthetic file per newly created private matter. Three GoTrue identities,
actual signed upload/readback, a bounded isolated parser, service-only atomic
promotion, restart/reopen, Word preview without citation authority, revoke and
scoped no-residue cleanup. No confidential material or privileged key in logs.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import os
import sys
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZIP_STORED, ZipFile

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from apps.api.signed_supabase_originals import OriginalRef, PrivateStorageDenied, SignedOriginalsStorage
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import PROJECT_REF, GoTrueDevAdmin
from scripts.verify_dev_live_review_roundtrip import _request, _server_start, _server_stop
from scripts.verify_dev_live_txt_journey import admin_rpc, success, denied
from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe
from scripts.verify_m1_live_positive_original import LiveFixtureError, _remove_original

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
QUOTE = "125 EUR"


def synthetic_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 14 Tf 40 300 Td (CaseProof original evidence says 125 EUR.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    data = BytesIO()
    writer.write(data)
    return data.getvalue()


def synthetic_docx() -> bytes:
    data = BytesIO()
    body = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>CaseProof original evidence says 125 EUR.</w:t>'
        '</w:r></w:p></w:body></w:document>'
    )
    with ZipFile(data, "w", compression=ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", body)
    return data.getvalue()


def signed_original_http(token: str, case: str, brief: str, document: str,
                         version: str) -> tuple[int, bytes, dict[str, str]]:
    path = (f"/dev/live/matters/{case}/briefs/{brief}"
            f"/evidence/{document}/versions/{version}/original")
    conn = http.client.HTTPConnection("127.0.0.1", 8765, timeout=15)
    try:
        conn.request("GET", path, headers={"Authorization": "Bearer " + token,
                                         "Cache-Control": "no-store"})
        response = conn.getresponse()
        headers = {k.lower(): v for k, v in response.getheaders()}
        return response.status, response.read(5242881), headers
    finally:
        conn.close()


def roundtrip(
    *, actors: tuple[str, ...], sessions: tuple[object, ...], creds: tuple[PasswordCredentials, ...],
    admin_key: str, publishable: str, raw: bytes, media: str, filename: str,
) -> None:
    run = str(uuid4())
    storage = SignedOriginalsStorage(publishable)
    original: OriginalRef | None = None
    proc = None
    provisioned = False
    owner = sessions[0].access_token
    outsiders = (sessions[1].access_token, sessions[2].access_token)
    case: str | None = None
    try:
        provisioned = True
        setup = admin_rpc(admin_key, "setup", {
            "p_run": run, "p_owner": actors[0], "p_guest": actors[1], "p_foreign": actors[2],
        })
        org = str(UUID(setup["org_id"]))
        proc = _server_start()
        created = success(owner, "POST", "/dev/live/matters", {
            "org_id": org, "name": "Signed synthetic binary matter",
            "request_id": str(uuid4()),
        })
        case = str(UUID(created["case_id"]))
        digest = hashlib.sha256(raw).hexdigest()
        register = success(owner, "POST", f"/dev/live/matters/{case}/sources", {
            "request_id": str(uuid4()), "filename": filename,
            "sha256": digest, "byte_length": len(raw), "media_type": media,
        })
        document, version = (str(UUID(register[k])) for k in ("document_id", "version_id"))
        original = OriginalRef(UUID(org), UUID(case), UUID(document), UUID(version), digest, media)
        path = f"/dev/live/matters/{case}/sources/{document}/{version}"
        data = {"content_base64": base64.b64encode(raw).decode("ascii")}
        for user in outsiders:
            denied(user, "POST", path + "/upload", data)
            denied(user, "POST", path + "/ingest?request_id=" + str(uuid4()))
        denied(owner, "POST", path + "/upload",
               {"content_base64": base64.b64encode(raw + b"corrupted").decode("ascii")})
        uploaded = success(owner, "POST", path + "/upload", data)
        if uploaded.get("sha256") != digest or storage.get_verified(original, owner) != raw:
            raise LiveFixtureError("signed private binary readback mismatched SHA")
        for user in outsiders:
            try:
                storage.get_verified(original, user)
            except PrivateStorageDenied:
                pass
            else:
                raise LiveFixtureError("ungranted signed actor read existing binary original")
        ingest_url = path + "/ingest?request_id=" + str(uuid4())
        ingested = success(owner, "POST", ingest_url)
        replay = success(owner, "POST", ingest_url)
        manifest = ingested.get("parse_manifest")
        if (ingested.get("original_sha") != digest or not isinstance(manifest, dict) or
            manifest.get("schema") != "dev-document-parse-v1" or
            manifest.get("media_type") != media or
            manifest.get("original_sha256") != digest or
            manifest.get("representation_sha256") != ingested.get("representation_sha") or
            ingested.get("exhibit_confirmed") is not False or
            replay.get("replayed") is not True or
            replay.get("snapshot_sha") != ingested.get("snapshot_sha") or
            QUOTE not in ingested.get("text", "")):
            raise LiveFixtureError("binary parser/source manifest not preserved correctly")
        if media == "application/pdf":
            if not manifest.get("complete") or manifest.get("pages") != [
                {"pdf_page": 1, "status": "text_extracted", "text_blocks": 1}
            ]:
                raise LiveFixtureError("PDF physical page completeness not verified")
        else:
            if (manifest.get("complete") is not False or
                manifest.get("page_mapping") != "unverified" or
                not manifest.get("warnings") or manifest.get("pages") != []):
                raise LiveFixtureError("DOCX unverified layout falsely counted complete")
        for user in outsiders:
            denied(user, "GET", f"/dev/live/matters/{case}/state")
        print("LIVE_BINARY_SOURCE: actual signed Storage bytes, isolated parser, exact page status, replay")

        brief = success(owner, "POST", f"/dev/live/matters/{case}/briefs", {
            "source_version_id": version,
            "text": "Our submitted invoice claims 125 EUR.",
            "quote": QUOTE, "request_id": str(uuid4()),
        })
        brief_id = str(UUID(brief["brief_version_id"]))
        root = f"/dev/live/matters/{case}/briefs/{brief_id}"
        checked = success(owner, "POST", root + "/check")
        outcome = "candidate_quote_supported" if media == "application/pdf" else "candidate_quote_not_assessed_partial"
        if checked.get("outcome") != outcome:
            raise LiveFixtureError("M2 binary coverage/abstention did not follow parser state")
        recorded = success(owner, "POST", root + "/reviews", {
            "snapshot_hash": checked["snapshot_hash"], "observation_id": checked["observation_id"],
            "request_id": str(uuid4()), "expected_revision": 0,
            "disposition": "needs_information",
            "rationale": "Manual synthetic review, not legal verification or release",
        })
        if recorded.get("review_revision") != 1:
            raise LiveFixtureError("new binary review was not saved")
        query = success(owner, "POST", root + "/evidence/search", {"query": QUOTE})
        if (query.get("schema") != "caseproof-evidence-search-v1" or
            query.get("coverage") != ("complete" if media == "application/pdf" else "partial") or
            len(query.get("hits", [])) != 1 or
            query["hits"][0]["citation"] is not None or
            query["hits"][0]["source_sha256"] != digest or
            query["hits"][0]["page"] != (1 if media == "application/pdf" else None)):
            raise LiveFixtureError("Word bridge invented or lost source locator/citation")
        for user in outsiders:
            denied(user, "POST", root + "/evidence/search", {"query": QUOTE})
        status, bytes_read, headers = signed_original_http(owner, case, brief_id, document, version)
        if (status != 200 or bytes_read != raw or
            headers.get("x-caseproof-original-sha256") != digest or
            headers.get("x-caseproof-original-media-type") != media):
            raise LiveFixtureError("Word original download did not bind real SHA")
        print("LIVE_BINARY_WORD: signed search, exact quote offsets, no unconfirmed citations, original download")

        old_pid = proc.pid
        _server_stop(proc)
        proc = _server_start()
        if proc.pid == old_pid:
            raise LiveFixtureError("no actual server restart")
        fresh = SupabasePasswordSignin(PROJECT_REF, publishable).sign_in(creds[0])
        state = success(fresh.access_token, "GET", f"/dev/live/matters/{case}/state")
        if (len(state.get("sources", [])) != 1 or
            state["sources"][0].get("parse_manifest") != manifest or
            state["sources"][0].get("original_sha") != digest or
            state["sources"][0].get("text") != ingested["text"] or
            len(state.get("briefs", [])) != 1):
            raise LiveFixtureError("parsed source not reopened after new process")
        saved = success(fresh.access_token, "GET", root + "/reviews/" + checked["snapshot_hash"])
        if saved.get("review_revision") != 1:
            raise LiveFixtureError("post-restart binary review did not reopen")
        if admin_rpc(admin_key, "revoke", {
            "p_run": run, "p_owner": actors[0], "p_case": case,
        }) is not True:
            raise LiveFixtureError("scoped matter revocation unavailable")
        denied(fresh.access_token, "GET", f"/dev/live/matters/{case}/state")
        denied(fresh.access_token, "POST", root + "/evidence/search", {"query": QUOTE})
        denied(fresh.access_token, "POST", path + "/ingest?request_id=" + str(uuid4()))
        status, _, _ = signed_original_http(fresh.access_token, case, brief_id, document, version)
        if status == 200:
            raise LiveFixtureError("revoked actor still downloads Word original")
        print("LIVE_BINARY_RESTART: persisted manifest/review reopened, grants revoked on source and Word")
    finally:
        _server_stop(proc)
        if provisioned:
            try:
                if original is not None:
                    _remove_original(admin_key, original)
                admin_rpc(admin_key, "cleanup", {"p_run": run, "p_owner": actors[0]})
            except Exception:
                raise LiveFixtureError("scoped signed binary cleanup failed") from None


def verify(creds: tuple[PasswordCredentials, ...], *, key: str, publishable: str) -> None:
    sessions = tuple(SupabasePasswordSignin(PROJECT_REF, publishable).sign_in(c) for c in creds)
    verifier = SupabaseAuthUserVerifier(PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, publishable))
    actors = tuple(verifier.verify_bearer(s.access_token).subject_id for s in sessions)
    if len(actors) != 3 or len(set(actors)) != 3:
        raise LiveFixtureError("three signed development identities required")
    for mime, data, filename in (
        ("application/pdf", synthetic_pdf(), "synthetic-proof.pdf"),
        (DOCX, synthetic_docx(), "synthetic-proof.docx"),
    ):
        roundtrip(actors=actors, sessions=sessions, creds=creds, admin_key=key,
                  publishable=publishable, raw=data, media=mime, filename=filename)
        print("LIVE_BINARY_FORMAT_PASSED: " + ("PDF" if mime == "application/pdf" else "DOCX"))


def main() -> int:
    try:
        if (
            os.getenv("CASEPROOF_DEV_LIVE_BINARY_JOURNEY") != "YES" or
            os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof" or
            os.getenv("GITHUB_REF") != "refs/heads/main" or
            not (os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch" or
                 (os.getenv("GITHUB_EVENT_NAME") == "push" and
                  os.getenv("CASEPROOF_ALLOW_ONE_TIME_PUSH") == "YES"))
        ):
            raise LiveFixtureError("protected main-only binary acceptance required")
        key = os.getenv("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
        publishable = os.getenv("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
        if not publishable.startswith("sb_publishable_"):
            raise LiveFixtureError("protected publishable key missing")
        ephemeral_private_probe(
            admin=GoTrueDevAdmin(key),
            probe=lambda creds: verify(creds, key=key, publishable=publishable),
        )
        print("LIVE_SIGNED_PDF_DOCX_WORD_SEARCH_RESTART_CLEANUP_PASSED")
        return 0
    except Exception as exc:
        reason = str(exc)[:180] if isinstance(exc, LiveFixtureError) else ""
        print(f"LIVE_BINARY_JOURNEY_FAILED: {type(exc).__name__} {reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
