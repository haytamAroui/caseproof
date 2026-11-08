"""Conservative, model-free factual-claim candidate inventory from a preserved DOCX.

This is *discovery*, not a claim classifier, semantic verifier, source linker,
or completeness certification. The existing DOCX region parser owns all content
and omission decisions. Original DOCX bytes remain the authority.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

from domains.disputes.reference_detection import detect_exhibit_references
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

CLAIM_DISCOVERY_VERSION = "caseproof-claim-candidates-v1"
MAX_CANDIDATES = 256
MAX_CANDIDATE_CHARS = 1200
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9])")
_PARAGRAPH = re.compile(r"[^\n]+")
_NUMBER = re.compile(r"(?<![\w])\d+(?:[.,]\d+)*(?![\w])")
_DATE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{4})\b")
_NAME_CANDIDATE = re.compile(
    r"\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[-'][A-ZÀ-ÖØ-Þ]?[a-zà-öø-ÿ]+)?"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,2}\b"
)


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    claim_id: str
    region: str
    start: int
    end: int
    text: str
    numbers: tuple[str, ...]
    dates: tuple[str, ...]
    name_candidates: tuple[str, ...]
    exhibit_references: tuple[str, ...]
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
            "schema": CLAIM_DISCOVERY_VERSION,
            "original_sha256": self.original_sha256,
            "candidates": [asdict(candidate) for candidate in self.candidates],
            "coverage": self.coverage,
        }


def _sentences(text: str) -> list[tuple[int, int]]:
    """Return text-region-local character spans. Split only obvious boundaries."""
    spans: list[tuple[int, int]] = []
    for paragraph in _PARAGRAPH.finditer(text):
        line = paragraph.group(0)
        cuts = [0, *(m.end() for m in _SENTENCE_BREAK.finditer(line)), len(line)]
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
    """Discover candidates but never declare them verified or fully recalled.

    Output is bounded. Skipped/unscanned text is explicit and cannot be
    interpreted as an empty or complete evidence universe.
    """
    extracted = extract_docx_text_regions(payload)
    original_sha256 = hashlib.sha256(payload).hexdigest()
    candidates: list[ClaimCandidate] = []
    omitted = 0
    for region in extracted.regions:
        for start, end in _sentences(region.text):
            statement = region.text[start:end]
            if len(statement) > MAX_CANDIDATE_CHARS or len(candidates) >= MAX_CANDIDATES:
                omitted += 1
                continue
            identity = hashlib.sha256(
                f"{original_sha256}\0{region.part}\0{start}\0{end}\0{statement}".encode("utf-8")
            ).hexdigest()
            candidates.append(
                ClaimCandidate(
                    claim_id="claim-" + identity[:24],
                    region=region.part,
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
    manifest = extracted.manifest
    coverage: dict[str, Any] = {
        "status": "partial" if (not extracted.coverage_complete or omitted) else "text_scanned",
        "text_coverage_complete": extracted.coverage_complete,
        "factual_claim_recall_measured": False,
        "claim_semantics_assessed": False,
        "candidate_count": len(candidates),
        "omitted_candidate_segments": omitted,
        "unscanned_parts": list(extracted.unscanned_parts),
        "regions_discovered": manifest.get("regions_discovered", 0),
        "regions_scanned": manifest.get("regions_scanned", 0),
        "scope": "supported_docx_text_regions_only",
    }
    return ClaimDiscovery(original_sha256, CLAIM_DISCOVERY_VERSION, tuple(candidates), coverage)
