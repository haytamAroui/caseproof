"""Receipt and worker boundaries; no live Auth/SQL assertion from these fixtures."""
import copy
import hashlib
from types import SimpleNamespace

import pytest

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_journey import canonical
from apps.api.signed_page_jobs import SignedPageJobs

PAGE = {'document_id': 'doc', 'version_id': 'version', 'original_sha256': 'a' * 64, 'pdf_page': 1, 'needs_ocr': True}
MANIFEST = {'engine_version': 'engine', 'pages': [PAGE]}
STATUS = {'org_id': 'org', 'actor_id': 'owner', 'manifest_hash': 'c' * 64, 'manifest': canonical(MANIFEST)}


class Store(SignedPageJobs):
    def __init__(self):
        super().__init__(SimpleNamespace(), 'synthetic-private-worker-receipt-key')
        self.artifact = {'schema': 'caseproof-page-artifact-v1', 'org_id': 'org', 'actor_id': 'owner',
                         'case_id': 'case', 'request_id': 'job', 'manifest_hash': 'c' * 64,
                         'engine_version': 'engine', **PAGE, 'state': 'ocr_candidate', 'semantic_support': 'not_assessed'}
        self.artifact['server_receipt'] = self.seal(self.artifact)
        self.calls = []

    def call(self, bearer, case, request, action, data=None):
        self.calls.append((bearer, case, request, action))
        if bearer != 'signed-fixture':
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if action == 'status':
            return copy.deepcopy(STATUS)
        serialized = canonical(self.artifact)
        return {'serialized': serialized, 'artifact_hash': hashlib.sha256(serialized.encode()).hexdigest()}


def test_valid_worker_receipt_is_verified_with_current_authorization():
    store = Store()
    result = store.read_page('signed-fixture', 'case', 'job', 'version:1')
    assert result['state'] == 'ocr_candidate' and result['semantic_support'] == 'not_assessed'
    assert [c[3] for c in store.calls] == ['status', 'page']


@pytest.mark.parametrize('field,value', [('case_id', 'foreign'), ('request_id', 'foreign'),
    ('org_id', 'foreign'), ('actor_id', 'foreign'), ('manifest_hash', 'e' * 64),
    ('version_id', 'foreign'), ('original_sha256', 'e' * 64), ('pdf_page', 2),
    ('engine_version', 'other'), ('semantic_support', 'CONFIRMED_SUPPORTED')])
def test_even_authentic_artifact_cannot_be_replayed_into_other_binding(field, value):
    store = Store()
    store.artifact.pop('server_receipt')
    store.artifact[field] = value
    store.artifact['server_receipt'] = store.seal(store.artifact)
    with pytest.raises(AccessRejected):
        store.read_page('signed-fixture', 'case', 'job', 'version:1')


def test_signed_client_cannot_forge_worker_receipt():
    store = Store()
    store.artifact['server_receipt'] = 'f' * 64
    with pytest.raises(AccessRejected):
        store.read_page('signed-fixture', 'case', 'job', 'version:1')


def test_service_key_is_not_accepted_as_worker_receipt_secret():
    with pytest.raises(ValueError):
        SignedPageJobs(SimpleNamespace(), 'sb_secret_' + 'a' * 64)


@pytest.mark.parametrize('mutation', [
    lambda artifact: artifact.update(state='verified'),
    lambda artifact: artifact.update(needs_ocr=False),
])
def test_receipt_rejects_invalid_processing_state_even_when_sealed(mutation):
    store = Store()
    store.artifact.pop('server_receipt')
    mutation(store.artifact)
    store.artifact['server_receipt'] = store.seal(store.artifact)
    with pytest.raises(AccessRejected):
        store.read_page('signed-fixture', 'case', 'job', 'version:1')


def test_receipt_rejects_non_object_json_payload():
    store = Store()
    def malformed_call(bearer, case, request, action, data=None):
        if action == 'status':
            return copy.deepcopy(STATUS)
        serialized = '[]'
        return {'serialized': serialized, 'artifact_hash': hashlib.sha256(serialized.encode()).hexdigest()}
    store.call = malformed_call
    with pytest.raises(AccessRejected):
        store.read_page('signed-fixture', 'case', 'job', 'version:1')
