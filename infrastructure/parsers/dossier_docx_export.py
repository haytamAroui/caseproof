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
        decisions = {d['reference_id']: d for d in report['human_decisions']}
        for f in report['findings']:
            decision = decisions.get(f['reference_id'], {})
            lines.append(f"{f['reference_id']} {f['literal']}: identity={f['identity']}; page={f['page_mapping']}; "
                         f"fidelity={f['fidelity']}; support={decision.get('decision', 'not_assessed')}; "
                         f"source={f['version_id']}; OCR={f['ocr_uncertainty']}")
            if decision:
                lines.append('Reviewer rationale: ' + decision['rationale'])
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
