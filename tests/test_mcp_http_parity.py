"""HTTP versus MCP over real DOCX parsing, signed report bytes and disk reopening.

Authorization here is a test identity gate; protected live acceptance is separate.
"""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace

import pytest

from application.litigation.content_release import ContentRelease
from apps.api.mcp_adapter_contract import call_tool
from tests.test_visual_dossier_api import DiskStore, client

TOKEN = 'owner-test-token'
DESTINATION = 'synthetic-local-client'


def grant(snapshot):
    return ContentRelease('case', 'draft', snapshot, DESTINATION,
                          sha256(TOKEN.encode()).hexdigest(), datetime.now(UTC) + timedelta(seconds=60))


@pytest.mark.parametrize('complete', [True, False])
def test_actual_http_and_mcp_frozen_discovery_json_markdown_parity(tmp_path, complete):
    store = DiskStore(tmp_path)
    # Explicit unavailability keeps this ordinary contract test independent of OCR binaries.
    from infrastructure.parsers.pdf_ocr import OCRUnavailable

    def unavailable(*args, **kwargs):
        raise OCRUnavailable('synthetic_unavailable')
    store.visual = SimpleNamespace(inspect=unavailable)
    original_rpc = store.rpc

    def rpc(token, case, action, data=None):
        result = original_rpc(token, case, action, data)
        if action == 'context':
            result['confirmation']['payload']['inventory_complete'] = complete
        return result
    store.rpc = rpc
    c = client(store)
    base = '/v2/matters/case/briefs/draft/dossier'
    headers = {'Authorization': 'Bearer ' + TOKEN}
    generated = c.post(base + '/checks', headers=headers,
                       json={'draft_language': 'nl', 'source_languages': {'source': 'fr'}})
    assert generated.status_code == 200, generated.text
    report = generated.json()
    snapshot = report['snapshot_hash']
    # A fresh process-shaped adapter must read the signed stored bytes, never recompute.
    reopened = DiskStore(tmp_path)
    reopened.load = lambda *a, **k: pytest.fail('MCP must not reassess a frozen report')
    args = {'case_id': 'case', 'brief_id': 'draft', 'snapshot_hash': snapshot}
    result = call_tool(store=reopened, bearer=TOKEN, name='caseproof_discover_references',
                       arguments=args, release=grant(snapshot), destination=DESTINATION)
    assert result['structuredContent'] == c.get(base, params={'snapshot_hash': snapshot}, headers=headers).json()
    for fmt in ('json', 'markdown'):
        response = c.get(base + '/export', params={'format': fmt, 'snapshot_hash': snapshot}, headers=headers)
        mcp = call_tool(store=reopened, bearer=TOKEN, name='caseproof_export_report',
                        arguments={**args, 'format': fmt}, release=grant(snapshot), destination=DESTINATION)
        assert response.status_code == 200, response.text
        assert response.content == mcp['content'].encode()
        assert response.headers['X-CaseProof-Export-SHA256'] == mcp['exportSha256'] == sha256(response.content).hexdigest()
        assert response.headers['content-type'].startswith(mcp['mediaType'])
    assert report['verification_contract'] == result['structuredContent']['verification_contract']
    assert report['findings'][0]['translation_review_required']
    assert all(f['support'] == 'not_assessed' for f in report['findings'])
    if not complete:
        assert all(f['identity'] == 'not_assessed' for f in report['findings'])


@pytest.mark.parametrize('mutation', ['case', 'brief', 'snapshot', 'destination', 'caller', 'expired', 'too_long'])
def test_release_cannot_be_replayed_outside_binding(mutation):
    snapshot = 'a' * 64
    release = grant(snapshot)
    changes = {'case': {'case_id': 'foreign'}, 'brief': {'brief_id': 'foreign'},
               'snapshot': {'snapshot_hash': 'b' * 64}, 'destination': {'destination': 'foreign'},
               'caller': {'caller_digest': sha256(b'foreign-token').hexdigest()},
               'expired': {'expires_at': datetime.now(UTC) - timedelta(seconds=1)},
               'too_long': {'expires_at': datetime.now(UTC) + timedelta(hours=1)}}
    class NoAccess:
        def reopen(self, *args):
            pytest.fail('invalid release must not access sources')
    result = call_tool(store=NoAccess(), bearer=TOKEN, name='caseproof_discover_references',
                       arguments={'case_id': 'case', 'brief_id': 'draft', 'snapshot_hash': snapshot},
                       release=replace(release, **changes[mutation]), destination=DESTINATION)
    assert result == {'isError': True, 'error': 'content_release_not_authorized'}


def test_boolean_alone_never_authorizes_release():
    result = call_tool(store=None, bearer=TOKEN, name='caseproof_discover_references',
                       arguments={'case_id': 'case', 'brief_id': 'draft', 'snapshot_hash': 'a' * 64},
                       allow_document_content=True)
    assert result == {'isError': True, 'error': 'content_release_not_authorized'}


def test_expiry_during_source_read_blocks_release(monkeypatch):
    from unittest.mock import Mock

    from apps.api import mcp_adapter_contract as adapter
    now = datetime.now(UTC)
    release = replace(grant('a' * 64), expires_at=now + timedelta(seconds=1))
    times = iter([now, now + timedelta(seconds=2)])
    monkeypatch.setattr(adapter, 'utc_now', lambda: next(times))
    store = Mock()
    store.reopen.return_value = ({'schema': 'caseproof-dossier-v1', 'snapshot_hash': 'a' * 64}, b'')
    result = call_tool(store=store, bearer=TOKEN, name='caseproof_discover_references',
                       arguments={'case_id': 'case', 'brief_id': 'draft', 'snapshot_hash': 'a' * 64},
                       release=release, destination=DESTINATION)
    assert result == {'isError': True, 'error': 'content_release_not_authorized'}
