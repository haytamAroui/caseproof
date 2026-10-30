"""Delete only exact-owned resources from the durable M0.5 ledger."""
from __future__ import annotations
import argparse
import os
from uuid import UUID

from scripts.m05_registry import forget, mark, rows
from scripts.verify_dev_ephemeral_auth import GoTrueDevAdmin
from scripts.verify_dev_live_txt_journey import admin_rpc
from scripts.verify_m1_live_positive_original import _remove_original
from apps.api.signed_supabase_originals import OriginalRef


def teardown(run_id: str, key: str) -> None:
    UUID(run_id)
    entries = rows(key, run_id)
    if not entries:
        return
    if not any(e["resource_type"] == "run" and e["resource_id"] == run_id for e in entries):
        raise RuntimeError("run ownership root missing")
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
    # A matter is only deleted through the existing run+owner-checked
    # fixture cleanup RPC. Never issue an unscoped DELETE on cases.
    entries = rows(key, run_id)
    owners = [e["resource_id"] for e in entries
              if e["resource_type"] == "auth_user" and e["resource_id"].startswith("owner:") and "@" not in e["resource_id"]]
    if len(owners) != 1:
        raise RuntimeError("exact owner identity missing")
    owner = owners[0].split(":", 1)[1]
    admin_rpc(key, "cleanup", {"p_run": run_id, "p_owner": owner})
    for entry in entries:
        if entry["resource_type"] == "matter":
            forget(key, run_id, "matter", entry["resource_id"])
    admin = GoTrueDevAdmin(key)
    for entry in rows(key, run_id):
        if entry["resource_type"] == "auth_user":
            identity = entry["resource_id"].split(":", 1)[-1]
            if "@" in identity:
                # Reservation is retained until the exact Auth ID is reconciled.
                continue
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
