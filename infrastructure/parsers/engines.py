"""Parser implementations. Invoke through LimitedDocumentParser in a bounded child."""

from __future__ import annotations

import io
import re
import stat
import zipfile
from collections import defaultdict
from email import policy
from email.parser import BytesParser
from typing import Any

from defusedxml import ElementTree as SafeXML  # type: ignore[import-untyped]
from pypdf import PdfReader
from pypdf import __version__ as PDF_VERSION

from application.documents.contracts import MAX_BLOCKS, MAX_TEXT_CHARS, PARSER_SCHEMA
from application.extraction.contracts import ExtractionError


class Builder:
    def __init__(self, parser: str) -> None:
        self.parser = parser
        self.parts: list[str] = []
        self.blocks: list[dict[str, Any]] = []
        self.warnings: set[str] = set()
        self.fields: list[list[str]] = []
        self.size = 0

    def add(self, content: str, kind: str, locator: str, page_index: int | None = None) -> None:
        if not content:
            return
        start = self.size + (2 if self.parts else 0)
        if len(self.blocks) >= MAX_BLOCKS or start + len(content) > MAX_TEXT_CHARS:
            raise ExtractionError("parser_output_limit")
        self.parts.append(content)
        self.blocks.append(
            {
                "block_id": f"block:{len(self.blocks)}",
                "start": start,
                "end": start + len(content),
                "kind": kind,
                "locator": locator,
                "page_index": page_index,
            }
        )
        self.size = start + len(content)

    def result(self) -> dict[str, Any]:
        if not self.blocks:
            self.warnings.add("no_extractable_text")
        return {
            "schema": PARSER_SCHEMA,
            "text": "\n\n".join(self.parts),
            "blocks": self.blocks,
            "parser_id": self.parser,
            "complete": not self.warnings,
            "warnings": sorted(self.warnings),
            "fields": self.fields,
        }


def parse_pdf(raw: bytes) -> dict[str, Any]:
    if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-2048:]:
        raise ExtractionError("pdf_signature_or_truncation")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        raise ExtractionError("encrypted_pdf_unsupported")
    if not 1 <= len(reader.pages) <= 64:
        raise ExtractionError("pdf_page_limit")
    root: Any = reader.trailer["/Root"]
    if any(k in root for k in ("/OpenAction", "/AA", "/AcroForm", "/AF")):
        raise ExtractionError("active_or_form_pdf_unsupported")
    names = root.get("/Names", {})
    if hasattr(names, "get_object"):
        names = names.get_object()
    if any(k in names for k in ("/JavaScript", "/EmbeddedFiles")):
        raise ExtractionError("active_or_embedded_pdf_unsupported")
    builder = Builder("pypdf:" + PDF_VERSION + ":page-text-v1")
    for i, page in enumerate(reader.pages):
        if "/AA" in page or "/AF" in page:
            raise ExtractionError("active_pdf_page_unsupported")
        if page.get("/Annots"):
            builder.warnings.add("pdf_annotations_unprocessed")
            builder.warnings.add(f"pdf_annotations_unprocessed:page:{i}")
        resources = page.get("/Resources", {})
        if hasattr(resources, "get_object"):
            resources = resources.get_object()
        objects = resources.get("/XObject", {})
        if hasattr(objects, "get_object"):
            objects = objects.get_object()
        if objects:
            # Images and nested form XObjects can contain material not recovered by text extraction.
            builder.warnings.add("pdf_visual_objects_require_review")
            builder.warnings.add(f"pdf_visual_objects_require_review:page:{i}")
        stream = page.get_contents()
        if stream is not None and len(stream.get_data()) > 2 * 1024 * 1024:
            raise ExtractionError("pdf_decoded_stream_limit")
        extracted = page.extract_text(extraction_mode="plain")
        if not extracted.strip():
            builder.warnings.add("pdf_page_needs_ocr_or_review")
            builder.warnings.add(f"pdf_page_needs_ocr_or_review:page:{i}")
        builder.add(extracted, "pdf_page", f"page:{i}", i)
    return builder.result()


