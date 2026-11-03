"""Exercise route bindings using a real synthetic DOCX and the actual router."""
import io
import os
from hashlib import sha256
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dossier_journey import create_dossier_router


def fixture(large=False):
    document = Document()
    document.add_paragraph('First Stuk 1')
    document.add_paragraph('Second Stuk 1')
    buffer = io.BytesIO()
    document.save(buffer)
    raw = buffer.getvalue()
    if large:
        package = io.BytesIO(raw)
        with ZipFile(package, 'a', ZIP_DEFLATED) as archive:
            archive.writestr('word/media/unused1.png', os.urandom(1_100_000))
            archive.writestr('word/media/unused2.png', os.urandom(1_100_000))
        raw = package.getvalue()
    report = {'snapshot_hash': 'a' * 64, 'findings': [
        {'reference_id': 'ref-1', 'region': 'word/document.xml', 'literal': 'Stuk 1',
         'offsets': {'start': 20, 'end': 26}},
    ]}
    class Store:
        def current_draft_version(self, bearer, case):
            assert bearer == 'signed'
            return 'activated'

        def load(self, bearer, case, brief):
            assert bearer == 'signed'
            return {**report, 'brief_id': brief}, raw

        def reopen(self, bearer, case, brief, snapshot):
            assert bearer == 'signed' and snapshot == report['snapshot_hash']
            return report, raw

    app = FastAPI()
    app.include_router(create_dossier_router(Store()))
    return TestClient(app), raw


def test_anchor_and_preview_bind_reference_to_specific_paragraph():
    client, raw = fixture()
    base = '/v2/matters/case/briefs/parent/dossier'
    headers = {'Authorization': 'Bearer signed'}
    anchor = client.get(f'{base}/snapshots/{"a" * 64}/references/ref-1/correction-anchor', headers=headers)
    assert anchor.status_code == 200
    assert anchor.json()['paragraph_index'] == 1
    payload = {'snapshot_hash': 'a' * 64, 'original_sha256': sha256(raw).hexdigest(),
               'reference_id': 'ref-1', 'paragraph_index': 1, 'before': 'Stuk 1', 'after': 'Stuk 2'}
    preview = client.post(f'{base}/corrections/preview', headers=headers, json=payload)
    assert preview.status_code == 200
    assert preview.json()['committed'] is False
    assert preview.json()['derivative_byte_length'] > 0
    assert len(preview.content) < 16384
    assert 'content_base64' not in preview.json()
    payload['paragraph_index'] = 0
    assert client.post(f'{base}/corrections/preview', headers=headers, json=payload).status_code == 422
    payload['paragraph_index'] = 1
    payload['before'] = 'Second'
    assert client.post(f'{base}/corrections/preview', headers=headers, json=payload).status_code == 422



def test_large_docx_preview_stays_bounded_without_base64():
    client, raw = fixture(large=True)
    assert len(raw) > 2_000_000
    base = '/v2/matters/case/briefs/parent/dossier'
    payload = {'snapshot_hash': 'a' * 64, 'original_sha256': sha256(raw).hexdigest(),
               'reference_id': 'ref-1', 'paragraph_index': 1, 'before': 'Stuk 1', 'after': 'Stuk 2'}
    response = client.post(base + '/corrections/preview',
                           headers={'Authorization': 'Bearer signed'}, json=payload)
    assert response.status_code == 200
    assert len(response.content) < 16384
    receipt = response.json()
    assert 'content_base64' not in receipt
    assert receipt['derivative_byte_length'] > 2_000_000
    assert len(receipt['derivative_sha256']) == 64


def test_recheck_uses_requested_activated_draft():
    client, _ = fixture()
    response = client.post('/v2/matters/case/briefs/activated/dossier/recheck',
                           headers={'Authorization': 'Bearer signed'}, json={})
    assert response.status_code == 200
    assert response.json()['brief_id'] == 'activated'
    stale = client.post('/v2/matters/case/briefs/parent/dossier/recheck',
                        headers={'Authorization': 'Bearer signed'}, json={})
    assert stale.status_code == 409


def test_recovery_route_scopes_metadata_and_denies_revoked_or_wrong_reference():
    from fastapi.responses import JSONResponse

    from apps.api.access_control import AccessFailure, AccessRejected

    class Revisions:
        revoked = False
        calls = []

        def recovery(self, bearer, case, brief, snapshot, reference):
            self.calls.append((bearer, case, brief, snapshot, reference))
            if self.revoked:
                raise AccessRejected(AccessFailure.RESOURCE_MASKED)
            return {'operations': [{'request_id': 'request', 'state': 'reserved',
                                    'version_id': None, 'created_at': '2026-11-03'}]}

    class Store:
        revisions = Revisions()

        def current_draft_version(self, bearer, case):
            return 'active-version'

        def frozen_report(self, bearer, case, brief, snapshot, *, historical):
            assert historical and bearer == 'signed'
            return {'findings': [{'reference_id': 'ref-1'}]}

    store = Store()
    app = FastAPI()
    app.include_router(create_dossier_router(store))

    @app.exception_handler(AccessRejected)
    def deny(request, error):
        return JSONResponse({'error': error.code.value}, status_code=error.http_status)

    client = TestClient(app)
    path = f'/v2/matters/case/briefs/parent/dossier/snapshots/{"a" * 64}/references/'
    headers = {'Authorization': 'Bearer signed'}
    response = client.get(path + 'ref-1/correction-operations', headers=headers)
    assert response.status_code == 200
    assert store.revisions.calls == [('signed', 'case', 'parent', 'a' * 64, 'ref-1')]
    assert response.json()['current_draft_version_id'] == 'active-version'
    assert client.get(path + 'different/correction-operations', headers=headers).status_code == 404
    assert len(store.revisions.calls) == 1
    store.revisions.revoked = True
    assert client.get(path + 'ref-1/correction-operations', headers=headers).status_code == 404


def test_correction_review_receipt_requires_same_actor_reference_and_snapshot():
    from types import SimpleNamespace

    from fastapi import HTTPException

    from apps.api.dossier_journey import DossierStore

    service = object.__new__(DossierStore)
    service.revisions = SimpleNamespace(verifier=SimpleNamespace(
        verify_bearer=lambda bearer: SimpleNamespace(subject_id='actor-one')))
    service.frozen_report = lambda bearer, case, brief, snapshot: {
        'findings': [{'reference_id': 'ref-1'}],
    }
    rows = [
        dict(reference_id='ref-1', reviewer_id='actor-two',
             request_id='other', timestamp='2026-11-03T01:00:00+00:00'),
    ]
    service.rpc = lambda bearer, case, action, data: {'decisions': rows}
    with __import__('pytest').raises(HTTPException) as denied:
        service.correction_review_receipt('signed', 'case', 'parent', 'a'*64, 'ref-1')
    assert denied.value.status_code == 409
    rows.append(dict(reference_id='ref-1', reviewer_id='actor-one',
                     request_id='own', timestamp='2026-11-03T01:00:00+00:00'))
    proof = service.correction_review_receipt('signed', 'case', 'parent', 'a'*64, 'ref-1')
    assert proof['review_request_id'] == 'own'
    assert proof['snapshot_hash'] == 'a'*64
    with __import__('pytest').raises(Exception):
        service.correction_review_receipt('signed', 'case', 'parent', 'a'*64, 'other-ref')
