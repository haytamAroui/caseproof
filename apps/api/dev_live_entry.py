"""Explicit opt-in ONLY for the development signed-live smoke workflow."""
import os

from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.supabase_headless_matter_store import SupabaseHeadlessMatterStore
from infrastructure.parsers.pdf_ocr import LocalPDFOCR

key = os.environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY")

app = create_litigation_development_app(
    publishable_key=key,
    headless=SupabaseHeadlessMatterStore(key) if key else None,
    trusted_ingest_key=os.environ.get("CASEPROOF_DEV_AUTH_ADMIN_KEY"),
    ocr=LocalPDFOCR() if os.environ.get("CASEPROOF_PHASE3_LIVE") == "YES" else None,
)
