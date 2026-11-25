"""'omission' is a reviewer statement ("a relevant passage or piece was not shown"). It never waives anything.

Applied to caseproof-dev as 20261124030659 (recorded in
supabase/migrations/20261124030659_caseproof_signed_review_omission_disposition.sql); NOT applied to production.
Without a local disposable PostgreSQL database, these tests verify allow-list parity and migration structure.
When CASEPROOF_LOCAL_PG_URI (or CASEPROOF_DISPOSABLE_DB=YES on 127.0.0.1/caseproof_s2_ci) is configured,
test_omission_disposition_rpc_on_local_postgres executes public.caseproof_dev_live_review ->
caseproof._rights_legacy_live_review end-to-end against PostgreSQL.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import get_args

import pytest

from application.litigation.review_blockers import review_blockers
from application.litigation.unified_review import ReviewDisposition
from application.litigation.workspace_contract import ClearbriefDecisionView
from apps.api.litigation_review_app import ReviewBody

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/20261124030659_caseproof_signed_review_omission_disposition.sql").read_text()
PROPOSAL = (ROOT / "db/proposals/SIGNED_review_omission_disposition.sql").read_text()
VALUES = {"confirmed_candidate", "dismissed", "needs_information", "omission"}
URI = os.environ.get("CASEPROOF_LOCAL_PG_URI") or (
    "postgresql://postgres:{pw}@127.0.0.1:5432/caseproof_s2_ci".format(pw=os.environ.get("PGPASSWORD", ""))
    if os.environ.get("CASEPROOF_DISPOSABLE_DB") == "YES" and os.environ.get("PGHOST") == "127.0.0.1"
    and os.environ.get("PGDATABASE") == "caseproof_s2_ci" else None)


def test_every_allow_list_agrees():
    assert {d.value for d in ReviewDisposition} == VALUES
    assert set(get_args(ReviewBody.model_fields["disposition"].annotation)) == VALUES
    assert set(get_args(ClearbriefDecisionView.model_fields["disposition"].annotation)) == VALUES
    for name in ("clearbrief-command", "clearbrief-review"):
        text = (ROOT / f"frontend/src/shared/api/{name}.schema.json").read_text()
        assert '"omission"' in text, name
    for sql_text in (MIGRATION, PROPOSAL):
        lists = re.findall(r"p_disposition not in \(([^)]*)\)", sql_text)
        assert len(lists) == 1 and set(re.findall(r"'([a-z_]+)'", lists[0])) == VALUES


def test_draft_is_a_single_function_replace_with_no_privilege_or_data_change():
    proposal_low = PROPOSAL.lower()
    assert "applied to caseproof-dev as 20261124030659" in proposal_low
    assert "not applied to production" in proposal_low
    assert "-- draft, not applied" not in proposal_low
    for low in (MIGRATION.lower(), proposal_low):
        assert low.count("create or replace function caseproof._rights_legacy_live_review(") == 1
        for forbidden in ("grant ", "revoke ", "drop ", "alter table", "insert into supabase_migrations", "delete from"):
            assert forbidden not in low.split("$function$", 1)[0] + low.split("$function$")[-1], forbidden


def test_omission_does_not_clear_a_blocker():
    from types import SimpleNamespace
    legal = SimpleNamespace(reference_id="r1", status="UNDETERMINED", reason="article_not_in_corpus")
    run = SimpleNamespace(citation_observations=(), factual_observations=(), event_observations=(),
                          passage_flags=(), incomplete=(), excluded=(), legal_observations=(legal,),
                          suitability_observations=(), snapshot_hash="a" * 64)
    decision = SimpleNamespace(observation_id="legal:r1", disposition=ReviewDisposition.OMISSION)
    out = review_blockers(run, (decision,))
    assert out["items"] == [{"observation_id": "legal:r1", "reason": "article_not_in_corpus",
                             "review_disposition": "omission"}]
    assert out["verdict"] == "not_computed" and out["release_authorized"] is False


def _psql(sql: str) -> tuple[int, str]:
    r = subprocess.run(["psql", URI or "", "-v", "ON_ERROR_STOP=1", "-At", "-f", "-"],
                       input=sql, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


def _users_sql(*named: tuple[str, str]) -> str:
    has = _psql("select 1 from information_schema.columns where table_schema='auth' and table_name='users' "
                "and column_name='instance_id'")[1].strip() == "1"
    zero = "'00000000-0000-0000-0000-000000000000'"
    if has:
        return "insert into auth.users(id,instance_id,email) values " + ",".join(
            f"('{u}',{zero},'{n}@x')" for u, n in named) + ";"
    return "insert into auth.users(id,email) values " + ",".join(f"('{u}','{n}@x')" for u, n in named) + ";"


@pytest.mark.skipif(not URI, reason="needs a disposable local PostgreSQL (CASEPROOF_LOCAL_PG_URI)")
def test_omission_disposition_rpc_on_local_postgres():
    org, case, doc, doc_ver = (str(uuid.uuid4()) for _ in range(4))
    brief, brief_ver, reviewer, outsider = (str(uuid.uuid4()) for _ in range(4))
    text = "CASEPROOF CI 2026: synthetic proof of 125 EUR on 23 October. Not client evidence.\n"
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    graph_sha = hashlib.sha256((text + brief + brief_ver).encode("utf-8")).hexdigest()
    start = text.index("125 EUR")
    end = start + len("125 EUR")
    setup = f"""
{_users_sql((reviewer, "rev"), (outsider, "out"))}
insert into caseproof.organizations(id,display_name) values ('{org}','omission-ci');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{org}','{reviewer}','{{case:read,evidence:read,finding:write,review:request}}');
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
 values ('{case}','{org}','{reviewer}','p1');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions) values
 ('{org}','{case}','{reviewer}','reviewer','{{case:read,evidence:read,draft:check,review:request}}');
