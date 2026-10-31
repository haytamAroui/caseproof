"""Append scoped review annotations to a separate DOCX derivative."""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from typing import Any
from xml.dom import minidom
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from defusedxml import ElementTree as SafeXML  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

from application.documents.file_boundary import validate_original_container
from application.extraction.contracts import ExtractionError
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _validate_derivative_package(original: bytes) -> None:
    # Preserve original evidence but refuse to emit an active derivative. Do not
    # silently remove links/macros and imply that edited bytes are the original.
    try:
        validate_original_container(original, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        with ZipFile(io.BytesIO(original)) as archive:
            for entry in archive.infolist():
                name = entry.filename.lower()
                if ('vbaproject' in name or 'activex' in name or name.endswith('.bin')
                        or name.startswith('word/embeddings/')):
                    raise ValueError('active draft cannot be exported')
                if name == '[content_types].xml':
                    root = SafeXML.fromstring(archive.read(entry), forbid_dtd=True,
                                              forbid_entities=True, forbid_external=True)
                    if any(any(active in node.get('ContentType', '').casefold()
                               for active in ('macroenabled', 'vbaproject', 'oleobject', 'activex', 'ms-office.control', 'text/html'))
                           for node in root.iter()):
                        raise ValueError('active draft content type cannot be exported')
                if name.endswith('.rels'):
                    root = SafeXML.fromstring(archive.read(entry), forbid_dtd=True,
                                              forbid_entities=True, forbid_external=True)
                    active_relationships = {'vbaproject', 'oleobject', 'package', 'control', 'activexcontrol',
                                            'activexcontrolbinary', 'afchunk', 'attachedtemplate'}
                    if any(node.get('Type', '').rstrip('/').rsplit('/', 1)[-1].casefold() in active_relationships
                           for node in root.iter()):
                        raise ValueError('active draft relationship cannot be exported')
                    if any(node.get('TargetMode', '').casefold() == 'external'
                           or ':' in node.get('Target', '') for node in root.iter()):
                        raise ValueError('external draft relationship cannot be exported')
                if name.startswith('word/') and name.endswith('.xml'):
                    root = SafeXML.fromstring(archive.read(entry), forbid_dtd=True,
                                              forbid_entities=True, forbid_external=True)
                    if any(node.tag in {'{' + NS + '}altChunk', '{' + NS + '}object', '{' + NS + '}control'}
                           for node in root.iter()):
                        raise ValueError('active draft object cannot be exported')
                    instructions = ''.join((node.text or '') if node.tag == '{' + NS + '}instrText'
                                           else node.get('{' + NS + '}instr', '')
                                           for node in root.iter()).upper()
                    instructions = re.sub(r'\s+', ' ', instructions)
                    # Conservative substring refusal also covers adjacent or
                    # fragmented fields; field boundaries cannot hide a command.
                    if any(word in instructions for word in ('INCLUDETEXT', 'INCLUDEPICTURE', 'DDE', 'DATABASE', 'LINK')):
                        raise ValueError('active draft field cannot be exported')
    except (ExtractionError, ET.ParseError, DefusedXmlException, BadZipFile, OSError, RuntimeError):
        raise ValueError('unsafe draft archive cannot be exported') from None


def annotated_docx(original: bytes, report: dict[str, Any]) -> bytes:
    _validate_derivative_package(original)
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
        lines.append('Verification contract: ' + str(report.get('verification_contract', {})))
        lines.append('Abstentions: ' + str(report.get('abstentions', [])))
        decisions = report['human_decisions']
        for f in report['findings']:
            human = [d for d in decisions if d['reference_id'] == f['reference_id']]
            lines.append(f"{f['reference_id']} {f['literal']}: identity={f['identity']}; page={f['page_mapping']}; "
                         f"fidelity={f['fidelity']}; automated support=not_assessed; "
                         f"source={f['version_id']}; OCR={f['ocr_uncertainty']}")
            lines.append('Identity reason: ' + str(f.get('identity_reason')) + '; literal=' + str(f.get('literal_assessment', {})) +
                         '; translation_review_required=' + str(f.get('translation_review_required', False)) +
                         '; draft_language=' + str(f.get('draft_language')) + '; source_language=' + str(f.get('source_language')) +
                         '; quoted_text=' + str(f.get('quoted_text')))
            lines.append('Source original context: ' + str(f.get('source_text_context', '')) + '; context_partial=' + str(f.get('source_text_context_partial', False)))
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
