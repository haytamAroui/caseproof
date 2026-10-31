"""Append scoped review annotations to a separate DOCX derivative."""
from __future__ import annotations

import io
from typing import Any
from xml.dom import minidom
from zipfile import ZIP_DEFLATED, ZipFile

from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def annotated_docx(original: bytes, report: dict[str, Any]) -> bytes:
    extracted = extract_docx_text_regions(original)  # bounded ZIP/XML validation
    if not any(r.part == 'word/document.xml' for r in extracted.regions):
        raise ValueError('draft cannot be annotated')
    with ZipFile(io.BytesIO(original)) as source:
        document = minidom.parseString(source.read('word/document.xml'))
        bodies = document.getElementsByTagNameNS(NS, 'body')
        if len(bodies) != 1:
            raise ValueError('missing body')
        body = bodies[0]
        prefix = (body.prefix + ':') if body.prefix else ''
        lines = ['CaseProof — scoped review annotations (derivative; original preserved)',
                 'Snapshot: ' + report['snapshot_hash'],
                 'Coverage: ' + str(report['coverage']),
                 'No filing, authenticity, fidelity or legal-support certificate.']
        decisions = report['human_decisions']
        for f in report['findings']:
            human = [d for d in decisions if d['reference_id'] == f['reference_id']]
            lines.append(f"{f['reference_id']} {f['literal']}: identity={f['identity']}; page={f['page_mapping']}; "
                         f"fidelity={f['fidelity']}; automated support=not_assessed; "
                         f"source={f['version_id']}; OCR={f['ocr_uncertainty']}")
            visual = f.get('visual_assessment', {})
            lines.append('Visual fidelity: ' + str(visual.get('state', 'not_assessed')) +
                         '; reason=' + str(visual.get('reason', 'visual_not_run')) +
                         '; calibration=' + str(visual.get('calibration_status', 'not_available')))
            for region in visual.get('regions', []):
                lines.append('Region ' + region['region_id'] + '; crop SHA256=' + region['crop_sha256'] +
                             '; page=' + str(region['page_number']) + '; bbox=' + str(region['bbox']) +
                             '; extracted=' + region['extracted_text'] + '; OCR=' + region['visual_text'])
            for decision in human:
                lines.append('Human decision: ' + decision['decision'] + '; reviewer=' +
                             str(decision.get('reviewer_id', 'unknown')) + '; timestamp=' +
                             str(decision.get('timestamp', 'unknown')) + '; rationale=' + decision['rationale'])
        section = next((node for node in body.childNodes
                        if node.namespaceURI == NS and node.localName == 'sectPr'), None)
        for line in lines:
            paragraph = document.createElementNS(NS, prefix + 'p')
            run = document.createElementNS(NS, prefix + 'r')
            text = document.createElementNS(NS, prefix + 't')
            text.appendChild(document.createTextNode(line))
            run.appendChild(text)
            paragraph.appendChild(run)
            body.insertBefore(paragraph, section)
        output = io.BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as target:
            for item in source.infolist():
                target.writestr(item, document.toxml(encoding='utf-8')
                                if item.filename == 'word/document.xml' else source.read(item))
    return output.getvalue()
