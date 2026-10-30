"""Executable synthetic-only fidelity benchmark; outputs no document text."""
from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path

from PIL import Image
from reportlab.pdfgen import canvas

from application.litigation.regional_fidelity import select_visual_assessment
from infrastructure.parsers.pdf_visual_fidelity import PDFVisualFidelity
from tests.fixtures.visual_fidelity import corpus


def main() -> None:
    engine=PDFVisualFidelity()
    rows=[]
    for fixture in corpus():
        started=time.perf_counter()
        page=engine.inspect(fixture.pdf,original_sha256=hashlib.sha256(fixture.pdf).hexdigest(),page_number=1)
        assessment=select_visual_assessment(page,fixture.target)
        # Actual independent image-only PDF from the rendered region is not a
        # full-page ablation. The executable fixture scan pairs below therefore
        # use their preserved image-only originals; no modality claim is faked.
        rows.append({'fixture':fixture.name,'sha256':hashlib.sha256(fixture.pdf).hexdigest(),
                     'label':fixture.expected,'state':assessment['state'],'reason':assessment['reason'],
                     'word_regions':len(page['regions']),'complete':page['complete'],
                     'seconds':round(time.perf_counter()-started,4)})
    review=[r for r in rows if r['label']=='review']
    flagged=[r for r in review if r['state'] in ('representation_conflict','ocr_unreliable')]
    control=[r for r in rows if r['label']=='clean']
    result={'schema':'caseproof.synthetic-fidelity-measurement.v1','rows':rows,
            'critical_review_cases':len(review),'flagged_or_unreliable':len(flagged),
            'critical_cases_not_flagged':len(review)-len(flagged),
            'clean_cases':len(control),'clean_false_alerts':sum(r['state']!='not_assessed' for r in control),
            'accepted_matches':0,'calibration':'not_available',
            'accuracy_claim':'None; synthetic labels, one run, uncalibrated OCR and limited detector.',
            'ablation':ablation(engine)}
    target=Path('/tmp/caseproof-visual-gate')
    target.mkdir(exist_ok=True)
    (target/'measurement.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if any(r['state']=='not_assessed' for r in review if not r['fixture'].startswith('scan_')):
        raise RuntimeError('seeded digital anomaly was not flagged')
    if result['clean_false_alerts']:
        raise RuntimeError('clean control false alert')


def ablation(engine: PDFVisualFidelity) -> dict[str, object]:
    """Same content: text extraction alone, raster-only PDF, then dual view.

    No LLM reader or LegalParseQA score is reproduced. Measure actionable
    anomaly candidates/abstention rather than downstream question answering.
    """
    import shutil
    import tempfile

    from pypdf import PdfReader

    from infrastructure.parsers.pdf_ocr import RASTER_DPI, _run

    rows=[]
    for fixture in corpus()[:5]:
        text=PdfReader(io.BytesIO(fixture.pdf)).pages[0].extract_text()
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.pdf'
            source.write_bytes(fixture.pdf)
            prefix=Path(directory)/'page'
            _run([str(shutil.which('pdftoppm')),'-f','1','-l','1','-singlefile','-r',str(RASTER_DPI),
                  '-png',str(source),str(prefix)],timeout=12)
            with Image.open(prefix.with_suffix('.png')) as image:
                out=io.BytesIO()
                pdf=canvas.Canvas(out,pagesize=(600,300),invariant=1)
                pdf.drawInlineImage(image,0,0,width=600,height=300)
                pdf.showPage()
                pdf.save()
            raster=out.getvalue()
        image_page=engine.inspect(raster,original_sha256=hashlib.sha256(raster).hexdigest(),page_number=1)
        dual=engine.inspect(fixture.pdf,original_sha256=hashlib.sha256(fixture.pdf).hexdigest(),page_number=1)
        rows.append({'fixture':fixture.name,'text_only':{'target_present':fixture.target in text,
                      'visual_assessment':'not_assessed'},
                     'image_only':{'candidates':sum(r['edit_candidate'] for r in image_page['regions']),
                                   'state':select_visual_assessment(image_page,fixture.target)['state']},
                     'dual_view':{'candidates':sum(r['edit_candidate'] for r in dual['regions']),
                                  'state':select_visual_assessment(dual,fixture.target)['state']}})
    return {'protocol':'fixed generated fixtures, real raster-only PDF, no model or semantic reader',
            'rows':rows,'generalization':'No inference about benchmark scores or sales value.'}


if __name__=='__main__':
    main()
