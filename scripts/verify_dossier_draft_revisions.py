"""Real disposable PostgreSQL acceptance for the uninstalled draft-revision proposal."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from scripts.verify_retention_disposable import main as install
from scripts.verify_s2_002_database import ROOT, _env, _run


def main():
    install()
    env = _env()
    proposal = ROOT / 'db/proposals/M1_M2_dossier_draft_revisions.sql'
    migration = ROOT / 'supabase/migrations/20261031234906_dossier_draft_revisions.sql'
    if proposal.read_bytes() != migration.read_bytes():
        raise RuntimeError('Deployed draft revision SQL differs from proposal')
    _run((ROOT / 'db/proposals/M1_M2_draft_revision_scoped_cleanup.sql').read_text(), env)
    actor, other, org, case = [str(uuid4()) for _ in range(4)]
    docs, versions = [[str(uuid4()) for _ in range(4)] for _ in range(2)]
    _run(f"""
insert into auth.users(id,instance_id) values('{actor}','{org}'),('{other}','{org}');
insert into caseproof.organizations(id,display_name) values('{org}','Synthetic revision');
insert into caseproof.organization_members(org_id,user_id,actions) values
('{org}','{actor}',array['case:read','evidence:read','finding:write','review:request']),
('{org}','{other}',array['case:read','evidence:read','finding:write','review:request']);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
values('{case}','{org}','{actor}','caseproof-dev-txt-v1');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions)
values('{org}','{case}','{actor}','reviewer',array['case:read','evidence:read','evidence:upload','draft:check','review:request']);
""", env)
    sources = []
    for doc, version, role in zip(docs, versions, ('draft','inventory','exhibit','exhibit'), strict=True):
        _run(f"""insert into caseproof.documents(id,org_id,case_id,source_label) values('{doc}','{org}','{case}','{role}');
