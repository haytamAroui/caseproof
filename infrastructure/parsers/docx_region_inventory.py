"""Fail-closed DOCX story-region inventory. Discovery is not text extraction.

Uses bounded ZIP metadata and stdlib XML; never executes embedded content.
A discovered region is not marked scanned by this inventory adapter.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from zipfile import BadZipFile, ZipFile

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_PACKAGE_BYTES = 25_000_000
MAX_PART_BYTES = 8_000_000
MAX_TOTAL_UNCOMPRESSED = 80_000_000
MAX_PARTS = 1000


class RegionStatus(StrEnum):
    UNSCANNED = "UNPROCESSED_REGION"
    UNSUPPORTED = "UNSUPPORTED_REGION"
    REVISION_UNRESOLVED = "REVISION_STATE_UNRESOLVED"


@dataclass(frozen=True)
class DocxRegion:
    part: str
    kind: str
    status: RegionStatus
    reason: str


@dataclass(frozen=True)
class DocxCoverage:
    regions: tuple[DocxRegion, ...]
    coverage_unknown: bool
    reason: str | None = None

    @property
    def regions_discovered(self) -> int:
        return len(self.regions)

    @property
    def regions_scanned(self) -> int:
        return 0

    @property
    def full_coverage(self) -> bool:
        return False


def _kind(name: str) -> str | None:
    if name == "word/document.xml":
        return "MAIN_BODY"
    if name.startswith("word/header") and name.endswith(".xml"):
        return "HEADER"
    if name.startswith("word/footer") and name.endswith(".xml"):
        return "FOOTER"
    if name == "word/footnotes.xml":
        return "FOOTNOTE"
    if name == "word/endnotes.xml":
        return "ENDNOTE"
    if name == "word/comments.xml":
        return "COMMENT_EXCLUDED"
    if name.startswith("word/") and name.endswith(".xml"):
        return "UNKNOWN_WORD_PART"
    return None


def inventory_docx_regions(payload: bytes) -> DocxCoverage:
    if len(payload) > MAX_PACKAGE_BYTES:
        return DocxCoverage((), True, "PACKAGE_TOO_LARGE")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_PARTS:
                return DocxCoverage((), True, "TOO_MANY_PARTS")
            if sum(info.file_size for info in infos) > MAX_TOTAL_UNCOMPRESSED:
                return DocxCoverage((), True, "UNCOMPRESSED_LIMIT")
            names = [info.filename for info in infos]
            if any(info.flag_bits & 1 for info in infos):
                return DocxCoverage((), True, "ENCRYPTED_ZIP_ENTRY")
            if len(set(names)) != len(names):
                return DocxCoverage((), True, "DUPLICATE_ZIP_ENTRY")
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                return DocxCoverage((), True, "NOT_DOCX")
            regions: list[DocxRegion] = []
            for info in infos:
                name = info.filename
                if name.startswith("/") or "\\" in name or ".." in name.split("/"):
                    return DocxCoverage((), True, "UNSAFE_PART_PATH")
                kind = _kind(name)
                if kind is None:
                    continue
                if info.file_size > MAX_PART_BYTES:
                    return DocxCoverage(tuple(regions), True, "PART_TOO_LARGE")
                if kind == "COMMENT_EXCLUDED":
                    regions.append(DocxRegion(name, kind, RegionStatus.UNSUPPORTED, "EXCLUDED_FROM_FILED_BODY"))
                    continue
                if kind == "UNKNOWN_WORD_PART":
                    regions.append(DocxRegion(name, kind, RegionStatus.UNSUPPORTED, "UNKNOWN_STORY_PART"))
                    continue
                xml = archive.read(info)
                if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    return DocxCoverage(tuple(regions), True, "DTD_FORBIDDEN")
                root = ET.fromstring(xml)
                revisions = any(node.tag in {
                    WORD_NS + "ins", WORD_NS + "del", WORD_NS + "moveFrom", WORD_NS + "moveTo"
                } for node in root.iter())
                if revisions:
                    regions.append(DocxRegion(name, kind, RegionStatus.REVISION_UNRESOLVED, "FROZEN_VIEW_REQUIRED"))
                else:
                    regions.append(DocxRegion(name, kind, RegionStatus.UNSCANNED, "TEXT_NOT_YET_SCANNED"))
                if any(node.tag in {
                    WORD_NS + "txbxContent", WORD_NS + "altChunk", WORD_NS + "drawing",
                    WORD_NS + "pict", WORD_NS + "object", WORD_NS + "fldChar",
                    WORD_NS + "fldSimple", WORD_NS + "instrText",
                } for node in root.iter()):
                    regions.append(DocxRegion(name + "#structured", "STRUCTURED_CONTENT", RegionStatus.UNSUPPORTED, "UNSUPPORTED_STRUCTURED_CONTENT"))
            return DocxCoverage(tuple(regions), False)
    except (BadZipFile, ET.ParseError, OSError, RuntimeError, ValueError):
        return DocxCoverage((), True, "UNREADABLE_PACKAGE")
