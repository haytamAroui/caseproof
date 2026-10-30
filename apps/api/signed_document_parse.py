"""Bounded, typed PDF/DOCX extraction after signed immutable Storage readback.

This module does not authenticate or promote evidence. The caller must verify
the signed user with GoTrue, match the original's SHA-256 against the signed
source record and invoke a service-only transaction. No OCR success is invented.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from application.documents.contracts import MAX_BLOCKS, MAX_TEXT_CHARS, PARSER_SCHEMA
from application.extraction.contracts import ExtractionError
from infrastructure.parsers.engines import DOCX_MIME
from infrastructure.parsers.limited import LimitedDocumentParser
from infrastructure.parsers.ocr_geometry_sidecar import GeometryReference, encode_page_geometry
from infrastructure.parsers.pdf_ocr import LocalPDFOCR, OCRUnavailable
from packages.evidence_kernel.domain.source_versions import SourceVersion

BINARY_MEDIA = frozenset({"application/pdf", DOCX_MIME})
MAX_BINARY_BYTES = 5 * 1024 * 1024
MAX_MANIFEST_BYTES = 300000


def parse_verified_original(
    *, document_id: str, version_id: str, data: bytes, media_type: str,
    parser: LimitedDocumentParser | None = None,
    ocr: LocalPDFOCR | None = None,
    ocr_languages: tuple[str, ...] = ("nl", "fr"),
    persist_geometry: Callable[[GeometryReference, bytes], None] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Validate a worker-produced representation and preserve absent page coverage."""
    if media_type not in BINARY_MEDIA or not 0 < len(data) <= MAX_BINARY_BYTES:
        raise ExtractionError("unsupported_bounded_binary_original")
    digest = sha256(data).hexdigest()
    source = SourceVersion(
        document_id=document_id, version_id=version_id, sha256_hex=digest,
        content=data, ingested_at=datetime.now(UTC), media_type=media_type,
    )
    artifact = (parser or LimitedDocumentParser()).parse(source)
    text = artifact.get("text")
    blocks = artifact.get("blocks")
    warnings = artifact.get("warnings")
    parser_id = artifact.get("parser_id")
    if (
        artifact.get("schema") != PARSER_SCHEMA or not isinstance(text, str)
        or len(text) > MAX_TEXT_CHARS or len(text.encode("utf-8")) > 480000
        or not isinstance(blocks, list) or len(blocks) > MAX_BLOCKS
        or not isinstance(warnings, list)
        or any(not isinstance(w, str) or len(w) > 200 for w in warnings)
        or not isinstance(parser_id, str) or not 0 < len(parser_id) <= 256
        or artifact.get("complete") not in (True, False)
    ):
        raise ExtractionError("untrusted_parser_artifact")
    expected_start = 0
    page_blocks: dict[int, int] = {}
    public_blocks: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise ExtractionError("invalid_parser_block")
        start, end = block.get("start"), block.get("end")
        locator, kind, page = block.get("locator"), block.get("kind"), block.get("page_index")
        if (
            type(start) is not int or type(end) is not int or start != expected_start
            or end <= start or end > len(text) or
            not isinstance(locator, str) or not 0 < len(locator) <= 4096 or
            kind not in {"pdf_page", "docx_paragraph", "docx_note"} or
            (media_type == "application/pdf" and (kind != "pdf_page"
                or type(page) is not int or not 0 <= page < 64)) or
            (media_type == DOCX_MIME and (page is not None or kind == "pdf_page"))
        ):
            raise ExtractionError("unmapped_parser_block")
        public_blocks.append({
            "block_id": f"block:{index}", "start": start, "end": end,
            "locator": locator, "kind": kind, "page_index": page,
        })
        if page is not None:
            page_blocks[page] = page_blocks.get(page, 0) + 1
        expected_start = end + 2
        if index < len(blocks) - 1 and text[end : end + 2] != "\n\n":
            raise ExtractionError("unmapped_parser_separator")
    if blocks and expected_start - 2 != len(text):
        raise ExtractionError("unmapped_parser_suffix")
    if not blocks and text:
        raise ExtractionError("unmapped_parser_text")
    # Empty scanned PDFs are valid PARTIAL sources, never clean evidence.
    if not text:
        warnings.append("no_extractable_text")
    if artifact["complete"] and (warnings or not blocks):
        raise ExtractionError("complete_extraction_has_missing_coverage")
    pages: list[dict[str, object]] = []
    if media_type == "application/pdf":
        indexes = set(page_blocks)
        for warning in warnings:
            for prefix in (
                "pdf_page_needs_ocr_or_review:page:",
                "pdf_visual_objects_require_review:page:",
                "pdf_annotations_unprocessed:page:",
            ):
                if warning.startswith(prefix):
                    suffix = warning[len(prefix):]
                    if not suffix.isdigit() or int(suffix) >= 64:
                        raise ExtractionError("malformed_page_status")
                    indexes.add(int(suffix))
        if not indexes:
            raise ExtractionError("pdf_page_inventory_unavailable")
        if sorted(indexes) != list(range(max(indexes) + 1)):
            raise ExtractionError("pdf_page_inventory_gap")
        for page in sorted(indexes):
            scanned = f"pdf_page_needs_ocr_or_review:page:{page}" in warnings
            visual = (f"pdf_visual_objects_require_review:page:{page}" in warnings or
                      f"pdf_annotations_unprocessed:page:{page}" in warnings)
            pages.append({"pdf_page": page + 1,
                          "status": "needs_ocr" if scanned else
                                    "needs_visual_review" if visual else "text_extracted",
                          "text_blocks": page_blocks.get(page, 0)})
    complete = bool(artifact["complete"]) and not warnings and bool(text)
    manifest: dict[str, Any] = {
        "schema": "dev-document-parse-v1", "media_type": media_type,
        "original_sha256": digest, "representation_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "parser_id": parser_id, "complete": complete,
        "coverage": "complete" if complete else "partial",
        "page_mapping": "pdf_physical_page" if media_type == "application/pdf" else "unverified",
        "pages": pages, "blocks": public_blocks, "warnings": sorted(set(warnings)),
    }
    # OCR is a review-only candidate and never changes extraction completeness.
    # The caller must explicitly opt in to a locally isolated OCR worker.
    if ocr is not None and media_type == "application/pdf":
        candidates: list[dict[str, Any]] = []
        for page in pages:
            if page["status"] != "needs_ocr":
                continue
            number = page["pdf_page"]
            if type(number) is not int:
                raise ExtractionError("invalid_pdf_page")
            try:
                result = ocr.recognize(source, page_number=number, languages=ocr_languages)
                if persist_geometry is None:
                    raise ExtractionError("ocr_geometry_persistence_required")
                reference, encoded = encode_page_geometry(result)
                persist_geometry(reference, encoded)
                candidates.append({
                    "pdf_page": number, "status": "OCR_UNRELIABLE",
                    "original_sha256": result.original_sha256,
                    "image_sha256": result.image_sha256,
                    "image_width_px": result.image_width_px,
                    "image_height_px": result.image_height_px,
                    "image_dpi": result.image_dpi,
                    "coordinate_basis": result.coordinate_basis,
                    "engine": result.engine,
                    "geometry_sha256": reference.geometry_sha256,
                    "word_count": reference.word_count,
                })
            except OCRUnavailable as exc:
                # Expose only the stable reason code, never OCR text or paths.
                reason = str(exc).split(":", 1)[0][:80]
                candidates.append({"pdf_page": number, "status": "ocr_unavailable", "reason": reason})
                if __import__("os").environ.get("CASEPROOF_OCR_DIAGNOSTICS") == "YES":
                    with open("/tmp/caseproof-ocr-diagnostic.txt", "a", encoding="utf-8") as diagnostic:
                        diagnostic.write(f"page={number} reason={reason}\n")
        manifest["ocr_candidates"] = candidates
    import json
    if len(json.dumps(manifest, ensure_ascii=False).encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise ExtractionError("parser_manifest_limit")
    return text, manifest
