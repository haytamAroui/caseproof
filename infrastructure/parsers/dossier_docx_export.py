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
from infrastructure.parsers.docx_edit_targets import select_editable_paragraph
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _valid_xml_text(value: str) -> bool:
    """XML 1.0 character set; never silently alter a lawyer's text."""
    return all(
        ord(ch) in (0x09, 0x0A, 0x0D)
        or 0x20 <= ord(ch) <= 0xD7FF
        or 0xE000 <= ord(ch) <= 0xFFFD
        or 0x10000 <= ord(ch) <= 0x10FFFF
        for ch in value
    )


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
    """Append a human-readable, scoped appendix; never change the preserved original.

    Unrepresentable XML characters cause refusal, not silent sanitization. All
    user-supplied content is inserted as inert XML text, never markup.
    """
    _validate_derivative_package(original)
    extracted = extract_docx_text_regions(original)
    if not any(r.part == 'word/document.xml' for r in extracted.regions):
        raise ValueError('draft cannot be annotated')

    with ZipFile(io.BytesIO(original)) as source:
        raw_document = source.read('word/document.xml')
        SafeXML.fromstring(raw_document, forbid_dtd=True, forbid_entities=True,
                           forbid_external=True)
        document = minidom.parseString(raw_document)
        bodies = document.getElementsByTagNameNS(NS, 'body')
        if len(bodies) != 1:
            raise ValueError('missing body')
        body = bodies[0]
        prefix = (body.prefix + ':') if body.prefix else ''
        section = next((node for node in body.childNodes
                        if node.namespaceURI == NS and node.localName == 'sectPr'), None)
        written = 0

        def element(name: str) -> Any:
            return document.createElementNS(NS, prefix + name)

        def scalar(value: Any) -> str:
            if value is None:
                return 'not supplied'
            if type(value) is bool:
                return 'yes' if value else 'no'
            if isinstance(value, (str, int, float)):
                result = str(value)
                if not _valid_xml_text(result):
                    raise ValueError('annotation contains XML-invalid characters')
                return result
            raise ValueError('unsupported annotation value')

        def run_text(run: Any, value: str) -> None:
            if not _valid_xml_text(value):
                raise ValueError('annotation contains XML-invalid characters')
            for part in re.split(r'(\r\n|\r|\n|\t)', value):
                if part in ('\r', '\n', '\r\n'):
                    run.appendChild(element('br'))
                elif part == '\t':
                    run.appendChild(element('tab'))
                elif part:
                    node = element('t')
                    node.setAttributeNS('http://www.w3.org/XML/1998/namespace',
                                        'xml:space', 'preserve')
                    node.appendChild(document.createTextNode(part))
                    run.appendChild(node)

        def line(label: str, value: Any = None, *, heading: bool = False,
                 indent: int = 0) -> None:
            nonlocal written
            written += 1
            if written > 3500:
                raise ValueError('annotation exceeds supported paragraph count')
            paragraph = element('p')
            properties = element('pPr')
            if indent:
                indentation = element('ind')
                indentation.setAttributeNS(NS, prefix + 'left', str(min(indent, 3) * 360))
                properties.appendChild(indentation)
            if heading:
                spacing = element('spacing')
                spacing.setAttributeNS(NS, prefix + 'before', '180')
                properties.appendChild(spacing)
            if properties.childNodes:
                paragraph.appendChild(properties)
            header = element('r')
            header_properties = element('rPr')
            header_properties.appendChild(element('b'))
            header.appendChild(header_properties)
            run_text(header, label + (': ' if value is not None else ''))
            paragraph.appendChild(header)
            if value is not None:
                content = element('r')
                run_text(content, scalar(value))
                paragraph.appendChild(content)
            body.insertBefore(paragraph, section)

        def details(label: str, value: Any, *, depth: int = 1) -> None:
            """Label nested data without Python repr, hiding nothing silently."""
            if depth > 3:
                line(label, 'Nested details: consult the frozen JSON artifact', indent=2)
                return
            if isinstance(value, dict):
                line(label, heading=depth == 1, indent=min(depth - 1, 2))
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise ValueError('invalid annotation field name')
                    details(key.replace('_', ' ').capitalize(), item, depth=depth + 1)
            elif isinstance(value, list):
                if len(value) > 50:
                    line(label, f'{len(value)} entries; item-level details in frozen JSON export',
                         indent=min(depth, 2))
                else:
                    line(label + f' ({len(value)} entries)', heading=depth == 1,
                         indent=min(depth - 1, 2))
                    for index, item in enumerate(value, 1):
                        details(f'Item {index}', item, depth=depth + 1)
            else:
                line(label, value, indent=min(depth, 2))

        line('CaseProof — scoped review annotations / overzicht / annexe', heading=True)
        line('Derivative notice',
             'Annotated copy only. The preserved source is unchanged; no legal, '
             'authenticity, filing or fidelity certificate is issued.')
        line('Snapshot SHA-256', report['snapshot_hash'])
        scope = report.get('review_completeness')
        if isinstance(scope, dict):
            line('Reviewed release scope', scope.get('release_type', 'unknown'))
            line('Reviewed detected findings', scope.get('reviewed_findings'))
            line('Total detected findings', scope.get('total_findings'))
            line('Unreviewed detected findings', scope.get('unreviewed_findings'))
            line('Partial release expressly acknowledged', scope.get('partial_acknowledged'))
            line('Scope warning', 'Review completeness is not evidence of full document coverage.')
        for key, label in (
            ('case_id', 'Matter'), ('brief_id', 'Draft source version'),
            ('bundle_signature', 'Bundle signature'), ('confirmation_id', 'Inventory confirmation'),
        ):
            if key in report and report[key] is not None:
                line(label, report[key])
        coverage = report['coverage']
        if not isinstance(coverage, dict):
            raise ValueError('invalid coverage structure')
        line('Coverage / dekking / couverture', heading=True)
        for key in (
            'checked', 'unresolved', 'fully_checked', 'references_detected', 'references_checked',
            'references_not_assessed', 'text_coverage_complete',
            'reference_recall_measured', 'source_pages_known_total',
            'source_pages_total', 'source_pages_ocr_processed',
            'source_pages_failed_or_skipped',
        ):
            if key in coverage:
                line('Fully checked (fully_checked)' if key == 'fully_checked'
                     else key.replace('_', ' ').capitalize(), coverage[key], indent=1)
        for key in ('dimension_counts', 'docx_regions', 'source_page_counts_unknown'):
            if key in coverage:
                details('DOCX region coverage (docx_regions)' if key == 'docx_regions'
                        else key.replace('_', ' ').capitalize(), coverage[key])
        if 'source_pages' in coverage:
            pages = coverage['source_pages']
            if not isinstance(pages, list):
                raise ValueError('invalid source page ledger')
            line('Source-page ledger',
                 f'{len(pages)} entries; full method and error details in frozen JSON',
                 indent=1)
        line('Verification scope and limitations', heading=True)
        verification = report.get('verification_contract', {})
        if not isinstance(verification, dict):
            raise ValueError('invalid verification contract')
        details('Verification contract', verification)
        line('Machine text matches do not establish semantic legal support.')
        line('Unmapped, unsupported and OCR-unreliable portions remain unresolved.')
        abstentions = report.get('abstentions', [])
        if not isinstance(abstentions, list):
            raise ValueError('invalid abstentions structure')
        details('Abstentions / onthoudingen / abstentions', abstentions)
        findings = report['findings']
        decisions = report['human_decisions']
        if not isinstance(findings, list) or not isinstance(decisions, list):
            raise ValueError('invalid findings or decisions')
        line('Findings / vaststellingen / constatations', heading=True)
        line('Number of detected references', len(findings))
        for index, finding in enumerate(findings, 1):
            if not isinstance(finding, dict):
                raise ValueError('invalid finding')
            line(f'Reference {index}', finding['reference_id'], heading=True)
            for key, label in (
                ('literal', 'Literal citation'), ('identity', 'Identity'),
                ('identity_reason', 'Identity reason'), ('page_mapping', 'Page mapping'),
                ('page_mapping_reason', 'Page reason'), ('pdf_page', 'Physical PDF page'),
                ('printed_page', 'Printed page'), ('bundle_page', 'Bundle page'),
                ('fidelity', 'Literal fidelity'), ('support', 'Human support state'),
                ('version_id', 'Preserved source version'),
                ('source_sha256', 'Source SHA-256'), ('ocr_uncertainty', 'OCR uncertainty'),
                ('draft_language', 'Draft language'), ('source_language', 'Source language'),
                ('translation_review_required', 'Translation review needed (translation_review_required)'),
                ('quoted_text', 'Quoted text'), ('source_text_context', 'Source representation context'),
                ('source_text_context_partial', 'Context was partial'),
            ):
                if key in finding:
                    line(label, finding[key], indent=1)
            for key in ('literal_assessment', 'visual_assessment'):
                if key in finding:
                    value = finding[key]
                    if key == 'visual_assessment' and isinstance(value, dict):
                        regions = value.get('regions', [])
                        if not isinstance(regions, list):
                            raise ValueError('invalid visual regions')
                        value = {k: v for k, v in value.items() if k != 'regions'}
                        details('Visual region count', len(regions))
                        for region_index, region in enumerate(regions, 1):
                            details(f'Visual region {region_index}',
                                    {k: v for k, v in region.items() if k != 'crop_base64'})
                    details(key.replace('_', ' ').capitalize(), value)
            line('Automated legal support', 'not_assessed', indent=1)
        line('Persisted human review / menselijke beoordeling / revue humaine',
             heading=True)
        line('Number of decision receipts', len(decisions))
        for index, decision in enumerate(decisions, 1):
            if not isinstance(decision, dict):
                raise ValueError('invalid human decision')
            line(f'Decision {index}', decision.get('reference_id'), heading=True)
            for key, label in (
                ('decision', 'Decision'), ('reviewer_id', 'Reviewer identity'),
                ('timestamp', 'Review timestamp'), ('request_id', 'Review request ID'),
                ('rationale', 'Rationale'),
            ):
                if key in decision:
                    line(label, decision[key], indent=1)
        output = io.BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as target:
            for entry in source.infolist():
                target.writestr(entry, document.toxml(encoding='utf-8')
                                if entry.filename == 'word/document.xml' else source.read(entry))
    return output.getvalue()


