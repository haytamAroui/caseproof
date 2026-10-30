"""Provision persistent Phase 3 test identities through GoTrue Admin, never SQL.
Run only in protected caseproof-dev Actions. No deletion/cleanup by design.
"""
from __future__ import annotations

import os
import secrets
import sys
from uuid import UUID, uuid4

from scripts.verify_dev_ephemeral_auth import GoTrueDevAdmin
from scripts.verify_dev_live_txt_journey import admin_rpc


def main() -> int:
    if (
        os.getenv("CASEPROOF_PHASE3_PERSISTENT_PROVISION") != "YES"
        or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
        or os.getenv("GITHUB_REF") != "refs/heads/feat/phase3-ocr-geometry-crops"
    ):
        print("PHASE3_PROVISION_DENIED: protected branch required", file=sys.stderr)
        return 1
    key = os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
    admin = GoTrueDevAdmin(key)
    # Do not log passwords, tokens or administrator keys.
    # Unique test emails avoid modifying any existing users.
    run = uuid4()
    actors = []
    for role in ("owner", "ungranted", "foreign"):
        email = f"caseproof-ci-phase3-{role}-{secrets.token_hex(10)}@example.com"
        password = secrets.token_urlsafe(36)
        actor = admin.create_confirmed(email=email, password=password)
        actors.append(str(UUID(actor)))
        print(f"PHASE3_AUTH_CREATED: {role} (credentials withheld)")
    # Existing protected setup RPC creates organization memberships and
    # grants only to the owner. It must not delete identities.
    setup = admin_rpc(key, "setup", {
        "p_run": str(run), "p_owner": actors[0],
        "p_guest": actors[1], "p_foreign": actors[2],
    })
    print("PHASE3_ORG_READY: organization membership fixture created")
    print("PHASE3_FIXTURE_RUN: " + str(run))
    print("PHASE3_AUTH_PERSISTENT: no cleanup or delete operations invoked")
    print("PHASE3_NEXT: provision source uploads and run signed nine-step acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
