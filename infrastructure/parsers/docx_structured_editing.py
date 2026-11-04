"""Deterministic DOCX-native text edits, including real OOXML tracked changes.

This is a source-bound editing kernel, NOT an authorization or persistence API.
The caller must bind authenticated actor, matter, current version and snapshot
and must never treat an edited derivative as an accepted human review.
"""
from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal
from xml.dom import minidom
from zipfile import ZIP_DEFLATED, ZipFile

from infrastructure.parsers.dossier_docx_export import (
    _valid_xml_text,
    _validate_derivative_package,
)
from infrastructure.parsers.safe_docx_xml import parse_docx_xml

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML = "http://www.w3.org/XML/1998/namespace"
STORY = re.compile(r"^word/(?:document|header[0-9]+|footer[0-9]+|footnotes|endnotes)\.xml$")
MAX_BLOCKS = 3000
MAX_EDITS = 40
MAX_TEXT = 20000
MAX_AUTHOR = 120
_SHA = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^20[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T[0-2][0-9]:[0-5][0-9]:[0-5][0-9][+]00:00$")


@dataclass(frozen=True)
class DocumentBlock:
    part: str
    paragraph_index: int
    kind: Literal["body", "table", "textbox", "story", "unsupported"]
    text: str
    text_sha256: str
    editable: bool

    @property
    def key(self) -> str:
        return f"{self.part}#p:{self.paragraph_index}"


@dataclass(frozen=True)
class DocumentTextEdit:
    part: str
    paragraph_index: int
    expected_text_sha256: str
    before: str
    after: str
    track_changes: bool = True


@dataclass(frozen=True)
class DocumentRevisionDecision:
    part: str
    revision_id: int
    action: Literal["accept", "reject"]


def _elements(node: Any) -> list[Any]:
    return [child for child in node.childNodes if child.nodeType == child.ELEMENT_NODE]


def _is(node: Any, local: str) -> bool:
    return getattr(node, "namespaceURI", None) == W and getattr(node, "localName", None) == local


def _kind(paragraph: Any) -> Literal["body", "table", "textbox", "story", "unsupported"]:
    parent = paragraph.parentNode
    if _is(parent, "tc"):
        return "table"
    if _is(parent, "txbxContent"):
        return "textbox"
    if _is(parent, "body"):
        return "body"
    if any(_is(parent, kind) for kind in ("hdr", "ftr", "footnote", "endnote")):
        return "story"
    return "unsupported"


def _runs(paragraph: Any) -> tuple[list[Any], list[Any]] | None:
    if _kind(paragraph) == "unsupported":
        return None
    parts = _elements(paragraph)
    if any(not (_is(p, "pPr") or _is(p, "r")) for p in parts):
        return None
    runs = [p for p in parts if _is(p, "r")]
    texts: list[Any] = []
    for run in runs:
        children = _elements(run)
        text = [p for p in children if _is(p, "t")]
        if len(text) != 1 or any(not (_is(p, "t") or _is(p, "rPr")) for p in children):
            return None
        texts.append(text[0])
    return (runs, texts)


def _plain_text(texts: Sequence[Any]) -> str:
    return "".join(
        node.data
        for text in texts
        for node in text.childNodes
        if node.nodeType == node.TEXT_NODE
    )


def _paragraphs(doc: Any) -> list[Any]:
    return list(doc.getElementsByTagNameNS(W, "p"))


def _open_story(original: bytes, part: str) -> Any:
    if not isinstance(part, str) or not STORY.fullmatch(part):
        raise ValueError("unsupported DOCX story part")
    with ZipFile(io.BytesIO(original)) as archive:
        if part not in archive.namelist():
            raise ValueError("DOCX story part missing")
        raw = archive.read(part)
    parse_docx_xml(raw)
    return minidom.parseString(raw)


def _block(doc: Any, part: str, index: int) -> tuple[DocumentBlock, Any]:
    paragraphs = _paragraphs(doc)
    if type(index) is not int or not 0 <= index < min(len(paragraphs), MAX_BLOCKS):
        raise ValueError("paragraph index unavailable")
    paragraph = paragraphs[index]
    target = _runs(paragraph)
    kind = _kind(paragraph)
    value = _plain_text(target[1]) if target is not None else ""
    # A missing or complex run never becomes an editable empty paragraph.
    editable = target is not None and bool(target[0]) and bool(value) and len(value) <= MAX_TEXT
    block = DocumentBlock(part, index, kind, value, hashlib.sha256(value.encode()).hexdigest(), editable)
    return block, paragraph


def list_document_blocks(original: bytes) -> tuple[DocumentBlock, ...]:
    """Bounded read-only inventory; hidden/complex material is not claimed editable."""
    _validate_derivative_package(original)
    result: list[DocumentBlock] = []
    with ZipFile(io.BytesIO(original)) as archive:
        parts = sorted(name for name in archive.namelist() if STORY.fullmatch(name))
    for part in parts:
        document = _open_story(original, part)
        for index, _ in enumerate(_paragraphs(document)):
            if len(result) >= MAX_BLOCKS:
                raise ValueError("too many document blocks")
            block, _ = _block(document, part, index)
            result.append(block)
    return tuple(result)


def _run(doc: Any, text: str, first: Any | None = None, *, deleted: bool = False) -> Any:
    run = doc.createElementNS(W, "w:r")
    if first is not None:
        props = next((p for p in _elements(first) if _is(p, "rPr")), None)
        if props is not None:
            run.appendChild(props.cloneNode(True))
    for piece in re.split(r"(\r\n|\r|\n|\t)", text):
        if not piece:
            continue
        if piece in ("\r", "\n", "\r\n"):
            if deleted:
                raise ValueError("cannot track multi-line deleted text in this engine")
            run.appendChild(doc.createElementNS(W, "w:br"))
        elif piece == "\t":
            if deleted:
                raise ValueError("cannot track tab deletion in this engine")
            run.appendChild(doc.createElementNS(W, "w:tab"))
        else:
            node = doc.createElementNS(W, "w:delText" if deleted else "w:t")
            node.setAttributeNS(XML, "xml:space", "preserve")
            node.appendChild(doc.createTextNode(piece))
            run.appendChild(node)
    return run


def _check_source(original: bytes, expected_sha256: str) -> None:
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
        raise ValueError("invalid source digest")
    if hashlib.sha256(original).hexdigest() != expected_sha256:
        raise ValueError("source bytes changed")
    _validate_derivative_package(original)


@dataclass(frozen=True)
class DocumentRevision:
    part: str
    revision_id: int
    kind: Literal["inserted", "deleted"]
    author: str
    timestamp: str
    text_sha256: str


def list_document_revisions(original: bytes) -> tuple[DocumentRevision, ...]:
    """Inspect OOXML textual suggestions without returning confidential text."""
    _validate_derivative_package(original)
    output: list[DocumentRevision] = []
    with ZipFile(io.BytesIO(original)) as archive:
        parts = sorted(name for name in archive.namelist() if STORY.fullmatch(name))
    for part in parts:
        doc = _open_story(original, part)
        for kind, tag in (("inserted", "ins"), ("deleted", "del")):
            for node in doc.getElementsByTagNameNS(W, tag):
                raw_id = node.getAttributeNS(W, "id")
                if not raw_id.isdigit() or int(raw_id) > 2_000_000_000:
                    raise ValueError("unsupported revision identity")
                value = "".join(
                    child.data
                    for name in ("t", "delText")
                    for txt in node.getElementsByTagNameNS(W, name)
                    for child in txt.childNodes if child.nodeType == child.TEXT_NODE
                )
                output.append(DocumentRevision(
                    part, int(raw_id), kind,
                    node.getAttributeNS(W, "author")[:MAX_AUTHOR],
                    node.getAttributeNS(W, "date")[:64],
                    hashlib.sha256(value.encode()).hexdigest(),
                ))
                if len(output) > MAX_BLOCKS:
                    raise ValueError("too many document revisions")
    return tuple(sorted(output, key=lambda revision: (revision.part, revision.revision_id, revision.kind)))


def _next_revision_id(original: bytes) -> int:
    maximum = 0
    with ZipFile(io.BytesIO(original)) as archive:
        parts = (name for name in archive.namelist() if STORY.fullmatch(name))
        for part in parts:
            doc = _open_story(original, part)
            for tag in ("ins", "del"):
                for node in doc.getElementsByTagNameNS(W, tag):
                    value = node.getAttributeNS(W, "id")
                    if value.isdigit():
                        maximum = max(maximum, int(value))
    if maximum > 2_000_000_000:
        raise ValueError("revision ID exhausted")
    return maximum + 1


def _metadata(node: Any, revision_id: int, author: str, timestamp: str) -> None:
    node.setAttributeNS(W, "w:id", str(revision_id))
    node.setAttributeNS(W, "w:author", author)
    node.setAttributeNS(W, "w:date", timestamp)


def edit_document_text(
    original: bytes, *, expected_sha256: str, edits: Sequence[DocumentTextEdit],
    author: str, timestamp: str,
) -> bytes:
    """Return a new DOCX; never store, activate or alter original bytes.

    Direct mode replaces the complete plain-text paragraph, preserving its
    paragraph properties and first run's style. Suggestion mode emits actual
    w:del/w:delText and w:ins markup with author/UTC timestamp.
    """
    _check_source(original, expected_sha256)
    if (not 1 <= len(edits) <= MAX_EDITS or not isinstance(author, str)
            or not 1 <= len(author) <= MAX_AUTHOR or not _valid_xml_text(author)
            or not isinstance(timestamp, str) or not _DATE.fullmatch(timestamp)):
        raise ValueError("invalid editing metadata")
    if any(not isinstance(edit, DocumentTextEdit) for edit in edits):
        raise ValueError("invalid editing operation")
    modified: dict[str, Any] = {}
    seen: set[tuple[str, int]] = set()
    next_id = _next_revision_id(original)
    for edit in edits:
        key = (edit.part, edit.paragraph_index)
        if key in seen:
            raise ValueError("duplicate document edit target")
        seen.add(key)
        if (not _SHA.fullmatch(edit.expected_text_sha256)
                or not isinstance(edit.before, str) or not isinstance(edit.after, str)
                or not 0 < len(edit.before) <= MAX_TEXT or len(edit.after) > MAX_TEXT
                or edit.before == edit.after or not _valid_xml_text(edit.after)
                or type(edit.track_changes) is not bool):
            raise ValueError("invalid edit payload")
        doc = modified.setdefault(edit.part, _open_story(original, edit.part))
        block, paragraph = _block(doc, edit.part, edit.paragraph_index)
        if not block.editable or block.text != edit.before or block.text_sha256 != edit.expected_text_sha256:
            raise ValueError("stale or unsupported edit target")
        existing = _runs(paragraph)
        if existing is None:
            raise ValueError("unsupported paragraph")
        runs, _ = existing
        if edit.track_changes and any(c in edit.before for c in "\n\r\t"):
            raise ValueError("unsupported source revision whitespace")
        first = runs[0]
        boundary = first
        if edit.track_changes:
            deletion = doc.createElementNS(W, "w:del")
            insertion = doc.createElementNS(W, "w:ins")
            _metadata(deletion, next_id, author, timestamp)
            _metadata(insertion, next_id + 1, author, timestamp)
            next_id += 2
            for run in runs:
                copy = run.cloneNode(True)
                for txt in copy.getElementsByTagNameNS(W, "t"):
                    replacement = doc.createElementNS(W, "w:delText")
                    while txt.firstChild:
                        replacement.appendChild(txt.firstChild)
                    for i in range(txt.attributes.length):
                        attr = txt.attributes.item(i)
                        if attr is not None and attr.namespaceURI == XML:
                            replacement.setAttributeNS(XML, attr.name, attr.value)
                    txt.parentNode.replaceChild(replacement, txt)
                deletion.appendChild(copy)
            insertion.appendChild(_run(doc, edit.after, first))
            paragraph.insertBefore(deletion, boundary)
            paragraph.insertBefore(insertion, boundary)
        else:
            paragraph.insertBefore(_run(doc, edit.after, first), boundary)
        for run in runs:
            paragraph.removeChild(run)
    output = io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source, ZipFile(output, "w", ZIP_DEFLATED) as result:
        for entry in source.infolist():
            value = (modified[entry.filename].toxml(encoding="utf-8")
                     if entry.filename in modified else source.read(entry))
            result.writestr(entry, value)
    derivative = output.getvalue()
    _validate_derivative_package(derivative)
    return derivative


def decide_document_revisions(
    original: bytes, *, expected_sha256: str, decisions: Sequence[DocumentRevisionDecision],
) -> bytes:
    """Accept or reject simple Word text insertions/deletions by exact part and id.

    Existing unknown revision types or nested revision elements are not silently
    normalized. The client cannot decide a revision absent from source bytes.
    """
    _check_source(original, expected_sha256)
    if not 1 <= len(decisions) <= MAX_EDITS:
        raise ValueError("invalid revision decision count")
    changed: dict[str, Any] = {}
    seen: set[tuple[str, int]] = set()
    for decision in decisions:
        if (not isinstance(decision, DocumentRevisionDecision)
                or type(decision.revision_id) is not int
                or not 0 <= decision.revision_id <= 2_000_000_000
                or decision.action not in ("accept", "reject")):
            raise ValueError("invalid revision decision")
        key = (decision.part, decision.revision_id)
        if key in seen:
            raise ValueError("duplicate revision decision")
        seen.add(key)
        doc = changed.setdefault(decision.part, _open_story(original, decision.part))
        nodes = [node for tag in ("ins", "del") for node in doc.getElementsByTagNameNS(W, tag)
                 if node.getAttributeNS(W, "id") == str(decision.revision_id)]
        if len(nodes) != 1:
            raise ValueError("missing or ambiguous Word revision")
        node = nodes[0]
        parent = node.parentNode
        if not _is(parent, "p"):
            raise ValueError("nested revision unsupported")
        runs = _elements(node)
        if not runs or any(not _is(child, "r") for child in runs):
            raise ValueError("complex revision unsupported")
        for run in runs:
            if any(not (_is(child, "rPr") or _is(child, "t") or _is(child, "delText"))
                   for child in _elements(run)):
                raise ValueError("unsupported revision run")
        keep = ((decision.action == "accept" and _is(node, "ins"))
                or (decision.action == "reject" and _is(node, "del")))
        if keep:
            for run in runs:
                copy = run.cloneNode(True)
                for removed in copy.getElementsByTagNameNS(W, "delText"):
                    replacement = doc.createElementNS(W, "w:t")
                    while removed.firstChild:
                        replacement.appendChild(removed.firstChild)
                    replacement.setAttributeNS(XML, "xml:space", "preserve")
                    removed.parentNode.replaceChild(replacement, removed)
                parent.insertBefore(copy, node)
        parent.removeChild(node)
    output = io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source, ZipFile(output, "w", ZIP_DEFLATED) as result:
        for entry in source.infolist():
            result.writestr(entry, changed[entry.filename].toxml(encoding="utf-8")
                            if entry.filename in changed else source.read(entry))
    derivative = output.getvalue()
    _validate_derivative_package(derivative)
    return derivative
