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
