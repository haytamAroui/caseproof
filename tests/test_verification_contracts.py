"""Contracts through real parsers, HTTP, frozen disk snapshots and reopened exports."""
from __future__ import annotations

import io
from zipfile import ZipFile

import pytest

from application.litigation.dossier_contracts import assess_fidelity, quotation_context
from domains.disputes.dossier_verification import build_findings
from domains.disputes.exhibit_identity import InventoryStatus
from infrastructure.parsers.docx_reference_discovery import discover_docx_references
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions
from tests.test_docx_text_regions_coverage import NS, _docx
from tests.test_phase4_headless_api import docx
from tests.test_visual_dossier_api import DiskStore, client


def test_structured_hidden_and_nested_story_coverage_accounts_without_duplicate_references():
    payload = _docx(body=f'''<w:document xmlns:w="{NS}"><w:body>
      <w:p><w:r><w:t>Stuk 1.</w:t></w:r><w:txbxContent><w:p><w:r><w:t>Stuk 99.</w:t></w:r></w:p></w:txbxContent></w:p>
      <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Pièce 2.</w:t></w:r></w:p>
      <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Stuk 3.</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:tc></w:tr></w:tbl>
      <w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>Stuk 98.</w:t></w:r></w:p>
      </w:body></w:document>''', extra={
        'word/footnotes.xml': f'<w:footnotes xmlns:w="{NS}"><w:p><w:r><w:t>Stuk 4.</w:t></w:r></w:p></w:footnotes>',
        'word/header1.xml': f'<w:hdr xmlns:w="{NS}"><w:p><w:r><w:t>Stuk 5.</w:t></w:r></w:p></w:hdr>'})
    result = discover_docx_references(payload)
    assert [r.number for r in result.references] == ['1', '2', '3', '4', '5']
    manifest = result.region_manifest
    assert manifest['regions_discovered'] == 5
    assert manifest['regions_scanned'] == 3
    assert manifest['regions_unsupported'] == 2
    assert not manifest['text_coverage_complete'] and not result.coverage_complete
    assert any(r['reason'] == 'EXCLUDED_HIDDEN_TEXT' for r in manifest['regions'])


@pytest.mark.parametrize('status', list(InventoryStatus))
def test_inventory_status_is_enforced_by_dossier_not_just_isolated_policy(status):
    raw = docx('Stuk 1, PDF p. 1. Stuk 9, PDF p. 1.')
    discovery = discover_docx_references(raw)
    regions = {r.part: r.text for r in extract_docx_text_regions(raw).regions}
    sources = [{'role': 'exhibit', 'version_id': 'v', 'document_id': 'd', 'sha256': 'a'*64, 'page_count': 1}]
    confirmation = {'payload': {'inventory_complete': True, 'entries': [
        {'label': 'stuk', 'number': '1', 'source_version_id': 'v', 'pages': []}]}}
    findings = build_findings(discovery, regions, sources, confirmation, inventory_status=status)['findings']
    if status == InventoryStatus.CONFIRMED_COMPLETE:
        assert [f['identity'] for f in findings] == ['resolved', 'not_in_inventory']
    else:
        assert all(f['identity'] == 'not_assessed' and f['identity_reason'] == status.value for f in findings)
        assert all(f['technical_check'] == 'unresolved' for f in findings)


@pytest.mark.parametrize('quote', ['Le paiement est dû.', 'Le paiement ne sera pas dû.', 'Sous réserve de confirmation.'])
@pytest.mark.parametrize('visual', ['not_assessed', 'ocr_unreliable', 'representation_conflict'])
def test_translation_never_becomes_exact_or_semantically_confirmed(quote, visual):
    f = quotation_context(f', PDF p. 1 "{quote}"', draft_language='fr', source_language='nl')
    f.update(visual_assessment={'state': visual, 'reason': 'uncalibrated_agreement'}, support='not_assessed')
    assess_fidelity(f, {'layer_text': quote})
    assert f['translation_review_required']
    assert f['literal_assessment']['state'] == 'translation_review_required'
    assert f['fidelity'] == ('translation_review_required' if visual == 'not_assessed' else visual)
    assert f['support'] == 'not_assessed'


def test_explicit_translation_marker_cannot_be_cleared_by_matching_language_declaration():
    context = quotation_context(', PDF p. 2 traduction: «payé»', draft_language='fr', source_language='fr')
    assert context['translation_review_required'] and context['quoted_text'] == 'payé'


