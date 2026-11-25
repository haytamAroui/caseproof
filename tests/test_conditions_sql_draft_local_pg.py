"""Behavioural checks of 20261124030604_caseproof_signed_matter_conditions.sql and its companion retention draft
on a LOCAL, disposable PostgreSQL.

Skipped unless CASEPROOF_LOCAL_PG_URI (or CASEPROOF_DISPOSABLE_DB=YES on 127.0.0.1/caseproof_s2_ci) points to a
database where the repo's candidate replay order and the companion retention draft are installed (test-only stub
auth/storage). Never point it at a shared environment: it inserts fixture rows.
Without a database the migration and companion draft are checked textually (append-only, no broad grants).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/20261124030604_caseproof_signed_matter_conditions.sql").read_text()
PROPOSAL = (ROOT / "db/proposals/SIGNED_matter_conditions.sql").read_text()
RETENTION = (ROOT / "db/proposals/SIGNED_matter_conditions_retention.sql").read_text()
URI = os.environ.get("CASEPROOF_LOCAL_PG_URI") or (
    "postgresql://postgres:{pw}@127.0.0.1:5432/caseproof_s2_ci".format(pw=os.environ.get("PGPASSWORD", ""))
    if os.environ.get("CASEPROOF_DISPOSABLE_DB") == "YES" and os.environ.get("PGHOST") == "127.0.0.1"
    and os.environ.get("PGDATABASE") == "caseproof_s2_ci" else None)


def test_draft_text_is_append_only_and_not_granted_to_anon():
    proposal_low = PROPOSAL.lower()
    assert "applied to caseproof-dev as 20261124030604" in proposal_low
    assert "not applied to production" in proposal_low
    assert "draft, not applied" not in proposal_low
    for low in (MIGRATION.lower(), proposal_low):
        assert "revoke all on caseproof.matter_condition_specs from public, anon, authenticated, service_role" in low
        assert "grant select on caseproof.matter_condition_specs to authenticated" in low
        assert "grant insert" not in low and "grant update" not in low and "grant delete" not in low
        assert "before update or delete" in low and "before truncate" in low
        assert "to anon" not in low and "to public" not in low


def _users_sql(*named: tuple[str, str]) -> str:
    """auth.users rows. The repo's disposable stub makes instance_id NOT NULL; a minimal stub may lack the column."""
    has = _psql("select 1 from information_schema.columns where table_schema='auth' and table_name='users' "
                "and column_name='instance_id'")[1].strip() == "1"
    zero = "'00000000-0000-0000-0000-000000000000'"
    if has:
        return "insert into auth.users(id,instance_id,email) values " + ",".join(f"('{u}',{zero},'{n}@x')" for u, n in named) + ";"
    return "insert into auth.users(id,email) values " + ",".join(f"('{u}','{n}@x')" for u, n in named) + ";"


