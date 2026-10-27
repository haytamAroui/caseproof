"""PIV-M1 disposable PostgreSQL integration: real CAS, audit and restricted grants.

Runs against the existing single-use CI Postgres fixture ONLY. It cannot
connect to caseproof-dev or any shared Supabase project.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from scripts.verify_s2_002_database import _env, _run

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "db/proposals/PIV-M1_disposable_matter_grants_and_exhibits.sql"
ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CASE = "aaaaaaaa-1111-4111-8111-111111111111"
ACTOR = "11111111-1111-4111-8111-111111111111"
FOREIGN = "22222222-2222-4222-8222-222222222222"


def main() -> None:
    env = _env()
    _run(PROPOSAL.read_text(encoding="utf-8"), env)
    # S2 foundation suite intentionally revoked this actor; restore ONLY
    # inside the disposable CI database before the fresh M1 negative probes.
    _run(
        "update caseproof.organization_members "
        "set active=true,actions=array['case:read','evidence:read','review:request'] "
        f"where org_id='{ORG}' and user_id='{ACTOR}'; "
        "insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions) "
        f"values ('{ORG}','{CASE}','{ACTOR}','reviewer',"
        "array['case:read','evidence:read','exhibit:confirm']);", env,
    )
    payload = {"schema": "caseproof-exhibit-register-v1", "entries": []}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    request = str(uuid4())
    command = (
        "select committed_revision::text || ':' || replay::text "
        "from caseproof._m1_disposable_confirm_exhibits("
        f"'{ACTOR}'::uuid,'{CASE}'::uuid,'{request}'::uuid,"
        f"0,'{encoded}'::jsonb,'{digest}');"
    )
    if _run(command, env) != "1:false" or _run(command, env) != "1:true":
        raise AssertionError("Exhibit register CAS and safe idempotent replay failed")
    if _run(
        f"select count(*)::text from caseproof.audit_events "
        f"where case_id='{CASE}' and action='m1_exhibit_register_confirm'", env
    ) != "1":
        raise AssertionError("exhibit commit did not generate exactly one audit event")
    stale = command.replace(f"'{request}'::uuid", f"'{uuid4()}'::uuid")
    _run(stale, env, should_pass=False)
    foreign = command.replace(f"'{ACTOR}'::uuid", f"'{FOREIGN}'::uuid")
    _run(foreign, env, should_pass=False)
    forged = (
        "set role authenticated; "
        f"select * from caseproof._m1_exhibit_heads where case_id='{CASE}';"
    )
    _run(forged, env, should_pass=False)
    _run(
        "set role authenticated; select * from "
        "caseproof._m1_disposable_confirm_exhibits("
        f"'{ACTOR}'::uuid,'{CASE}'::uuid,'{uuid4()}'::uuid,"
        f"1,'{encoded}'::jsonb,'{digest}');", env, should_pass=False,
    )
    # Role and org membership alone must NOT allow exhibit confirmation.
    _run(
        f"update caseproof._m1_matter_grants set permissions=array['case:read'] "
        f"where case_id='{CASE}';", env,
    )
    no_permission = (
        "select * from caseproof._m1_disposable_confirm_exhibits("
        f"'{ACTOR}'::uuid,'{CASE}'::uuid,'{uuid4()}'::uuid,"
        f"1,'{encoded}'::jsonb,'{digest}');"
    )
    _run(no_permission, env, should_pass=False)
    _run(
        f"update caseproof._m1_matter_grants set active=false where case_id='{CASE}';", env,
    )
    denied = (
        "select * from caseproof._m1_disposable_confirm_exhibits("
        f"'{ACTOR}'::uuid,'{CASE}'::uuid,'{uuid4()}'::uuid,"
        f"1,'{encoded}'::jsonb,'{digest}');"
    )
    _run(denied, env, should_pass=False)
    if _run(
        f"select revision::text from caseproof._m1_exhibit_heads where case_id='{CASE}'", env
    ) != "1":
        raise AssertionError("revoked case grant incorrectly modified register")
    _run(
        "update caseproof._m1_exhibit_events set expected_revision=8;",
        env, should_pass=False,
    )
    print("M1_DISPOSABLE_POSTGRES_CAS_AUDIT_RLS_REVOCATION_PASSED")


if __name__ == "__main__":
    main()
