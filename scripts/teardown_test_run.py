"""Delete only exact-owned resources from the durable M0.5 ledger."""
from __future__ import annotations

import argparse
import http.client
import json
import os
from uuid import UUID

from apps.api.signed_supabase_originals import OriginalRef
from scripts.m05_registry import HOST, forget, rows
from scripts.verify_dev_ephemeral_auth import GoTrueDevAdmin
from scripts.verify_dev_live_txt_journey import admin_rpc
from scripts.verify_m1_live_positive_original import _remove_original


def verify_storage_empty(key: str, paths: list[str]) -> None:
    """Independently list the exact owned Storage prefixes after deletion."""
    prefixes = {"/".join(path.split("/")[:2]) + "/" for path in paths}
    for prefix in sorted(prefixes):
        headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + key
        conn = http.client.HTTPSConnection(HOST, timeout=20)
        try:
            conn.request("POST", "/storage/v1/object/list/caseproof-originals-dev",
                         json.dumps({"prefix": prefix, "limit": 1000}).encode(), headers)
            response = conn.getresponse()
            status, raw = response.status, response.read(100001)
        finally:
            conn.close()
        if status != 200 or len(raw) > 100000:
            raise RuntimeError("independent Storage listing failed")
        items = json.loads(raw)
        if not isinstance(items, list) or items:
            raise RuntimeError("owned Storage prefix is not empty")


def teardown(run_id: str, key: str) -> None:
    UUID(run_id)
    entries = rows(key, run_id)
    if not entries:
        return
    if not any(e["resource_type"] == "run" and e["resource_id"] == run_id for e in entries):
        raise RuntimeError("run ownership root missing")
    owned_paths = [e["resource_id"] for e in entries if e["resource_type"] == "storage_file"]
    for entry in entries:
        if entry["resource_type"] == "storage_file":
            path = entry["resource_id"]
            parts = path.split("/")
            if len(parts) != 5 or len(parts[4]) != 64:
                raise RuntimeError("unrecognized original Storage path")
            ref = OriginalRef(UUID(parts[0]), UUID(parts[1]), UUID(parts[2]),
                              UUID(parts[3]), parts[4], "application/pdf")
            _remove_original(key, ref)
            forget(key, run_id, "storage_file", path)
    verify_storage_empty(key, owned_paths)
    print("M05_STORAGE_EMPTY_VERIFIED", flush=True)
    # A matter is only deleted through the existing run+owner-checked
    # fixture cleanup RPC. Never issue an unscoped DELETE on cases.
    entries = rows(key, run_id)
    owners = [e["resource_id"] for e in entries
              if e["resource_type"] == "auth_user" and e["resource_id"].startswith("owner:") and "@" not in e["resource_id"]]
    if len(owners) > 1:
        raise RuntimeError("ambiguous owner identity")
    if owners:
        owner = owners[0].split(":", 1)[1]
        admin_rpc(key, "cleanup", {"p_run": run_id, "p_owner": owner})
    elif any(e["resource_type"] == "matter" for e in entries):
        raise RuntimeError("matter exists without registered owner")
    for entry in entries:
        if entry["resource_type"] == "matter":
            forget(key, run_id, "matter", entry["resource_id"])
    admin = GoTrueDevAdmin(key)
    for entry in rows(key, run_id):
        if entry["resource_type"] == "auth_user":
            identity = entry["resource_id"].split(":", 1)[-1]
            if "@" in identity:
                # A remote creation may have committed before the response was lost.
                # Never discard an unresolved reservation or guess an Auth ID.
                raise RuntimeError("unreconciled Auth email reservation")
            admin.delete(identity)
            forget(key, run_id, "auth_user", entry["resource_id"])
    forget(key, run_id, "run", run_id)
    if rows(key, run_id):
        raise RuntimeError("residual ownership ledger rows")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    teardown(args.run_id, os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"])
    print("M05_SCOPED_TEARDOWN_LEDGER_EMPTY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
