"""Signed creator-only matter deletion; pinned to caseproof-dev."""
from __future__ import annotations

import argparse
import http.client
import json
import os
from uuid import UUID

from scripts.verify_dev_ephemeral_auth import PROJECT_REF


def rpc(key: str, token: str | None, name: str, payload: dict) -> object:
    if name not in {"caseproof_soft_delete_matter", "caseproof_retention", "caseproof_retention_test"}:
        raise ValueError("unsupported retention RPC")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    con = http.client.HTTPSConnection(PROJECT_REF + ".supabase.co", timeout=30)
    try:
        con.request("POST", "/rest/v1/rpc/" + name, json.dumps(payload).encode(), headers)
        res = con.getresponse()
        status, body = res.status, res.read(4_000_001)
    finally:
        con.close()
    if status != 200 or len(body) > 4_000_000:
        raise RuntimeError(f"retention RPC failed: HTTP {status}")
    return json.loads(body)


def soft_delete(matter_id: str, key: str, token: str) -> None:
    UUID(matter_id)
    if rpc(key, token, "caseproof_soft_delete_matter", {"p_case": matter_id}) is not True:
        raise RuntimeError("deletion not acknowledged")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matter-id", type=UUID, required=True)
    args = parser.parse_args()
    soft_delete(str(args.matter_id), os.environ["CASEPROOF_DEV_PUBLISHABLE_KEY"],
                os.environ["CASEPROOF_OWNER_JWT"])
    print("MATTER_SOFT_DELETED")


if __name__ == "__main__":
    main()
