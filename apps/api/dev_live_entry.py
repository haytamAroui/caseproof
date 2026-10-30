"""Explicit opt-in ONLY for the development signed-live smoke workflow."""
import os

from apps.api.litigation_development_app import create_litigation_development_app
from infrastructure.parsers.pdf_ocr import LocalPDFOCR

app = create_litigation_development_app(
    publishable_key=os.environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY"),
    trusted_ingest_key=os.environ.get("CASEPROOF_DEV_AUTH_ADMIN_KEY"),
    ocr=LocalPDFOCR() if os.environ.get("CASEPROOF_PHASE3_LIVE") == "YES" else None,
)