insert into caseproof.document_versions(id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type,bundle_role)
values('{version}','{org}','{doc}',1,repeat('a',64),30,'application/pdf','{role}');""", env)
        sources.append(dict(role=role, filename=role, document_id=doc, version_id=version,
                            sha256='a'*64, byte_length=30, media_type='application/pdf'))
    payload = json.dumps(dict(case_id=case,sources=sources))
    _run(f"insert into caseproof._dev_journey_operations(org_id,actor_id,operation,request_id,input_sha,response) "
         f"values('{org}','{actor}','bundle_register','{uuid4()}',repeat('a',64),'{payload}'::jsonb);", env)

    def call(function, params, *, user=actor, service=False, succeeds=True):
        role = 'service_role' if service else 'authenticated'
        encoded = ','.join("'" + str(value).replace("'", "''") + "'" for value in params)
        return _run(f"begin; set local role {role}; set local request.jwt.claim.sub='{user}';"
                    f"set local request.jwt.claims='{{\"role\":\"{role}\"}}';"
                    f"select public.{function}({encoded}); commit;", env, should_pass=succeeds)

    context = json.loads(call('caseproof_dossier', [case,'context','{}']))
    confirmation = str(uuid4())
    call('caseproof_dossier', [case,'confirm',json.dumps(dict(bundle_signature=context['bundle_signature'],
         request_id=confirmation,payload=dict(inventory_complete=True,entries=[])))])
    report = dict(case_id=case,brief_id=versions[0],bundle_signature=context['bundle_signature'],
                  confirmation_id=confirmation,findings=[dict(reference_id='ref-0000',technical_check='checked')])
    serial = json.dumps(report,sort_keys=True)
    snapshot = hashlib.sha256(serial.encode()).hexdigest()
    call('caseproof_dossier',[case,'snapshot',json.dumps(dict(snapshot_hash=snapshot,serialized=serial))])
    call('caseproof_dossier',[case,'review',json.dumps(dict(snapshot_hash=snapshot,reference_id='ref-0000',
         request_id=str(uuid4()),decision='CONFIRMED_SUPPORTED',rationale='Synthetic manual review'))])
    request = str(uuid4())
    command = dict(command_sha256='b'*64,snapshot_hash=snapshot,parent_version_id=versions[0],
                   parent_sha256='a'*64,reference_id='ref-0000',sha256='c'*64,byte_length=40)
    args = [case,request,'reserve',json.dumps(command)]
    call('caseproof_dossier_draft_reserve',args,user=other,succeeds=False)
    reserved = json.loads(call('caseproof_dossier_draft_reserve',args))
    assert reserved['state']=='reserved'
    assert json.loads(call('caseproof_dossier_draft_reserve',args))['version_id']==reserved['version_id']
    pending = json.loads(call('caseproof_dossier',[case,'context','{}']))
    assert pending['bundle_signature'] == context['bundle_signature']
    assert pending['confirmation']['request_id'] == confirmation
    assert json.loads(call('caseproof_dev_bundle_manifest',[case]))['sources'][0]['version_id']==versions[0]
    call('caseproof_dossier_draft_reserve',[case,request,'reserve',json.dumps(command | {'command_sha256':'d'*64})],succeeds=False)
    competing_request = str(uuid4())
    call('caseproof_dossier_draft_reserve',[case,competing_request,'reserve',json.dumps(command | {'command_sha256':'e'*64})])
    activation=[actor,case,request,'c'*64,40]
    call('caseproof_dossier_draft_activate',activation,succeeds=False)
    call('caseproof_dossier_draft_activate',[actor,case,request,'d'*64,40],service=True,succeeds=False)
    # Audit failure must roll activation and active-pointer visibility back.
    _run("create function caseproof.reject_revision_audit() returns trigger language plpgsql as $$ begin "
         "if new.action in ('dossier_draft_activated','dossier_draft_reserved') then raise exception 'forced audit failure'; end if; return new; end $$;"
         "create trigger reject_revision_audit before insert on caseproof.audit_events "
         "for each row execute function caseproof.reject_revision_audit();",env)
    failed_request = str(uuid4())
    before_count = _run(f"select count(*) from caseproof.document_versions where org_id='{org}';",env)
    call('caseproof_dossier_draft_reserve',[case,failed_request,'reserve',json.dumps(command)],succeeds=False)
    assert _run(f"select count(*) from caseproof.document_versions where org_id='{org}';",env) == before_count
    call('caseproof_dossier_draft_activate',activation,service=True,succeeds=False)
    assert json.loads(call('caseproof_dossier_draft_reserve',[case,request,'status',json.dumps(command)]))['state']=='reserved'
    _run('drop trigger reject_revision_audit on caseproof.audit_events;',env)
    with ThreadPoolExecutor(max_workers=2) as pool:
        activations = list(pool.map(lambda _: json.loads(call('caseproof_dossier_draft_activate',activation,service=True)), range(2)))
    assert sorted(result['replayed'] for result in activations) == [False, True]
    activated = activations[0]
    assert activated['state']=='active'
    assert json.loads(call('caseproof_dossier_draft_activate',activation,service=True))['replayed'] is True
    manifest=json.loads(call('caseproof_dev_bundle_manifest',[case]))
    assert manifest['sources'][0]['version_id']==reserved['version_id']
    assert manifest['sources'][0]['version_number']==2
    call('caseproof_dossier_draft_activate',[actor,case,competing_request,'c'*64,40],service=True,succeeds=False)
    changed=json.loads(call('caseproof_dossier',[case,'context','{}']))
    assert changed['bundle_signature']!=context['bundle_signature'] and changed['confirmation'] is None
    call('caseproof_dossier',[case,'decisions',json.dumps(dict(snapshot_hash=snapshot))],succeeds=False)
    revised = dict(report, brief_id=reserved['version_id'], bundle_signature=changed['bundle_signature'],
                   confirmation_id=None, findings=[dict(reference_id='ref-0000', technical_check='unresolved')])
    revised_serial = json.dumps(revised, sort_keys=True)
    revised_hash = hashlib.sha256(revised_serial.encode()).hexdigest()
    call('caseproof_dossier',[case,'snapshot',json.dumps(dict(snapshot_hash=revised_hash,serialized=revised_serial))])
    assert json.loads(call('caseproof_dossier',[case,'decisions',json.dumps(dict(snapshot_hash=revised_hash))]))['decisions'] == []
    assert json.loads(call('caseproof_dossier_snapshot_read',[case,revised_hash]))['serialized'] == revised_serial
    _run(f"update caseproof.organization_members set active=false where org_id='{org}' and user_id='{actor}';",env)
    call('caseproof_dossier_draft_activate',activation,service=True,succeeds=False)
    _run(f"update caseproof.organization_members set active=true where org_id='{org}' and user_id='{actor}';",env)
    _run(f"update caseproof._m1_matter_grants set active=false where case_id='{case}';",env)
    call('caseproof_dossier_draft_activate',activation,service=True,succeeds=False)
    call('caseproof_dossier_draft_reserve',[case,request,'status',json.dumps(command)],succeeds=False)
    run, foreign, foreign_org = [str(uuid4()) for _ in range(3)]
    _run(f"insert into auth.users(id,instance_id) values('{foreign}','{foreign_org}');"
         f"insert into caseproof.organizations(id,display_name) values('{foreign_org}','Synthetic foreign');"
         f"insert into caseproof._dev_journey_fixtures(run_id,owner_id,guest_id,foreign_id,org_id,foreign_org_id) "
         f"values('{run}','{actor}','{other}','{foreign}','{org}','{foreign_org}');",env)
    # The cleanup allowlist must still reject unexpected activity, transactionally.
    _run(f"begin; set local request.jwt.claims='{{\"role\":\"service_role\"}}';"
         f"insert into caseproof.audit_events(org_id,case_id,actor_type,actor_user_id,action,event_schema_version,correlation_id,input_sha256_hex) "
         f"values('{org}','{case}','human','{actor}','unexpected_activity','test','{uuid4()}',repeat('a',64));"
         f"select public.caseproof_dev_journey_cleanup('{run}','{actor}'); commit;",env,should_pass=False)
    call('caseproof_dev_journey_cleanup',[run,actor],service=True)
    assert _run(f"select count(*) from caseproof.dossier_draft_revisions where org_id='{org}';",env).strip() == '0'
    assert _run(f"select count(*) from caseproof.cases where id='{case}';",env).strip() == '0'
    print('DRAFT_REVISION_RESERVE_REPLAY_READBACK_FENCE_AUDIT_ROLLBACK_ACTIVATE_INVALIDATION_REVOKE_CLEANUP_PASSED')


if __name__ == '__main__':
    main()
