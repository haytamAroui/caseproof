"""Versioned conservative development envelope; NOT a pilot capacity approval.

These are the already-enforced four-source intake and export boundaries.
Do not infer signed full-journey support from a standalone 200-page worker test.
"""
from __future__ import annotations

from typing import Final

MAX_SOURCE_BYTES: Final[int] = 5_242_880
MAX_INTAKE_BYTES: Final[int] = 12_000_000
MAX_INVENTORY_BYTES: Final[int] = 1_048_576
MAX_PDF_PAGES: Final[int] = 64
MAX_INVENTORY_IDENTITIES: Final[int] = 512
SOURCE_COUNT: Final[int] = 4
MAX_BASE64_CHARS: Final[int] = 4 * ((MAX_SOURCE_BYTES + 2) // 3)

CAPACITY_POLICY: Final[dict[str, int | str]] = {
    "schema": "caseproof-capacity-envelope-v1",
    "approval": "development_only_not_pilot_approved",
    "source_count": SOURCE_COUNT,
    "max_source_bytes": MAX_SOURCE_BYTES,
    "max_intake_bytes": MAX_INTAKE_BYTES,
    "max_inventory_bytes": MAX_INVENTORY_BYTES,
    "max_inventory_identities": MAX_INVENTORY_IDENTITIES,
    "max_pdf_pages_per_source": MAX_PDF_PAGES,
    "max_ocr_original_bytes": 3_145_728,
    "max_export_json_bytes": 2_000_000,
    "max_export_markdown_bytes": 2_000_000,
    "max_export_docx_bytes": 5_242_880,
}


def refusal_reason(
    *, source_count: int, byte_lengths: list[int], inventory_bytes: int,
    pdf_page_counts: list[int],
) -> str | None:
    """Typed refusal independent of file content; never grants authorization."""
    if source_count != SOURCE_COUNT or len(byte_lengths) != source_count:
        return "CAPACITY_SOURCE_COUNT"
    if any(type(n) is not int or n < 1 or n > MAX_SOURCE_BYTES for n in byte_lengths):
        return "CAPACITY_SOURCE_BYTES"
    if sum(byte_lengths) > MAX_INTAKE_BYTES:
        return "CAPACITY_INTAKE_BYTES"
    if type(inventory_bytes) is not int or not 0 < inventory_bytes <= MAX_INVENTORY_BYTES:
        return "CAPACITY_INVENTORY_BYTES"
    if any(type(p) is not int or not 1 <= p <= MAX_PDF_PAGES for p in pdf_page_counts):
        return "CAPACITY_PDF_PAGES"
    return None
