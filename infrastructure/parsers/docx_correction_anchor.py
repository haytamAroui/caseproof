"""Resolve a report reference to a supported, exact main-body DOCX paragraph."""
from __future__ import annotations

import io
import hashlib
from typing import Any
from xml.dom import minidom
from zipfile import ZipFile

from defusedxml import ElementTree as SafeXML  # type: ignore[import-untyped]

from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def correction_anchor(original: bytes, finding: dict[str, Any]) -> int:
    """Return a paragraph index only when extraction and editable XML agree.

    The editor accepts plain text runs in a direct body paragraph. Other
    paragraphs and tables may coexist only when the extracted body is mapped
    exactly; unsupported target structures and tracked changes still abstain.
    """
    literal, offsets = finding.get('literal'), finding.get('offsets')
    locator = finding.get('locator_identity')
    if locator is not None and not isinstance(locator, dict):
        raise ValueError('invalid locator identity')
    if (finding.get('region') != 'word/document.xml' or not isinstance(literal, str)
            or not literal or not isinstance(offsets, dict)
            or type(offsets.get('start')) is not int or type(offsets.get('end')) is not int):
        raise ValueError('unsupported reference anchor')
    extraction = extract_docx_text_regions(original)
    region = next((r.text for r in extraction.regions if r.part == 'word/document.xml'), None)
    if any(part in {'word/document.xml#hidden', 'word/document.xml#structured'}
           for part in extraction.unscanned_parts):
        raise ValueError('unmapped structured or hidden content')
    start, end = offsets['start'], offsets['end']
    if region is None or start < 0 or end <= start or region[start:end] != literal:
        raise ValueError('stale reference anchor')
    with ZipFile(io.BytesIO(original)) as archive:
        xml = archive.read('word/document.xml')
    SafeXML.fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    document = minidom.parseString(xml)
    revision_tags = {'ins', 'del', 'moveFrom', 'moveTo', 'rPrChange', 'pPrChange', 'sectPrChange'}
    if any(document.getElementsByTagNameNS(_NS, tag) for tag in revision_tags):
        raise ValueError('unresolved tracked changes')
    def elements(node: Any) -> list[Any]:
        return [child for child in node.childNodes if child.nodeType == child.ELEMENT_NODE]
    bodies = [n for n in elements(document.documentElement) if n.namespaceURI == _NS and n.localName == 'body']
    if len(bodies) != 1:
        raise ValueError('unsupported body')
    body = elements(bodies[0])
    if any(n.namespaceURI != _NS or n.localName not in {'p', 'tbl', 'sectPr'} for n in body):
        raise ValueError('unsupported body structure')
    direct = [n for n in body if n.namespaceURI == _NS and n.localName == 'p']
    direct_indices = {id(node): index for index, node in enumerate(direct)}
    pieces: list[str] = []
    spans: list[tuple[Any, int | None, int, int]] = []
    cursor = 0
    # Match the extractor's document order, including table paragraphs. Reject
    # nested paragraphs, since a flattened offset cannot identify their parent.
    for paragraph in bodies[0].getElementsByTagNameNS(_NS, 'p'):
        ancestor = paragraph.parentNode
        while ancestor is not None and ancestor is not bodies[0]:
            if getattr(ancestor, 'namespaceURI', None) == _NS and getattr(ancestor, 'localName', None) == 'p':
                raise ValueError('nested paragraph unsupported')
            ancestor = ancestor.parentNode
        value = ''.join(
            child.data
            for text in paragraph.getElementsByTagNameNS(_NS, 't')
            for child in text.childNodes if child.nodeType == child.TEXT_NODE
        )
        if not value:
            continue
        if pieces:
            cursor += 1
        pieces.append(value)
        spans.append((paragraph, direct_indices.get(id(paragraph)), cursor, cursor + len(value)))
        cursor += len(value)
    if '\n'.join(pieces) != region:
        raise ValueError('unmapped document text')
    matches = [(paragraph, index, left, right) for paragraph, index, left, right in spans
               if left <= start < end <= right]
    if len(matches) != 1:
        raise ValueError('reference crosses paragraph')
    paragraph, index, left, right = matches[0]
    if index is None:
        raise ValueError('target is not a direct body paragraph')
    children = elements(paragraph)
    runs = [n for n in children if n.namespaceURI == _NS and n.localName == 'r']
    if not runs or any(n.namespaceURI != _NS or n.localName not in {'pPr', 'r'} for n in children):
        raise ValueError('unsupported target paragraph')
    for target_run in runs:
        run = elements(target_run)
        texts = [n for n in run if n.namespaceURI == _NS and n.localName == 't']
        if len(texts) != 1 or any(n.namespaceURI != _NS or n.localName not in {'rPr', 't'} for n in run):
            raise ValueError('unsupported target run')
    if region[left:right].count(literal) != 1:
        raise ValueError('ambiguous reference in paragraph')
    if locator is not None:
        paragraph_text = region[left:right]
        exact_text = locator.get('exact_text')
        if exact_text is not None and (not isinstance(exact_text, str) or exact_text != literal):
            raise ValueError('stale locator exact text')
        expected_hash = locator.get('content_hash')
        if (not isinstance(expected_hash, str) or len(expected_hash) != 64
                or any(character not in '0123456789abcdef' for character in expected_hash)):
            raise ValueError('invalid locator content hash')
        if hashlib.sha256(paragraph_text.encode('utf-8')).hexdigest() != expected_hash:
            raise ValueError('stale locator content hash')
        expected_id = locator.get('paragraph_id')
        if expected_id is not None:
            para_ns = 'http://schemas.microsoft.com/office/word/2010/wordml'
            actual_id = paragraph.getAttributeNS(para_ns, 'paraId')
            if not actual_id or actual_id != expected_id:
                raise ValueError('stale locator paragraph identity')
        prefix, suffix = locator.get('prefix'), locator.get('suffix')
        if not isinstance(prefix, str) or not isinstance(suffix, str):
            raise ValueError('invalid locator context')
        local_start, local_end = start - left, end - left
        if not paragraph_text[:local_start].endswith(prefix) or not paragraph_text[local_end:].startswith(suffix):
            raise ValueError('stale locator context')
        occurrence = locator.get('occurrence_index')
        if type(occurrence) is not int or occurrence < 0:
            raise ValueError('invalid locator occurrence')
        matches = [i for i in range(len(paragraph_text)) if paragraph_text.startswith(literal, i)]
        if occurrence >= len(matches) or matches[occurrence] != local_start:
            raise ValueError('stale locator occurrence')
    return index


def bound_locator(original: bytes, finding: dict[str, Any], source_version_id: str) -> dict[str, Any]:
    """Identity extracted from the source bytes and its already validated target."""
    from docx import Document
    index = correction_anchor(original, finding)
    paragraph = Document(io.BytesIO(original)).paragraphs[index]
    content = paragraph.text
    literal = finding['literal']
    at = content.find(literal)
    if at < 0 or content.find(literal, at + 1) >= 0:
        raise ValueError('ambiguous target')
    para_ns = 'http://schemas.microsoft.com/office/word/2010/wordml'
    return {'exact_text': literal, 'prefix': content[:at],
            'suffix': content[at + len(literal):], 'occurrence_index': 0,
            'content_hash': hashlib.sha256(content.encode()).hexdigest(),
            'paragraph_id': paragraph._p.get('{%s}paraId' % para_ns),
            'source_version_id': source_version_id}
