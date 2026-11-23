"""Deterministic PDF hidden-text scan over raw content streams.

Scope is deliberately narrow and declared: text-showing operators (Tj, TJ, ')
drawn with the invisible rendering mode (Tr 3) or with a white fill colour
(DeviceRGB 1 1 1 or DeviceGray 1.0) on the default page background. Raster
images, annotations, optional-content layers, metadata, embedded files and
JavaScript are NOT covered; a clean result is never a certification that a
document carries no injected content.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

_MAX_FINDINGS = 8
_SHOW_OPS = {b"Tj", b"TJ", b"'", b'"'}
_WHITE = 0.999


@dataclass(frozen=True)
class HiddenTextFinding:
    page_index: int
    runs: int


def _text_of(operator: bytes, operands: list[Any]) -> str:
    if operator == b"TJ" and operands:
        array = operands[0]
        return "".join(str(part) for part in array if isinstance(part, str))
    if operands and isinstance(operands[-1], str):
        return str(operands[-1])
    return ""


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def scan_pdf_hidden_text(data: bytes, *, max_pages: int) -> tuple[HiddenTextFinding, ...]:
    """Bounded scan of page content streams for invisible or white text runs.

    Raises on unreadable structure: the caller treats a failed scan as
    fail-closed, never as a clean result.
    """
    from pypdf import PdfReader
    from pypdf.generic import ContentStream

    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    findings: list[HiddenTextFinding] = []
    for page_index, page in enumerate(reader.pages[:max_pages]):
        contents = page.get_contents()
        if contents is None:
            continue
        stream = ContentStream(contents, reader)
        rendering_mode = 0
        fill_white = False
        runs = 0
        for operands, raw_operator in stream.operations:
            operator = raw_operator if isinstance(raw_operator, bytes) else bytes(raw_operator)
            if operator == b"Tr" and operands:
                mode = _number(operands[0])
                rendering_mode = int(mode) if mode is not None else 0
            elif operator == b"rg" and len(operands) == 3:
                channels = [_number(channel) for channel in operands]
                fill_white = None not in channels and all(
                    float(channel) >= _WHITE for channel in channels if channel is not None
                )
            elif operator == b"g" and len(operands) == 1:
                gray = _number(operands[0])
                fill_white = gray is not None and gray >= _WHITE
            elif operator == b"G" or operator == b"RG":
                continue
            elif operator in _SHOW_OPS:
                if _text_of(operator, operands).strip() and (
                    rendering_mode == 3 or fill_white
                ):
                    runs += 1
        if runs:
            findings.append(HiddenTextFinding(page_index=page_index, runs=min(runs, _MAX_FINDINGS)))
        if len(findings) > max_pages:
            break
    return tuple(findings)
