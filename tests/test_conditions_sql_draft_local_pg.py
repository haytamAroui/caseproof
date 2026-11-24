"""Behavioural checks of db/proposals/SIGNED_matter_conditions.sql on a LOCAL, disposable PostgreSQL.

Skipped unless CASEPROOF_LOCAL_PG_URI points to a database where the repo's candidate replay order and the draft
are installed (test-only stub auth/storage). Never point it at a shared environment: it inserts fixture rows.
Without a database the draft is only checked textually (append-only, no broad grants).
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
DRAFT = (ROOT / "db/proposals/SIGNED_matter_conditions.sql").read_text()
URI = os.environ.get("CASEPROOF_LOCAL_PG_URI")


def test_draft_text_is_append_only_and_not_granted_to_anon():
    low = DRAFT.lower()
    assert "draft, not applied" in low
    assert "revoke all on caseproof.matter_condition_specs from public, anon, authenticated, service_role" in low
    assert "grant select on caseproof.matter_condition_specs to authenticated" in low
    assert "grant insert" not in low and "grant update" not in low and "grant delete" not in low
    assert "before update or delete" in low and "before truncate" in low
    assert "to anon" not in low and "to public" not in low


def _psql(sql: str) -> tuple[int, str]:
    r = subprocess.run(["psql", URI or "", "-v", "ON_ERROR_STOP=1", "-At", "-f", "-"],
                       input=sql, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


@pytest.mark.skipif(not URI, reason="needs a disposable local PostgreSQL (CASEPROOF_LOCAL_PG_URI)")
def test_rpc_and_policies_on_local_postgres():
    org, case = str(uuid.uuid4()), str(uuid.uuid4())
    writer, viewer, outsider = (str(uuid.uuid4()) for _ in range(3))
    setup = f"""
insert into auth.users(id,email) values ('{writer}','w@x'),('{viewer}','v@x'),('{outsider}','o@x');
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
    assert "revision conflict" in call(writer, 0)[1]
    assert "not authorized" in call(viewer, 1)[1]
    assert "not authorized" in call(outsider, 1)[1]
    assert "spec hash mismatch" in call(writer, 1, digest="0" * 64)[1]
    assert "spec hash mismatch" in call(writer, 1, body=text + " ")[1]
    bad = '{"format":"x","conditions":[]}'
    assert "unsupported conditions format" in call(writer, 1, bad, hashlib.sha256(bad.encode()).hexdigest())[1]
    assert "permission denied" in call(writer, 1, role="anon")[1]
    assert "append-only" in _psql(f"update caseproof.matter_condition_specs set revision=revision where case_id='{case}'")[1]
    assert "append-only" in _psql(f"delete from caseproof.matter_condition_specs where case_id='{case}'")[1]
    seen = _psql(f"begin; set local role authenticated; select set_config('request.jwt.claim.sub','{viewer}',true); "
                 "select count(*) from caseproof.matter_condition_specs; commit;")[1]
    assert "1" in seen.splitlines()
    none = _psql(f"begin; set local role authenticated; select set_config('request.jwt.claim.sub','{outsider}',true); "
                 "select count(*) from caseproof.matter_condition_specs; commit;")[1]
    assert "0" in none.splitlines()
