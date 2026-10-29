"""Bounded text extraction for selected DOCX regions with explicit omissions.

Not a malware sandbox. Does not claim full document-wide reference recall.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO
from zipfile import ZipFile

from infrastructure.parsers.docx_region_inventory import (
    MAX_PACKAGE_BYTES,
    MAX_PART_BYTES,
    MAX_PARTS,
    MAX_TOTAL_UNCOMPRESSED,
    WORD_NS,
    inventory_docx_regions,
)


@dataclass(frozen=True)
class TextRegion:
    part: str
    text: str


@dataclass(frozen=True)
class DocxTextExtraction:
    regions: tuple[TextRegion, ...]
    unscanned_parts: tuple[str, ...]
    coverage_complete: bool


def extract_docx_text_regions(payload: bytes) -> DocxTextExtraction:
    coverage = inventory_docx_regions(payload)
    if coverage.coverage_unknown or len(payload) > MAX_PACKAGE_BYTES:
        return DocxTextExtraction((), ("COVERAGE_UNKNOWN",), False)
    extracted: list[TextRegion] = []
    unscanned: list[str] = []
    with ZipFile(BytesIO(payload)) as archive:
        # Re-validate package identity before reading XML; inventory alone is not a parser sandbox.
        infos = archive.infolist()
        if len(infos) > MAX_PARTS or sum(i.file_size for i in infos) > MAX_TOTAL_UNCOMPRESSED:
            return DocxTextExtraction((), ("LIMIT_EXCEEDED",), False)
        for region in coverage.regions:
            if region.kind not in {"MAIN_BODY", "HEADER", "FOOTER", "FOOTNOTE", "ENDNOTE"}:
                unscanned.append(region.part)
                continue
            if region.status.value != "UNPROCESSED_REGION":
                unscanned.append(region.part)
                continue
            info = archive.getinfo(region.part)
            if info.file_size > MAX_PART_BYTES:
                unscanned.append(region.part)
                continue
            xml = archive.read(info)
            if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                unscanned.append(region.part)
                continue
            try:
                root = ET.fromstring(xml)
            except ET.ParseError:
                unscanned.append(region.part)
                continue
            # Only plain paragraph text. Nested tables are traversed by paragraph order.
            # Hyperlink text is included; field results, revisions and shapes are not certified.
            paragraphs: list[str] = []
            for node in root.iter():
                if node.tag == WORD_NS + "p":
                    fragments = [
                        child.text or ""
                        for child in node.iter()
                        if child.tag == WORD_NS + "t"
                    ]
                    if fragments:
                        paragraphs.append("".join(fragments))
            extracted.append(TextRegion(region.part, "\n".join(paragraphs)))
    # A parsed paragraph stream is not proof that all Word story content was read.\n    # Unknown/structured parts, revisions and an absent main body must keep\n    # reference-discovery coverage explicitly incomplete.\n    scanned_main = any(region.part == "word/document.xml" for region in extracted)\n    complete = scanned_main and not unscanned and not coverage.coverage_unknown\n    return DocxTextExtraction(tuple(extracted), tuple(unscanned), complete)
