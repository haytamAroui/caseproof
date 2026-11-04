"""Conservative reference correspondence never transfers human review."""
from __future__ import annotations

import pytest

from application.litigation.finding_drift import explain_finding_drift


def finding(ref: str, literal: str, start: int, **changes: object) -> dict:
    return {
        'reference_id': ref, 'literal': literal, 'region': 'body.p1',
        'offsets': {'start': start, 'end': start + len(literal)},
        'identity': 'resolved', 'page_mapping': 'mapped', 'pdf_page': 1,
        'version_id': 'exhibit-1', 'source_sha256': '1' * 64,
        'fidelity': 'exact_match', 'support': 'not_assessed',
        **changes,
    }


def report(brief: str, digest: str, findings: list[dict]) -> dict:
    return {'schema': 'caseproof-dossier-v1', 'case_id': 'case-1',
            'brief_id': brief, 'snapshot_hash': digest, 'findings': findings}


def compare(old: list[dict], new: list[dict]) -> dict:
    return explain_finding_drift(report('old', 'a' * 64, old),
                                 report('new', 'b' * 64, new))


def test_same_literal_exact_anchor_reports_source_and_page_drift():
    outcome = compare([finding('ref-1', 'Stuk 1', 4)],
                      [finding('ref-9', 'Stuk 1', 4, version_id='exhibit-2',
                               pdf_page=3)])
    row = outcome['rows'][0]
    assert row['status'] == 'changed'
    assert 'source_version_changed' in row['reasons']
    assert 'physical_page_changed' in row['reasons']
    assert row['review_transfer'] == outcome['review_transfer'] == 'never'


def test_renumbered_reference_is_uncertain_not_automatically_approved():
    outcome = compare([finding('ref-1', 'Pièce 1', 0)],
                      [finding('ref-1', 'Pièce 2', 0)])
    assert outcome['rows'][0]['status'] == 'uncertain'
    assert 'literal_changed_possible_renumbering_or_replacement' in outcome['rows'][0]['reasons']


def test_missing_and_duplicate_anchors_do_not_guess_correspondence():
    old = [finding('ref-1', 'Stuk 1', 0)]
    new = [finding('ref-2', 'Stuk 1', 4), finding('ref-3', 'Stuk 2', 4)]
    outcome = compare(old, new)
    assert outcome['rows'][0]['status'] == 'removed'
    assert all(row['review_transfer'] == 'never' for row in outcome['rows'])
    assert any(row['status'] == 'uncertain' for row in outcome['rows'][1:])


def test_mismatched_matter_refuses_comparison():
    a = report('old', 'a' * 64, [])
    b = report('new', 'b' * 64, [])
    b['case_id'] = 'different-matter'
    with pytest.raises(ValueError, match='incompatible'):
        explain_finding_drift(a, b)
