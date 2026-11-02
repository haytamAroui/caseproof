"""Synthetic intake boundary/recovery tests; no claim of live Auth or Storage."""
import base64
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.access_control import AccessRejected
from apps.api.signed_supabase_originals import (
    PrivateStorageDenied,
    PrivateStorageExists,
    PrivateStorageOutcomeUnknown,
)
from apps.api.workspace_intake import (
    IntakeCommand,
    WorkspaceIntake,
    create_workspace_intake_router,
    preflight,
)
from tests.fixtures.dossier_journey import dossier_bundle

CASE = str(uuid4())


def command():
    return IntakeCommand(request_id=str(uuid4()), files=[dict(role=s.role, filename=s.filename,
        media_type=s.media_type, byte_length=len(s.content), sha256=sha256(s.content).hexdigest(),
        content_base64=base64.b64encode(s.content).decode()) for s in dossier_bundle()])


def test_real_formats_preflight_and_corrupt_last_has_no_registration_or_writes():
    good = command()
    assert len(preflight(good)) == 4
    last = good.files[-1]
    last.content_base64 = base64.b64encode(b'%PDF-1.7 invalid').decode()
    last.byte_length = len(b'%PDF-1.7 invalid')
    last.sha256 = sha256(b'%PDF-1.7 invalid').hexdigest()
    client = Mock()
    service = WorkspaceIntake(client, Mock())
    service.register = Mock()
    with pytest.raises(HTTPException) as failure:
        service.upload('synthetic', CASE, good)
    assert failure.value.status_code == 422
    service.register.assert_not_called()
    client.library.put_once.assert_not_called()


def test_duplicates_wrong_roles_size_and_hash_are_rejected():
    good = command()
    values = good.model_dump()
    values['files'][-1]['filename'] = values['files'][0]['filename']
    with pytest.raises(ValidationError):
        IntakeCommand(**values)
    good.files[-1].sha256 = '0' * 64
    with pytest.raises(HTTPException):
        preflight(good)
    good = command()
    good.files[-1].filename = '../escape.pdf'
    with pytest.raises(HTTPException):
        preflight(good)


@pytest.mark.parametrize('write_failure', [PrivateStorageOutcomeUnknown, PrivateStorageDenied, PrivateStorageExists])
def test_unknown_upload_only_recovers_after_exact_fresh_readback_and_stable_registration(write_failure):
    c = command()
    raw = preflight(c)
    rows = [dict(f.model_dump(exclude={'content_base64'}), document_id=str(uuid4()), version_id=str(uuid4())) for f in c.files]
    client = Mock()
    client.library.source.side_effect = [(SimpleNamespace(org_id='same', sha256_hex=r['sha256'], content_type=r['media_type']), r['byte_length']) for r in rows] * 2
    client.library.put_once.side_effect = write_failure('synthetic write outcome')
    client.library.read.side_effect = [item for value in raw for item in (PrivateStorageDenied("missing or masked"), value)] + raw
    service = WorkspaceIntake(client, Mock())
    service.register = Mock(return_value={'case_id': CASE, 'sources': rows})
    receipt = SimpleNamespace(readback_complete=True)
    service.context = Mock(return_value=receipt)
    assert service.upload('synthetic', CASE, c) is receipt
    first = service.register.call_args.args[2]
    # Cold caller request IDs do not duplicate the same immutable source set.
    c.request_id = str(uuid4())
    assert service.upload('synthetic', CASE, c) is receipt
    assert service.register.call_args.args[2] == first
    assert client.library.read.call_count == 12
    client.library.source.side_effect = [(SimpleNamespace(org_id='same', sha256_hex=r['sha256'], content_type=r['media_type']), r['byte_length']) for r in rows]
    client.library.read.side_effect = [b'tampered']
    service.context.reset_mock()
    with pytest.raises(AccessRejected):
        service.upload('synthetic', CASE, c)
    service.context.assert_not_called()


def test_cross_organization_registered_refs_never_write():
    c = command()
    rows = [dict(f.model_dump(exclude={'content_base64'}), document_id=str(uuid4()), version_id=str(uuid4())) for f in c.files]
    client = Mock()
    client.library.source.side_effect = [(SimpleNamespace(org_id=str(i), sha256_hex=r['sha256'], content_type=r['media_type']), r['byte_length']) for i, r in enumerate(rows)]
    service = WorkspaceIntake(client, Mock())
    service.register = Mock(return_value={'case_id': CASE, 'sources': rows})
    with pytest.raises(AccessRejected):
        service.upload('synthetic', CASE, c)
    client.library.put_once.assert_not_called()


