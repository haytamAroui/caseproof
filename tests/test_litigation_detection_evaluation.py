"""Measured denominators and missing coverage must survive evaluation reporting."""
from scripts.evaluate_litigation_detection import EXPECTED, evaluate


def test_actual_docx_evaluation_reports_all_reference_occurrences_and_limits():
    report = evaluate()
    assert len(report['cases']) == 18
    assert sum(row['tp'] + row['fn'] for row in report['cases']) == sum(map(len, EXPECTED.values()))
    assert sum(row['fp'] for row in report['cases']) == 0
    assert not report['independent_gold']
    assert not report['representative_client_accuracy_accepted']
    assert all(not row['coverage_complete_claimed'] for row in report['cases'])
    for row in report['cases']:
        assert len(row['missing']) == row['fn']
    assert report['cohorts']['en']['tp'] + report['cohorts']['en']['fn'] == 6
    assert report['cohorts']['en']['flagged_unsupported'] == 6


def test_measurement_preserves_actual_input_bytes_and_provenance(tmp_path):
    from hashlib import sha256
    report = evaluate(tmp_path)
    assert len(report['corpus_sha256']) == 64
    assert report['dossier_algorithm'] == 'caseproof-dossier-v4'
    for row in report['cases']:
        original = tmp_path / (row['case_id'] + '.docx')
        assert sha256(original.read_bytes()).hexdigest() == row['docx_sha256']
        assert len(row['brief_utf8_sha256']) == 64
