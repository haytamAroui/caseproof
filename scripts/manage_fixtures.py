"""Protected CLI for CaseProof development fixture provisioning.

Usage: python -m scripts.manage_fixtures create-bundle
Requires signed owner JWT and development API already running locally.
User creation remains delegated to the protected GoTrue provisioning workflow.
No implicit deletion of persistent Phase 3 acceptance records.
"""
from __future__ import annotations

import argparse
import os

from tests.fixtures.factory import FixtureFactory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create-bundle", "create-users", "delete-all"))
    args = parser.parse_args()
    if args.action == "create-users":
        from scripts.provision_phase3_persistent_users import main as provision_users

        return provision_users()
    if args.action == "delete-all":
        raise SystemExit(
            "Refusing broad deletion: only a dedicated run-scoped disposable "
            "cleanup protocol may delete its own resources."
        )
    if os.environ.get("CASEPROOF_FIXTURE_DEV") != "YES":
        raise SystemExit("CASEPROOF_FIXTURE_DEV=YES required")
    from scripts.phase3_live_acceptance import direct
    from scripts.verify_dev_live_txt_journey import success

    factory = FixtureFactory(
        api=success,
        rpc=direct,
        publishable_key=os.environ["CASEPROOF_DEV_PUBLISHABLE_KEY"],
    )
    result = factory.create_bundle(
        os.environ["CASEPROOF_FIXTURE_OWNER_JWT"],
        os.environ["CASEPROOF_FIXTURE_ORG_ID"],
    )
    print(f"FIXTURE_BUNDLE_CREATED: {result.matter_id} ({len(result.sources)} sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
