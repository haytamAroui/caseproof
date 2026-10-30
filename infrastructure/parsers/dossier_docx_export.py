"""Append scoped review annotations to a separate DOCX derivative."""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def annotated_docx(original: bytes, report: dict[str, Any]) -> bytes:
    extracted = extract_docx_text_regions(original)  # bounded ZIP/XML validation
    if not any(r.part == 'word/document.xml' for r in extracted.regions):
        raise ValueError('draft cannot be annotated')
    with ZipFile(io.BytesIO(original)) as source:
        root = ET.fromstring(source.read('word/document.xml'))
        body = root.find(NS + 'body')
        if body is None:
            raise ValueError('missing body')
        lines = ['CaseProof — scoped review annotations (derivative; original preserved)',
                 'Snapshot: ' + report['snapshot_hash'],
                 'Coverage: ' + str(report['coverage']),
                 'No filing, authenticity, fidelity or legal-support certificate.']
        decisions = {d['reference_id']: d for d in report['human_decisions']}
        for f in report['findings']:
            decision = decisions.get(f['reference_id'], {})
            lines.append(f"{f['reference_id']} {f['literal']}: identity={f['identity']}; page={f['page_mapping']}; "
                         f"fidelity={f['fidelity']}; support={decision.get('decision', 'not_assessed')}; "
                         f"source={f['version_id']}; OCR={f['ocr_uncertainty']}")
            if decision:
                lines.append('Reviewer rationale: ' + decision['rationale'])
        section = body.find(NS + 'sectPr')
        for line in lines:
            paragraph = ET.Element(NS + 'p')
            ET.SubElement(ET.SubElement(paragraph, NS + 'r'), NS + 't').text = line
            body.insert(list(body).index(section) if section is not None else len(body), paragraph)
        output = io.BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as target:
            for item in source.infolist():
                target.writestr(item, ET.tostring(root, encoding='utf-8', xml_declaration=True)
                                if item.filename == 'word/document.xml' else source.read(item))
    return output.getvalue()
