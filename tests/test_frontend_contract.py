"""Projection compatibility with actual canonical deterministic findings."""
import pytest
from pydantic import ValidationError

from application.litigation.frontend_contract import DossierView
from domains.disputes.exhibit_identity import IdentityState
from tests.test_dossier_journey import assess
from tests.test_phase4_headless_api import docx


def test_actual_canonical_unsupported_and_missing_findings_remain_unassessed():
    report = assess(docx('Exhibit A; Stuk 1, PDF p. 1.'), [], None)
    view = DossierView.model_validate({**report, 'schema': 'caseproof-dossier-v1',
        'case_id': 'case', 'brief_id': 'brief', 'snapshot_hash': 'a' * 64})
    assert len(view.findings) == 2
    assert all(f.support == 'not_assessed' for f in view.findings)
    assert all(f.page_mapping == 'unmapped' for f in view.findings)


def test_identity_projection_tracks_domain_enum_and_rejects_unknown_success():
    schema = DossierView.model_json_schema()
    states = schema['$defs']['FindingView']['properties']['identity']['enum']
    assert set(states) == {state.value.lower() for state in IdentityState}
    with pytest.raises(ValidationError):
        DossierView.model_validate({'schema': 'caseproof-dossier-v1', 'case_id': 'case',
            'brief_id': 'brief', 'snapshot_hash': 'a' * 64, 'coverage': {},
            'findings': [{'reference_id': 'r', 'literal': 'Stuk 1', 'identity': 'verified',
                'page_mapping': 'mapped', 'fidelity': 'not_assessed', 'support': 'not_assessed'}]})
