"""Bounded text extraction for selected DOCX regions with explicit omissions.

Not a malware sandbox. Does not claim full document-wide reference recall.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from io import BytesIO
from zipfile import ZipFile

from infrastructure.parsers.docx_region_inventory import (
    MAX_PACKAGE_BYTES,
    MAX_PART_BYTES,
    MAX_PARTS,
    MAX_TOTAL_UNCOMPRESSED,
    WORD_NS,
    inventory_docx_regions,
    word_on_off_enabled,
)

_BLOCKED = {WORD_NS + tag for tag in ("txbxContent", "drawing", "pict", "object", "altChunk", "fldSimple", "instrText")}


@dataclass(frozen=True)
class TextRegion:
    part: str
    text: str


@dataclass(frozen=True)
class DocxTextExtraction:
    regions: tuple[TextRegion, ...]
    unscanned_parts: tuple[str, ...]
    coverage_complete: bool
    manifest: dict[str, object] = field(default_factory=dict)


def extract_docx_text_regions(payload: bytes) -> DocxTextExtraction:
    coverage = inventory_docx_regions(payload)
    if coverage.coverage_unknown or len(payload) > MAX_PACKAGE_BYTES:
        return DocxTextExtraction((), ("COVERAGE_UNKNOWN",), False, {"coverage_unknown": True, "reason": coverage.reason, "regions": [], "regions_discovered": 0, "regions_scanned": 0})
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
            pending = [root]
            while pending:
                node = pending.pop()
                if node.tag in _BLOCKED:
                    continue
                if node.tag == WORD_NS + "p":
                    fragments: list[str] = []
                    children = [node]
                    while children:
                        child = children.pop()
                        if child.tag in _BLOCKED or (child.tag == WORD_NS + "r" and
                                word_on_off_enabled(child.find("./" + WORD_NS + "rPr/" + WORD_NS + "vanish"))):
                            continue
                        if child.tag == WORD_NS + "t":
                            fragments.append(child.text or "")
                        else:
                            children.extend(reversed(list(child)))
                    if fragments:
                        paragraphs.append("".join(fragments))
                else:
                    pending.extend(reversed(list(node)))
            extracted.append(TextRegion(region.part, "\n".join(paragraphs)))
    # A parsed paragraph stream is not proof that all Word story content was read.
    # Unknown/structured parts, revisions and an absent main body must keep
    # reference-discovery coverage explicitly incomplete.
    scanned_main = any(region.part == "word/document.xml" for region in extracted)
    complete = scanned_main and not unscanned and not coverage.coverage_unknown
    scanned = {r.part for r in extracted}
    ledger = [{"part": r.part, "kind": r.kind,
               "status": "SCANNED" if r.part in scanned else r.status.value,
               "reason": "TEXT_SCANNED_RECALL_UNMEASURED" if r.part in scanned else r.reason}
              for r in coverage.regions]
    manifest: dict[str, object] = {
        "coverage_unknown": False, "regions_discovered": len(ledger),
        "regions_scanned": len(scanned), "regions_supported": sum(r.kind in {
            "MAIN_BODY", "HEADER", "FOOTER", "FOOTNOTE", "ENDNOTE"} for r in coverage.regions),
        "regions_unprocessed": sum(r["status"] in {"UNPROCESSED_REGION", "REVISION_STATE_UNRESOLVED"} for r in ledger),
        "regions_unsupported": sum(r["status"] == "UNSUPPORTED_REGION" for r in ledger),
        "regions": ledger, "text_coverage_complete": complete, "reference_recall_measured": False,
    }
    return DocxTextExtraction(tuple(extracted), tuple(unscanned), complete, manifest)
