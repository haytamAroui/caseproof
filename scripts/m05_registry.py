"""Privileged development CI ownership ledger via PostgREST.

Only exact run-scoped IDs are written. No bearer or secret is ever logged.
"""
from __future__ import annotations
import http.client
import json
from uuid import UUID
from scripts.verify_dev_ephemeral_auth import PROJECT_REF

HOST = f"{PROJECT_REF}.supabase.co"
TABLE = "/rest/v1/test_run_registry"
ALLOWED = {"run", "auth_user", "matter", "storage_file"}


def request(key: str, method: str, path: str, payload=None):
    if not (key.startswith("sb_secret_") or key.startswith("eyJ")):
        raise RuntimeError("protected dev admin credential required")
    headers = {"apikey": key, "Content-Type": "application/json",
               "Accept": "application/json", "Accept-Profile": "caseproof",
               "Content-Profile": "caseproof", "Prefer": "return=representation,resolution=merge-duplicates"}
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    conn = http.client.HTTPSConnection(HOST, timeout=20)
    try:
        conn.request(method, path, None if payload is None else json.dumps(payload).encode(), headers)
        res = conn.getresponse()
        status, raw = res.status, res.read(100000)
    finally:
        conn.close()
    if status not in (200, 201, 204):
        raise RuntimeError(f"protected registry request failed: HTTP {status}")
    return json.loads(raw) if raw else []


def record(key: str, run_id: str, kind: str, resource_id: str, state="RESERVED"):
    UUID(run_id)
    if kind not in ALLOWED or not resource_id or len(resource_id) > 512:
        raise ValueError("invalid ownership record")
    return request(key, "POST", TABLE + "?on_conflict=run_id,resource_type,resource_id",
                   {"run_id": run_id, "resource_type": kind,
                    "resource_id": resource_id, "state": state})


def rows(key: str, run_id: str):
    UUID(run_id)
    return request(key, "GET", TABLE + "?run_id=eq." + run_id + "&select=*&order=created_at.asc")


def mark(key: str, run_id: str, kind: str, resource_id: str, state: str):
    if state not in ("RESERVED", "CREATED", "CLEANING", "CLEANED"):
        raise ValueError("invalid state")
    UUID(run_id)
    return request(key, "PATCH", TABLE + "?run_id=eq." + run_id +
                   "&resource_type=eq." + kind + "&resource_id=eq." + resource_id,
                   {"state": state})


def forget(key: str, run_id: str, kind: str, resource_id: str):
    UUID(run_id)
    return request(key, "DELETE", TABLE + "?run_id=eq." + run_id +
                   "&resource_type=eq." + kind + "&resource_id=eq." + resource_id)


def stale_runs(key: str, cutoff: str):
    return request(key, "GET", TABLE + "?resource_type=eq.run&created_at=lt." +
                   cutoff + "&select=run_id")
