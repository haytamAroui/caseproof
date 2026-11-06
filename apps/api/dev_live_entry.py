"""Explicit opt-in ONLY for the development signed-live smoke workflow."""
import os
from pathlib import Path

from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.signed_supabase_originals import SignedOriginalsStorage
from apps.api.signed_supabase_source_library import SignedSourceLibrary
from apps.api.supabase_headless_matter_store import SupabaseHeadlessMatterStore
from infrastructure.parsers.pdf_ocr import LocalPDFOCR

key = os.environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY")

app = create_litigation_development_app(
    publishable_key=key,
    signed_originals=SignedSourceLibrary(
        SignedOriginalsStorage(key), rights_shadow_enabled=True,
    ) if key and os.environ.get("CASEPROOF_RIGHTS_SHADOW_DEV") == "YES" else None,
    workspace_directory=(Path(__file__).resolve().parents[2] / "frontend/dist") if os.environ.get("CASEPROOF_WORKSPACE_ENABLED") == "YES" else None,
    page_worker_secret=os.environ.get("CASEPROOF_PAGE_WORKER_SECRET"),
    headless=SupabaseHeadlessMatterStore(key) if key else None,
    trusted_ingest_key=os.environ.get("CASEPROOF_DEV_AUTH_ADMIN_KEY"),
    ocr=LocalPDFOCR() if os.environ.get("CASEPROOF_PHASE3_LIVE") == "YES" else None,
)
