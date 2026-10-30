from __future__ import annotations

import base64
import hashlib
import io
import os
from dataclasses import replace

import pytest
from PIL import Image

from application.litigation.regional_fidelity import select_visual_assessment
from application.litigation.representation_normalization import normalize_region
from application.litigation.visual_calibration import CalibrationDocument, calibrate
from infrastructure.parsers.pdf_visual_fidelity import PDFVisualFidelity, RasterWord, _vector_lines
from tests.fixtures.visual_fidelity import corpus


def test_normalization_keeps_offsets_and_semantic_characters():
    raw='  e\u0301 \t -1.000,00 EUR  '
    normalized=normalize_region(raw)
    assert normalized.text=='é -1.000,00 EUR'
    assert raw[slice(*normalized.raw_ranges[0])]=='e\u0301'
    assert normalize_region('1000').text != normalize_region('1200').text
    assert normalize_region('non payé').text != normalize_region('payé').text
    assert normalize_region('con-\ntract').text=='con- tract'


def test_vector_detector_reads_real_painted_coloured_and_diagonal_strokes():
    fixtures={f.name:f for f in corpus()}
    for name in ('black','grey','red','diagonal'):
        lines,supported=_vector_lines(fixtures[name].pdf,1,1200,600)
        assert supported and lines
    assert not _vector_lines(fixtures['clipped'].pdf,1,1200,600)[1]
    assert not _vector_lines(fixtures['hidden_text'].pdf,1,1200,600)[1]


def test_regional_selection_does_not_block_same_page_control():
    page={'layer_text':'1000 Clean control 1200','regions':[
        {'region_id':'struck','text_start':0,'text_end':4,'state':'representation_conflict'},
        {'region_id':'clean','text_start':19,'text_end':23,'state':'not_assessed'}],
          'vector_geometry_supported':True}
    assert select_visual_assessment(page,'1000')['state']=='representation_conflict'
    assert select_visual_assessment(page,'1200')['state']=='not_assessed'
    assert select_visual_assessment(page,None)['reason']=='citation_has_no_anchored_quotation'
    assert select_visual_assessment({'layer_text':'','regions':[]},'1000')['state']=='ocr_unreliable'


def test_crop_bytes_and_regional_metadata_bound_to_real_source():
    f=next(f for f in corpus() if f.name=='grey')
    image=Image.new('RGB',(1200,600),'white')
    out=io.BytesIO()
    image.save(out,format='PNG')
    # Only adapter comparison test; executable raster/OCR is independently required below.
    result=PDFVisualFidelity().compare(image,out.getvalue(),f.pdf,1,
        [RasterWord('1000',(80,115,190,160))],[RasterWord('1000',(80,115,190,160),'95')])
    region=result['regions'][0]
    assert region['state']=='representation_conflict'
    assert hashlib.sha256(base64.b64decode(region['crop_base64'])).hexdigest()==region['crop_sha256']
    assert region['original_sha256']==hashlib.sha256(f.pdf).hexdigest()
    assert region['quality']['probability'] is None


def test_calibration_refuses_small_sample_or_leakage_and_never_invents_probability():
    docs=tuple(CalibrationDocument(hashlib.sha256(str(i).encode()).hexdigest(),.9,False) for i in range(20))
    args=dict(thresholds=(.7,.9), training_hashes=frozenset(),evaluation_hashes=frozenset(),
              target_risk=.01,delta=.05,independently_adjudicated=True)
    result=calibrate(docs,**args)
    assert result['status']=='insufficient_evidence' and result['per_field_probability'] is None
    with pytest.raises(ValueError,match='leakage'):
        calibrate(docs,**{**args,'training_hashes':frozenset([docs[0].document_sha256])})
    with pytest.raises(ValueError,match='unadjudicated'):
        calibrate(docs,**{**args,'independently_adjudicated':False})
    assert calibrate(docs,**{**args,'target_risk':.5})['status']=='eligible_under_assumptions'
    with pytest.raises(ValueError):
        calibrate((replace(docs[0],minimum_score=float('nan')),),**args)


@pytest.mark.skipif(os.getenv('CASEPROOF_VISUAL_EXECUTABLE')!='YES',reason='required executable OCR job')
def test_real_sandboxed_document_to_regional_gate():
    fixtures={f.name:f for f in corpus()}
    engine=PDFVisualFidelity()
    for name in ('clean','black','grey','red','diagonal','hidden_text','white_text','overlay','clipped'):
        f=fixtures[name]
        result=engine.inspect(f.pdf,original_sha256=hashlib.sha256(f.pdf).hexdigest(),page_number=1)
        target=select_visual_assessment(result,f.target)
        if name=='clean':
            assert target['state']=='not_assessed',target
            assert target['reason']=='uncalibrated_agreement'
        else:
            assert target['state'] in ('representation_conflict','ocr_unreliable'),(name,target)
        control=select_visual_assessment(result,'1200')
        assert control['state']=='not_assessed',(name,control)
        assert control['regions'] and all(r['extracted_text']=='1200' for r in control['regions'])


def test_long_page_cannot_claim_uniqueness_from_truncated_prefix():
    layer='1000 '+'filler '*600+'1000'
    page={'layer_text':layer,'regions':[{'region_id':'first','text_start':0,'text_end':4,
                                        'state':'representation_conflict'}]}
    result=select_visual_assessment(page,'1000')
    assert result['state']=='not_assessed' and result['regions']==[]
    assert result['reason']=='layer_alignment_budget_exceeded'
