"""Real Chromium interaction test of the panel; transport fixture is not Auth proof."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright


def main() -> None:
    out=Path('/tmp/caseproof-visual-gate')
    out.mkdir(exist_ok=True)
    image=Image.new('RGB',(200,80),'white')
    stream=io.BytesIO()
    image.save(stream,format='PNG')
    png=stream.getvalue()
    sha=hashlib.sha256(png).hexdigest()
    region={'region_id':'b'*64,'crop_sha256':sha,'original_sha256':'c'*64,'page_number':1,
            'bbox':[0,0,200,80],'reason':'painted_line_candidate','extracted_text':'<img src=x>1000',
            'visual_text':'1000'}
    report={'schema':'caseproof-dossier-v1','snapshot_hash':'a'*64,
        'coverage':{'references_detected':1,'references_checked':1,'source_pages_total':2,
                    'source_pages_ocr_processed':1,'source_pages_failed_or_skipped':1,
                    'docx_regions':{'regions_discovered':2,'regions_scanned':1,'regions_unsupported':1,
                                    'coverage_unknown':False,'regions':[{'part':'word/document.xml#structured',
                                    'kind':'STRUCTURED_CONTENT','status':'UNSUPPORTED_REGION','reason':'UNSUPPORTED_STRUCTURED_CONTENT'}]}},'findings':[
        {'reference_id':'ref-0000','literal':'Stuk 1','identity':'resolved','page_mapping':'mapped',
         'fidelity':'representation_conflict','support':'not_assessed','translation_review_required':True,
         'quoted_text':'<img src=x>1000','draft_language':'fr','source_language':'nl',
         'literal_assessment':{'state':'translation_review_required','reason':'translated_prose_requires_human_review'},
         'visual_assessment':{'state':'representation_conflict','reason':'regional_representation_conflict',
                              'regions':[region]}}]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=shutil.which('google-chrome') or shutil.which('chromium'),
                                  args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1250,'height':900})
        page.route('https://caseproof.test/**',lambda route:route.fulfill(body='<main id="panel"></main>',content_type='text/html'))
        page.goto('https://caseproof.test/')
        page.add_script_tag(content=Path('apps/web/clearbrief/fidelity-panel.js').read_text())
        page.add_style_tag(content=Path('apps/web/clearbrief/workspace.css').read_text())
        page.evaluate('''({report,png,sha})=>{
          window.calls=[]; window.failSave=true;window.testReport=report;
          window.panel=window.CaseProofFidelity.mount({root:document.getElementById('panel'),context:()=>({caseId:'case',briefId:'brief'}),
            api:async(url,options)=>{window.calls.push({url,options});
              if(url.includes('/sources/')&&url.includes('/pages/'))return new Response('%PDF-1.4 synthetic transport only',{headers:{'X-CaseProof-Original-SHA256':'c'.repeat(64),'X-CaseProof-PDF-Page':'1','Content-Type':'application/pdf'}});
              if(url.endsWith('/crops')){if(window.delayCrop)await new Promise(resolve=>window.releaseCrop=resolve);return {snapshot_hash:report.snapshot_hash,crops:[{
                region_id:'b'.repeat(64),crop_sha256:sha,original_sha256:'c'.repeat(64),crop_base64:png}]};}
              if(url.endsWith('/reviews')){if(window.rejectSave){window.rejectSave=false;const e=Error('stale');e.code=409;throw e;}if(window.failSave){window.failSave=false;throw Error('network');}return {saved:true};}
              return report;
            }});
        }''',{'report':report,'png':base64.b64encode(png).decode(),'sha':sha})
        page.get_by_role('button',name='Inspect dossier').click()
        expect(page.get_by_text('⚠ Representation conflict',exact=False)).to_be_visible()
        expect(page.get_by_role('heading',name='Declared processing coverage')).to_be_visible()
        expect(page.get_by_text('Translation review required ·',exact=False)).to_be_visible()
        page.get_by_text('Regions and reasons',exact=True).click()
        expect(page.get_by_text('word/document.xml#structured',exact=False)).to_be_visible()
        expect(page.get_by_text('Preserved crop hashes checked.',exact=False)).to_be_visible()
        expect(page.locator('.fidelity-pair pre').first).to_have_text('<img src=x>1000')
        assert page.locator('.fidelity-pair img').count()==1
        save=page.get_by_role('button',name='Save human review')
        expect(save).to_be_disabled()
        page.get_by_role('checkbox').check()
        save.click()
        expect(page.locator('textarea')).to_be_focused()
        page.get_by_role('textbox',name='Rationale').fill('I inspected the actual crop.')
        save.click()
        expect(page.get_by_text('Review was not confirmed.',exact=False)).to_be_visible()
        save.click()
        expect(page.get_by_text('Human review saved.',exact=False)).to_be_visible()
        calls=page.evaluate('window.calls.filter(c=>c.url.endsWith("/reviews"))')
        assert calls[0]['options']['json']['request_id']==calls[1]['options']['json']['request_id']
        assert calls[1]['options']['json']['reviewed_region_ids']==['b'*64]
        page.evaluate('window.rejectSave=true')
        save.click()
        expect(page.get_by_text('Review rejected.',exact=False)).to_be_visible()
        page.get_by_role('button',name='Inspect dossier').click()
        expect(page.get_by_text('Preserved crop hashes checked.',exact=False)).to_be_visible()
        expect(page.get_by_role('textbox',name='Rationale')).to_have_value('I inspected the actual crop.')
        page.screenshot(path=str(out/'desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        expect(save).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.screenshot(path=str(out/'narrow.png'),full_page=True)
        # A delayed first crop must not reintroduce later findings after signout.
        page.evaluate("window.delayCrop=true")
        page.evaluate("window.releaseCrop=null")
        # Extend the same transport report to ensure the outer rendering loop is cancelled.
        page.evaluate("window.testReport.findings.push({...window.testReport.findings[0],literal:'Old private reference'})")
        page.get_by_role('button',name='Inspect dossier').click()
        page.wait_for_function("typeof window.releaseCrop==='function'")
        page.evaluate("window.panel.clear();window.releaseCrop()")
        expect(page.get_by_text('Session cleared.',exact=False)).to_be_visible()
        expect(page.locator('.fidelity-finding')).to_have_count(0)
        expect(page.get_by_role('button',name='Inspect dossier')).to_be_enabled()
        page.evaluate("window.delayCrop=false;window.testReport.findings.pop()")
        page.get_by_role('button',name='Inspect dossier').click()
        expect(page.get_by_text('Preserved crop hashes checked.',exact=False)).to_be_visible()
        # Genuine translated prose has no literal crop. Preserve original context
        # and require the authorized page download before enabling disposition.
        page.evaluate("""window.panel.clear();window.testReport.findings=[{...window.testReport.findings[0],
          quoted_text:'Le paiement ne sera pas dû.',source_text_context:'De betaling is verschuldigd.',
          source_sha256:'c'.repeat(64),source_page:{version_id:'source',pdf_page:1},
          visual_assessment:{state:'not_assessed',reason:'quotation_missing_or_ambiguous_in_layer',regions:[]}}]""")
        page.get_by_role('button',name='Inspect dossier').click()
        expect(page.get_by_text('De betaling is verschuldigd.',exact=True)).to_be_visible()
        page.get_by_role('checkbox').check()
        expect(page.get_by_role('button',name='Save human review')).to_be_disabled()
        with page.expect_download() as download:
            page.get_by_role('button',name='Download preserved source page').click()
        assert download.value.suggested_filename=='caseproof-source-page.pdf'
        expect(page.get_by_role('button',name='Save human review')).to_be_enabled()
        (out/'browser.json').write_text(json.dumps({'crop_hash_checked':True,'escaped_text':True,
            'explicit_review':True,'signout_cancels_render':True,'idempotent_retry':True,'narrow':True,'identity':'synthetic transport only'}))
        browser.close()
    print('FIDELITY_PANEL_BROWSER_PASSED')


if __name__=='__main__':
    main()