insert into caseproof.documents(id,org_id,case_id,source_label) values ('{doc}','{org}','{case}','P1');
insert into caseproof.document_versions(id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type)
 values ('{doc_ver}','{org}','{doc}',1,'{sha}',{len(text.encode('utf-8'))},'text/plain');
insert into storage.objects(bucket_id,name)
 values ('caseproof-originals-dev','{org}/{case}/{doc}/{doc_ver}/{sha}');
do $seed$
declare
  v_text text := $t${text}$t$;
  v_exhibit jsonb := pg_catalog.jsonb_build_object(
    'label','P1','source_id','{doc}','version_id','{doc_ver}',
    'original_sha256','{sha}','source_text',v_text,'scope','processed',
    'origin','disposable ci omission fixture');
begin
  insert into caseproof._m1_exhibit_heads(org_id,case_id,revision,payload,payload_sha256)
   values ('{org}','{case}',1,v_exhibit,
     encode(extensions.digest(convert_to(v_exhibit::text,'UTF8'),'sha256'),'hex'));
  insert into caseproof._m2_brief_versions(
    org_id,case_id,brief_id,version_id,revision,document_id,document_version_id,
    vault_intent_id,original_sha256,representation_sha256,parser_id,
    representation,document_role,graph_sha256,case_revision,exhibit_revision,actor_id)
   values ('{org}','{case}','{brief}','{brief_ver}',1,'{doc}','{doc_ver}',
     gen_random_uuid(),'{sha}','{sha}','dev-synthetic-preseed-v1',
     v_text,'own_draft','{graph_sha}',1,1,'{reviewer}');
  insert into caseproof._m2_brief_references(
    org_id,case_id,brief_id,version_id,reference_order,reference_id,exhibit_label,exact_quote)
   values ('{org}','{case}','{brief}','{brief_ver}',0,'P1','P1','125 EUR');
  insert into caseproof._m2_brief_assertions(
    org_id,case_id,brief_id,version_id,claim_order,claim_id,reference_id,
    text_start,text_end,assertion_text,kind,fact_role,language,source_language)
   values ('{org}','{case}','{brief}','{brief_ver}',0,'fact:money-1','P1',
     {start},{end},'125 EUR','money','invoice','en','en');
  insert into caseproof._m2_brief_heads(org_id,case_id,brief_id,revision,version_id)
   values ('{org}','{case}','{brief}',1,'{brief_ver}');
end $seed$;
"""
    code, out = _psql(setup)
    assert code == 0, out

    def call(user: str, sql_call: str, role: str = "authenticated") -> tuple[int, str]:
        claims = json.dumps({"role": role, "is_anonymous": False})
        return _psql(
            f"begin; set local role {role}; "
            f"select set_config('request.jwt.claim.sub','{user}',true); "
            f"select set_config('request.jwt.claims','{claims}',true); "
            f"{sql_call}; commit;"
        )

    code, out = call(reviewer, f"select public.caseproof_dev_live_review('{case}','{brief_ver}','check')")
    assert code == 0, out
    check_payload = json.loads([line for line in out.splitlines() if line.startswith("{")][-1])
    snapshot = check_payload["snapshot_hash"]
    assert check_payload["observation_id"] == "fact:money-1" and check_payload["release_authorized"] is False

    req_omission = str(uuid.uuid4())
    review_sql = (
        f"select public.caseproof_dev_live_review('{case}','{brief_ver}','review',"
        f"'{snapshot}','{req_omission}',0,'fact:money-1','omission','Pièce absente du dossier')"
    )
    code, out = call(reviewer, review_sql)
    assert code == 0, out
    review_payload = json.loads([line for line in out.splitlines() if line.startswith("{")][-1])
    assert review_payload["review_revision"] == 1
    assert review_payload["replayed"] is False
    assert review_payload["release_authorized"] is False
    assert review_payload["decisions"][0]["decision"]["disposition"] == "omission"

    # Idempotent replay returns replayed=true without creating a second revision.
    code, out = call(reviewer, review_sql)
    assert code == 0, out
    replay_payload = json.loads([line for line in out.splitlines() if line.startswith("{")][-1])
    assert replay_payload["review_revision"] == 1 and replay_payload["replayed"] is True

    # Unknown disposition is still rejected.
    bad_req = str(uuid.uuid4())
    code, out = call(
        reviewer,
        f"select public.caseproof_dev_live_review('{case}','{brief_ver}','review',"
        f"'{snapshot}','{bad_req}',1,'fact:money-1','waive_all','should fail')",
    )
    assert code != 0 and "invalid review proposal" in out

    # Outsider and anon are denied; direct execution of internal _rights_legacy_live_review is fenced.
    code, out = call(outsider, f"select public.caseproof_dev_live_review('{case}','{brief_ver}','check')")
    assert code != 0 and "matter unavailable" in out
    code, out = call(reviewer, f"select public.caseproof_dev_live_review('{case}','{brief_ver}','check')", role="anon")
    assert code != 0 and "permission denied" in out
    code, out = call(reviewer, f"select caseproof._rights_legacy_live_review('{case}','{brief_ver}','check')")
    assert code != 0 and "permission denied" in out
