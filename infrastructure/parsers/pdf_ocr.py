"""M1 optional on-prem PDF raster/OCR adapter with exact image/word lineage.

Does NOT replace the immutable original, prove accuracy or satisfy production
sandbox/AV review. Requires approved local Poppler and Tesseract binaries.
Never sends material to a cloud OCR provider or model.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import resource
import sys
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pypdf import PdfReader

from packages.evidence_kernel.domain.source_versions import SourceVersion


class OCRUnavailable(ValueError):
    """Explicit unprocessed page; callers must preserve original bytes."""


LANGUAGES = {"nl": "nld", "fr": "fra", "en": "eng"}
OCR_LIMIT = 3 * 1024 * 1024
MAX_WORDS = 20_000
MAX_OUTPUT = 1024 * 1024
RASTER_DPI = 150


@dataclass(frozen=True, slots=True)
class OCRWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: str


@dataclass(frozen=True, slots=True)
class OCRPage:
    source_document_id: str
    source_version_id: str
    original_sha256: str
    page_number: int
    image_sha256: str
    image_width_px: int
    image_height_px: int
    image_dpi: int
    content: str
    words: tuple[OCRWord, ...]
    status: str = "draft_requires_human_review"
    engine: str = "poppler+tesseract-tsv-v1"
    coordinate_basis: str = "raster_pixels_top_left_150dpi"


def parse_tsv(raw: bytes, *, width: int, height: int) -> tuple[OCRWord, ...]:
    if len(raw) > MAX_OUTPUT:
        raise OCRUnavailable("ocr_output_limit")
    try:
        text = raw.decode("utf-8", errors="strict")
        reader = csv.DictReader(io.StringIO(text), dialect="excel-tab")
        required = {"level", "left", "top", "width", "height", "conf", "text"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise OCRUnavailable("ocr_tsv_columns_missing")
        result: list[OCRWord] = []
        for row in reader:
            if row.get("level") != "5":
                continue
            content = row.get("text") or ""
            if not content.strip():
                continue
            try:
                coords = [int(row[key]) for key in ("left", "top", "width", "height")]
                confidence = Decimal(row.get("conf", "-1"))
            except (ValueError, TypeError, InvalidOperation, KeyError):
                raise OCRUnavailable("ocr_tsv_invalid_geometry") from None
            x, y, w, h = coords
            if not (0 <= x < width and 0 <= y < height
                    and 0 < w <= width - x and 0 < h <= height - y):
                raise OCRUnavailable("ocr_tsv_out_of_image")
            if confidence.is_nan() or confidence < -1 or confidence > 100:
                raise OCRUnavailable("ocr_invalid_confidence")
            if len(content) > 4096:
                raise OCRUnavailable("ocr_token_limit")
            result.append(OCRWord(content, x, y, w, h, str(confidence)))
            if len(result) > MAX_WORDS:
                raise OCRUnavailable("ocr_word_limit")
        return tuple(result)
    except (UnicodeError, csv.Error):
        raise OCRUnavailable("ocr_malformed_tsv") from None


def _worker_limits() -> None:
    """Bound the child process, never the API process."""
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))


def _isolated_command(command: list[str]) -> list[str]:
    """Enforce network isolation using a dedicated container or user namespace.

    Never execute the OCR binaries directly when isolation is unavailable.
    """
    if sys.platform != "linux":
        raise OCRUnavailable("ocr_linux_sandbox_required")
    if os.getenv("CASEPROOF_OCR_SANDBOX") == "docker":
        docker = shutil.which("docker")
        if not docker:
            raise OCRUnavailable("ocr_docker_unavailable")
        workspace = Path(command[-2] if Path(command[0]).name == "pdftoppm" else command[1]).parent
        # All OCR input and output paths must be under the ephemeral workspace.
        # The caller uses only fixed executable names and trusted local paths.
        mapped = []
        for arg in command[1:]:
            if arg.startswith(str(workspace) + "/"):
                mapped.append("/work/" + Path(arg).name)
            else:
                mapped.append(arg)
        executable = Path(command[0]).name
        if executable not in ("pdftoppm", "tesseract"):
            raise OCRUnavailable("ocr_executable_not_allowed")
        return [
            docker, "run", "--rm", "--network", "none", "--memory", "768m",
            "--cpus", "1", "--pids-limit", "64", "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
            "--mount", f"type=bind,src={workspace},dst=/work",
            os.getenv("CASEPROOF_OCR_IMAGE", "caseproof-ocr-worker:ci"),
            executable, *mapped,
        ]
    unshare = shutil.which("unshare")
    if not unshare:
        raise OCRUnavailable("ocr_network_sandbox_unavailable")
    return [unshare, "--user", "--map-root-user", "--net", "--", *command]


def _run(command: list[str], *, timeout: int) -> None:
    try:
        completed = subprocess.run(
            _isolated_command(command), capture_output=True,
            timeout=timeout, check=False, preexec_fn=_worker_limits,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise OCRUnavailable("ocr_binary_unavailable_or_timeout") from None
    if completed.returncode != 0:
        # Never log source bytes, OCR text or paths. Keep only bounded engine stderr.
        diagnostic = completed.stderr.decode("utf-8", errors="replace")[-400:]
        raise OCRUnavailable(f"ocr_external_process_failed_or_sandbox_denied:{completed.returncode}:{diagnostic}")


class LocalPDFOCR:
    """Optional adapter; operator must provide sandbox/malware controls externally."""

    def __init__(self) -> None:
        self.rasterizer = shutil.which("pdftoppm")
        self.recognizer = shutil.which("tesseract")

    def recognize(
        self, source: SourceVersion, *, page_number: int, languages: tuple[str, ...],
    ) -> OCRPage:
        if source.media_type != "application/pdf" or not source.content.startswith(b"%PDF-"):
            raise OCRUnavailable("ocr_pdf_only")
        if len(source.content) > OCR_LIMIT or len(source.content) == 0:
            raise OCRUnavailable("ocr_input_budget")
        if type(page_number) is not int or not 1 <= page_number <= 64:
            raise OCRUnavailable("ocr_page_range")
        if (
            type(languages) is not tuple or not languages or len(languages) > 3
            or len(set(languages)) != len(languages)
            or any(language not in LANGUAGES for language in languages)
        ):
            raise OCRUnavailable("unsupported_ocr_languages")
        rasterizer, recognizer = self.rasterizer, self.recognizer
        if rasterizer is None or recognizer is None:
            raise OCRUnavailable("ocr_binaries_not_installed")
        try:
            reader = PdfReader(io.BytesIO(source.content), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 64:
                raise OCRUnavailable("ocr_pdf_unsupported")
            if page_number > len(reader.pages):
                raise OCRUnavailable("ocr_missing_page")
        except (ValueError, OSError):
            raise OCRUnavailable("ocr_pdf_unreadable") from None
        with tempfile.TemporaryDirectory(prefix="caseproof-m1-ocr-") as workspace:
            root = Path(workspace)
            raw_pdf = root / "original.pdf"
            raw_pdf.write_bytes(source.content)
            prefix = root / "page"
            _run(
                [
                    rasterizer, "-f", str(page_number),
                    "-l", str(page_number), "-singlefile", "-r",
                    str(RASTER_DPI), "-png", str(raw_pdf), str(prefix),
                ],
                timeout=12,
            )
            png_path = root / "page.png"
            try:
                png = png_path.read_bytes()
            except OSError:
                raise OCRUnavailable("ocr_raster_missing") from None
            if not 24 <= len(png) <= 12 * 1024 * 1024:
                raise OCRUnavailable("ocr_raster_budget")
            if png[:8] != bytes((137, 80, 78, 71, 13, 10, 26, 10)) or png[12:16] != b"IHDR":
                raise OCRUnavailable("ocr_png_invalid")
            width, height = struct.unpack(">II", png[16:24])
            if not 0 < width <= 5000 or not 0 < height <= 6500:
                raise OCRUnavailable("ocr_image_dimensions")
            # Running tesseract without shell. The user-provided file name and
            # content are never accepted as command arguments.
            output = root / "page"
            _run(
                [
                    recognizer, str(png_path), str(output),
                    "-l", "+".join(LANGUAGES[language] for language in languages), "tsv",
                ],
                timeout=20,
            )
            try:
                tsv = (root / "page.tsv").read_bytes()
            except OSError:
                raise OCRUnavailable("ocr_tsv_missing") from None
            words = parse_tsv(tsv, width=width, height=height)
            if not words:
                raise OCRUnavailable("ocr_no_recognizable_text")
            contents = " ".join(w.text for w in words)
            if len(contents) > 300_000:
                raise OCRUnavailable("ocr_text_budget")
            return OCRPage(
                source.document_id, source.version_id, source.sha256_hex,
                page_number, hashlib.sha256(png).hexdigest(), width, height,
                RASTER_DPI, contents, words,
            )
