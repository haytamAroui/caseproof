"""Bounded parser adapter for Final Filing PDF vs. verified DOCX snapshot parity."""

from __future__ import annotations

import hashlib
import io
from typing import Any

from pypdf import PdfReader

from application.extraction.contracts import ExtractionError
from application.litigation.filing_pdf_parity import compare_verified_docx_and_filing_pdf
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions
from infrastructure.parsers.engines import parse_pdf

MAX_FILING_PDF_BYTES = 10 * 1024 * 1024


def check_filing_pdf_parity(
    *,
    original_docx: bytes,
    filing_pdf: bytes,
    case_id: str,
    brief_id: str,
    snapshot_hash: str,
) -> dict[str, Any]:
    """Validate bounded PDF/DOCX bytes and run deterministic text-layer parity comparison."""
    if not 0 < len(filing_pdf) <= MAX_FILING_PDF_BYTES:
        raise ExtractionError("pdf_size_limit")

    parsed_pdf = parse_pdf(filing_pdf)
    reader = PdfReader(io.BytesIO(filing_pdf), strict=True)
    page_count = len(reader.pages)
    page_texts = [""] * page_count
    for block in parsed_pdf.get("blocks", ()):
        idx = block.get("page_index")
        if isinstance(idx, int) and 0 <= idx < page_count:
            chunk = parsed_pdf["text"][block["start"] : block["end"]]
            page_texts[idx] = f"{page_texts[idx]}\n{chunk}" if page_texts[idx] else chunk

    docx_extraction = extract_docx_text_regions(original_docx)
    docx_text = "\n\n".join(region.text for region in docx_extraction.regions if region.text)

    return compare_verified_docx_and_filing_pdf(
        case_id=case_id,
        brief_id=brief_id,
        snapshot_hash=snapshot_hash,
        verified_docx_sha256=hashlib.sha256(original_docx).hexdigest(),
        filing_pdf_sha256=hashlib.sha256(filing_pdf).hexdigest(),
        filing_pdf_byte_length=len(filing_pdf),
        docx_text=docx_text,
        docx_coverage_complete=docx_extraction.coverage_complete,
        docx_unscanned_parts=docx_extraction.unscanned_parts,
        pdf_pages=page_texts,
        pdf_warnings=parsed_pdf.get("warnings", ()),
    )
