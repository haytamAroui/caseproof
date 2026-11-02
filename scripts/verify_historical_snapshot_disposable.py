"""Historical authorization checks using only disposable PostgreSQL fixtures."""
import json
from pathlib import Path

from scripts.verify_s2_002_database import _env, _run


def main():
    env = _env()
    _run(Path('db/proposals/PIV-F1_historical_snapshot_read.sql').read_text(), env)
    case, owner = _run("select c.id,g.user_id from caseproof.cases c join caseproof._m1_matter_grants g on g.case_id=c.id where c.effective_policy_version='f1-test' limit 1", env).split('|')
    _run(f"update caseproof.cases set deleted_at=null where id='{case}'", env)
    def read(user=owner, role='authenticated', anonymous=False, digest='0'*64, succeeds=True):
        return _run(f"begin;set local role {role};set local request.jwt.claim.sub='{user}';"
                    f"set local request.jwt.claims='{{\"role\":\"{role}\",\"is_anonymous\":{str(anonymous).lower()}}}';"
                    f"select public.caseproof_dossier_historical_read('{case}','{digest}');commit;", env, should_pass=succeeds)
    assert 'serialized' in json.loads(read())
    read(role='anon', succeeds=False)
    read(anonymous=True, succeeds=False)
    read(digest='invalid', succeeds=False)
    read(digest='f'*64, succeeds=False)
    guest = _run(f"select user_id from caseproof.organization_members where user_id<>'{owner}' limit 1", env)
    read(user=guest, succeeds=False)
    _run(f"update caseproof._m1_matter_grants set active=false where case_id='{case}'", env)
    read(succeeds=False)
    _run(f"update caseproof._m1_matter_grants set active=true where case_id='{case}';update caseproof.organization_members set active=false where user_id='{owner}'", env)
    read(succeeds=False)
    _run(f"update caseproof.organization_members set active=true where user_id='{owner}';update caseproof.cases set deleted_at=now() where id='{case}'", env)
    read(succeeds=False)
    print('HISTORICAL_READ_AUTHORIZATION_DISPOSABLE_PASSED')


if __name__ == '__main__':
    main()
