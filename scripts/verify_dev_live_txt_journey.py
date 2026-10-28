"""Protected live development acceptance: NO seeded matters, sources or briefs.

Three genuine Supabase GoTrue users -> signed create -> signed Storage verified
TXT ingest -> authored brief -> persisted M2 check and review -> real uvicorn
cold process restart -> fresh login, exact state reopens -> grant revoke -> deny
-> scoped cleanup. Protected main only; no credentials or bytes in CI logs.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID, uuid4

from apps.api.signed_supabase_matter_catalog import SignedMatterCatalog
from apps.api.signed_supabase_originals import OriginalRef, PrivateStorageDenied, SignedOriginalsStorage
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import ISSUER, PROJECT_REF, GoTrueDevAdmin
from scripts.verify_dev_live_review_roundtrip import _request, _server_start, _server_stop
from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe
from scripts.verify_m1_live_positive_original import LiveFixtureError, _remove_original

HOST = f"{PROJECT_REF}.supabase.co"
FIXTURE = b"CaseProof synthetic TXT evidence: the invoice total is 125 EUR, dated 23 October 2026.\n"
DIGEST = hashlib.sha256(FIXTURE).hexdigest()


def admin_rpc(key: str, name: str, args: dict[str, Any]) -> Any:
    if name not in {"setup", "revoke", "cleanup"} or not (
        key.startswith("sb_secret_") or key.startswith("eyJ")
    ):
        raise LiveFixtureError("unsupported protected journey administrator")
    con = http.client.HTTPSConnection(HOST, timeout=15)
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    try:
        con.request("POST", "/rest/v1/rpc/caseproof_dev_journey_" + name,
                    json.dumps(args).encode(), headers)
        response = con.getresponse()
        status = response.status
        body = response.read(16385)
    finally:
        con.close()
    if status != 200 or len(body) > 16384:
        raise LiveFixtureError("protected journey administration unavailable")
    try:
        return json.loads(body)
    except (UnicodeError, ValueError):
        raise LiveFixtureError("invalid administration response") from None


def success(token: str, method: str, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    status, result = _request(token, method, path, data)
    if status != 200:
        raise LiveFixtureError("signed journey HTTP stage failed")
    return result


def denied(token: str, method: str, path: str, data: dict[str, Any] | None = None) -> None:
    status, _ = _request(token, method, path, data)
    if status == 200:
        raise LiveFixtureError("ungranted or revoked operation succeeded")


def verify(
    credentials: tuple[PasswordCredentials, ...], *,
    admin_key: str, publishable: str,
) -> None:
    signin = SupabasePasswordSignin(PROJECT_REF, publishable)
    verifier = SupabaseAuthUserVerifier(
        PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, publishable),
    )
    sessions = tuple(signin.sign_in(c) for c in credentials)
    identities = tuple(verifier.verify_bearer(s.access_token) for s in sessions)
    actors = tuple(i.subject_id for i in identities)
    if len(set(actors)) != 3 or any(
        i.issuer != ISSUER or i.audience != "authenticated"
        or i.subject_id != s.user_id for i, s in zip(identities, sessions, strict=True)
    ):
        raise LiveFixtureError("three real signed GoTrue identities required")
    print("LIVE_TXT_1: three genuine signed users")
    run_id = str(uuid4())
    provision_attempted = False
    proc = None
    ref: OriginalRef | None = None
    case: str | None = None
    try:
        provision_attempted = True
        setup = admin_rpc(admin_key, "setup", {
            "p_run": run_id, "p_owner": actors[0],
            "p_guest": actors[1], "p_foreign": actors[2],
        })
        org = str(UUID(setup["org_id"]))
        proc = _server_start()
        owner = sessions[0].access_token
        outsiders = (sessions[1].access_token, sessions[2].access_token)
        req = str(uuid4())
        create = {"org_id": org, "name": "Synthetic authored matter", "request_id": req}
        created = success(owner, "POST", "/dev/live/matters", create)
        case = str(UUID(created["case_id"]))
        replay = success(owner, "POST", "/dev/live/matters", create)
        if replay.get("case_id") != case or replay.get("replayed") is not True:
            raise LiveFixtureError("matter idempotency replay created duplicate")
        denied(owner, "POST", "/dev/live/matters",
               {**create, "name": "colliding request"})
        for outsider in outsiders:
            denied(outsider, "POST", "/dev/live/matters", create)
        catalog = SignedMatterCatalog(publishable)
        if not any(m["case_id"] == case for m in catalog.list_matters(owner)):
            raise LiveFixtureError("newly created matter absent from signed list")
        if any(any(m["case_id"] == case for m in catalog.list_matters(x)) for x in outsiders):
            raise LiveFixtureError("ungranted users enumerated private matter")
        print("LIVE_TXT_2: signed matter created; grant, audit, idempotency and denial")

        source_path = f"/dev/live/matters/{case}/sources"
        denied(owner, "POST", source_path, {
            "request_id": str(uuid4()), "filename": "wrong.pdf",
            "sha256": DIGEST, "byte_length": len(FIXTURE), "media_type": "application/pdf",
        })
        denied(owner, "POST", source_path, {
            "request_id": str(uuid4()), "filename": "empty.txt",
            "sha256": DIGEST, "byte_length": 0, "media_type": "text/plain",
        })
        denied(owner, "POST", source_path, {
            "request_id": str(uuid4()), "filename": "oversized.txt",
            "sha256": DIGEST, "byte_length": 1048577, "media_type": "text/plain",
        })
        # A racing second source registration must fail even with another
        # idempotency key. Only one matter original is permitted in this slice.
        def race_register(_index: int) -> tuple[int, dict[str, Any]]:
            return _request(owner, "POST", source_path, {
                "request_id": str(uuid4()), "filename": "invoice.txt",
                "sha256": DIGEST, "byte_length": len(FIXTURE),
                "media_type": "text/plain",
            })
        with ThreadPoolExecutor(max_workers=2) as executor:
            contenders = list(executor.map(race_register, range(2)))
        winners = [payload for status, payload in contenders if status == 200]
        if len(winners) != 1 or len(contenders) != 2:
            raise LiveFixtureError("concurrent registration created duplicate originals")
        reg = winners[0]
        doc, version = (str(UUID(reg[k])) for k in ("document_id", "version_id"))
        ref = OriginalRef(UUID(org), UUID(case), UUID(doc), UUID(version), DIGEST, "text/plain")
        endpoint = source_path + f"/{doc}/{version}"
        import base64
        content = {"content_base64": base64.b64encode(FIXTURE).decode("ascii")}
        for outsider in outsiders:
            denied(outsider, "POST", endpoint + "/upload", content)
            denied(outsider, "POST", endpoint + "/ingest?request_id=" + str(uuid4()))
        denied(owner, "POST", endpoint + "/upload",
               {"content_base64": base64.b64encode(FIXTURE + b"tampered").decode("ascii")})
        uploaded = success(owner, "POST", endpoint + "/upload", content)
        if uploaded.get("sha256") != DIGEST or uploaded.get("verified") is not True:
            raise LiveFixtureError("signed Storage SHA256 readback missing")
        stored = SignedOriginalsStorage(publishable)
        if stored.get_verified(ref, owner) != FIXTURE:
            raise LiveFixtureError("real private original bytes mismatch")
        for outsider in outsiders:
            try:
                stored.get_verified(ref, outsider)
            except PrivateStorageDenied:
                pass
            else:
                raise LiveFixtureError("ungranted user read existing Storage original")
        # A direct bearer-authenticated database request must NEVER be able
        # to certify source bytes by inventing content_base64. Storage's path
        # metadata alone is not cryptographic evidence of the original bytes.
        con = http.client.HTTPSConnection(HOST, timeout=12)
        try:
            con.request("POST", "/rest/v1/rpc/caseproof_dev_journey",
                body=json.dumps({
                    "p_action": "ingest", "p_case": case, "p_request": str(uuid4()),
                    "p_data": {"document_id": doc, "version_id": version,
                               "content_base64": content["content_base64"]},
                }).encode(), headers={
                    "apikey": publishable, "Authorization": "Bearer " + owner,
                    "Content-Type": "application/json",
                })
            direct_status = con.getresponse().status
        finally:
            con.close()
        if direct_status == 200:
            raise LiveFixtureError("CRITICAL: authenticated self-certified ingest succeeded")
        print("LIVE_TXT_3A: direct signed ingestion RPC denied; only trusted server can promote")
        print("LIVE_TXT_3: signed Storage upload/readback; content and access negatives")

        bad_utf8 = {"content_base64": base64.b64encode(b"\xff\xfe").decode()}
        denied(owner, "POST", endpoint + "/upload", bad_utf8)
        ingest_path = endpoint + "/ingest?request_id=" + str(uuid4())
        ingested = success(owner, "POST", ingest_path)
        if (ingested.get("original_sha") != DIGEST or
            ingested.get("text") != FIXTURE.decode("utf-8") or
            ingested.get("exhibit_confirmed") is not False):
            raise LiveFixtureError("actual strict TXT representation mismatch")
        repeated = success(owner, "POST", ingest_path)
        if repeated.get("replayed") is not True or repeated.get("snapshot_sha") != ingested["snapshot_sha"]:
            raise LiveFixtureError("duplicate ingestion failed replay")
        print("LIVE_TXT_4: verified immutable ingestion snapshot, strict TXT and retry")

        claim = "125 EUR"
        statement = "The provided invoice states 125 EUR, which requires independent review."
        authored = success(owner, "POST", f"/dev/live/matters/{case}/briefs", {
            "source_version_id": version, "text": statement,
            "quote": claim, "request_id": str(uuid4()),
        })
        brief = str(UUID(authored["brief_version_id"]))
        base = f"/dev/live/matters/{case}/briefs/{brief}"
        checked = success(owner, "POST", base + "/check")
        if checked.get("outcome") != "candidate_quote_supported" or checked.get("observation_id") != "fact:amount-1":
            raise LiveFixtureError("live checker did not use ingested authored quote")
        snapshot = checked["snapshot_hash"]
        for outsider in outsiders:
            denied(outsider, "POST", base + "/check")
        review = {
            "snapshot_hash": snapshot, "observation_id": checked["observation_id"],
            "request_id": str(uuid4()), "expected_revision": 0,
            "disposition": "needs_information",
            "rationale": "Manual independent review; no legal approval",
        }
        committed = success(owner, "POST", base + "/reviews", review)
        replay = success(owner, "POST", base + "/reviews", review)
        if committed.get("review_revision") != 1 or replay.get("replayed") is not True:
            raise LiveFixtureError("M2 review persistence, audit or replay failed")
        denied(owner, "POST", base + "/reviews", {**review, "request_id": str(uuid4())})
        print("LIVE_TXT_5: authored brief, data-driven check and atomic signed M2 review")

        # A reviewed change is a NEW immutable authored brief revision. It
        # never overwrites the signed private source, original brief or review.
        correction = {
            "snapshot_hash": snapshot, "expected_review_revision": 1,
            "before": claim, "after": "126 EUR", "request_id": str(uuid4()),
        }
        for outsider in outsiders:
            denied(outsider, "POST", base + "/corrections/preview", correction)
            denied(outsider, "POST", base + "/corrections/commit", correction)
        denied(owner, "POST", base + "/corrections/commit",
               {**correction, "snapshot_hash": "f" * 64})
        preview = success(owner, "POST", base + "/corrections/preview", correction)
        corrected_text = statement.replace("125 EUR", "126 EUR")
        if (preview.get("preview_text") != corrected_text
            or preview.get("committed") is not False):
            raise LiveFixtureError("review-bound correction preview mismatch")
        changed = success(owner, "POST", base + "/corrections/commit", correction)
        changed_replay = success(owner, "POST", base + "/corrections/commit", correction)
        new_version = str(UUID(changed["brief_version_id"]))
        if (changed.get("committed") is not True
            or changed.get("revision") != 2
            or changed.get("parent_version_id") != brief
            or changed_replay.get("replayed") is not True
            or changed_replay.get("brief_version_id") != new_version):
            raise LiveFixtureError("durable correction/idempotent receipt mismatch")
        denied(owner, "POST", base + "/corrections/commit",
               {**correction, "after": "127 EUR"})
        denied(owner, "POST", base + "/corrections/commit",
               {**correction, "request_id": str(uuid4())})
        denied(owner, "POST", base + "/check")
        new_base = f"/dev/live/matters/{case}/briefs/{new_version}"
        rechecked = success(owner, "POST", new_base + "/check")
        if (rechecked.get("outcome") != "candidate_quote_mismatch"
            or rechecked.get("snapshot_hash") == snapshot
            or rechecked.get("review_revision") != 0
            or rechecked.get("release_authorized") is not False):
            raise LiveFixtureError("new revision did not produce separate unapproved finding")
        new_review = {
            "snapshot_hash": rechecked["snapshot_hash"],
            "observation_id": rechecked["observation_id"],
            "request_id": str(uuid4()), "expected_revision": 0,
            "disposition": "needs_information",
            "rationale": "New draft mismatch must be manually resolved; no approval",
        }
        new_saved = success(owner, "POST", new_base + "/reviews", new_review)
        if new_saved.get("review_revision") != 1:
            raise LiveFixtureError("corrected draft has no independent review")
        print("LIVE_TXT_5A: reviewed correction preview, atomic CAS/replay, fresh mismatch and recheck")

        old_pid = proc.pid
        _server_stop(proc)
        proc = _server_start()
        if proc.pid == old_pid:
            raise LiveFixtureError("no actual server restart")
        fresh = signin.sign_in(credentials[0])
        if verifier.verify_bearer(fresh.access_token).subject_id != actors[0]:
            raise LiveFixtureError("fresh login changed actor identity")
        reopened = success(fresh.access_token, "GET", f"/dev/live/matters/{case}/state")
        if (len(reopened.get("sources", [])) != 1 or
            reopened["sources"][0]["text"] != FIXTURE.decode("utf-8") or
            reopened["sources"][0]["snapshot_sha"] != ingested["snapshot_sha"] or
            len(reopened.get("briefs", [])) != 2 or
            reopened["briefs"][0]["brief_version_id"] != new_version or
            reopened["briefs"][0]["parent_version_id"] != brief or
            reopened["briefs"][0]["text"] != corrected_text or
            reopened["briefs"][0]["quote"] != "126 EUR" or
            reopened["briefs"][1]["text"] != statement or
            reopened["briefs"][1]["quote"] != claim):
            raise LiveFixtureError("immutable draft revisions not reopened after cold restart")
        saved = success(fresh.access_token, "GET", new_base + "/reviews/" + rechecked["snapshot_hash"])
        if saved.get("review_revision") != 1 or len(saved.get("decisions", [])) != 1:
            raise LiveFixtureError("new correction check/review not reopened from live Supabase")
        for outsider in outsiders:
            denied(outsider, "GET", f"/dev/live/matters/{case}/state")
            denied(outsider, "GET", base + "/reviews/" + snapshot)
        print("LIVE_TXT_6: real server restart, fresh sign-in, full original/brief/review reopening")

        if admin_rpc(admin_key, "revoke", {"p_run": run_id, "p_owner": actors[0],
                                           "p_case": case}) is not True:
            raise LiveFixtureError("scoped revoke failed")
        denied(fresh.access_token, "GET", f"/dev/live/matters/{case}/state")
        denied(fresh.access_token, "POST", new_base + "/check")
        denied(fresh.access_token, "POST", new_base + "/corrections/commit", correction)
        denied(fresh.access_token, "POST", endpoint + "/ingest?request_id=" + str(uuid4()))
        try:
            stored.get_verified(ref, fresh.access_token)
        except PrivateStorageDenied:
            pass
        else:
            raise LiveFixtureError("revoked actor still reads guessed Storage path")
        print("LIVE_TXT_7: revoked read/write/Storage immediately denied")
    finally:
        _server_stop(proc)
        if provision_attempted:
            try:
                if ref is not None:
                    _remove_original(admin_key, ref)
                cleaned = admin_rpc(admin_key, "cleanup", {
                    "p_run": run_id, "p_owner": actors[0],
                })
                if cleaned not in (True, False):
                    raise LiveFixtureError("cleanup receipt malformed")
            except Exception:
                raise LiveFixtureError("scoped dev TXT cleanup failed") from None
    print("LIVE_TXT_8: scoped matter/source/journal/Storage cleanup completed")


def main() -> int:
    try:
        if (os.getenv("CASEPROOF_DEV_LIVE_TXT_JOURNEY") != "YES"
            or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
            or os.getenv("GITHUB_REF") != "refs/heads/main"
            or not (
                os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
                or (os.getenv("GITHUB_EVENT_NAME") == "push"
                    and os.getenv("CASEPROOF_ALLOW_ONE_TIME_PUSH") == "YES")
            )):
            raise LiveFixtureError("protected main-only journey acceptance required")
        publishable = os.getenv("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
        admin_key = os.getenv("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
        if not publishable.startswith("sb_publishable_"):
            raise LiveFixtureError("protected development publishable key missing")
        ephemeral_private_probe(
            admin=GoTrueDevAdmin(admin_key),
            probe=lambda credentials: verify(
                credentials, admin_key=admin_key, publishable=publishable,
            ),
        )
        print("LIVE_CREATED_MATTER_INGESTED_TXT_AUTHORED_REVIEW_COLD_RESTART_PASSED")
        return 0
    except Exception as exc:
        print(f"LIVE_TXT_JOURNEY_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
