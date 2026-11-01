"""Report projection refuses foreign bindings and invalid keyset navigation."""
import json
from unittest.mock import patch

import pytest

from apps.api.access_control import AccessRejected
from apps.api.workspace_reports import WorkspaceReports
from tests.test_clearbrief_signed_matter_catalog import CASE, Connection


def projection(rows=None, cursor=None, case=CASE):
    return {'schema': 'caseproof-workspace-reports-v1', 'case_id': case,
            'reports': [] if rows is None else rows, 'next_cursor': cursor}


ROW = {'brief_id': CASE, 'snapshot_hash': 'a'*64, 'created_at': '2026-11-01T12:00:00Z'}


def call(payload, after=None):
    conn = Connection(json.dumps(payload).encode())
    with patch('apps.api.workspace_reports.http.client.HTTPSConnection', return_value=conn):
        result = WorkspaceReports('sb_publishable_test').read('signed', CASE, after)
    assert conn.request_args[0][1] == '/rest/v1/rpc/caseproof_workspace_reports'
    assert conn.request_args[0][0] == 'POST'
    assert conn.request_args[0][2] is not None
    return result


def test_valid_and_empty_catalogue_never_requests_a_check():
    assert call(projection()).reports == []
    assert call(projection([ROW])).reports[0].snapshot_hash == 'a'*64


@pytest.mark.parametrize('payload,after', [
    (projection([ROW, ROW]), None), (projection([ROW], cursor='a'*64), None),
    (projection([ROW]), 'b'*64), (projection([ROW], case='foreign'), None),
    (projection([{**ROW, 'private_text': 'must-not-project'}]), None),
])
def test_invalid_report_catalogue_fails_closed(payload, after):
    with pytest.raises(AccessRejected):
        call(payload, after)
