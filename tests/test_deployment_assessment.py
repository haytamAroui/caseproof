from copy import deepcopy

from application.security.deployment_assessment import DATA_CLASSES, MODES, assess


def complete(mode):
    record = {'mode': mode, 'environment': 'synthetic fixture', 'build_sha': 'a'*40,
              'configuration_sha256': 'b'*64, 'security_owner': 'Mock owner', 'privacy_owner': 'Mock reviewer',
              'data_flows': [{'data_classes': list(DATA_CLASSES), 'origin': 'synthetic browser',
                              'destination': 'synthetic runtime', 'region': 'fixture', 'purpose': 'test',
                              'access_roles': ['fixture-operator']}],
              'network_capture': {'artifact_sha256': 'c'*64, 'test_date': '2026-11-01',
                  'scope': 'whole_claimed_deployment', 'expected_destinations': ['fixture-runtime'],
                  'observation_limits': 'Mock declared evidence only', 'failure_retry_evidence': 'mock-proof',
                  'capture_access_roles': ['fixture-operator'], 'capture_retention_seconds': 3600,
                  'unexpected_destinations': []}, 'retention': []}
    for category in DATA_CLASSES:
        record['retention'].append({'data_class': category, 'kept': True, 'duration_seconds': 3600,
            'location': 'mock-private-runtime', 'access_roles': ['fixture-operator'],
            'deletion_rule': 'mock scoped deletion', 'deletion_evidence': 'mock-proof', 'legal_hold_rule': 'mock no hold',
            'expiry_rule': 'mock backup expiry', 'restore_test_evidence': 'mock-proof',
            'restored_data_redeletion_rule': 'mock re-deletion'})
    return record


def test_each_mode_needs_its_own_complete_record_and_never_grants_approval():
    for mode in MODES:
        result = assess(complete(mode))
        assert result['ready_for_independent_review']
        assert not result['client_data_authorized'] and not result['sec_01_16_approved']
        assert not assess({'mode': mode})['ready_for_independent_review']


def test_worker_capture_unknown_retention_and_missing_backup_proof_cannot_close_mode():
    base = complete('hybrid')
    for defect in ('worker', 'zero', 'backup', 'metadata', 'unexpected'):
        record = deepcopy(base)
        if defect == 'worker':
            record['network_capture']['scope'] = 'ocr_network_namespace'
        elif defect == 'zero':
            record['retention'][0]['duration_seconds'] = 0
        elif defect == 'backup':
            next(row for row in record['retention'] if row['data_class'] == 'backups').pop('restore_test_evidence')
        elif defect == 'metadata':
            record['retention'] = [row for row in record['retention'] if row['data_class'] != 'hashes']
        else:
            record['network_capture']['unexpected_destinations'] = ['unreviewed-provider']
        assert not assess(record)['ready_for_independent_review']
