"""QR payload and PNG rendering for a completed review record.

The QR encodes a BOUNDED offline-verification payload only: schema name,
record digest and the signing public key. It contains no private case text,
no secret and no URL: scanning it can never imply a hosted public
verification service exists, because there is none. Verification stays the
documented offline path (scripts/verify_review_record_file.py) with a
trusted key pinned by an independent channel; without such a pin the key
is a self-asserted installation/test issuer.
"""

from __future__ import annotations

import io
import re
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PUBLIC_KEY = re.compile(r"^[0-9a-f]{64}$")
MAX_PAYLOAD_CHARS = 256

__all__ = ["build_qr_payload", "render_qr_png"]


def build_qr_payload(body: dict[str, Any]) -> str:
    """Bounded verification payload from a completed (signed) record body."""
    digest = body.get("record_sha256")
    if type(digest) is not str or not _SHA256.fullmatch(digest):
        raise ValueError("completed record digest required")
    receipt = body.get("receipt")
    if receipt is not None:
        if not isinstance(receipt, dict):
            raise ValueError("invalid receipt")
        public = receipt.get("public_key")
        if type(public) is not str or not _PUBLIC_KEY.fullmatch(public):
            raise ValueError("invalid receipt public key")
    else:
        public = "unsigned"
    payload = f"caseproof-review-record-v1|sha256:{digest}|key:{public}"
    if len(payload) > MAX_PAYLOAD_CHARS:
        raise ValueError("verification payload outside allowed bounds")
    return payload


def render_qr_png(payload: str) -> bytes:
    """Deterministic compact PNG of the payload; input is already bounded."""
    if type(payload) is not str or not 0 < len(payload) <= MAX_PAYLOAD_CHARS:
        raise ValueError("verification payload outside allowed bounds")
    import segno

    out = io.BytesIO()
    segno.make(payload, error="m", micro=False).save(
        out, kind="png", scale=4, border=2, dark="black", light="white"
    )
    png = out.getvalue()
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("QR rendering failed")
    return png