def test_same_language_bilingual_literal_is_not_inferred_to_be_translation():
    context = quotation_context(', PDF p. 2 "betaling / paiement"', draft_language='nl', source_language='nl')
    assert not context['translation_review_required']


def test_contracts_survive_http_freeze_restart_and_all_existing_export_formats(tmp_path):
    class Visual:
        def inspect(self, *args, **kwargs):
            return {'layer_text': '1000 1200', 'engine': 'synthetic-test-adapter',
                    'regions': [], 'vector_geometry_supported': True}

    store = DiskStore(tmp_path)
    store.visual = Visual()
    c = client(store)
    headers = {'Authorization': 'Bearer owner-test-token'}
    base = '/v2/matters/case/briefs/draft/dossier'
    opts = {'draft_language': 'fr', 'source_languages': {'source': 'nl'}}
    denied = c.post(base+'/checks', headers={'Authorization': 'Bearer ungranted'}, json=opts)
    assert denied.status_code == 404
    assert c.post(base+'/checks', headers=headers, json={**opts, 'source_languages': {'foreign': 'nl'}}).status_code == 422
    assert c.post(base+'/checks', headers=headers, json={**opts, 'tenant': 'forged'}).status_code == 422
    response = c.post(base+'/checks', headers=headers, json=opts)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report['coverage']['source_pages_ocr_processed'] == 1
    assert report['coverage']['docx_regions']['regions_scanned'] == 1
    assert all(f['translation_review_required'] for f in report['findings'])
    assert report['abstentions'] and not report['coverage']['fully_checked']
    sha = report['snapshot_hash']
    reopened = client(DiskStore(tmp_path))
    assert reopened.get(base+'?snapshot_hash='+sha, headers=headers).json() == report
    for fmt in ('json', 'markdown', 'docx'):
        out = reopened.get(base+f'/export?format={fmt}&snapshot_hash={sha}', headers=headers)
        assert out.status_code == 200
        data = out.content
        if fmt == 'docx':
            with ZipFile(io.BytesIO(data)) as archive:
                data = archive.read('word/document.xml')
        for field in (b'translation_review_required', b'INVENTORY', b'docx_regions'):
            if field != b'INVENTORY':
                assert field in data
        assert b'caseproof-verification-contracts-v1' in data
    assert reopened.get(base+'/export?snapshot_hash='+sha, headers={'Authorization': 'Bearer ungranted'}).status_code == 404


def test_translated_scan_with_failed_worker_keeps_both_uncertainties():
    f = quotation_context(', PDF p. 1 "Le paiement est dû."', draft_language='fr', source_language='nl')
    f.update(fidelity='ocr_unreliable', visual_assessment={'state': 'not_assessed', 'reason': 'ocr_unavailable'})
    assess_fidelity(f, {'error': 'ocr_unavailable'})
    assert f['fidelity'] == f['visual_assessment']['state'] == 'ocr_unreliable'
    assert f['translation_review_required']
    assert f['literal_assessment']['state'] == 'translation_review_required'


def test_actual_prose_translation_preserves_original_context_in_http_and_export(tmp_path):
    (tmp_path/'original-draft.docx').write_bytes(docx('Stuk 1, PDF p. 1 "Le paiement ne sera pas dû."'))
    class Visual:
        def inspect(self, *args, **kwargs):
            return {'layer_text': 'De betaling is verschuldigd.', 'regions': [], 'vector_geometry_supported': True}
    store = DiskStore(tmp_path)
    store.visual = Visual()
    c = client(store)
    headers = {'Authorization': 'Bearer owner-test-token'}
    base = '/v2/matters/case/briefs/draft/dossier'
    out = c.post(base+'/checks', headers=headers, json={'draft_language':'fr','source_languages':{'source':'nl'}})
    assert out.status_code == 200
    f = out.json()['findings'][0]
    assert f['quoted_text'] == 'Le paiement ne sera pas dû.'
    assert f['source_text_context'] == 'De betaling is verschuldigd.'
    assert f['literal_assessment']['state'] == 'translation_review_required'
    assert f['support'] == 'not_assessed' and not f['visual_assessment']['regions']
    assert f['source_page'] == {'version_id':'source','pdf_page':1}
    assert c.get(base+'/sources/source/pages/1', headers=headers).status_code == 200
