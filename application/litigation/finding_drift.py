"""Conservative explanation of reference drift between two *authorized frozen* reports.

A positional correspondence candidate is not a verified semantic match and never
carries a signed human decision into a new draft.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


def _anchor(finding: dict[str, Any]) -> tuple[str, int] | None:
    region = finding.get('region')
    offsets = finding.get('offsets')
    if (not isinstance(region, str) or not region
            or not isinstance(offsets, dict)
            or type(offsets.get('start')) is not int or offsets['start'] < 0):
        return None
    return region, offsets['start']


def explain_finding_drift(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on version/scope confusion, unstable anchors and repeated citations."""
    if (previous.get('schema') != 'caseproof-dossier-v1'
            or current.get('schema') != 'caseproof-dossier-v1'
            or previous.get('case_id') != current.get('case_id')
            or not all(isinstance(report.get('snapshot_hash'), str)
                       and len(report['snapshot_hash']) == 64
                       and isinstance(report.get('brief_id'), str)
                       for report in (previous, current))):
        raise ValueError('incompatible frozen reports')
    old_rows, new_rows = previous.get('findings'), current.get('findings')
    if (not isinstance(old_rows, list) or not isinstance(new_rows, list)
            or len(old_rows) > 10000 or len(new_rows) > 10000
            or any(not isinstance(row, dict) or not isinstance(row.get('reference_id'), str)
                   for row in old_rows + new_rows)):
        raise ValueError('invalid finding correspondence input')
    old_keys = Counter(_anchor(row) for row in old_rows)
    new_keys = Counter(_anchor(row) for row in new_rows)
    candidates = {_anchor(row): row for row in new_rows if _anchor(row) is not None}
    seen: set[str] = set()
    rows = []
    for old in old_rows:
        key = _anchor(old)
        newer = (candidates.get(key) if key is not None
                 and old_keys[key] == 1 and new_keys[key] == 1 else None)
        reasons: list[str] = []
        if newer is None:
            state = 'uncertain' if key is None or (key is not None and (
                old_keys[key] > 1 or new_keys[key] > 1)) else 'removed'
            reasons.append('locator_missing_or_ambiguous' if state == 'uncertain'
                           else 'not_at_previous_location_possible_move_or_removal')
        else:
            seen.add(newer['reference_id'])
            if (old.get('identity_reason') == 'UNSUPPORTED_REFERENCE_DIALECT'
                    or newer.get('identity_reason') == 'UNSUPPORTED_REFERENCE_DIALECT'):
                state = 'uncertain'
                reasons.append('unsupported_reference_dialect')
            elif old.get('literal') != newer.get('literal'):
                # Same region/offset alone cannot prove identity after an edit.
                state = 'uncertain'
                reasons.append('literal_changed_possible_renumbering_or_replacement')
            else:
                for field, reason in (
                    ('version_id', 'source_version_changed'),
                    ('source_sha256', 'source_content_changed'),
                    ('identity', 'inventory_identity_changed'),
                    ('page_mapping', 'page_mapping_changed'),
                    ('pdf_page', 'physical_page_changed'),
                    ('printed_page', 'printed_page_changed'),
                    ('bundle_page', 'bundle_page_changed'),
                    ('fidelity', 'fidelity_changed'),
                    ('support', 'human_support_state_changed'),
                ):
                    if old.get(field) != newer.get(field):
                        reasons.append(reason)
                state = 'changed' if reasons else 'unchanged'
                if old.get('identity') != 'resolved' or newer.get('identity') != 'resolved':
                    reasons.append('identity_not_confirmed')
                if old.get('page_mapping') != 'mapped' or newer.get('page_mapping') != 'mapped':
                    reasons.append('page_not_confirmed')
        rows.append({
            'previous_reference_id': old['reference_id'],
            'current_reference_id': newer['reference_id'] if newer else None,
            'status': state,
            'reasons': reasons,
            'review_transfer': 'never',
        })
    for newer in new_rows:
        if newer['reference_id'] not in seen:
            rows.append({
                'previous_reference_id': None,
                'current_reference_id': newer['reference_id'],
                'status': 'added' if _anchor(newer) is not None
                          and new_keys[_anchor(newer)] == 1 else 'uncertain',
                'reasons': ['unpaired_current_reference_review_required'],
                'review_transfer': 'never',
            })
    return {
        'schema': 'caseproof-finding-drift-v1',
        'case_id': previous['case_id'],
        'previous_brief_id': previous['brief_id'],
        'previous_snapshot_hash': previous['snapshot_hash'],
        'current_brief_id': current['brief_id'],
        'current_snapshot_hash': current['snapshot_hash'],
        'correspondence_basis': 'unique_region_and_start_offset_candidate_not_identity_proof',
        'review_transfer': 'never',
        'rows': rows,
    }
