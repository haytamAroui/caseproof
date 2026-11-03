"""Historical metadata uses a distinct read capability and the same integrity checks."""
import hashlib
from unittest.mock import Mock

import pytest

from apps.api.access_control import AccessRejected
from apps.api.dossier_journey import DossierStore, canonical


def fixture():
    store = DossierStore.__new__(DossierStore)
    store.receipt_key = b'synthetic-test-receipt-key'
    report = {'case_id': 'case', 'brief_id': 'brief', 'findings': [], 'sources': []}
    report['server_receipt'] = store.receipt(report)
    serialized = canonical(report)
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    store.rpc = Mock(return_value={'serialized': serialized})
    return store, digest


def test_historical_read_has_distinct_capability_and_verifies_snapshot():
    store, digest = fixture()
    result = store.frozen_report('signed', 'case', 'brief', digest, historical=True)
    assert result['snapshot_hash'] == digest
    store.rpc.assert_called_once_with('signed', 'case', 'historical_read', {'snapshot_hash': digest})


def test_current_reads_keep_the_existing_freshness_capability():
    store, digest = fixture()
    store.frozen_report('signed', 'case', 'brief', digest)
    store.rpc.assert_called_once_with('signed', 'case', 'read', {'snapshot_hash': digest})


def test_historical_read_rejects_wrong_brief_and_tampering():
    store, digest = fixture()
    with pytest.raises(AccessRejected):
        store.frozen_report('signed', 'case', 'foreign', digest, historical=True)
    store.rpc.return_value = {'serialized': '{}'}
    with pytest.raises(AccessRejected):
        store.frozen_report('signed', 'case', 'brief', digest, historical=True)


def test_hash_consistent_malformed_frozen_json_fails_closed():
    store, _ = fixture()
    serialized = '{invalid json'
    store.rpc.return_value = {'serialized': serialized}
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    with pytest.raises(AccessRejected):
        store.frozen_report('signed', 'case', 'brief', digest, historical=True)
