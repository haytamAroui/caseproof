"""Stable, scoped identifiers for editable DOCX main-body and simple table-cell paragraphs.

Identifiers are only hints. Every request must also be checked against the exact
source bytes, frozen finding offsets and version-bound locator identity before
mutation. No support is implied for nested tables, shapes, tracked revisions or
arbitrary Word editing.
"""
from __future__ import annotations

from typing import Any

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TABLE_TARGET_BASE = 50_000
MAX_TABLE_PARAGRAPHS = 50_000


def _children(node: Any) -> list[Any]:
    return [child for child in node.childNodes if child.nodeType == child.ELEMENT_NODE]


def _is_word(node: Any, name: str) -> bool:
    return getattr(node, "namespaceURI", None) == WORD_NS and getattr(node, "localName", None) == name


def _body(document: Any) -> Any:
    elements = _children(document.documentElement)
    bodies = [child for child in elements if _is_word(child, "body")]
    if len(bodies) != 1:
        raise ValueError("unsupported body")
    return bodies[0]


def _simple_table_cell_paragraphs(body: Any) -> list[Any]:
    """Return only direct cell paragraphs in top-level tables, in document order.

    A nested table, structured document tag, drawing or textbox never becomes an
    editable target via an accidentally matching flattened paragraph index.
    """
    candidates: list[Any] = []
    for paragraph in body.getElementsByTagNameNS(WORD_NS, "p"):
        cell = paragraph.parentNode
        if not _is_word(cell, "tc"):
            continue
        row = cell.parentNode
        table = row.parentNode
        if not (_is_word(row, "tr") and _is_word(table, "tbl") and table.parentNode is body):
            continue
        candidates.append(paragraph)
        if len(candidates) > MAX_TABLE_PARAGRAPHS:
            raise ValueError("too many table paragraphs")
    return candidates


def editable_indices(document: Any) -> dict[int, int]:
    """Map DOM node identity to an opaque, backward-compatible correction index."""
    body = _body(document)
    direct = [node for node in _children(body) if _is_word(node, "p")]
    if len(direct) >= TABLE_TARGET_BASE:
        raise ValueError("too many body paragraphs")
    tables = _simple_table_cell_paragraphs(body)
    result = {id(node): index for index, node in enumerate(direct)}
    for index, node in enumerate(tables):
        result[id(node)] = TABLE_TARGET_BASE + index
    return result


def select_editable_paragraph(document: Any, index: int) -> Any:
    """Resolve the index to exactly one paragraph in the same source document."""
    if type(index) is not int or not 0 <= index < TABLE_TARGET_BASE + MAX_TABLE_PARAGRAPHS:
        raise ValueError("paragraph index out of bounds")
    body = _body(document)
    if index < TABLE_TARGET_BASE:
        paragraphs = [node for node in _children(body) if _is_word(node, "p")]
        if index >= len(paragraphs):
            raise ValueError("paragraph unavailable")
        return paragraphs[index]
    paragraphs = _simple_table_cell_paragraphs(body)
    offset = index - TABLE_TARGET_BASE
    if offset >= len(paragraphs):
        raise ValueError("table paragraph unavailable")
    return paragraphs[offset]
