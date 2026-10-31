"""Real signed dev fixture → visual conflict → frozen crop/review/restart/export."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.dossier_live_acceptance import json_request, request
from scripts.m05_registry import record
from scripts.phase3_live_acceptance import direct
from scripts.verify_dev_ephemeral_auth import PROJECT_REF
from scripts.verify_dev_live_review_roundtrip import _server_start, _server_stop
from scripts.verify_dev_live_txt_journey import admin_rpc, success
from tests.fixtures.factory import SyntheticSource
from tests.fixtures.visual_fidelity import corpus
from tests.test_phase4_headless_api import docx


def verify_live_panel(token: str, case: str, brief: str, region_id: str) -> None:
    """Real signed browser → API → private crop → persisted human review."""
    import shutil

    from playwright.sync_api import expect, sync_playwright

    output=Path('/tmp/caseproof-visual-gate')
    output.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=shutil.which('google-chrome') or shutil.which('chromium'),
                                  args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000})
        # Authorized signed dev identity in memory only; never screenshot, log,
        # persist or put the bearer in a URL. The UI's session bridge owns it.
        page.add_init_script('window.caseproofSession={getBearer:async()=>'+json.dumps(token)+'};')
        page.goto('http://127.0.0.1:8765/dev/clearbrief')
        page.locator('#case-id').fill(case)
        page.locator('#brief-id').fill(brief)
        page.get_by_role('button',name='Inspect dossier').click()
        expect(page.locator('#fidelity-panel .fidelity-finding')).to_have_count(3,timeout=120000)
        finding=page.locator('#fidelity-panel .fidelity-finding').first
        expect(finding.get_by_text('Preserved crop hashes checked.',exact=False)).to_be_visible(timeout=120000)
        expect(finding.locator('img')).to_have_count(1)
        assert finding.locator('img').evaluate('(image)=>image.complete && image.naturalWidth>0')
        expect(finding.get_by_text('⚠ Representation conflict',exact=False)).to_be_visible()
        finding.get_by_role('textbox',name='Rationale').fill('Signed browser inspection of the preserved synthetic crop.')
        finding.get_by_role('checkbox').check()
        finding.get_by_role('button',name='Save human review').click()
        expect(finding.get_by_text('Human review saved.',exact=False)).to_be_visible(timeout=30000)
        # Full UI contains development UUID inputs; hide only those identifiers
        # in the screenshot, not the result or its source image.
        page.screenshot(path=str(output/'signed-browser.png'),full_page=True,
                        mask=[page.locator('#case-id'),page.locator('#brief-id')])
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        browser.close()
    print('VISUAL_REAL_SIGNED_BROWSER_CROP_INSPECTION_AND_REVIEW_PASSED',flush=True)


def main() -> None:
    key=os.environ['CASEPROOF_DEV_PUBLISHABLE_KEY']
    signin=SupabasePasswordSignin(PROJECT_REF,key)
    credentials={r:PasswordCredentials(email=os.environ[f'CASEPROOF_P3_{r.upper()}_EMAIL'],
                   password=os.environ[f'CASEPROOF_P3_{r.upper()}_PASSWORD']) for r in ('owner','ungranted','foreign')}
    sessions={r:signin.sign_in(c) for r,c in credentials.items()}
    token=sessions['owner'].access_token
    fixtures={f.name:f for f in corpus()}
    bundle=(SyntheticSource('draft.docx','draft','application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                 docx('Stuk 1, PDF p. 1 "1000". Stuk 1, PDF p. 1 "1200". Pièce 2, PDF p. 1 "1000".')),
            SyntheticSource('inventory.txt','inventory','text/plain',b'Stuk 1 redline; Piece 2 scan'),
            SyntheticSource('redline.pdf','exhibit','application/pdf',fixtures['grey'].pdf),
            SyntheticSource('scan.pdf','exhibit','application/pdf',fixtures['scan_strike'].pdf))
    proc=None
    try:
        proc=_server_start()
        case=success(token,'POST','/dev/live/matters',{'org_id':os.environ['CASEPROOF_P3_ORG_ID'],
            'name':'Synthetic representation gate','request_id':str(uuid4())})['case_id']
        admin=os.environ['CASEPROOF_DEV_AUTH_ADMIN_KEY']
        run=os.environ['CASEPROOF_P3_RUN_ID']
        record(admin,run,'matter',case,'CREATED')
        status,raw=direct(token,key,'/rest/v1/rpc/caseproof_dev_register_bundle','POST',
            {'p_case':case,'p_request':str(uuid4()),'p_sources':[s.metadata() for s in bundle]})
        if status!=200:
            raise RuntimeError('VISUAL_BUNDLE_REGISTRATION_FAILED')
        registered=json.loads(raw)['sources']
        for source,row in zip(bundle,registered,strict=True):
            path='/'.join((os.environ['CASEPROOF_P3_ORG_ID'],case,row['document_id'],row['version_id'],source.sha256))
            record(admin,run,'storage_file',path)
            success(token,'POST',f'/dev/live/matters/{case}/sources/{row["document_id"]}/{row["version_id"]}/upload',
                {'content_base64':base64.b64encode(source.content).decode()})
        brief=registered[0]['version_id']
        base=f'/v2/matters/{case}/briefs/{brief}/dossier'
        before=json_request(token,'GET',base)
        confirmation={'bundle_signature':before['bundle_signature'],'request_id':str(uuid4()),
            'inventory_complete':True,'entries':[
                {'label':label,'number':number,'source_version_id':row['version_id'],'pages':[]}
                for label,number,row in [('stuk','1',registered[2]),('piece','2',registered[3])]]}
        json_request(token,'POST',base+'/confirmation',confirmation)
        report=json_request(token,'GET',base)
        conflict,clean,scan=report['findings']
        if conflict['fidelity']!='representation_conflict' or clean['visual_assessment']['state']!='not_assessed':
            raise RuntimeError('VISUAL_REGIONAL_CONFLICT_OR_CLEAN_CONTROL_FAILED')
        if scan['visual_assessment']['state']!='ocr_unreliable':
            raise RuntimeError('VISUAL_SCAN_WITHOUT_INDEPENDENT_LAYER_DID_NOT_ABSTAIN')
        snapshot=report['snapshot_hash']
        selected=conflict['visual_assessment']['regions']
        crop_route=base+f'/snapshots/{snapshot}/regions/{selected[0]["region_id"]}/crop'
        status,png=request(token,'GET',crop_route)
        if status!=200 or hashlib.sha256(png).hexdigest()!=selected[0]['crop_sha256']:
            raise RuntimeError('VISUAL_SIGNED_FROZEN_CROP_HASH_FAILED')
        review={'snapshot_hash':snapshot,'reference_id':conflict['reference_id'],'request_id':str(uuid4()),
            'decision':'CONFIRMED_QUALIFIED','rationale':'Synthetic fixture inspection; conflicting struck amount retained.',
            'reviewed_region_ids':[r['region_id'] for r in selected]}
        json_request(token,'POST',base+'/reviews',review)
        verify_live_panel(token, case, brief, selected[0]['region_id'])
        exported=json_request(token,'GET',base+'/export?snapshot_hash='+snapshot)
        if exported['human_decisions'][0].get('reviewed_region_ids') != sorted(review['reviewed_region_ids']):
            raise RuntimeError('VISUAL_ATTESTATION_NOT_PERSISTED')
        # Existing RPC accepts signed user snapshots, so prove receipt checking
        # rejects a client-authored report even with a valid bundle and hash.
        from apps.api.dossier_journey import canonical
        forged=json.loads(json.dumps(report))
        forged.pop('snapshot_hash',None)
        # Keep the authentic source set: this specifically tests receipt
        # authentication, not only rejection of omitted source metadata.
        forged['findings'][0]['fidelity']='invented_match'
        serialized=canonical(forged)
        fake_hash=hashlib.sha256(serialized.encode()).hexdigest()
        status,_=direct(token,key,'/rest/v1/rpc/caseproof_dossier','POST',
            {'p_case':case,'p_action':'snapshot','p_data':{'snapshot_hash':fake_hash,'serialized':serialized}})
        if status!=200:
            raise RuntimeError('VISUAL_FORGERY_FIXTURE_NOT_WRITTEN')
        for suffix in ('?snapshot_hash='+fake_hash,'/export?snapshot_hash='+fake_hash):
            if request(token,'GET',base+suffix)[0]!=503:
                raise RuntimeError('VISUAL_CLIENT_FORGED_REPORT_TRUSTED')
        _server_stop(proc)
        proc=_server_start()
        token=signin.sign_in(credentials['owner']).access_token
        if json_request(token,'GET',base+'/export?snapshot_hash='+snapshot)!=exported:
            raise RuntimeError('VISUAL_RESTART_CHANGED_FROZEN_REPORT')
        for format in ('markdown','docx'):
            status,data=request(token,'GET',base+f'/export?format={format}&snapshot_hash={snapshot}')
            if status!=200:
                raise RuntimeError('VISUAL_EXPORT_FAILED')
            if format=='docx':
                with ZipFile(io.BytesIO(data)) as z:
                    if b'representation_conflict' not in z.read('word/document.xml'):
                        raise RuntimeError('VISUAL_DOCX_LOST_CONFLICT')
        for role in ('ungranted','foreign'):
            for suffix in (f'?snapshot_hash={snapshot}',f'/export?snapshot_hash={snapshot}',crop_route.removeprefix(base)):
                if request(sessions[role].access_token,'GET',base+suffix)[0] not in (403,404):
                    raise RuntimeError('VISUAL_UNGRANTED_READ_ALLOWED')
        # A new inventory mapping invalidates every old crop/review/snapshot.
        confirmation['request_id']=str(uuid4())
        json_request(token,'POST',base+'/confirmation',confirmation)
        if request(token,'GET',crop_route)[0]!=409:
            raise RuntimeError('VISUAL_STALE_CROP_ALLOWED')
        admin_rpc(admin,'revoke',{'p_run':run,'p_owner':str(sessions['owner'].user_id),'p_case':case})
        if request(token,'GET',crop_route)[0] not in (403,404):
            raise RuntimeError('VISUAL_REVOKED_CROP_ALLOWED')
        target=Path('/tmp/caseproof-visual-gate')
        target.mkdir(exist_ok=True)
        (target/'signed-receipt.json').write_text(json.dumps({'commit':os.getenv('GITHUB_SHA'),
            'original_hashes':[s.sha256 for s in bundle], 'regional_conflict':True,'clean_same_page':True,
            'scan_abstention':True,'crop_hash':selected[0]['crop_sha256'],'review_restart_export':True,
            'forged_snapshot_denied':True,'ungranted_foreign_revoked_denied':True,'changed_confirmation_stale':True,
            'cleanup':'required_by_registry_wrapper'},indent=2))
        print('VISUAL_SIGNED_CROP_REVIEW_RESTART_EXPORT_AND_DENIALS_PASSED',flush=True)
    finally:
        _server_stop(proc)