def parse_xml(raw: bytes) -> dict[str, Any]:
    # UTF-8 only; defusedxml independently rejects DTD/entity/external declarations.
    decoded = raw.decode("utf-8", errors="strict")
    if "\x00" in decoded:
        raise ExtractionError("xml_encoding_unsupported")
    encoding = re.search(r'<\?xml[^>]*encoding\s*=\s*[\'"]([^\'"]+)', decoded, re.IGNORECASE)
    if encoding and encoding[1].lower() != "utf-8":
        raise ExtractionError("xml_encoding_unsupported")
    root = SafeXML.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    builder = Builder("defusedxml:0.7.1:expanded-path-v1")
    count = 0

    def walk(element: Any, path: str, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_BLOCKS or depth > 32:
            raise ExtractionError("xml_structure_limit")
        if element.text and element.text.strip():
            # Preserve decoded scalar whitespace; path prefixes are declared parser serialization, not original XML bytes.
            if len(element):
                builder.warnings.add("xml_mixed_content_requires_review")
            value = element.text
            builder.add(path + " = " + value, "xml_field", path)
            builder.fields.append([path, value])
        for key, value in sorted(element.attrib.items()):
            attribute = path + "/@" + key
            builder.add(attribute + " = " + value, "xml_field", attribute)
            builder.fields.append([attribute, value])
        siblings: dict[str, int] = defaultdict(int)
        for child in element:
            siblings[child.tag] += 1
            walk(child, path + "/" + child.tag + f"[{siblings[child.tag]}]", depth + 1)
            if child.tail and child.tail.strip():
                builder.warnings.add("xml_mixed_tail_content_unprocessed")

    walk(root, "/" + root.tag + "[1]", 0)
    return builder.result()


def parse_email(raw: bytes) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    builder = Builder("python-email:rfc5322-mime-v1")
    stack: list[tuple[Any, str, int]] = [(message, "mime:0", 0)]
    parts = 0
    # Headers are asserted by the email, never authenticated sender identity.
    for name in ("From", "To", "Cc", "Subject", "Date", "Message-ID", "In-Reply-To", "References"):
        values = message.get_all(name, [])
        if len(values) > 1 and name in {"From", "Subject", "Date", "Message-ID"}:
            builder.warnings.add("email_ambiguous_headers")
        for i, value in enumerate(values):
            if getattr(value, "defects", ()):
                builder.warnings.add("email_header_defects")
            builder.add(str(value), "email_header", f"header:{name.lower()}:{i}")
    while stack:
        part, locator, depth = stack.pop()
        parts += 1
        if depth > 16 or parts > 128:
            raise ExtractionError("email_structure_limit")
        if part.defects:
            builder.warnings.add("email_parser_defects")
        if part.is_multipart():
            # Attached messages are not silently merged into the parent's author/identity.
            if part.get_content_type() == "message/rfc822":
                builder.warnings.add("email_attached_message_unprocessed")
                continue
            children = list(part.iter_parts())
            stack.extend(
                (child, locator + f"/{i}", depth + 1) for i, child in reversed(list(enumerate(children)))
            )
            continue
        if part.get_content_disposition() == "attachment" or part.get_filename():
            builder.warnings.add("email_attachment_unprocessed")
            continue
        if part.get_content_type() != "text/plain":
            builder.warnings.add("email_nontext_part_unprocessed")
            continue
        try:
            payload = part.get_payload(decode=True)
            if type(payload) is not bytes:
                raise ExtractionError("invalid_email_body")
            content = payload.decode(part.get_content_charset() or "ascii", errors="strict")
        except (UnicodeError, LookupError):
            builder.warnings.add("email_charset_unresolved")
            continue
        # Decoding may add defects (e.g. malformed base64); inspect again.
        if part.defects:
            builder.warnings.add("email_parser_defects")
        builder.add(content, "email_body", locator)
    return builder.result()



DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_paragraph_text(paragraph: Any) -> str:
    """Keep literal run separators; never flatten nested paragraphs into a quote."""
    if any(node is not paragraph and node.tag == _W + "p" for node in paragraph.iter()):
        raise ExtractionError("docx_nested_paragraph_unsupported")
    parts: list[str] = []
    for token in paragraph.iter():
        if token.tag == _W + "t":
            parts.append(token.text or "")
        elif token.tag == _W + "tab":
            parts.append("\\t")
        elif token.tag in {_W + "br", _W + "cr"}:
            parts.append("\\n")
    return "".join(parts)


def parse_docx(raw: bytes) -> dict[str, Any]:
    """Resource-bounded DOCX text, NOT Word layout or trustworthy printed page mapping."""
    if not raw.startswith(b"PK\x03\x04"):
        raise ExtractionError("docx_signature_required")
    builder = Builder("python-zipfile:defusedxml:docx-text-v1")
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r", allowZip64=False) as archive:
            entries = archive.infolist()
            if not 2 <= len(entries) <= 128:
                raise ExtractionError("docx_entry_limit")
            if len({part.filename for part in entries}) != len(entries):
                raise ExtractionError("docx_duplicate_entries")
            if sum(part.file_size for part in entries) > 8 * 1024 * 1024:
                raise ExtractionError("docx_decompressed_limit")
            for part in entries:
                name = part.filename
                if (
                    name.startswith("/") or "\\" in name or ".." in name.split("/")
                    or (name.endswith("/") and part.file_size)
                    or stat.S_IFMT(part.external_attr >> 16) == stat.S_IFLNK
                    or part.flag_bits & 1
                    or part.file_size > 2 * 1024 * 1024
                    or part.file_size > max(part.compress_size, 1) * 80
                ):
                    raise ExtractionError("docx_unsafe_archive")
                lower = name.lower()
                if (
                    "vbaproject" in lower or "activex" in lower
                    or lower.startswith("word/embeddings/") or lower.endswith(".bin")
                ):
                    raise ExtractionError("docx_active_or_embedded_unsupported")
            names = {part.filename for part in entries}
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise ExtractionError("docx_document_part_required")
            for name in sorted(n for n in names if n.endswith(".rels")):
                rels = SafeXML.fromstring(
                    archive.read(name), forbid_dtd=True, forbid_entities=True, forbid_external=True
                )
                if any(el.attrib.get("TargetMode", "").lower() == "external" for el in rels.iter()):
                    raise ExtractionError("docx_external_relationship_unsupported")
            document = SafeXML.fromstring(
                archive.read("word/document.xml"),
                forbid_dtd=True, forbid_entities=True, forbid_external=True,
            )
            body = document.find(_W + "body")
            if body is None:
                raise ExtractionError("docx_body_required")
            if any(
                el.tag in {_W + "ins", _W + "del", _W + "moveFrom", _W + "moveTo"}
                for el in body.iter()
            ):
                builder.warnings.add("docx_tracked_changes_require_review")
            if any(el.tag in {_W + "drawing", _W + "pict", _W + "object"} for el in body.iter()):
                builder.warnings.add("docx_visual_objects_require_review")
            if any(el.tag == _W + "altChunk" for el in body.iter()):
                raise ExtractionError("docx_altchunk_unsupported")
            # Text boxes have their own reading order. Flattening nested w:p
            # would fabricate contiguous evidence and duplicate text spans.
            if any(el.tag == _W + "txbxContent" for el in body.iter()):
                raise ExtractionError("docx_textboxes_unsupported")
            for i, paragraph in enumerate(body.iter(_W + "p")):
                builder.add(
                    _docx_paragraph_text(paragraph),
                    "docx_paragraph",
                    f"docx:body:paragraph:{i}",
                )
            for kind in ("footnotes", "endnotes"):
                part_name = f"word/{kind}.xml"
                if part_name not in names:
                    continue
                tree = SafeXML.fromstring(
                    archive.read(part_name),
                    forbid_dtd=True, forbid_entities=True, forbid_external=True,
                )
                if any(el.tag == _W + "txbxContent" for el in tree.iter()):
                    raise ExtractionError("docx_textboxes_unsupported")
                for i, para in enumerate(tree.iter(_W + "p")):
                    builder.add(
                        _docx_paragraph_text(para),
                        "docx_note",
                        f"docx:{kind}:paragraph:{i}",
                    )
            if any(name.startswith("word/media/") for name in names):
                builder.warnings.add("docx_images_require_review")
            if any(name.startswith(("word/header", "word/footer", "word/comments")) for name in names):
                builder.warnings.add("docx_headers_footers_comments_unprocessed")
            if any(name.startswith("customXml/") for name in names):
                builder.warnings.add("docx_custom_xml_unprocessed")
            if any(el.tag in {_W + "instrText", _W + "fldChar"} for el in body.iter()):
                builder.warnings.add("docx_fields_require_review")
    except (zipfile.BadZipFile, EOFError, OSError):
        raise ExtractionError("docx_archive_rejected") from None
    builder.warnings.add("docx_layout_page_numbers_unverified")
    return builder.result()


def parse_bytes(raw: bytes, media_type: str) -> dict[str, Any]:
    if media_type == "application/pdf":
        return parse_pdf(raw)
    if media_type == DOCX_MIME:
        return parse_docx(raw)
    if media_type in {"application/xml", "text/xml"}:
        return parse_xml(raw)
    if media_type == "message/rfc822":
        return parse_email(raw)
    if media_type == "text/plain":
        b = Builder("python:utf8-identity-v1")
        b.add(raw.decode("utf-8", errors="strict"), "text", "text:0")
        return b.result()
    raise ExtractionError("unsupported_media_type")
