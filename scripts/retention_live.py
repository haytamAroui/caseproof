"""Protected M0.5 live wrapper: create, register, execute, always teardown."""
from __future__ import annotations

import os
import sys
from uuid import UUID

from scripts.m05_registry import call, forget, record
from scripts.teardown_test_run import teardown
from scripts.verify_dev_ephemeral_auth import GoTrueDevAdmin
from scripts.verify_dev_live_txt_journey import admin_rpc
from tests.fixtures.run_lifecycle import credentials, new_run_id


def main() -> int:
    if os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof" or os.getenv("GITHUB_REF") not in {"refs/heads/feat/production-hardening", "refs/heads/feat/final-hardening-and-verification"}:
        raise RuntimeError("protected M0.5 branch required")
    key = os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
    run = new_run_id()
    record(key, run, "run", run)
    admin = GoTrueDevAdmin(key)
    actors = {}
    generated = credentials(run)
    failure = None
    try:
        for role, (email, password) in generated.items():
            # Reserve identity before remote creation; GoTrue generates its ID.
            # Unknown HTTP outcomes must be reconciled by exact run-tagged email.
            record(key, run, "auth_user", role + ":" + email, "RESERVED")
            user_id = admin.create_confirmed(email=email, password=password)
            actors[role] = user_id
            record(key, run, "auth_user", role + ":" + user_id, "CREATED")
            forget(key, run, "auth_user", role + ":" + email)
            os.environ[f"CASEPROOF_P3_{role.upper()}_EMAIL"] = email
            os.environ[f"CASEPROOF_P3_{role.upper()}_PASSWORD"] = password
        setup = admin_rpc(key, "setup", {
            "p_run": run, "p_owner": actors["owner"],
            "p_guest": actors["ungranted"], "p_foreign": actors["foreign"],
        })
        org = str(UUID(setup["org_id"]))
        os.environ["CASEPROOF_P3_ORG_ID"] = org
        os.environ["CASEPROOF_P3_RUN_ID"] = run
        from scripts.retention_live_acceptance import main as phase3
        phase3()
    except Exception as exc:
        failure = type(exc).__name__ + ":" + str(exc)
    finally:
        try:
            teardown(run, key)
        except Exception as exc:
            print("M05_TEARDOWN_FAILED:" + type(exc).__name__, file=sys.stderr)
            return 1
    if call(key, "verify", run) is not True:
        raise RuntimeError("independent zero-residual verification failed")
    print("ZERO_RESIDUAL_VERIFIED", flush=True)
    if failure:
        print("M05_EXPECTED_OR_UNEXPECTED_FAILURE:" + failure, file=sys.stderr)
        return 1
    print("RETENTION_SIGNED_ACCEPTANCE_AND_TEARDOWN_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
