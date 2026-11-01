"""Real disposable PostgreSQL authorization/keyset tests, not genuine Auth."""
import json
from pathlib import Path
from uuid import uuid4

from scripts.verify_retention_disposable import main as install
from scripts.verify_s2_002_database import _env, _run


def main():
    install()
    env = _env()
    _run(Path('db/proposals/PIV-F1_workspace_report_catalog.sql').read_text(), env)
    owner, guest, foreign, org, org2, case, brief = (str(uuid4()) for _ in range(7))
    _run(f"""
insert into auth.users(id,instance_id) values('{owner}','{org}'),('{guest}','{org}'),('{foreign}','{org2}');
insert into caseproof.organizations(id,display_name) values('{org}','F1 synthetic'),('{org2}','Foreign');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{org}','{owner}',array['case:read','evidence:read']),('{org}','{guest}',array['case:read','evidence:read']),
 ('{org2}','{foreign}',array['case:read','evidence:read']);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
 values('{case}','{org}','{owner}','f1-test');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions)
 values('{org}','{case}','{owner}','reviewer',array['case:read','evidence:read']);
""", env)

    def read(user=owner, after=None, succeeds=True, role='authenticated', anonymous=False):
        cursor = "null" if after is None else "'" + after + "'"
        return _run(f"begin; set local role {role}; set local request.jwt.claim.sub='{user}';"
                    f"set local request.jwt.claims='{{\"role\":\"{role}\",\"is_anonymous\":{str(anonymous).lower()}}}';"
                    f"select public.caseproof_workspace_reports('{case}',{cursor});commit;", env, should_pass=succeeds)

    assert json.loads(read())['reports'] == []
    # Fixture-only direct insert does not stand in for signed snapshot creation.
    for i in range(25):
        digest = f'{i:064x}'
        _run(f"insert into caseproof.dossier_snapshots(org_id,case_id,snapshot_hash,bundle_signature,serialized)"
             f"values('{org}','{case}','{digest}',repeat('a',64),'{{\"brief_id\":\"{brief}\"}}');", env)
    first = json.loads(read())
    assert len(first['reports']) == 20 and first['next_cursor'] == f'{19:064x}'
    second = json.loads(read(after=first['next_cursor']))
    assert len(second['reports']) == 5 and second['next_cursor'] is None
    assert {r['snapshot_hash'] for r in first['reports']}.isdisjoint(r['snapshot_hash'] for r in second['reports'])
    for user in (guest, foreign):
        read(user=user, succeeds=False)
    read(role='anon', succeeds=False)
    read(anonymous=True, succeeds=False)
    read(after='not-a-hash', succeeds=False)
    _run(f"update caseproof._m1_matter_grants set active=false where case_id='{case}'", env)
    read(succeeds=False)
    _run(f"update caseproof._m1_matter_grants set active=true where case_id='{case}'; update caseproof.organization_members set active=false where user_id='{owner}'", env)
    read(succeeds=False)
    _run(f"update caseproof.organization_members set active=true where user_id='{owner}'; update caseproof.cases set deleted_at=now() where id='{case}'", env)
    read(succeeds=False)
    _run(f"begin;set local role authenticated;select * from caseproof.dossier_snapshots where case_id='{case}';commit;", env, should_pass=False)
    print('F1_POSTGRES_CATALOG_PAGING_FOREIGN_UNGRANTED_REVOKED_DELETED_ANONYMOUS_DENIAL_PASSED')


if __name__ == '__main__':
    main()
