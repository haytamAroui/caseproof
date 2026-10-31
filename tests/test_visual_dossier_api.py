"""Real parsing/API + disk restart; identity fixture is NOT live signed Auth proof."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_journey import DossierStore, create_dossier_router
from infrastructure.parsers.pdf_visual_fidelity import PDFVisualFidelity
from tests.fixtures.visual_fidelity import corpus
from tests.test_phase4_headless_api import docx


class DiskStore(DossierStore):
    def __init__(self, root):
        self.sources_calls=0
        self.root=root
        self.receipt_key=b"synthetic-test-receipt-only-not-a-live-secret"
        self.visual=PDFVisualFidelity()
        self.client=SimpleNamespace(read_geometry=self.missing_geometry)
        self.pdf=next(f.pdf for f in corpus() if f.name=='grey')
        path = root/'original-draft.docx'
        if not path.exists():
            path.write_bytes(docx('Stuk 1, PDF p. 1 "1000". Stuk 1, PDF p. 1 "1200".'))
        self.draft=path.read_bytes()
        self.manifest=[{'role':role,'version_id':version,'document_id':version,
                        'sha256':hashlib.sha256(raw).hexdigest(),'page_count':1 if role=='exhibit' else 0}
                       for role,version,raw in [('draft','draft',self.draft),('inventory','inv',b'Stuk 1'),
                                                ('exhibit','source',self.pdf)]]

    @staticmethod
    def missing_geometry(*args):
        raise AccessRejected(AccessFailure.RESOURCE_MASKED)

    def authorize(self, token, case):
        if token!='owner-test-token' or case!='case':
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)

    def sources(self, token, case):
        self.authorize(token,case)
        self.sources_calls+=1
        return copy.deepcopy(self.manifest),{'draft':self.draft,'inv':b'Stuk 1','source':self.pdf}

    def rpc(self, token, case, action, data=None):
        self.authorize(token,case)
        if action=='context':
            return {'bundle_signature':'a'*64,'confirmation':{'request_id':'confirmation',
                'payload':{'inventory_complete':True,'entries':[
                    {'label':'stuk','number':'1','source_version_id':'source','pages':[]}]}}}
        if action=='snapshot':
            (self.root/(data['snapshot_hash']+'.json')).write_text(data['serialized'])
            return {'snapshot_hash':data['snapshot_hash']}
        if action=='read':
            return {'serialized':(self.root/(data['snapshot_hash']+'.json')).read_text()}
        if action=='review':
            (self.root/'decision.json').write_text(json.dumps(data))
            return {'request_id':data['request_id']}
        if action=='decisions':
            path=self.root/'decision.json'
            return {'decisions':[json.loads(path.read_text())] if path.exists() else []}
        raise AssertionError(action)


def client(store):
    app=FastAPI()
    app.include_router(create_dossier_router(store))

    @app.exception_handler(AccessRejected)
    def denied(request,error):
        return JSONResponse({'detail':'unavailable'},status_code=404)
    return TestClient(app)


@pytest.mark.skipif(os.getenv('CASEPROOF_VISUAL_EXECUTABLE')!='YES',reason='required executable OCR job')
def test_actual_document_dossier_crop_review_restart_export_and_denials(tmp_path):
    store=DiskStore(tmp_path)
    c=client(store)
    headers={'Authorization':'Bearer owner-test-token'}
    base='/v2/matters/case/briefs/draft/dossier'
    response=c.get(base,headers=headers)
    assert response.status_code==200,response.text
    report=response.json()
    conflict,control=report['findings']
    assert conflict['fidelity']=='representation_conflict'
    assert control['visual_assessment']['state']=='not_assessed'
    assert all(r['extracted_text']=='1200' for r in control['visual_assessment']['regions'])
    sha=report['snapshot_hash']
    region=conflict['visual_assessment']['regions'][0]
    route=base+f'/snapshots/{sha}/regions/{region["region_id"]}/crop'
    previous_source_reads=store.sources_calls
    crop=c.get(route,headers=headers)
    assert store.sources_calls==previous_source_reads
    assert crop.status_code==200 and hashlib.sha256(crop.content).hexdigest()==region['crop_sha256']
    batch=c.post(base+f'/snapshots/{sha}/crops',headers=headers,json={'region_ids':[region['region_id']]})
    assert batch.status_code==200 and batch.json()['crops'][0]['crop_sha256']==region['crop_sha256']
    assert store.sources_calls==previous_source_reads
    assert c.get(route,headers={'Authorization':'Bearer ungranted'}).status_code==404
    assert c.get(route.replace('/case/','/other/'),headers=headers).status_code==404
    review={'snapshot_hash':sha,'reference_id':conflict['reference_id'],'request_id':str(uuid4()),
            'decision':'CONFIRMED_QUALIFIED','rationale':'I inspected the preserved strike and crop.'}
    assert c.post(base+'/reviews',headers=headers,json=review).status_code==409
    review['reviewed_region_ids']=[r['region_id'] for r in conflict['visual_assessment']['regions']]
    assert c.post(base+'/reviews',headers=headers,json=review).status_code==200
    reopened=client(DiskStore(tmp_path))
    assert reopened.get(base+'?snapshot_hash='+sha,headers=headers).json()==report
    for format in ('json','markdown','docx'):
        export=reopened.get(base+f'/export?format={format}&snapshot_hash={sha}',headers=headers)
        assert export.status_code==200
        if format!='docx':
            assert b'representation_conflict' in export.content and region['region_id'].encode() in export.content
    # A signed reader may write a custom JSON snapshot through the legacy RPC,
    # but cannot authenticate its provenance for these new read/export routes.
    forged = json.loads((tmp_path/(sha+'.json')).read_text())
    # Source identities remain valid; only the authenticated finding changes.
    forged['findings'][0]['fidelity'] = 'invented_match'
    from apps.api.dossier_journey import canonical
    payload = canonical(forged)
    fake_hash = hashlib.sha256(payload.encode()).hexdigest()
    (tmp_path/(fake_hash+'.json')).write_text(payload)
    assert reopened.get(base+'?snapshot_hash='+fake_hash,headers=headers).status_code==404
    # Bytes in the private snapshot are checked independently on download.
    frozen=json.loads((tmp_path/(sha+'.json')).read_text())
    frozen['visual_pages']['source:1']['regions'][0]['crop_base64']='AAAA'
    (tmp_path/(sha+'.json')).write_text(json.dumps(frozen))
    assert reopened.get(route,headers=headers).status_code==404
