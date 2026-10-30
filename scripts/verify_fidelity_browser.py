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
    report={'schema':'caseproof-dossier-v1','snapshot_hash':'a'*64,'findings':[
        {'reference_id':'ref-0000','literal':'Stuk 1','identity':'resolved','page_mapping':'mapped',
         'fidelity':'representation_conflict','support':'not_assessed',
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
          window.calls=[]; window.failSave=true;
          window.CaseProofFidelity.mount({root:document.getElementById('panel'),context:()=>({caseId:'case',briefId:'brief'}),
            api:async(url,options)=>{window.calls.push({url,options});
              if(url.endsWith('/crop'))return new Response(Uint8Array.from(atob(png),c=>c.charCodeAt(0)),{headers:{
                'X-CaseProof-Snapshot':report.snapshot_hash,'X-CaseProof-Original-SHA256':'c'.repeat(64)}});
              if(url.endsWith('/reviews')){if(window.rejectSave){window.rejectSave=false;const e=Error('stale');e.code=409;throw e;}if(window.failSave){window.failSave=false;throw Error('network');}return {saved:true};}
              return report;
            }});
        }''',{'report':report,'png':base64.b64encode(png).decode(),'sha':sha})
        page.get_by_role('button',name='Inspect dossier').click()
        expect(page.get_by_text('⚠ Representation conflict',exact=False)).to_be_visible()
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
        (out/'browser.json').write_text(json.dumps({'crop_hash_checked':True,'escaped_text':True,
            'explicit_review':True,'idempotent_retry':True,'narrow':True,'identity':'synthetic transport only'}))
        browser.close()
    print('FIDELITY_PANEL_BROWSER_PASSED')


if __name__=='__main__':
    main()
