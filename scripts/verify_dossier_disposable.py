"""Adversarial dossier RPC checks on the disposable schema, never signed proof."""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from scripts.verify_retention_disposable import main as install_and_check_retention
from scripts.verify_s2_002_database import _env, _run


def main():
    install_and_check_retention()
    env = _env()
    actor, other, org, case = (str(uuid4()) for _ in range(4))
    documents = [str(uuid4()) for _ in range(4)]
    versions = [str(uuid4()) for _ in range(4)]
    _run(f"""
insert into auth.users(id,instance_id) values('{actor}','{org}'),('{other}','{org}');
insert into caseproof.organizations(id,display_name) values('{org}','Synthetic dossier');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{org}','{actor}',array['case:read','evidence:read','review:request']),
 ('{org}','{other}',array['case:read','evidence:read','review:request']);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
 values('{case}','{org}','{actor}','dossier-test');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions)
 values('{org}','{case}','{actor}','reviewer',array['case:read','evidence:read','review:request']);
""", env)
    for document, version, role in zip(documents, versions, ('draft', 'inventory', 'exhibit', 'exhibit'), strict=True):
        _run(f"insert into caseproof.documents(id,org_id,case_id,source_label) values('{document}','{org}','{case}','fixture');"
             f"insert into caseproof.document_versions(id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type,bundle_role)"
             f"values('{version}','{org}','{document}',1,repeat('a',64),30,'application/pdf','{role}');", env)

    def rpc(action, payload=None, *, user=actor, succeeds=True):
        encoded = json.dumps(payload or {}).replace("'", "''")
        return _run(f"begin; set local role authenticated; set local request.jwt.claim.sub='{user}';"
                    "set local request.jwt.claims='{\"role\":\"authenticated\"}';"
                    f"select public.caseproof_dossier('{case}','{action}','{encoded}'::jsonb); commit;", env, should_pass=succeeds)

    context = json.loads(rpc('context'))
    rpc('context', user=other, succeeds=False)
    confirmed = {'bundle_signature': context['bundle_signature'], 'request_id': str(uuid4()),
                 'payload': {'inventory_complete': True, 'entries': [
                     {'label': 'stuk', 'number': '1', 'source_version_id': versions[2], 'pages': []}]}}
    rpc('confirm', confirmed, user=other, succeeds=False)
    rpc('confirm', confirmed)
    rpc('confirm', confirmed)  # idempotent
    report = {'case_id': case, 'brief_id': versions[0], 'bundle_signature': context['bundle_signature'],
              'confirmation_id': confirmed['request_id'],
              'findings': [{'reference_id': 'ref-0000', 'technical_check': 'checked'}]}
    serialized = json.dumps(report, sort_keys=True)
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    rpc('snapshot', {'snapshot_hash': digest, 'serialized': serialized})
    review = {'snapshot_hash': digest, 'reference_id': 'ref-0000', 'request_id': str(uuid4()),
              'decision': 'CONFIRMED_SUPPORTED', 'rationale': 'Synthetic original inspected'}
    rpc('review', review)
    assert len(json.loads(rpc('decisions', {'snapshot_hash': digest}))['decisions']) == 1
    rpc('review', {**review, 'rationale': 'conflicting replay'}, succeeds=False)
    confirmed['request_id'] = str(uuid4())
    rpc('confirm', confirmed)
    rpc('review', {**review, 'request_id': str(uuid4())}, succeeds=False)
    rpc('decisions', {'snapshot_hash': digest}, succeeds=False)
    # Exact source metadata changes invalidate both confirmation and snapshots.
    _run(f"update caseproof.document_versions set original_sha256_hex=repeat('b',64) where id='{versions[1]}'", env)
    assert json.loads(rpc('context'))['confirmation'] is None
    rpc('snapshot', {'snapshot_hash': digest, 'serialized': serialized}, succeeds=False)
    _run(f"begin; set local role authenticated; set local request.jwt.claim.sub='{actor}';"
         "set local request.jwt.claims='{\"role\":\"authenticated\"}';"
         f"select public.caseproof_soft_delete_matter('{case}'); commit;", env)
    rpc('context', succeeds=False)
    _run(f"update caseproof.cases set deleted_at=now()-interval '31 days' where id='{case}';"
         "set request.jwt.claims='{\"role\":\"service_role\"}';"
         f"select public.caseproof_retention('plan','{case}'); select public.caseproof_retention('finalize','{case}');", env)
    for table in ('dossier_confirmations', 'dossier_snapshots'):
        assert _run(f"select count(*) from caseproof.{table} where case_id='{case}'", env) == '0'
    print('DOSSIER_SQL_AUTHORIZATION_IDEMPOTENCY_SOURCE_REVISION_STALENESS_AND_ERASURE_PASSED')


if __name__ == '__main__':
    main()
