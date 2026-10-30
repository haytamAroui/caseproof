"""Fixed synthetic ground truth, independent of the matching implementation."""
from __future__ import annotations

import io
from zipfile import ZIP_DEFLATED, ZipFile

from tests.fixtures.factory import SyntheticSource, generate_bundle


def dossier_bundle() -> tuple[SyntheticSource, ...]:
    from docx import Document

    bundle = list(generate_bundle())
    draft = Document()
    for text in ('Zie Stuk 1, PDF p. 1.', 'Voir Pièce 2, printed p. 7.',
                 'Zie Stuk 1, bundle p. 12.', 'Zie Stuk 3, PDF p. 1.',
                 'Zie Stuk 9, PDF p. 1.', 'Zie Stuk 4, PDF p. 1.',
                 'Zie Stuk 1, PDF p. 99.', 'Zie Stuk 1, p. 1.'):
        draft.add_paragraph(text)
    raw = io.BytesIO()
    draft.save(raw)
    # A known unsupported part is deliberately included in the denominator.
    out = io.BytesIO()
    with ZipFile(io.BytesIO(raw.getvalue())) as original, ZipFile(out, 'w', ZIP_DEFLATED) as target:
        for item in original.infolist():
            target.writestr(item, original.read(item))
        target.writestr('word/comments.xml', '<comments>UNPROCESSED SYNTHETIC REGION</comments>')
    bundle[0] = SyntheticSource('draft.docx', 'draft', bundle[0].media_type, out.getvalue())
    bundle[1] = SyntheticSource('inventory.txt', 'inventory', 'text/plain',
                               b'Stuk 1 invoice; bundle p. 12 is PDF p. 1\nPiece 2 scanned receipt; printed p. 7 is PDF p. 1\nStuk 3 missing source\nStuk 4 ambiguous identity\n')
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas
    image = Image.new('RGB', (1500, 650), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 54)
    for y, line in enumerate(('PIECE 2 SCANNED RECEIPT', 'PAYMENT RECEIVED EUR 1250', 'PRINTED PAGE 7')):
        draw.text((80, 90 + y * 100), line, fill='black', font=font)
    scanned = io.BytesIO()
    pdf = canvas.Canvas(scanned, pagesize=(750, 325), invariant=1)
    pdf.drawInlineImage(image, 0, 0, width=750, height=325)
    pdf.showPage()
    pdf.save()
    bundle[3] = SyntheticSource(bundle[3].filename, 'exhibit', 'application/pdf', scanned.getvalue())
    text_pdf = io.BytesIO()
    text = canvas.Canvas(text_pdf, pagesize=(595, 842), invariant=1)
    text.drawString(60, 760, 'STUK 1 INVOICE - SYNTHETIC EVIDENCE')
    text.drawString(60, 720, 'EUR 1250 - PHYSICAL PDF PAGE 1')
    text.showPage()
    text.save()
    bundle[2] = SyntheticSource(bundle[2].filename, 'exhibit', 'application/pdf', text_pdf.getvalue())
    return tuple(bundle)


EXPECTED_IDENTITIES = ['resolved', 'resolved', 'resolved', 'source_missing',
                       'not_in_inventory', 'ambiguous', 'resolved', 'resolved']
EXPECTED_COUNTS = {'detected': 8, 'checked': 3, 'unresolved': 5}


def confirmation(signature: str, request_id: str, text_version: str, scan_version: str) -> dict:
    return {'bundle_signature': signature, 'request_id': request_id, 'inventory_complete': True,
            'entries': [
                {'label': 'stuk', 'number': '1', 'source_version_id': text_version,
                 'pages': [{'space': 'bundle', 'label': '12', 'pdf_page': 1,
                            'rationale': 'Synthetic bundle sheet 12 is this preserved first PDF page'}]},
                {'label': 'piece', 'number': '2', 'source_version_id': scan_version,
                 'pages': [{'space': 'printed', 'label': '7', 'pdf_page': 1,
                            'rationale': 'Synthetic reviewer confirms printed label 7 on preserved scan page'}]},
                {'label': 'stuk', 'number': '3', 'source_version_id': None, 'pages': []},
                {'label': 'stuk', 'number': '4', 'source_version_id': text_version, 'pages': []},
                {'label': 'stuk', 'number': '4', 'source_version_id': scan_version, 'pages': []},
            ]}
