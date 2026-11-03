"""Resolve a report reference to a supported, exact main-body DOCX paragraph."""
from __future__ import annotations

import io
from typing import Any
from xml.dom import minidom
from zipfile import ZipFile

from defusedxml import ElementTree as SafeXML  # type: ignore[import-untyped]

from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def correction_anchor(original: bytes, finding: dict[str, Any]) -> int:
    """Return a paragraph index only when extraction and editable XML agree.

    The existing editor accepts a single plain run in a direct body paragraph.
    Refuse the entire anchor if other body content cannot be mapped exactly.
    """
    literal, offsets = finding.get('literal'), finding.get('offsets')
    if (finding.get('region') != 'word/document.xml' or not isinstance(literal, str)
            or not literal or not isinstance(offsets, dict)
            or type(offsets.get('start')) is not int or type(offsets.get('end')) is not int):
        raise ValueError('unsupported reference anchor')
    regions = extract_docx_text_regions(original).regions
    region = next((r.text for r in regions if r.part == 'word/document.xml'), None)
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
    if any(n.namespaceURI != _NS or n.localName not in {'p', 'sectPr'} for n in body):
        raise ValueError('unsupported body structure')
    paragraphs = [n for n in body if n.localName == 'p']
    pieces: list[str] = []
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    for index, paragraph in enumerate(paragraphs):
        children = elements(paragraph)
        runs = [n for n in children if n.namespaceURI == _NS and n.localName == 'r']
        if any(n.namespaceURI != _NS or n.localName not in {'pPr', 'r'} for n in children):
            raise ValueError('unsupported paragraph')
        if not runs:
            continue
        if len(runs) != 1:
            raise ValueError('unsupported run count')
        run = elements(runs[0])
        texts = [n for n in run if n.namespaceURI == _NS and n.localName == 't']
        if len(texts) != 1 or any(n.namespaceURI != _NS or n.localName not in {'rPr', 't'} for n in run):
            raise ValueError('unsupported run')
        value = ''.join(n.data for n in texts[0].childNodes if n.nodeType == n.TEXT_NODE)
        if not value:
            continue
        if pieces:
            cursor += 1
        pieces.append(value)
        spans.append((index, cursor, cursor + len(value)))
        cursor += len(value)
    if '\n'.join(pieces) != region:
        raise ValueError('unmapped document text')
    matches = [(index, left, right) for index, left, right in spans if left <= start < end <= right]
    if len(matches) != 1:
        raise ValueError('reference crosses paragraph')
    index, left, right = matches[0]
    if region[left:right].count(literal) != 1:
        raise ValueError('ambiguous reference in paragraph')
    return index
