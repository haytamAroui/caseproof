"""Development OCR injection is explicit and remains opt-in."""

from fastapi import APIRouter

from apps.api import litigation_development_app, litigation_live_journey
from infrastructure.parsers.pdf_ocr import LocalPDFOCR


def test_development_app_passes_ocr_to_live_router(monkeypatch):
    seen = []
    monkeypatch.setattr(
        litigation_development_app, "create_live_journey_router",
        lambda key, secret, *, ocr: seen.append((key, secret, ocr)) or APIRouter(),
    )
    adapter = LocalPDFOCR()
    litigation_development_app.create_litigation_development_app(ocr=adapter)
    litigation_development_app.create_litigation_development_app()
    assert seen == [(None, None, adapter), (None, None, None)]


def test_live_router_passes_ocr_to_journey_client(monkeypatch):
    seen = []
    monkeypatch.setattr(
        litigation_live_journey, "JourneyClient",
        lambda key, secret, *, ocr: seen.append((key, secret, ocr)),
    )
    adapter = LocalPDFOCR()
    litigation_live_journey.create_live_journey_router("test-key", "test-secret", ocr=adapter)
    assert seen == [("test-key", "test-secret", adapter)]
