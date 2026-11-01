from copy import deepcopy

from scripts.validate_m0_independent_reviews import validate


def packet():
    return {'corpus_sha256': 'a'*64, 'cases': [{'id': 'blind-1', 'language': 'nl'}]}


def submission(name):
    return {'schema': 'caseproof-m0-review-submission-v1', 'corpus_sha256': 'a'*64,
            'submission_status': 'COMPLETED',
            'reviewer': {'real_name': name, 'organization': 'Mock reviewer fixture',
                         'independence_and_conflicts_attested': True, 'languages_competent': ['nl'],
                         'belgian_legal_qualification': 'Mock qualification, not a real credential',
                         'credential_and_signed_attestation_evidence': 'mock-proof', 'review_date': '2026-11-01'},
            'cases': [{'id': 'blind-1', 'identity': 'not_assessed', 'page': 'unmapped',
                       'fidelity': 'not_assessed', 'semantic_support': 'NOT_ASSESSED',
                       'source_observations': 'Mock unavailable source', 'independent_rationale': 'Mock rationale',
                       'confidence_and_limitations': 'Synthetic test fixture only'}]}


def test_empty_packet_does_not_become_approved():
    result = validate(packet(), [])
    assert result['issues'] and not result['ready_for_owner_review'] and not result['m0_approved']


def test_two_complete_records_only_make_packet_ready_for_external_verification():
    result = validate(packet(), [submission('Mock A'), submission('Mock B')])
    assert result['ready_for_owner_review']
    assert not result['m0_approved'] and not result['credentials_independently_verified']


def test_duplicate_reviewer_hash_conflict_language_and_disagreement_fail_closed():
    a, b = submission('Mock A'), submission('Mock B')
    assert not validate(packet(), [a, a])['ready_for_owner_review']
    alias = deepcopy(a)
    alias['reviewer']['organization'] = 'Another affiliation'
    assert not validate(packet(), [a, alias])['ready_for_owner_review']
    for change in ('hash', 'language', 'disagreement', 'blank', 'independence'):
        altered = deepcopy(b)
        if change == 'hash':
            altered['corpus_sha256'] = 'b'*64
        elif change == 'language':
            altered['reviewer']['languages_competent'] = ['fr']
        elif change == 'disagreement':
            altered['cases'][0]['identity'] = 'resolved'
        elif change == 'independence':
            altered['reviewer']['independence_and_conflicts_attested'] = False
        else:
            altered['cases'][0]['independent_rationale'] = ''
        assert not validate(packet(), [a, altered])['ready_for_owner_review']


def test_disagreement_retains_original_judgments_and_needs_distinct_qualified_adjudicator():
    a, b, third = submission('Mock A'), submission('Mock B'), submission('Mock C')
    b['cases'][0]['identity'] = 'resolved'
    assert not validate(packet(), [a, b])['ready_for_owner_review']
    resolved = validate(packet(), [a, b], [third])
    assert resolved['ready_for_owner_review']
    assert resolved['disagreements'] == ['blind-1'] and resolved['adjudicated_cases'] == ['blind-1']
    assert resolved['complete_assessments']['blind-1'] == 2 and not resolved['m0_approved']
    assert not validate(packet(), [a, b], [a])['ready_for_owner_review']
    third['reviewer']['belgian_legal_qualification'] = ''
    assert not validate(packet(), [a, b], [third])['ready_for_owner_review']