def test_router_unconfigured_and_invalid_body_fail_closed():
    from apps.api.litigation_development_app import create_litigation_development_app
    client = TestClient(create_litigation_development_app(), client=('127.0.0.1', 40000), base_url='http://127.0.0.1')
    assert client.get('/v2/workspace/intake/organizations').status_code == 503
    assert client.post(f'/v2/workspace/intake/matters/{CASE}/sources', json={}).status_code == 422
    fake = Mock()
    app = FastAPI()
    app.include_router(create_workspace_intake_router(fake))
    client = TestClient(app)
    assert client.post('/v2/workspace/intake/matters', headers={'Authorization': 'Bearer synthetic'}, json={'org_id': CASE, 'name': 'Sample', 'request_id': CASE, 'actor_id': CASE}).status_code == 422
    fake.client.call.assert_not_called()


def test_revoked_preflight_does_not_parse_register_or_write():
    from apps.api.access_control import AccessFailure
    client = Mock()
    client.call.side_effect = AccessRejected(AccessFailure.RESOURCE_MASKED)
    service = WorkspaceIntake(client, Mock())
    service.register = Mock()
    with pytest.raises(AccessRejected):
        service.upload('revoked', CASE, command())
    service.register.assert_not_called()
    client.library.put_once.assert_not_called()


def test_oversized_intake_body_is_rejected_before_route_validation():
    from apps.api.litigation_development_app import create_litigation_development_app
    client = TestClient(create_litigation_development_app(), client=('127.0.0.1', 40000), base_url='http://127.0.0.1')
    response = client.post('/v2/workspace/intake/matters', content=b' ' * 17_000_001,
                           headers={'Content-Type': 'application/json'})
    assert response.status_code == 413


def test_complete_http_intake_projects_real_parser_manifest_and_confirmation_candidates(monkeypatch):
    import json
    from uuid import UUID

    import apps.api.workspace_intake as module
    from apps.api.dossier_journey import DossierStore
    from apps.api.signed_supabase_originals import OriginalRef
    c = command()
    source_rows = [dict(f.model_dump(exclude={'content_base64'}), document_id=str(uuid4()), version_id=str(uuid4())) for f in c.files]
    client = Mock()
    client.bundle_manifest.return_value = {'case_id': CASE, 'sources': source_rows}
    client.library.source.side_effect = lambda **kw: next((OriginalRef(UUID('11111111-1111-4111-8111-111111111111'), UUID(CASE), UUID(r['document_id']), UUID(r['version_id']), r['sha256'], r['media_type']), r['byte_length']) for r in source_rows if r['version_id'] == kw['version_id'])
    content = {}
    client.library.put_once.side_effect = lambda **kw: content.__setitem__(kw['version_id'], kw['data'])
    def read(**kw):
        if kw['version_id'] not in content:
            raise PrivateStorageDenied('missing or masked')
        return content[kw['version_id']]
    client.library.read.side_effect = read
    store = DossierStore.__new__(DossierStore)
    store.client = client
    store.rpc = Mock(return_value={'bundle_signature': 'a' * 64, 'confirmation': None})
    service = WorkspaceIntake(client, store)
    service.register = Mock(return_value={'case_id': CASE, 'sources': source_rows})
    connection = Mock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.return_value = json.dumps([{'version_id': source_rows[0]['version_id']}]).encode()
    monkeypatch.setattr(module.http.client, 'HTTPSConnection', Mock(return_value=connection))
    app = FastAPI()
    app.include_router(create_workspace_intake_router(service))
    response = TestClient(app).post(f'/v2/workspace/intake/matters/{CASE}/sources',
        headers={'Authorization': 'Bearer synthetic'}, json=c.model_dump())
    assert response.status_code == 200
    result = response.json()
    assert result['schema'] == 'caseproof-workspace-intake-v1'
    assert result['readback_complete'] is True
    assert result['brief_id'] == source_rows[0]['version_id']
    assert len(result['entries']) == 4
    assert result['sources'][3]['processing'] == 'partial'
    assert result['sources'][2]['page_count'] == 1
    assert result['inventory_complete'] is False


@pytest.mark.parametrize('count', [512, 513])
def test_distinct_inventory_candidate_budget_checked_before_registration(count):
    c = command()
    inventory = next(f for f in c.files if f.role == 'inventory')
    content = '\n'.join(f'Stuk {i}' for i in range(1, count + 1)).encode()
    inventory.content_base64 = base64.b64encode(content).decode()
    inventory.byte_length = len(content)
    inventory.sha256 = sha256(content).hexdigest()
    client = Mock()
    service = WorkspaceIntake(client, Mock())
    service.register = Mock()
    if count == 512:
        assert len(preflight(c)) == 4
    else:
        for action in (service.reserve, service.upload):
            with pytest.raises(HTTPException) as rejected:
                action('synthetic', CASE, c)
            assert rejected.value.status_code == 422
            assert '512 distinct' in rejected.value.detail
        service.register.assert_not_called()
        client.library.put_once.assert_not_called()
