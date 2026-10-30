"""Ephemeral Phase 3 OCR acceptance; cleanup managed by M0.5 wrapper."""

from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import os
import time
import tracemalloc
from uuid import uuid4

from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.m05_registry import record
from scripts.verify_dev_ephemeral_auth import PROJECT_REF
from scripts.verify_dev_live_review_roundtrip import _request, _server_start, _server_stop
from scripts.verify_dev_live_txt_journey import success

ROLES = ("owner", "ungranted", "foreign")


def sources():
    """Use the same synthetic originals as the reusable fixture factory."""
    from docx import Document
    from docx.enum.text import WD_BREAK

    from tests.fixtures.factory import generate_bundle
    bundle = list(generate_bundle())
    doc = Document()
    for page in range(1, 151):
        p = doc.add_paragraph(f"Synthetic stress page {page}: ")
        if page <= 60:
            label = "Stuk" if page % 2 else "Pièce"
            number = page if page % 5 else page + 100
            p.add_run(f"{label} {number}, p. {page if page % 7 else 999}.")
        if page < 150:
            p.add_run().add_break(WD_BREAK.PAGE)
    out = io.BytesIO()
    doc.save(out)
    bundle[0] = type(bundle[0])(
        filename=bundle[0].filename, role=bundle[0].role,
        media_type=bundle[0].media_type, content=out.getvalue(),
    )
    return [(source.filename, source.media_type, source.content) for source in bundle]


def direct(token, key, path, method="GET", payload=None, profile=None):
    con = http.client.HTTPSConnection(PROJECT_REF + ".supabase.co", timeout=20)
    headers = {"apikey": key, "Authorization": "Bearer " + token}
    if profile:
        headers["Accept-Profile"] = profile
    if payload is not None:
        headers["Content-Type"] = "application/json"
    try:
        con.request(method, path, None if payload is None else json.dumps(payload).encode(), headers)
        res = con.getresponse()
        return res.status, res.read(250000)
    finally:
        con.close()


