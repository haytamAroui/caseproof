"""Live signed-dev acceptance: preseeded source -> check -> review -> cold reopen.

Three real Supabase GoTrue identities and the protected Actions environment are
mandatory. Reviewer and outsider operations go through actual signed HTTP, then
a fresh uvicorn PROCESS and a fresh GoTrue sign-in reopen the live Supabase row.
Never logs credentials, object bytes, bearer tokens or private response bodies.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from typing import Any
from uuid import UUID, uuid4

from apps.api.signed_supabase_originals import OriginalRef, PrivateStorageDenied, SignedOriginalsStorage
from apps.api.signed_supabase_source_library import SignedSourceLibrary
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import ISSUER, PROJECT_REF, GoTrueDevAdmin
from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe
from scripts.verify_m1_live_positive_original import (
    DIGEST,
    FIXTURE,
    LiveFixtureError,
    _remove_original,
    _rpc,
)

PORT = 8765
HOST = f"{PROJECT_REF}.supabase.co"


def _admin(key: str, action: str, payload: dict[str, Any]) -> Any:
    if action not in ("seed", "cleanup"):
        raise LiveFixtureError("unapproved review fixture administration")
    if not (key.startswith("sb_secret_") or key.startswith("eyJ")):
        raise LiveFixtureError("missing protected admin credential")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    con = http.client.HTTPSConnection(HOST, timeout=15)
    try:
        con.request(
            "POST", "/rest/v1/rpc/caseproof_dev_review_" + action,
            json.dumps(payload).encode(), headers,
        )
        res = con.getresponse()
        status = res.status
        data = res.read(16385)
    finally:
        con.close()
    if status != 200 or len(data) > 16384:
        raise LiveFixtureError("scoped review fixture operation failed")
    try:
        return json.loads(data)
    except (UnicodeError, ValueError):
        raise LiveFixtureError("invalid review fixture result") from None


def _server_start() -> subprocess.Popen[bytes]:
    proc: subprocess.Popen[bytes] = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "apps.api.dev_live_entry:app",
            "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "error",
            "--no-access-log",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    for _ in range(50):
        if proc.poll() is not None:
            raise LiveFixtureError("development server failed startup")
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.2):
                return proc
        except OSError:
            time.sleep(0.1)
    proc.terminate()
    proc.wait(timeout=10)
    raise LiveFixtureError("development server startup timeout")


def _server_stop(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _request(
    token: str, method: str, path: str, payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    con = http.client.HTTPConnection("127.0.0.1", PORT, timeout=15)
    try:
        con.request(
            method, path,
            None if payload is None else json.dumps(payload).encode(),
            {"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        response = con.getresponse()
        status = response.status
        raw = response.read(32769)
    finally:
        con.close()
    if len(raw) > 32768:
        raise LiveFixtureError("oversized live review response")
    try:
        obj = json.loads(raw)
    except (UnicodeError, ValueError):
        raise LiveFixtureError("invalid live review response") from None
    if not isinstance(obj, dict):
        raise LiveFixtureError("invalid live review envelope")
    return status, obj


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
    if len(actors) != 3 or len(set(actors)) != 3 or any(
        v.issuer != ISSUER or v.audience != "authenticated"
        or v.subject_id != s.user_id
        for v, s in zip(identities, sessions, strict=True)
    ):
        raise LiveFixtureError("real signed Auth identities invalid")
    print("LIVE_REVIEW_1: three real signed dev users verified")

    run_id = str(uuid4())
    fixture_attempted = False
    ref: OriginalRef | None = None
    proc: subprocess.Popen[bytes] | None = None
    library = SignedSourceLibrary(SignedOriginalsStorage(publishable))
    try:
        fixture_attempted = True
        data = _rpc(admin_key, "begin", {
            "p_run_id": run_id, "p_owner": actors[0], "p_guest": actors[1],
            "p_foreign": actors[2], "p_sha": DIGEST, "p_size": len(FIXTURE),
        })
        org, case, doc, version = (
            str(UUID(data[k]))
            for k in ("org_id", "case_id", "document_id", "version_id")
        )
        ref = OriginalRef(UUID(org), UUID(case), UUID(doc), UUID(version), DIGEST, "text/plain")
        params = {"case_id": case, "document_id": doc, "version_id": version}
        library.put_once(bearer=sessions[0].access_token, data=FIXTURE, **params)
        import hashlib
        if hashlib.sha256(library.read(bearer=sessions[0].access_token, **params)).hexdigest() != DIGEST:
            raise LiveFixtureError("signed original SHA256 readback mismatch")
        seeded = _admin(admin_key, "seed", {"p_run_id": run_id, "p_owner": actors[0]})
        if seeded.get("case_id") != case or seeded.get("original_sha256") != DIGEST:
            raise LiveFixtureError("live seeded graph and source mismatch")
        b = str(UUID(seeded["brief_version_id"]))
        base = f"/dev/live/matters/{case}/briefs/{b}"
        proc = _server_start()
        print("LIVE_REVIEW_2: existing synthetic matter, signed Storage SHA256 and seeded brief")

        checked, result = _request(sessions[0].access_token, "POST", base + "/check")
        if checked != 200 or result.get("outcome") != "candidate_quote_supported" or result.get("review_revision") != 0:
            raise LiveFixtureError("real live candidate check failed")
        snapshot = result["snapshot_hash"]
        if not isinstance(snapshot, str) or len(snapshot) != 64:
            raise LiveFixtureError("missing immutable check snapshot")
        for denied in sessions[1:]:
            code, _ = _request(denied.access_token, "POST", base + "/check")
            if code == 200:
                raise LiveFixtureError("ungranted user performed live check")
        print("LIVE_REVIEW_3: signed candidate check persisted; two ungranted actors denied")

        command = {
            "snapshot_hash": snapshot,
            "observation_id": result["observation_id"],
            "request_id": str(uuid4()),
            "expected_revision": 0,
            "disposition": "needs_information",
            "rationale": "Synthetic reviewer requests corroboration; not a legal approval",
        }
        code, saved = _request(sessions[0].access_token, "POST", base + "/reviews", command)
        if code != 200 or saved.get("review_revision") != 1 or saved.get("replayed"):
            raise LiveFixtureError("atomic signed review was not committed")
        code, replay = _request(sessions[0].access_token, "POST", base + "/reviews", command)
        if code != 200 or replay.get("review_revision") != 1 or replay.get("replayed") is not True:
            raise LiveFixtureError("idempotent review replay failed")
        conflicting = {**command, "request_id": str(uuid4())}
        code, _ = _request(sessions[0].access_token, "POST", base + "/reviews", conflicting)
        if code == 200:
            raise LiveFixtureError("stale review CAS unexpectedly succeeded")
        print("LIVE_REVIEW_4: real M2 review, audit, receipt, replay and CAS verified")

        old_pid = proc.pid
        _server_stop(proc)
        proc = None
        proc = _server_start()
        if proc.pid == old_pid:
            raise LiveFixtureError("server process did not restart")
        fresh = signin.sign_in(credentials[0])
        fresh_actor = verifier.verify_bearer(fresh.access_token)
        if fresh_actor.subject_id != actors[0]:
            raise LiveFixtureError("fresh session lost signed identity")
        code, reopened = _request(fresh.access_token, "GET", base + "/reviews/" + snapshot)
        decisions = reopened.get("decisions")
        if code != 200 or reopened.get("review_revision") != 1 or not isinstance(decisions, list) or len(decisions) != 1:
            raise LiveFixtureError("cold restart did not reopen Supabase review")
        if decisions[0]["decision"]["rationale"] != command["rationale"]:
            raise LiveFixtureError("reopened review differs from committed decision")
        print("LIVE_REVIEW_5: fresh login, new server process, same persisted decision reopened")

        for denied in sessions[1:]:
            code, _ = _request(denied.access_token, "GET", base + "/reviews/" + snapshot)
            if code == 200:
                raise LiveFixtureError("ungranted actor read existing review")
            code, _ = _request(denied.access_token, "POST", base + "/reviews", {**command, "request_id": str(uuid4()), "expected_revision": 1})
            if code == 200:
                raise LiveFixtureError("ungranted actor wrote existing review")
        if _rpc(admin_key, "revoke", {"p_run_id": run_id, "p_owner": actors[0]}) is not True:
            raise LiveFixtureError("grant revoke failed")
        code, _ = _request(fresh.access_token, "GET", base + "/reviews/" + snapshot)
        if code == 200:
            raise LiveFixtureError("revoked owner reopened review")
        code, _ = _request(fresh.access_token, "POST", base + "/check")
        if code == 200:
            raise LiveFixtureError("revoked owner reran check")
        try:
            library.read(bearer=fresh.access_token, **params)
        except PrivateStorageDenied:
            pass
        else:
            raise LiveFixtureError("revoked user can read Storage original")
        print("LIVE_REVIEW_6: ungranted/revoked read and write fail closed")
    finally:
        _server_stop(proc)
        if fixture_attempted:
            cleanup_ok = True
            try:
                if _admin(admin_key, "cleanup", {"p_run_id": run_id, "p_owner": actors[0]}) not in (True, False):
                    cleanup_ok = False
                if ref is not None:
                    _remove_original(admin_key, ref)
                if _rpc(admin_key, "cleanup", {"p_run_id": run_id, "p_owner": actors[0]}) not in (True, False):
                    cleanup_ok = False
            except Exception:
                cleanup_ok = False
            if not cleanup_ok:
                raise LiveFixtureError("exact dev cleanup FAILED; inspect fixture before rerun")
        print("LIVE_REVIEW_7: synthetic M2 journals, Storage and matter cleaned")


def main() -> int:
    try:
        if (os.getenv("CASEPROOF_DEV_LIVE_ROUNDTRIP") != "YES"
            or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
            or not (
                (
                    os.getenv("GITHUB_REF") == "refs/heads/main"
                    and (
                        os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
                        or (os.getenv("GITHUB_EVENT_NAME") == "push"
                            and os.getenv("CASEPROOF_ALLOW_ONE_TIME_PUSH") == "YES")
                    )
                )
            )):
            raise LiveFixtureError("protected manual main-only run required")
        pub = os.environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
        admin = os.environ.get("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
        if not pub.startswith("sb_publishable_"):
            raise LiveFixtureError("missing protected dev publishable key")
        ephemeral_private_probe(
            admin=GoTrueDevAdmin(admin),
            probe=lambda creds: verify(creds, admin_key=admin, publishable=pub),
        )
        print("LIVE_M2_SIGNED_COLD_RESTART_REVIEW_RLS_CLEANUP_PASSED")
        return 0
    except Exception as e:
        print(f"LIVE_M2_SIGNED_ROUNDTRIP_FAILED: {type(e).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
