"""Real disposable SQL state/fence proof with synthetic actors, never live Auth."""
import hashlib
import json
from uuid import uuid4

from scripts.verify_s2_002_database import _env, _run


def main():
    env = _env()
    owner, other, org, case, doc, version, request = (str(uuid4()) for _ in range(7))
    _run(f"""
insert into auth.users(id,instance_id) values('{owner}','{org}'),('{other}','{org}');
insert into caseproof.organizations(id,display_name) values('{org}','Synthetic page jobs');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{org}','{owner}',array['case:read','evidence:read','review:request']),
 ('{org}','{other}',array['case:read','evidence:read','review:request']);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version) values('{case}','{org}','{owner}','pages-test');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions) values
 ('{org}','{case}','{owner}','reviewer',array['case:read','evidence:read','review:request']),
 ('{org}','{case}','{other}','reviewer',array['case:read','evidence:read','review:request']);
insert into caseproof.documents(id,org_id,case_id,source_label) values('{doc}','{org}','{case}','Synthetic exhibit');
insert into caseproof.document_versions(id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type,bundle_role)
 values('{version}','{org}','{doc}',1,repeat('a',64),100,'application/pdf','exhibit');
""", env)
    def rpc(action, data=None, *, actor=owner, target=case, succeeds=True):
        payload = json.dumps(data or {}).replace("'", "''")
        raw = _run(f"begin; set local role authenticated; set local request.jwt.claim.sub='{actor}';"
                   "set local request.jwt.claims='{\"role\":\"authenticated\"}';"
                   f"select public.caseproof_page_job('{target}','{request}','{action}','{payload}'); commit;",
                   env, should_pass=succeeds)
        return json.loads(raw) if succeeds else None
    signature = json.loads(_run(f"begin; set local role authenticated; set local request.jwt.claim.sub='{owner}';"
                "set local request.jwt.claims='{\"role\":\"authenticated\"}';"
                f"select public.caseproof_dossier('{case}','context'); commit;", env))['bundle_signature']
    page = {'document_id': doc, 'version_id': version, 'original_sha256': 'a' * 64, 'pdf_page': 1, 'needs_ocr': True}
    manifest = {'schema': 'caseproof-page-job-v1', 'case_id': case, 'request_id': request,
                'bundle_signature': signature, 'engine_version': 'synthetic-sql-only', 'pages': [page]}
    serialized = json.dumps(manifest, sort_keys=True, separators=(',', ':'))
    hashed = hashlib.sha256(serialized.encode()).hexdigest()
    row = rpc('enqueue', {'manifest': serialized, 'manifest_hash': hashed})
    assert rpc('enqueue', {'manifest': serialized, 'manifest_hash': hashed})['deadline_at'] == row['deadline_at']
    rpc('status', actor=other, succeeds=False)
    rpc('status', target=str(uuid4()), succeeds=False)
    _run("begin; set local role authenticated; select * from caseproof.page_jobs; commit;", env, should_pass=False)
    # Audit failure must roll back the lease itself.
    _run("create function public.page_audit_fail() returns trigger language plpgsql as $$begin raise exception 'audit unavailable'; end$$;"
         "create trigger page_audit_fail before insert on caseproof.page_job_events for each row execute function public.page_audit_fail();", env)
    rpc('claim', succeeds=False)
    _run("drop trigger page_audit_fail on caseproof.page_job_events; drop function public.page_audit_fail();", env)
    assert rpc('status')['state'] == 'queued'
    lease = rpc('claim')['lease_token']
    rpc('claim', succeeds=False)
    rpc('heartbeat', {'lease_token': str(uuid4())}, succeeds=False)
    rpc('finish', {'lease_token': lease}, succeeds=False)
    artifact = {'schema': 'caseproof-page-artifact-v1', 'org_id': org, 'case_id': case,
                'actor_id': owner, 'request_id': request, 'manifest_hash': hashed, 'engine_version': manifest['engine_version'],
                **page, 'semantic_support': 'not_assessed', 'state': 'ocr_unavailable', 'server_receipt': 'b' * 64}
    encoded = json.dumps(artifact, sort_keys=True, separators=(',', ':'))
    put = {'lease_token': lease, 'page_key': version + ':1', 'serialized': encoded,
           'artifact_hash': hashlib.sha256(encoded.encode()).hexdigest()}
    rpc('put', put)
    rpc('put', put)
    rpc('yield', {'lease_token': lease})
    lease2 = rpc('claim')['lease_token']
    assert lease2 != lease
    rpc('put', put, succeeds=False)
    rpc('finish', {'lease_token': lease2})
    assert rpc('status')['state'] == 'succeeded'
    # HMAC here is deliberately synthetic; application consumer must reject it.
    assert rpc('page', {'page_key': version + ':1'})['serialized'] == encoded
    _run(f"update caseproof._m1_matter_grants set active=false where case_id='{case}' and user_id='{owner}'", env)
    rpc('status', succeeds=False)
    rpc('page', {'page_key': version + ':1'}, succeeds=False)
    _run(f"update caseproof._m1_matter_grants set active=true where case_id='{case}' and user_id='{owner}'", env)
    _run(f"update caseproof.organization_members set active=false where org_id='{org}' and user_id='{owner}'", env)
    rpc('status', succeeds=False)
    print('SIGNED_PAGE_SQL_ACTOR_SCOPE_LEASE_AUDIT_IMMUTABILITY_AND_REVOCATION_PASSED')


if __name__ == '__main__':
    main()
