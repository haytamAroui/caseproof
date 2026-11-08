"""Bounded claim-unit *candidates* from supported, preserved DOCX text regions.

This is deterministic discovery only; no sentence/proposition completeness,
original-page coordinate guarantee, semantic assessment or source support claim.
The DOCX original remains authoritative; text spans are representation-local.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

from domains.disputes.reference_detection import detect_exhibit_references
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

CLAIM_DISCOVERY_VERSION = "caseproof-claim-candidates-v2"
SEGMENTATION_VERSION = "nl-fr-conservative-segments-v2"
MAX_CANDIDATES = 256
MAX_CANDIDATE_CHARS = 1200
MAX_RESPONSE_CHARS = 160_000

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9])")
_PARAGRAPH = re.compile(r"[^\n]+")
_NUMBER = re.compile(r"(?<![\w])\d+(?:[.,]\d+)*(?![\w])")
_DATE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{4})\b")
_NAME_CANDIDATE = re.compile(
    r"\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[-'][A-ZÀ-ÖØ-Þ]?[a-zà-öø-ÿ]+)?"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,2}\b"
)
_ABBREVIATIONS = frozenset({
    "art", "arts", "m", "mme", "mlle", "mr", "mrs", "me", "dr", "prof",
    "nr", "nrs", "no", "nos", "p", "pp", "blz", "pag", "par", "al",
    "bv", "bijv", "cf", "ref", "fig", "doc", "st", "etc", "dhr", "mevr",
})


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    claim_id: str
    region: str
    region_sha256: str
    segmentation_version: str
    start: int
    end: int
    text: str
    numbers: tuple[str, ...]
    dates: tuple[str, ...]
    name_candidates: tuple[str, ...]
    exhibit_references: tuple[str, ...]
    boundary_quality: str = "heuristic_not_adjudicated"
    claim_classification: str = "not_assessed"
    semantic_support: str = "not_assessed"
    source_link_status: str = "not_searched"


@dataclass(frozen=True, slots=True)
class ClaimDiscovery:
    original_sha256: str
    version: str
    candidates: tuple[ClaimCandidate, ...]
    coverage: dict[str, Any]

    def response(self) -> dict[str, Any]:
        return {
            "schema": self.version,
            "original_sha256": self.original_sha256,
            "segmentation_version": SEGMENTATION_VERSION,
            "candidates": [asdict(candidate) for candidate in self.candidates],
            "coverage": self.coverage,
        }


def _abbreviation_before_boundary(line: str, space_start: int) -> bool:
    """Don't split on known NL/FR abbreviations; never infer legal semantics."""
    prefix = line[:space_start].rstrip()
    if not prefix.endswith("."):
        return False
    token = re.search(r"([^\W\d_]+)\.$", prefix, re.UNICODE)
    return token is not None and token.group(1).casefold() in _ABBREVIATIONS


def _sentences(text: str) -> list[tuple[int, int]]:
    """Return derived-text region offsets with conservative legal punctuation."""
    spans: list[tuple[int, int]] = []
    for paragraph in _PARAGRAPH.finditer(text):
        line = paragraph.group(0)
        cuts = [0]
        for match in _SENTENCE_BREAK.finditer(line):
            if not _abbreviation_before_boundary(line, match.start()):
                cuts.append(match.end())
        cuts.append(len(line))
        for first, last in zip(cuts, cuts[1:], strict=False):
            fragment = line[first:last]
            leading = len(fragment) - len(fragment.lstrip())
            trailing = len(fragment.rstrip())
            if trailing <= leading:
                continue
            start = paragraph.start() + first + leading
            end = paragraph.start() + first + trailing
            spans.append((start, end))
    return spans


def discover_docx_claim_candidates(payload: bytes) -> ClaimDiscovery:
    """Return bounded candidate spans without promoting them to legal findings.

    A derived-text span is not an OOXML byte or Word range; source/parse changes
    require stale detection and independent review before citation insertion.
    """
    extracted = extract_docx_text_regions(payload)
    original_sha256 = hashlib.sha256(payload).hexdigest()
    candidates: list[ClaimCandidate] = []
    omitted = 0
    emitted_chars = 0
    for region in extracted.regions:
        region_sha256 = hashlib.sha256(region.text.encode()).hexdigest()
        for start, end in _sentences(region.text):
            statement = region.text[start:end]
            if (len(statement) > MAX_CANDIDATE_CHARS
                    or len(candidates) >= MAX_CANDIDATES
                    or emitted_chars + len(statement) > MAX_RESPONSE_CHARS):
                omitted += 1
                continue
            identity = hashlib.sha256(
                f"{CLAIM_DISCOVERY_VERSION}\0{SEGMENTATION_VERSION}\0{original_sha256}"
                f"\0{region.part}\0{region_sha256}\0{start}\0{end}\0{statement}".encode()
            ).hexdigest()
            candidates.append(
                ClaimCandidate(
                    claim_id="claim-" + identity[:24],
                    region=region.part,
                    region_sha256=region_sha256,
                    segmentation_version=SEGMENTATION_VERSION,
                    start=start,
                    end=end,
                    text=statement,
                    numbers=tuple(m.group(0) for m in _NUMBER.finditer(statement)),
                    dates=tuple(m.group(0) for m in _DATE.finditer(statement)),
                    name_candidates=tuple(m.group(0) for m in _NAME_CANDIDATE.finditer(statement)),
                    exhibit_references=tuple(
                        r.raw for r in detect_exhibit_references(statement, region=region.part)
                    ),
                )
            )
            emitted_chars += len(statement)
    manifest = extracted.manifest
    coverage: dict[str, Any] = {
        "status": "partial" if (not extracted.coverage_complete or omitted) else "text_scanned",
        "text_coverage_complete": extracted.coverage_complete,
        "factual_claim_recall_measured": False,
        "claim_review_coverage_measured": False,
        "claim_semantics_assessed": False,
        "candidate_count": len(candidates),
        "omitted_candidate_segments": omitted,
        "unscanned_parts": list(extracted.unscanned_parts),
        "regions_discovered": manifest.get("regions_discovered", 0),
        "regions_scanned": manifest.get("regions_scanned", 0),
        "scope": "supported_docx_text_regions_only",
        "boundary_quality": "heuristic_not_adjudicated",
    }
    return ClaimDiscovery(original_sha256, CLAIM_DISCOVERY_VERSION, tuple(candidates), coverage)
