"""Completeness checks for mode-specific data-flow and retention evidence.

These checks do not authenticate reviewers, inspect a deployment or grant approval.
"""
from __future__ import annotations

from typing import Any

DATA_CLASSES = frozenset({'originals', 'ocr_text', 'crops', 'translations', 'reviews', 'reports',
                         'hashes', 'reference_strings', 'verdicts', 'identifiers', 'timing', 'queues', 'logs', 'caches',
                         'temporary_files', 'backups'})
MODES = frozenset({'hosted', 'hybrid', 'firm_controlled', 'offline'})


def assess(record: dict[str, Any]) -> dict[str, Any]:
    issues = []
    if not isinstance(record.get('mode'), str) or record['mode'] not in MODES:
        issues.append('deployment mode missing or unsupported')
    for field in ('environment', 'build_sha', 'configuration_sha256', 'security_owner', 'privacy_owner'):
        if not isinstance(record.get(field), str) or not record[field].strip():
            issues.append(field + ' not assigned')
    flows = record.get('data_flows', [])
    if not isinstance(flows, list) or not flows:
        issues.append('field-level data-flow inventory missing')
        flows = []
    flowed: set[str] = set()
    for flow in flows:
        if not isinstance(flow, dict) or any(not flow.get(key) for key in
                ('data_classes', 'origin', 'destination', 'region', 'purpose', 'access_roles')):
            issues.append('incomplete data-flow entry')
        elif (not isinstance(flow['data_classes'], list)
              or any(not isinstance(item, str) for item in flow['data_classes'])
              or not set(flow['data_classes']) <= DATA_CLASSES):
            issues.append('unknown data class in flow')
        else:
            flowed.update(flow['data_classes'])
    if flowed != DATA_CLASSES:
        issues.append('data-flow inventory omits potentially sensitive fields')
    capture = record.get('network_capture', {})
    if not isinstance(capture, dict):
        capture = {}
        issues.append('network capture record missing')
    for key in ('artifact_sha256', 'test_date', 'scope', 'expected_destinations', 'observation_limits',
                'failure_retry_evidence', 'capture_access_roles', 'capture_retention_seconds'):
        if not capture.get(key):
            issues.append('network capture missing ' + key)
    if capture.get('scope') != 'whole_claimed_deployment':
        issues.append('worker-only capture does not assess the deployment perimeter')
    if capture.get('unexpected_destinations') != []:
        issues.append('unresolved or unmeasured egress')
    schedule = record.get('retention', [])
    if not isinstance(schedule, list):
        schedule = []
    seen: set[str] = set()
    for entry in schedule:
        if not isinstance(entry, dict):
            issues.append('invalid retention entry')
            continue
        category = entry.get('data_class')
        if not isinstance(category, str) or category not in DATA_CLASSES or category in seen:
            issues.append('unknown or duplicated retention data class')
            continue
        seen.add(category)
        if type(entry.get('kept')) is not bool:
            issues.append('retention kept status unspecified')
        duration = entry.get('duration_seconds')
        if (type(duration) is not int or duration < 0 or (entry.get('kept') and duration == 0)
                or (entry.get('kept') is False and duration != 0)):
            issues.append('retention duration missing or inconsistent')
        for key in ('location', 'access_roles', 'deletion_rule', 'deletion_evidence', 'legal_hold_rule'):
            if not entry.get(key):
                issues.append('retention missing ' + key)
        if category == 'backups':
            for key in ('expiry_rule', 'restore_test_evidence', 'restored_data_redeletion_rule'):
                if not entry.get(key):
                    issues.append('backup policy missing ' + key)
    if seen != DATA_CLASSES:
        issues.append('retention schedule does not cover all data classes')
    return {'schema': 'caseproof-deployment-assessment-completeness-v1', 'mode': record.get('mode'),
            'issues': issues, 'ready_for_independent_review': not issues,
            'client_data_authorized': False, 'sec_01_16_approved': False,
            'limitation': 'Declared completeness is not measured deployment safety or independent approval.'}
