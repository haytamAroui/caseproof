"""Exercise route bindings using a real synthetic DOCX and the actual router."""
import io
from hashlib import sha256

from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dossier_journey import create_dossier_router


def fixture():
    document = Document()
    document.add_paragraph('First Stuk 1')
    document.add_paragraph('Second Stuk 1')
    buffer = io.BytesIO()
    document.save(buffer)
    raw = buffer.getvalue()
    report = {'snapshot_hash': 'a' * 64, 'findings': [
        {'reference_id': 'ref-1', 'region': 'word/document.xml', 'literal': 'Stuk 1',
         'offsets': {'start': 20, 'end': 26}},
    ]}
    class Store:
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
    payload['paragraph_index'] = 0
    assert client.post(f'{base}/corrections/preview', headers=headers, json=payload).status_code == 422
    payload['paragraph_index'] = 1
    payload['before'] = 'Second'
    assert client.post(f'{base}/corrections/preview', headers=headers, json=payload).status_code == 422


def test_recheck_uses_requested_activated_draft():
    client, _ = fixture()
    response = client.post('/v2/matters/case/briefs/activated/dossier/recheck',
                           headers={'Authorization': 'Bearer signed'}, json={})
    assert response.status_code == 200
    assert response.json()['brief_id'] == 'activated'


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
    assert client.get(path + 'different/correction-operations', headers=headers).status_code == 404
    assert len(store.revisions.calls) == 1
    store.revisions.revoked = True
    assert client.get(path + 'ref-1/correction-operations', headers=headers).status_code == 404
