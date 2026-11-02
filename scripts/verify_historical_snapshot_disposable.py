"""Independent historical-read permission/retention checks on disposable PostgreSQL."""
import json
from pathlib import Path
from uuid import uuid4

from scripts.verify_retention_disposable import main as install
from scripts.verify_s2_002_database import _env, _run


def main() -> None:
    install()
    env = _env()
    proposal = Path('db/proposals/PIV-F1_historical_snapshot_read.sql')
    migration = Path('supabase/migrations/20261102150600_caseproof_historical_snapshot_read.sql')
    assert proposal.read_bytes() == migration.read_bytes()
    assert _run("select to_regprocedure('public.caseproof_dossier_historical_read(uuid,text)') is not null", env) == 't'
    owner, guest, foreign, org, other_org, case, brief = (str(uuid4()) for _ in range(7))
    snapshot = 'a' * 64
    _run(f"""
insert into auth.users(id,instance_id) values
 ('{owner}','{org}'),('{guest}','{org}'),('{foreign}','{other_org}');
insert into caseproof.organizations(id,display_name) values
 ('{org}','Historical synthetic'),('{other_org}','Unrelated');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{org}','{owner}',array['case:read','evidence:read']),
 ('{org}','{guest}',array['case:read','evidence:read']),
 ('{other_org}','{foreign}',array['case:read','evidence:read']);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
 values ('{case}','{org}','{owner}','f1-history');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions)
 values ('{org}','{case}','{owner}','reviewer',array['case:read','evidence:read']);
insert into caseproof.dossier_snapshots(org_id,case_id,snapshot_hash,bundle_signature,serialized)
 values ('{org}','{case}','{snapshot}',repeat('b',64),'{{"brief_id":"{brief}"}}');
""", env)

    def read(user=owner, role='authenticated', anonymous=False, digest=snapshot, succeeds=True):
        sql = (f"begin;set local role {role};set local request.jwt.claim.sub='{user}';"
               f"set local request.jwt.claims='{{\"role\":\"{role}\",\"is_anonymous\":{str(anonymous).lower()}}}';"
               f"select public.caseproof_dossier_historical_read('{case}','{digest}');commit;")
        return _run(sql, env, should_pass=succeeds)

    assert json.loads(read()) == {'serialized': json.dumps({'brief_id': brief}, separators=(',', ':'))}
    for user in (guest, foreign):
        read(user=user, succeeds=False)
    read(role='anon', succeeds=False)
    read(anonymous=True, succeeds=False)
    read(digest='invalid', succeeds=False)
    read(digest='f' * 64, succeeds=False)
    _run(f"begin;set local role authenticated;select * from caseproof.dossier_snapshots where case_id='{case}';commit;", env, should_pass=False)
    _run(f"update caseproof._m1_matter_grants set active=false where case_id='{case}'", env)
    read(succeeds=False)
    _run(f"update caseproof._m1_matter_grants set active=true where case_id='{case}';"
         f"update caseproof.organization_members set active=false where user_id='{owner}'", env)
    read(succeeds=False)
    _run(f"update caseproof.organization_members set active=true where user_id='{owner}';"
         f"update caseproof.cases set deleted_at=now() where id='{case}'", env)
    read(succeeds=False)
    # Only the run-specific synthetic data is deleted. The CI service itself is
    # disposable; this is not a production retention or purge exercise.
    _run(f"""delete from caseproof.dossier_snapshots where case_id='{case}';
delete from caseproof._m1_matter_grants where case_id='{case}';
delete from caseproof.cases where id='{case}';
delete from caseproof.organization_members where org_id in ('{org}','{other_org}');
delete from caseproof.organizations where id in ('{org}','{other_org}');
delete from auth.users where id in ('{owner}','{guest}','{foreign}');""", env)
    assert _run(f"select count(*) from caseproof.cases where id='{case}'", env) == '0'
    assert _run(f"select count(*) from caseproof.dossier_snapshots where case_id='{case}'", env) == '0'
    print('HISTORICAL_SIGNED_SQL_GRANTS_RETENTION_ANONYMOUS_FOREIGN_CLEANUP_PASSED')


if __name__ == '__main__':
    main()
