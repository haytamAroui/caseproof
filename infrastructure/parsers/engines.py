"""Parser implementations. Invoke through LimitedDocumentParser in a bounded child."""

from __future__ import annotations

import io
import re
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
        resources = page.get("/Resources", {})
        if hasattr(resources, "get_object"):
            resources = resources.get_object()
        objects = resources.get("/XObject", {})
        if hasattr(objects, "get_object"):
            objects = objects.get_object()
        if objects:
            # Images and nested form XObjects can contain material not recovered by text extraction.
            builder.warnings.add("pdf_visual_objects_require_review")
        stream = page.get_contents()
        if stream is not None and len(stream.get_data()) > 2 * 1024 * 1024:
            raise ExtractionError("pdf_decoded_stream_limit")
        extracted = page.extract_text(extraction_mode="plain")
        if not extracted.strip():
            builder.warnings.add("pdf_page_needs_ocr_or_review")
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


def parse_bytes(raw: bytes, media_type: str) -> dict[str, Any]:
    if media_type == "application/pdf":
        return parse_pdf(raw)
    if media_type in {"application/xml", "text/xml"}:
        return parse_xml(raw)
    if media_type == "message/rfc822":
        return parse_email(raw)
    if media_type == "text/plain":
        b = Builder("python:utf8-identity-v1")
        b.add(raw.decode("utf-8", errors="strict"), "text", "text:0")
        return b.result()
    raise ExtractionError("unsupported_media_type")