def corrected_docx_preview(original: bytes, *, expected_sha256: str,
                           paragraph_index: int, before: str, after: str) -> bytes:
    """Bounded plain-run body/table-cell correction; preserve other ZIP member bytes.

    Replacement inherits the first affected run's formatting; unaffected text
    retains its run formatting. Fields, revisions, hyperlinks and bookmarks
    within the target remain unsupported. This creates a derivative,
    never a new accepted source version or a persisted reviewer decision.
    """
    from hashlib import sha256

    if (sha256(original).hexdigest() != expected_sha256
            or type(paragraph_index) is not int or paragraph_index < 0
            or not before or before == after or len(after) > 4000
            or not _valid_xml_text(after) or any(ch in after for ch in '\t\n\r')):
        raise ValueError('stale or invalid correction')
    _validate_derivative_package(original)
    with ZipFile(io.BytesIO(original)) as archive:
        xml_bytes = archive.read('word/document.xml')
        SafeXML.fromstring(xml_bytes, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        # Preserve namespace declarations, including prefixes referenced only by
        # mc:Ignorable. ElementTree would drop such declarations on serialization.
        document = minidom.parseString(xml_bytes)
        revision_tags = {'ins', 'del', 'moveFrom', 'moveTo', 'rPrChange', 'pPrChange', 'sectPrChange'}
        if any(document.getElementsByTagNameNS(NS, tag) for tag in revision_tags):
            raise ValueError('unresolved tracked changes')

        def elements(node: Any) -> list[Any]:
            return [child for child in node.childNodes if child.nodeType == child.ELEMENT_NODE]

        paragraph = select_editable_paragraph(document, paragraph_index)
        children = elements(paragraph)
        runs = [node for node in children if node.namespaceURI == NS and node.localName == 'r']
        if (not runs or any(node.namespaceURI != NS or node.localName not in {'pPr', 'r'}
                            for node in children)):
            raise ValueError('complex paragraph requires manual correction')
        text_nodes = []
        pieces = []
        for run in runs:
            children = elements(run)
            texts = [node for node in children if node.namespaceURI == NS and node.localName == 't']
            if (len(texts) != 1 or any(node.namespaceURI != NS or node.localName not in {'rPr', 't'}
                                       for node in children)):
                raise ValueError('complex run requires manual correction')
            text_nodes.append(texts[0])
            pieces.append(''.join(node.data for node in texts[0].childNodes if node.nodeType == node.TEXT_NODE))
        text = ''.join(pieces)
        if text.count(before) != 1:
            raise ValueError('ambiguous or stale correction range')
        start = text.index(before)
        end = start + len(before)
        cursor = 0
        inserted = False
        for node, value in zip(text_nodes, pieces, strict=True):
            left, right = cursor, cursor + len(value)
            cursor = right
            if right <= start or left >= end:
                continue
            prefix = value[:max(0, start - left)]
            suffix = value[max(0, end - left):]
            replacement = after if not inserted else ''
            inserted = True
            for child in list(node.childNodes):
                node.removeChild(child)
            node.appendChild(document.createTextNode(prefix + replacement + suffix))
            node.setAttributeNS('http://www.w3.org/XML/1998/namespace', 'xml:space', 'preserve')
        if not inserted:
            raise ValueError('correction range unavailable')
        output = io.BytesIO()
        with ZipFile(output, 'w', compression=ZIP_DEFLATED) as target:
            for entry in archive.infolist():
                target.writestr(entry, document.toxml(encoding='utf-8')
                                if entry.filename == 'word/document.xml' else archive.read(entry))
    return output.getvalue()
