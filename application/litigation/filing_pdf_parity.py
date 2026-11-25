"""Deterministic pre-filing parity check: verified DOCX snapshot vs. final filing PDF text layer.

Addresses the Farhat v. Cutera, Inc. workflow failure (converting an older/uncorrected draft
to PDF at court-filing handoff) strictly within Step 3 Pre-Filing Truth Audit scope:
- 0% LLM, stdlib-only deterministic token comparison + bounded contextual diff hunks.
- Fail-closed CANNOT_VERIFY (OCR_UNRELIABLE) whenever any PDF page has no extractable text.
- Never claims visual layout equivalence, legal validity, qualified signature, or filing proof.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

PARITY_SCHEMA = "caseproof-filing-pdf-parity-v1"
MAX_DIFF_HUNKS = 20
MAX_EXCERPT_CHARS = 240
CONTEXT_TOKENS = 6

BASE_LIMITATIONS = (
    "Deterministic text-layer comparison only; visual layout, headers/footers, embedded images, and scanned pages are not certified.",
    "Not a qualified electronic signature (eIDAS QES), constat d'huissier, or proof of court filing.",
)

_OCR_WARNING_PREFIX = "pdf_page_needs_ocr_or_review:page:"


def normalize_filing_text(text: str) -> str:
    """Normalize benign Unicode punctuation, soft hyphens, and whitespace without dropping words or numbers."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = (
        normalized.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u00ad", "")
    )
    return re.sub(r"\s+", " ", normalized).strip()


def tokenize_filing_text(text: str) -> list[str]:
    """Split normalized filing text into order-preserving tokens independent of line breaks."""
    cleaned = normalize_filing_text(text)
    return cleaned.split() if cleaned else []


def _truncate_excerpt(tokens: Sequence[str], *, limit: int = MAX_EXCERPT_CHARS) -> str:
    joined = " ".join(tokens)
    if len(joined) <= limit:
        return joined
    return joined[: limit - 1].rstrip() + "…"


def _excerpt_window(tokens: Sequence[str], start: int, end: int) -> str:
    lo = max(0, start - CONTEXT_TOKENS)
    hi = min(len(tokens), end + CONTEXT_TOKENS)
    window: list[str] = []
    if lo > 0:
        window.append("…")
    window.extend(tokens[lo:hi])
    if hi < len(tokens):
        window.append("…")
    return _truncate_excerpt(window)


def compare_verified_docx_and_filing_pdf(
    *,
    case_id: str,
    brief_id: str,
    snapshot_hash: str,
    verified_docx_sha256: str,
    filing_pdf_sha256: str,
    filing_pdf_byte_length: int,
    docx_text: str,
    docx_coverage_complete: bool,
    docx_unscanned_parts: Sequence[str],
    pdf_pages: Sequence[str],
    pdf_warnings: Sequence[str] = (),
) -> dict[str, Any]:
    """Compare verified DOCX text against extracted per-page filing PDF text deterministically."""
    empty_indices = {i for i, page_text in enumerate(pdf_pages) if not normalize_filing_text(page_text)}
    for warning in pdf_warnings:
        if warning.startswith(_OCR_WARNING_PREFIX):
            suffix = warning[len(_OCR_WARNING_PREFIX) :]
            if suffix.isdigit():
                empty_indices.add(int(suffix))
    pdf_pages_without_text = sorted(i for i in empty_indices if 0 <= i < len(pdf_pages))

    docx_tokens = tokenize_filing_text(docx_text)
    pdf_tokens = tokenize_filing_text("\n".join(pdf_pages))

    reason_codes: list[str] = []
    limitations: list[str] = list(BASE_LIMITATIONS)
    if not docx_coverage_complete:
        reason_codes.append("DOCX_COVERAGE_PARTIAL")
        limitations.append(
            "Verified DOCX coverage is partial; unscanned or unsupported Word story regions are excluded from parity comparison."
        )
    if any(
        w.startswith("pdf_visual_objects_require_review") or w.startswith("pdf_annotations_unprocessed")
        for w in pdf_warnings
    ):
        reason_codes.append("PDF_CONTAINS_VISUAL_OR_ANNOTATION_OBJECTS")
        limitations.append(
            "Filing PDF contains visual XObjects or annotations that are not inspected by deterministic text-layer parity."
        )

    diffs: list[dict[str, Any]] = []
    diff_count = 0
    diff_truncated = False

    if not pdf_pages or not pdf_tokens or pdf_pages_without_text:
        status = "CANNOT_VERIFY"
        reason_codes.extend(["OCR_UNRELIABLE", "PDF_TEXT_LAYER_EMPTY_OR_IMAGE_ONLY"])
    elif not docx_tokens:
        status = "CANNOT_VERIFY"
        reason_codes.append("DOCX_TEXT_EMPTY")
    else:
        matcher = difflib.SequenceMatcher(None, docx_tokens, pdf_tokens, autojunk=False)
        opcodes = [op for op in matcher.get_opcodes() if op[0] != "equal"]
        if not opcodes:
            status = "MATCH_OBSERVED"
            reason_codes.append("TEXT_PARITY_MATCH")
        else:
            status = "MISMATCH_DETECTED"
            reason_codes.append("TEXT_MISMATCH_DETECTED")
            diff_count = len(opcodes)
            diff_truncated = diff_count > MAX_DIFF_HUNKS
            for tag, i1, i2, j1, j2 in opcodes[:MAX_DIFF_HUNKS]:
                diffs.append(
                    {
                        "op": tag,
                        "docx_token_index": i1,
                        "pdf_token_index": j1,
                        "docx_excerpt": _excerpt_window(docx_tokens, i1, i2),
                        "pdf_excerpt": _excerpt_window(pdf_tokens, j1, j2),
                        "docx_changed": _truncate_excerpt(docx_tokens[i1:i2]),
                        "pdf_changed": _truncate_excerpt(pdf_tokens[j1:j2]),
                    }
                )

    return {
        "schema": PARITY_SCHEMA,
        "case_id": case_id,
        "brief_id": brief_id,
        "snapshot_hash": snapshot_hash,
        "verified_docx_sha256": verified_docx_sha256,
        "filing_pdf_sha256": filing_pdf_sha256,
        "filing_pdf_byte_length": filing_pdf_byte_length,
        "filing_pdf_page_count": len(pdf_pages),
        "status": status,
        "reason_codes": reason_codes,
        "docx_token_count": len(docx_tokens),
        "pdf_token_count": len(pdf_tokens),
        "docx_coverage_complete": bool(docx_coverage_complete),
        "docx_unscanned_parts": list(docx_unscanned_parts),
        "pdf_pages_without_text": pdf_pages_without_text,
        "pdf_warnings": list(pdf_warnings),
        "diff_count": diff_count,
        "diff_truncated": diff_truncated,
        "diffs": diffs,
        "limitations": limitations,
    }
