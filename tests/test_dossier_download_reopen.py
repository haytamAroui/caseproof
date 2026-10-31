"""Downloaded file signatures must not substitute for independent decoding."""
import io
from zipfile import BadZipFile

import pytest
from docx import Document
from PIL import Image, UnidentifiedImageError
from pypdf import PdfWriter
from pypdf.errors import PdfReadError

from scripts.dossier_live_acceptance import validate_reopened_artifacts


def artifacts():
    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(pdf)
    png = io.BytesIO()
    Image.new('RGB', (10, 10), 'white').save(png, format='PNG')
    docx = io.BytesIO()
    document = Document()
    document.add_paragraph('CaseProof scoped review annotations')
    document.save(docx)
    return pdf.getvalue(), png.getvalue(), docx.getvalue()


def test_actual_downloads_reopen():
    validate_reopened_artifacts(*artifacts())


@pytest.mark.parametrize('index,payload', [(0, b'%PDF-broken'), (1, b'\x89PNG\r\n\x1a\nbroken'),
                                          (2, b'PK\x03\x04broken')])
def test_signature_only_downloads_are_rejected(index, payload):
    values = list(artifacts())
    values[index] = payload
    with pytest.raises((PdfReadError, UnidentifiedImageError, BadZipFile)):
        validate_reopened_artifacts(*values)
