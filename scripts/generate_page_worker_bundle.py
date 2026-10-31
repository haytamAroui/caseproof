"""Deterministic synthetic bundle: 100 text-layer pages and 100 image-only pages in four PDFs.

Each PDF stays within the 64-page SQL limit. Synthetic content only; no client data.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas

PAGES_PER_PDF = 50
# Version ids sort text PDFs first so a crash lands inside the slower scanned pages.
BUNDLE = (
    ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-0000000000d1', 'text'),
    ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-0000000000d2', 'text'),
    ('00000000-0000-4000-8000-000000000003', '00000000-0000-4000-8000-0000000000d3', 'scan'),
    ('00000000-0000-4000-8000-000000000004', '00000000-0000-4000-8000-0000000000d4', 'scan'),
)


def _font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(path, 44)
        except OSError:
            continue
    return ImageFont.load_default()


def text_pdf(tag: str, pages: int = PAGES_PER_PDF) -> bytes:
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(595, 842), invariant=1)
    for number in range(1, pages + 1):
        pdf.setFont('Helvetica', 14)
        pdf.drawString(60, 780, f'Stuk {tag} - synthetic text page {number}')
        pdf.drawString(60, 750, 'Le paiement est du selon la convention.')
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def scan_pdf(tag: str, pages: int = PAGES_PER_PDF) -> bytes:
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(595, 842), invariant=1)
    font = _font()
    for number in range(1, pages + 1):
        image = Image.new('RGB', (900, 600), 'white')
        draw = ImageDraw.Draw(image)
        draw.text((40, 80), f'Stuk {tag} scan page {number}', fill='black', font=font)
        draw.text((40, 200), 'De betaling is verschuldigd.', fill='black', font=font)
        pdf.drawInlineImage(image, 20, 200, width=555, height=370)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def build_bundle() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (version_id, document_id, kind) in enumerate(BUNDLE, 1):
        data = text_pdf(f'T{index}') if kind == 'text' else scan_pdf(f'S{index}')
        rows.append({'version_id': version_id, 'document_id': document_id, 'kind': kind,
                     'pages': PAGES_PER_PDF, 'data': data})
    return rows


def write_bundle(directory: Path) -> list[dict[str, Any]]:
    directory.mkdir(parents=True, exist_ok=True)
    rows = build_bundle()
    for row in rows:
        (directory / f"{row['version_id']}.pdf").write_bytes(row['data'])
    (directory / 'bundle.json').write_text(json.dumps([
        {k: row[k] for k in ('version_id', 'document_id', 'kind', 'pages')} for row in rows], indent=2))
    return rows


if __name__ == '__main__':
    import sys

    target = Path(sys.argv[1] if len(sys.argv) > 1 else 'page-worker-bundle')
    written = write_bundle(target)
    print(f'{sum(r["pages"] for r in written)} pages written to {target}')
