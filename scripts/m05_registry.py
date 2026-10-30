"""Protected M0.5 registry RPC. Only service-role requests may mutate ledger."""
from __future__ import annotations
import http.client
import json
from uuid import UUID
from scripts.verify_dev_ephemeral_auth import PROJECT_REF

HOST = f"{PROJECT_REF}.supabase.co"
RPC = "/rest/v1/rpc/caseproof_m05_registry"
ALLOWED = {"run", "auth_user", "matter", "storage_file"}


def call(key: str, action: str, run_id: str, kind=None, resource=None, state=None, cutoff=None):
    if not (key.startswith("sb_secret_") or key.startswith("eyJ")):
        raise RuntimeError("protected dev admin credential required")
    UUID(run_id)
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    payload = {"p_action": action, "p_run": run_id, "p_kind": kind,
               "p_resource": resource, "p_state": state, "p_cutoff": cutoff}
    conn = http.client.HTTPSConnection(HOST, timeout=20)
    try:
        conn.request("POST", RPC, json.dumps(payload).encode(), headers)
        res = conn.getresponse()
        status, raw = res.status, res.read(100000)
    finally:
        conn.close()
    if status != 200:
        raise RuntimeError(f"protected registry RPC failed: HTTP {status}")
    return json.loads(raw)


def record(key, run_id, kind, resource_id, state="RESERVED"):
    if kind not in ALLOWED or not resource_id or len(resource_id) > 512:
        raise ValueError("invalid ownership record")
    return call(key, "record", run_id, kind, resource_id, state)


def rows(key, run_id):
    return call(key, "rows", run_id)


def forget(key, run_id, kind, resource_id):
    return call(key, "forget", run_id, kind, resource_id)


def stale_runs(key, cutoff):
    return call(key, "stale", "00000000-0000-0000-0000-000000000000", cutoff=cutoff)
