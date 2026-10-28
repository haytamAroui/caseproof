"""Explicit opt-in ONLY for the development signed-live smoke workflow."""
import os

from apps.api.litigation_development_app import create_litigation_development_app

app = create_litigation_development_app(
    publishable_key=os.environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY"),
)