def crop(token, case, doc, version, box):
    path = f"/dev/live/matters/{case}/sources/{doc}/{version}/crop"
    con = http.client.HTTPConnection("127.0.0.1", 8765, timeout=30)
    try:
        con.request(
            "POST",
            path,
            json.dumps(box).encode(),
            {"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        res = con.getresponse()
        return res.status, res.read(3000000)
    finally:
        con.close()


def main():
    if (
        os.getenv("CASEPROOF_PHASE3_LIVE") != "YES"
        or os.getenv("GITHUB_REF") != "refs/heads/feat/production-hardening"
        or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
    ):
        raise RuntimeError("protected Phase 3 branch required")
    key = os.environ["CASEPROOF_DEV_PUBLISHABLE_KEY"]
    signin = SupabasePasswordSignin(PROJECT_REF, key)
    sessions = {}
    credentials = {}
    actors = {}
    for role in ROLES:
        email = os.environ[f"CASEPROOF_P3_{role.upper()}_EMAIL"]
        password = os.environ[f"CASEPROOF_P3_{role.upper()}_PASSWORD"]
        session = signin.sign_in(PasswordCredentials(email=email, password=password))
        sessions[role] = session.access_token
        credentials[role] = PasswordCredentials(email=email, password=password)
        actors[role] = str(session.user_id)
    if len(set(actors.values())) != 3:
        raise RuntimeError("P3_DISTINCT_AUTH_USERS_REQUIRED")
    print("P3_AUTH_SIGNED: three ephemeral users", flush=True)
    proc = None
    try:
        proc = _server_start()
        owner = sessions["owner"]
        case = success(
            owner,
            "POST",
            "/dev/live/matters",
            {"org_id": os.environ["CASEPROOF_P3_ORG_ID"], "name": "CaseProof CI " + os.environ["CASEPROOF_P3_RUN_ID"], "request_id": str(uuid4())},
        )["case_id"]
        record(os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"], os.environ["CASEPROOF_P3_RUN_ID"], "matter", case, "CREATED")
        print("P3_MATTER_CREATED: " + case, flush=True)
        bundle = sources()
        metadata = [
            {
                "role": "draft"
                if name.endswith(".docx")
                else "inventory"
                if name.endswith(".txt")
                else "exhibit",
                "filename": name,
                "media_type": media,
                "byte_length": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for name, media, raw in bundle
        ]
        status, body = direct(
            owner,
            key,
            "/rest/v1/rpc/caseproof_dev_register_bundle",
            "POST",
            {"p_case": case, "p_request": str(uuid4()), "p_sources": metadata},
        )
        if status != 200:
            try:
                detail = json.loads(body).get("message", "")[:180]
            except ValueError:
                detail = "non-json"
            raise RuntimeError(f"P3_BUNDLE_REGISTER_FAILED: {status} {detail}")
        registered = json.loads(body)["sources"]
        if len(registered) != 4:
            raise RuntimeError("P3_BUNDLE_INCOMPLETE")
        print("P3_BUNDLE_REGISTERED: four source identities", flush=True)
        if os.getenv("FORCE_FAILURE") == "YES":
            raise RuntimeError("P3_INJECTED_FAILURE_STEP_3")
        scan = None
        for (filename, _media, raw), item in zip(bundle, registered, strict=True):
            doc, version = item["document_id"], item["version_id"]
            digest = hashlib.sha256(raw).hexdigest()
            storage_path = "/".join((os.environ["CASEPROOF_P3_ORG_ID"], case, doc, version, digest))
            record(os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"], os.environ["CASEPROOF_P3_RUN_ID"], "storage_file", storage_path)
            uploaded = success(
                owner,
                "POST",
                f"/dev/live/matters/{case}/sources/{doc}/{version}/upload",
                {"content_base64": base64.b64encode(raw).decode()},
            )
            if uploaded.get("verified") is not True:
                raise RuntimeError("P3_UPLOAD_SHA_FAILED")
            if filename.endswith("scanned-receipt.pdf"):
                scan = (doc, version)
            print("P3_UPLOAD_VERIFIED: " + filename, flush=True)
        print("P3_FOUR_SOURCES_UPLOADED", flush=True)
        doc, version = scan
        success(
            owner, "POST", f"/dev/live/matters/{case}/sources/{doc}/{version}/ingest?request_id={uuid4()}"
        )
        print("P3_INGEST_RPC_SUCCEEDED", flush=True)
        status, raw = direct(
            owner,
            key,
            "/rest/v1/rpc/caseproof_signed_ocr_geometry",
            method="POST",
            payload={"p_version": version, "p_page": 1},
        )
        if status != 200:
            raise RuntimeError(f"P3_GEOMETRY_RPC_FAILED: {status}")
        rows = json.loads(raw)
        if not rows:
            raise RuntimeError("P3_SIDECAR_MISSING: no persisted geometry")
        row = rows[0]
        payload = json.loads(row["payload"])
        if hashlib.sha256(row["payload"].encode()).hexdigest() != row["geometry_sha256_hex"]:
            raise RuntimeError("P3_SIDECAR_HASH_MISMATCH")
        print("P3_SIDECAR_PERSISTED: verified signed DB read and canonical SHA", flush=True)
        draft_version = next(item["version_id"] for item in registered if item["role"] == "draft")
        base = f"/v2/matters/{case}/briefs/{draft_version}/verification"
        tracemalloc.start()
        start = time.perf_counter()
        status, discovered = _request(owner, "GET", base + "/discovery")
        elapsed_ms = (time.perf_counter() - start) * 1000
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        api_peak_rss_kib = None
        try:
            status_text = __import__("pathlib").Path(
                f"/proc/{proc.pid}/status"
            ).read_text(encoding="utf-8")
            for line in status_text.splitlines():
                if line.startswith("VmHWM:"):
                    api_peak_rss_kib = int(line.split()[1])
                    break
        except (OSError, ValueError):
            pass
        if status != 200:
            raise RuntimeError(f"P4_DISCOVERY_FAILED:{status}")
        findings = discovered.get("findings", [])
        # The independent synthetic ground truth has exactly 60 citations.
        # Detection precision/recall measure extraction, not legal identity,
        # OCR fidelity, page mapping or semantic support.
        actual = [(f.get("number"), f.get("literal", "").casefold().startswith("stuk")) for f in findings]
        expected = [(str(page if page % 5 else page + 100), bool(page % 2)) for page in range(1, 61)]
        from collections import Counter
        truth, observed = Counter(expected), Counter(actual)
        tp = sum((truth & observed).values())
        fp = sum((observed - truth).values())
        fn = sum((truth - observed).values())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        print("M5_BENCHMARK_JSON:" + json.dumps({
            "intended_pages": 150, "reference_truth": 60,
            "discovery_ms": round(elapsed_ms, 3),
            "client_python_peak_bytes": peak_bytes,
            "api_process_peak_rss_kib": api_peak_rss_kib,
            "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": precision, "recall": recall,
            "false_positive_rate": None,
            "false_negative_rate": fn / (tp + fn) if tp + fn else None,
            "note": "Client Python peak only; not server RSS. FPR needs TN ground truth. Accuracy is reference detection only."
        }, sort_keys=True), flush=True)
        if tp != 60 or fp or fn:
            raise RuntimeError("M5_REFERENCE_EXTRACTION_BENCHMARK_FAILED")
        scanned = next((f for f in findings if f["number"] == "2"), None)
        if not scanned or not scanned.get("ocr_crop"):
            raise RuntimeError("P4_REAL_OCR_CROP_NOT_RETURNED:" + str({
                "identity": scanned.get("identity") if scanned else None,
                "page_mapping": scanned.get("page_mapping") if scanned else None,
                "manifest_ambiguous": scanned.get("ambiguous_manifest") if scanned else None,
                "ocr_words": len(payload.get("words", [])),
            }))
        if scanned["ocr_crop"].get("geometry_sha256") != row["geometry_sha256_hex"]:
            raise RuntimeError("P4_CROP_NOT_BOUND_TO_PERSISTED_SIDECAR")
        review_id = str(uuid4())
        status, reviewed = _request(owner, "POST", base + "/reviews", {
            "snapshot_hash": discovered["snapshot_hash"],
            "reference_id": scanned["reference_id"],
            "request_id": review_id, "decision": "CONFIRMED_SUPPORTED",
            "rationale": "Synthetic source reviewed by signed development actor",
        })
        if status != 200 or reviewed.get("request_id") != review_id:
            raise RuntimeError(f"P4_SIGNED_REVIEW_NOT_PERSISTED:{status}")
        print("P4_DISCOVERY_CROP_AND_SIGNED_REVIEW_PASSED", flush=True)
        # Sequence security: cross-matter and export access checks use
        # independently signed users, not a mocked authorization layer.
        for role in ("ungranted", "foreign"):
            denied_status, _ = _request(sessions[role], "GET", base + "/discovery")
            if denied_status not in (403, 404):
                raise RuntimeError(f"M5_CROSS_MATTER_DENIAL_FAILED:{role}:{denied_status}")
            denied_status, _ = _request(sessions[role], "GET", base + "/export")
            if denied_status not in (403, 404):
                raise RuntimeError(f"M5_EXPORT_PERMISSION_FAILED:{role}:{denied_status}")
        print("M5_CROSS_MATTER_AND_EXPORT_PERMISSION_PASSED", flush=True)
        words = payload.get("words", [])
        if not words:
            raise RuntimeError("P3_NO_OCR_WORDS")
        w = words[0]
        box = {"page_number": 1, **{k: w[k] for k in ("left", "top", "width", "height")}}
        status, png = crop(owner, case, doc, version, box)
        if status != 200 or not png.startswith(bytes.fromhex("89504e470d0a1a0a")):
            raise RuntimeError(f"P3_AUTH_CROP_FAILED: {status}")
        print("P3_AUTH_CROP_PNG: 200", flush=True)
        _server_stop(proc)
        proc = None
        proc = _server_start()
        # Fresh login, no cached session or geometry.
        fresh = signin.sign_in(credentials["owner"]).access_token
        status, png = crop(fresh, case, doc, version, box)
        if status != 200 or not png.startswith(bytes.fromhex("89504e470d0a1a0a")):
            raise RuntimeError(f"P3_COLD_RESTART_CROP_FAILED: {status}")
        print("P3_RESTART_RELOGIN_CROP_PNG: 200", flush=True)
        status, exported = _request(fresh, "GET", base + "/export")
        if status != 200 or not any(
            d.get("request_id") == review_id and d.get("decision") == "CONFIRMED_SUPPORTED"
            for d in exported.get("human_decisions", [])
        ):
            raise RuntimeError(f"P4_COLD_RESTART_EXPORT_MISSING_REVIEW:{status}")
        print("P4_COLD_RESTART_SIGNED_EXPORT_PASSED", flush=True)
        # Denial checks before revocation.
        for role in ("ungranted", "foreign"):
            status, body = crop(sessions[role], case, doc, version, box)
            if status not in (403, 404) or body.startswith(bytes.fromhex("89504e47")):
                raise RuntimeError(f"P3_{role.upper()}_ACCESS_FAILURE: {status}")
            print(f"P3_{role.upper()}_CROP_DENIED: {status}", flush=True)
        status, body = direct(fresh, key, "/rest/v1/ocr_geometry_sidecars?select=*", profile="caseproof")
        if status == 406:
            try:
                rejection = json.loads(body)
            except ValueError:
                rejection = {}
            if rejection.get("code") != "PGRST106":
                raise RuntimeError(f"P3_POSTGREST_UNEXPECTED_406: {rejection.get('code')}")
        elif status not in (401, 403, 404):
            raise RuntimeError(f"P3_PRIVATE_POSTGREST_EXPOSED: {status}")
        print("P3_PRIVATE_POSTGREST_DENIED", flush=True)
        # Revocation is tested before scoped teardown by the caller.
        from scripts.verify_dev_live_txt_journey import admin_rpc

        # revoke RPC requires the fixture run and owner identity.
        ok = admin_rpc(
            os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"],
            "revoke",
            {"p_run": os.environ["CASEPROOF_P3_RUN_ID"], "p_owner": actors["owner"], "p_case": case},
        )
        if ok is not True:
            raise RuntimeError("P3_REVOKE_RPC_FAILED")
        status, body = crop(fresh, case, doc, version, box)
        if status not in (403, 404) or body.startswith(bytes.fromhex("89504e47")):
            raise RuntimeError(f"P3_REVOKED_CROP_NOT_DENIED: {status}")
        print("P3_REVOKED_CROP_DENIED", flush=True)
        revoked_status, _ = _request(fresh, "GET", base + "/export")
        if revoked_status not in (403, 404):
            raise RuntimeError(f"M5_REVOKED_EXPORT_NOT_DENIED:{revoked_status}")
        print("M5_REVOCATION_EXPORT_PASSED", flush=True)
        print("P3_ALL_NINE_STEPS_PASSED; teardown required", flush=True)
    finally:
        if proc is not None:
            _server_stop(proc)


if __name__ == "__main__":
    main()
