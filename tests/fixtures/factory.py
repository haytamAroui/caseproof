"""Reusable synthetic CaseProof evidence fixture factory.

Pure document generation is safe offline. Remote provisioning uses the signed
matter/bundle/upload API; no service-role Storage bypass or direct SQL inserts.
"""
from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class SyntheticSource:
    filename: str
    role: str
    media_type: str
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    def metadata(self) -> dict[str, str | int]:
        return {
            "filename": self.filename,
            "role": self.role,
            "media_type": self.media_type,
            "byte_length": len(self.content),
            "sha256": self.sha256,
        }


def generate_bundle() -> tuple[SyntheticSource, ...]:
    """Four deterministic NL/FR originals; scan PDF contains no text layer."""
    from docx import Document
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas

    from scripts.verify_dev_live_multisource import _text_pdf

    draft = Document()
    draft.add_paragraph("Synthetic CaseProof draft. See Stuk 1 and Pièce 2.")
    docx = io.BytesIO()
    draft.save(docx)

    image = Image.new("RGB", (1500, 650), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 54)
    draw.text((80, 90), "PIECE 2 SCANNED RECEIPT", fill="black", font=font)
    draw.text((80, 190), "PAYMENT RECEIVED EUR 1250", fill="black", font=font)
    draw.text((80, 290), "14 OCTOBER 2026", fill="black", font=font)
    scan = io.BytesIO()
    pdf = canvas.Canvas(scan, pagesize=(750, 325), invariant=1)
    pdf.drawInlineImage(image, 0, 0, width=750, height=325)
    pdf.showPage()
    pdf.save()

    return (
        SyntheticSource("draft.docx", "draft",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        docx.getvalue()),
        SyntheticSource("inventory.txt", "inventory", "text/plain",
                        b"Inventory: Stuk 1 invoice; Piece 2 scanned receipt.\n"),
        SyntheticSource("stuk-1-invoice.pdf", "exhibit", "application/pdf",
                        _text_pdf("Stuk 1 invoice EUR 1250")),
        SyntheticSource("piece-2-scanned-receipt.pdf", "exhibit",
                        "application/pdf", scan.getvalue()),
    )


@dataclass(frozen=True, slots=True)
class ProvisionedBundle:
    matter_id: str
    sources: tuple[tuple[str, str, str], ...]


class FixtureFactory:
    """Signed, injectable transport. Does not create users or delete records."""

    def __init__(
        self,
        *,
        api: Callable[..., dict],
        rpc: Callable[..., tuple[int, bytes]],
        publishable_key: str,
    ) -> None:
        self.api = api
        self.rpc = rpc
        self.publishable_key = publishable_key

    def create_bundle(
        self, owner_token: str, org_id: str, *, name: str = "Synthetic CaseProof fixture"
    ) -> ProvisionedBundle:
        sources = generate_bundle()
        matter = self.api(
            owner_token, "POST", "/dev/live/matters",
            {"org_id": org_id, "name": name, "request_id": str(uuid4())},
        )["case_id"]
        status, body = self.rpc(
            owner_token, self.publishable_key,
            "/rest/v1/rpc/caseproof_dev_register_bundle", "POST",
            {"p_case": matter, "p_request": str(uuid4()),
             "p_sources": [source.metadata() for source in sources]},
        )
        if status != 200:
            raise RuntimeError("fixture_bundle_registration_failed")
        import json

        registered = json.loads(body)["sources"]
        if len(registered) != len(sources):
            raise RuntimeError("fixture_bundle_incomplete")
        result = []
        for source, row in zip(sources, registered, strict=True):
            doc, version = row["document_id"], row["version_id"]
            uploaded = self.api(
                owner_token, "POST",
                f"/dev/live/matters/{matter}/sources/{doc}/{version}/upload",
                {"content_base64": base64.b64encode(source.content).decode()},
            )
            if uploaded.get("verified") is not True:
                raise RuntimeError("fixture_original_hash_unverified")
            result.append((source.filename, doc, version))
        return ProvisionedBundle(matter, tuple(result))