def _psql(sql: str) -> tuple[int, str]:
    r = subprocess.run(["psql", URI or "", "-v", "ON_ERROR_STOP=1", "-At", "-f", "-"],
                       input=sql, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


@pytest.mark.skipif(not URI, reason="needs a disposable local PostgreSQL (CASEPROOF_LOCAL_PG_URI)")
def test_rpc_and_policies_on_local_postgres():
    org, case = str(uuid.uuid4()), str(uuid.uuid4())
    writer, viewer, outsider = (str(uuid.uuid4()) for _ in range(3))
    users = _users_sql((writer, "w"), (viewer, "v"), (outsider, "o"))
    setup = f"""
{users}
insert into caseproof.organizations(id,display_name) values ('{org}','t');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{org}','{writer}','{{case:read,finding:write}}'),('{org}','{viewer}','{{case:read}}');
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version) values ('{case}','{org}','{writer}','p1');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions) values
 ('{org}','{case}','{writer}','reviewer','{{case:read,finding:write}}'),
 ('{org}','{case}','{viewer}','viewer','{{case:read}}');"""
    assert _psql(setup)[0] == 0
    text = json.dumps({"format": "caseproof-conditions-v1", "conditions": [
        {"id": "c1", "label": "L", "question": "", "trigger": ["courrier"], "evidence": ["reçu"], "pieces": []}]},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    sha = hashlib.sha256(text.encode()).hexdigest()

    def call(user: str, expected: int, body: str = text, digest: str = sha, role: str = "authenticated") -> tuple[int, str]:
        return _psql(f"begin; set local role {role}; select set_config('request.jwt.claim.sub','{user}',true); "
                     f"select public.caseproof_append_conditions('{case}',{expected},$j${body}$j$,'{digest}'); commit;")

    code, out = call(writer, 0)
    assert code == 0 and '"revision": 1' in out
    assert '"conflict": true' in call(writer, 0)[1]
    def read(user: str, role: str = "authenticated") -> str:
        return _psql(f"begin; set local role {role}; select set_config('request.jwt.claim.sub','{user}',true); "
                     f"select public.caseproof_read_conditions('{case}'); commit;")[1]

    assert '"revision": 1' in read(writer) and "spec_text" in read(viewer)
    assert "not authorized" in read(outsider) and "spec_text" not in read(outsider)
    h1 = read(writer)
    assert f'"actor_id": "{writer}"' in h1 and '"history"' in h1 and "recorded_at" in h1 and "Z" in h1
    assert "history" not in read(outsider)
    assert "permission denied" in read(writer, "anon")
    empty = '{"conditions":[],"format":"caseproof-conditions-v1"}'
    assert '"revision": 2' in call(writer, 1, empty, hashlib.sha256(empty.encode()).hexdigest())[1]  # cleared
    assert "not authorized" in call(viewer, 2)[1]
    assert "not authorized" in call(outsider, 1)[1]
    assert "spec hash mismatch" in call(writer, 1, digest="0" * 64)[1]
    assert "spec hash mismatch" in call(writer, 1, body=text + " ")[1]
    bad = '{"format":"x","conditions":[]}'
    assert "unsupported conditions format" in call(writer, 1, bad, hashlib.sha256(bad.encode()).hexdigest())[1]
    assert "permission denied" in call(writer, 1, role="anon")[1]
    assert "append-only" in _psql(f"update caseproof.matter_condition_specs set revision=revision where case_id='{case}'")[1]
    assert "append-only" in _psql(f"delete from caseproof.matter_condition_specs where case_id='{case}'")[1]
    # setting the bypass flag as an API role does not open a delete path (no DELETE privilege)
    assert "permission denied" in _psql(
        "begin; set local role authenticated; select set_config('caseproof.dev_review_cleanup','single_fixture',true); "
        f"delete from caseproof.matter_condition_specs where case_id='{case}'; commit;")[1]
    seen = _psql(f"begin; set local role authenticated; select set_config('request.jwt.claim.sub','{viewer}',true); "
                 "select count(*) from caseproof.matter_condition_specs; commit;")[1]
    assert "2" in seen.splitlines()
    none = _psql(f"begin; set local role authenticated; select set_config('request.jwt.claim.sub','{outsider}',true); "
                 "select count(*) from caseproof.matter_condition_specs; commit;")[1]
    assert "0" in none.splitlines()


def test_retention_companion_is_a_bounded_generated_function():
    low = RETENTION.lower()
    assert "applied to caseproof-dev" in low
    assert "not applied to production" in low
    assert "draft, not applied" not in low
    assert low.count("delete from caseproof.matter_condition_specs") == 1
    assert "security definer" in low and "set search_path to ''" in low
    assert "grant execute on function public.caseproof_retention(text,uuid) to service_role" in low
    assert "to authenticated" not in low and "to anon" not in low


@pytest.mark.skipif(not URI, reason="needs a disposable local PostgreSQL (CASEPROOF_LOCAL_PG_URI)")
def test_purge_finalize_removes_condition_revisions_and_soft_deleted_matter_refuses_writes():
    org, case, writer = (str(uuid.uuid4()) for _ in range(3))
    assert _psql(f"""
{_users_sql((writer, 'p'))}
insert into caseproof.organizations(id,display_name) values ('{org}','t');
insert into caseproof.organization_members(org_id,user_id,actions) values ('{org}','{writer}','{{case:read,finding:write}}');
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version) values ('{case}','{org}','{writer}','p1');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions) values
 ('{org}','{case}','{writer}','reviewer','{{case:read,finding:write}}');""")[0] == 0
    text = json.dumps({"format": "caseproof-conditions-v1", "conditions": [
        {"id": "c1", "label": "L", "question": "", "trigger": ["b"], "evidence": ["a"], "pieces": []}]},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    sha = hashlib.sha256(text.encode()).hexdigest()

    def append(expected: int) -> tuple[int, str]:
        return _psql(f"begin; set local role authenticated; select set_config('request.jwt.claim.sub','{writer}',true); "
                     f"select public.caseproof_append_conditions('{case}',{expected},$j${text}$j$,'{sha}'); commit;")

    assert append(0)[0] == 0
    assert _psql(f"update caseproof.cases set deleted_at=now()-interval '90 days' where id='{case}'")[0] == 0
    code, out = append(1)
    assert code != 0, out  # a soft-deleted matter takes no new revision
    svc = ("begin; set local role service_role; select set_config('request.jwt.claims','{\"role\":\"service_role\"}',true); "
           "select public.caseproof_retention('%s','" + case + "'); commit;")
    assert _psql(svc % "plan")[0] == 0
    code, out = _psql(svc % "finalize")
    assert code == 0 and '"purged": true' in out, out
    left = _psql(f"select (select count(*) from caseproof.matter_condition_specs where case_id='{case}'),"
                 f"(select count(*) from caseproof.cases where id='{case}')")[1]
    assert left.strip().splitlines()[-1] == "0|0"
