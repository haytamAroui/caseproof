"""Retryable dev reaper: Storage API first, locked DB finalization second."""
from __future__ import annotations

import argparse
import http.client
import json
import os
from uuid import UUID

from scripts.soft_delete_matter import rpc
from scripts.teardown_test_run import verify_storage_empty
from scripts.verify_dev_ephemeral_auth import PROJECT_REF


def purge(matter_id: str, key: str) -> dict:
    UUID(matter_id)
    token = key if key.startswith("eyJ") else None
    plan = rpc(key, token, "caseproof_retention", {"p_action": "plan", "p_case": matter_id})
    if not isinstance(plan, dict):
        raise RuntimeError("invalid purge plan")
    if plan.get("purged") is True:
        return plan
    prefix, paths = plan["prefix"], plan["paths"]
    if not isinstance(paths, list) or len(prefix.split("/")) != 3 or prefix.split("/")[1] != matter_id:
        raise RuntimeError("invalid matter Storage prefix")
    # Every returned object must be in this exact tenant/matter prefix. Do not
    # assume the final component is a hash: remove stray objects there as well.
    if any(not isinstance(p, str) or not p.startswith(prefix) for p in paths):
        raise RuntimeError("cross-matter Storage plan")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    for offset in range(0, len(paths), 100):
        con = http.client.HTTPSConnection(PROJECT_REF + ".supabase.co", timeout=30)
        try:
            con.request("DELETE", "/storage/v1/object/caseproof-originals-dev",
                        json.dumps({"prefixes": paths[offset:offset + 100]}).encode(), headers)
            res = con.getresponse()
            status = res.status
            res.read(1_000_001)
        finally:
            con.close()
        if status != 200:
            raise RuntimeError(f"Storage purge incomplete: HTTP {status}")
    verify_storage_empty(key, [prefix + "placeholder"])
    result = rpc(key, token, "caseproof_retention", {"p_action": "finalize", "p_case": matter_id})
    if not isinstance(result, dict) or result.get("purged") is not True:
        raise RuntimeError("purge not committed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matter-id", type=UUID)
    args = parser.parse_args()
    key = os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
    token = key if key.startswith("eyJ") else None
    matters = [str(args.matter_id)] if args.matter_id else rpc(
        key, token, "caseproof_retention", {"p_action": "due"})
    if not isinstance(matters, list):
        raise RuntimeError("invalid due matter list")
    for matter in matters:
        purge(matter, key)
        print("MATTER_PURGED")


if __name__ == "__main__":
    main()
